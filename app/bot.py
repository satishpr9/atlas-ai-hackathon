from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import pypdf
import io
import base64
import httpx
import logging
from app.config import settings
from app.services import get_or_create_user, save_message, get_recent_chat_history, update_user_profile
from app.agents.assistant import atlas_agent
from app.scheduler import generate_curated_morning_brief
from app.market_data import MarketDataProvider

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "there"
    await get_or_create_user(user_id, first_name=user_name, username=update.effective_user.username)

    welcome_text = (
        f"👋 Welcome to Atlas AI, {user_name}!\n\n"
        "I am your institutional financial intelligence partner. You can communicate with me completely naturally using **Text, Voice Notes, or Images**—no complex commands or menus needed.\n\n"
        "Here are some examples of what you can do:\n"
        "• 💬 *Ask naturally:* 'Compare Microsoft and Alphabet on valuation and latest news'\n"
        "• 🎙️ *Send a Voice Message:* Ask questions on the go and get an instant voice-transcribed answer\n"
        "• 🖼️ *Send a Chart or Table Photo:* Get instant technical and fundamental analysis on any financial screenshot\n"
        "• 📑 *Drop an Earnings/10-K PDF:* Receive an instant executive summary of quarterly results\n\n"
        "To help me tailor your experience, feel free to share what best describes your role (e.g. Investor, Analyst, Founder) or which stocks you actively track!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def briefing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.chat.send_action("typing")
    user = await get_or_create_user(user_id)
    user_dict = {
        "telegram_id": user_id,
        "watch_list": user.watch_list or ["NVDA", "AAPL", "MSFT"],
        "role": user.role,
        "interests": user.interests,
        "preferred_insights": user.preferred_insights
    }
    briefing_text = await generate_curated_morning_brief(user_dict)
    await update.message.reply_text(briefing_text)

async def watchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_or_create_user(user_id)
    watchlist = user.watch_list or []
    
    if not watchlist:
        text = (
            "📋 Your Watchlist is currently empty.\n\n"
            "Tell me which stocks you follow (e.g. *'Add NVDA and TSLA to my watchlist'*) "
            "and I will monitor them for you during daily morning briefings!"
        )
    else:
        quotes_summary = []
        for sym in watchlist:
            q = MarketDataProvider.get_quote(sym)
            if q:
                sign = "+" if q.percent_change >= 0 else ""
                quotes_summary.append(f"• {q.symbol}: ${q.price:,.2f} ({sign}{q.percent_change:.2f}% today)")
            else:
                quotes_summary.append(f"• {sym}: Tracking")
                
        text = (
            f"📋 Your Watchlist ({len(watchlist)} stocks)\n\n"
            + "\n".join(quotes_summary) +
            "\n\n💡 Tell me 'Remove AAPL' or 'Add AMZN' anytime."
        )
        
    await update.message.reply_text(text, parse_mode="Markdown")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document.file_name.endswith('.pdf'):
        await update.message.reply_text("Please upload a PDF document for analysis.")
        return

    await update.message.chat.send_action("typing")
    user_id = update.effective_user.id
    
    file = await context.bot.get_file(document.file_id)
    file_byte_array = await file.download_as_bytearray()
    
    try:
        pdf_reader = pypdf.PdfReader(io.BytesIO(file_byte_array))
        text = ""
        for page in pdf_reader.pages[:6]:
            text += page.extract_text() or ""
            
        truncated_text = text[:4000]
        
        prompt = (
            f"A user uploaded an earnings report / financial document: '{document.file_name}'.\n"
            f"Here is the text excerpt:\n\n{truncated_text}\n\n"
            "Please provide a clean executive synthesis in our ultra-clean Telegram style:\n"
            "📑 Document Synthesis\n"
            "💰 Key Financials (Revenue, Net Income, Margins, EPS)\n"
            "🎯 Primary Highlights & Guidance\n"
            "💡 Bottom Line & Watch Items"
        )
        
        response = await atlas_agent.process_message(user_id, prompt)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        await update.message.reply_text(f"Sorry, I encountered an issue analyzing '{document.file_name}'. Please ensure it contains readable text.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles voice messages by transcribing audio and routing to conversational agent."""
    user_id = update.effective_user.id
    voice = update.message.voice or update.message.audio
    if not voice:
        return

    await update.message.chat.send_action("typing")
    file = await context.bot.get_file(voice.file_id)
    audio_bytes = await file.download_as_bytearray()

    try:
        # Transcribe using Whisper API via OpenAI client / HTTP endpoint
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        files = {"file": ("voice.ogg", io.BytesIO(audio_bytes), "audio/ogg")}
        data = {"model": "whisper-1"}
        
        base_url = settings.openai_base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{base_url}/audio/transcriptions", headers=headers, files=files, data=data)
            
        if resp.status_code == 200:
            transcription = resp.json().get("text", "").strip()
        else:
            transcription = ""

        if not transcription:
            await update.message.reply_text("I received your voice note, but could not transcribe it clearly. Please try speaking again or type your message.")
            return

        # Process the transcribed text
        response = await atlas_agent.process_message(user_id, transcription)
        await update.message.reply_text(f"🎙️ *\"{transcription}\"*\n\n{response}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error handling voice message: {e}")
        await update.message.reply_text("I encountered an issue processing the audio note. Please try sending it again or type your request.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles financial charts, table screenshots, and balance sheet images using Vision analysis."""
    user_id = update.effective_user.id
    photos = update.message.photo
    if not photos:
        return

    await update.message.chat.send_action("typing")
    photo = photos[-1] # Highest resolution
    file = await context.bot.get_file(photo.file_id)
    img_bytes = await file.download_as_bytearray()
    
    caption = update.message.caption or "Analyze this financial chart / document screenshot."
    b64_img = base64.b64encode(img_bytes).decode("utf-8")
    
    try:
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.model_name or "gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"You are Atlas, an institutional financial analyst. {caption}\n\nProvide a clean, structured analysis:\n📊 Visual / Financial Overview\n💰 Key Metrics / Levels Identified\n💡 Strategic Takeaway"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                    ]
                }
            ],
            "temperature": 0.1
        }
        
        base_url = settings.openai_base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            
        if resp.status_code == 200:
            result = resp.json()
            analysis_text = result["choices"][0]["message"]["content"]
            await update.message.reply_text(analysis_text)
        else:
            logger.error(f"Vision API error: {resp.text}")
            await update.message.reply_text("I analyzed your image, but could not extract verified financial metrics. Please ensure the chart or table is clear.")
    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        await update.message.reply_text("I encountered an issue analyzing your image. Please try uploading again.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    if not user_message:
        return

    await update.message.chat.send_action("typing")
    
    try:
        response = await atlas_agent.process_message(user_id, user_message)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await update.message.reply_text(
            "I encountered a momentary data feed hiccup. Please try your request again."
        )

def setup_bot():
    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("briefing", briefing_command))
    app.add_handler(CommandHandler("watchlist", watchlist_command))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app

get_application = setup_bot
