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

# In-memory document context store (user_id -> {text, name})
_DOCUMENT_CONTEXT: dict = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "there"
    user = await get_or_create_user(user_id, first_name=user_name, username=update.effective_user.username)

    if not user.is_authorized:
        await update.message.reply_text("🔒 Welcome to Atlas. This is a private financial intelligence bot. Please enter the access code to continue.")
        return

    welcome_text = (
        f"Welcome to Atlas AI, {user_name}!\n\n"
        "I am your financial intelligence partner. Talk to me naturally — text, voice notes, or images.\n\n"
        "Here are some things I can help with:\n"
        "• Ask about any company — public or private\n"
        "• Compare stocks or analyze price movements\n"
        "• Upload earnings reports, 10-Ks, or financial PDFs for instant analysis\n"
        "• Get a personalized morning market briefing\n"
        "• Track stocks and set up alerts\n\n"
        "To get started, tell me your role (e.g. Investor, Analyst, Founder) or which stocks you follow."
    )
    await update.message.reply_text(welcome_text)







async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Conversational document intelligence.
    Extracts text from PDFs, stores it in session for follow-up Q&A,
    and generates an instant executive summary.
    """
    user_id = update.effective_user.id
    user = await get_or_create_user(user_id)
    if not user.is_authorized:
        await update.message.reply_text("🔒 Welcome to Atlas. This is a private financial intelligence bot. Please enter the access code to continue.")
        return

    document = update.message.document
    if not document.file_name.endswith('.pdf'):
        await update.message.reply_text("I can analyze PDF documents. Please upload a PDF file.")
        return

    await update.message.chat.send_action("typing")
    user_id = update.effective_user.id
    caption = update.message.caption or ""
    
    file = await context.bot.get_file(document.file_id)
    file_byte_array = await file.download_as_bytearray()
    
    try:
        pdf_reader = pypdf.PdfReader(io.BytesIO(file_byte_array))
        total_pages = len(pdf_reader.pages)
        text = ""
        for page in pdf_reader.pages:  # Process all pages to ensure no data is lost
            text += (page.extract_text() or "") + "\n"
            
        # Store for follow-up questions
        doc_text = text[:150000]  # Allow up to ~35k tokens (well within 128k limit)
        _DOCUMENT_CONTEXT[user_id] = {
            "text": doc_text,
            "name": document.file_name,
            "pages": total_pages,
        }
        
        # Also persist in user profile for cross-session continuity
        await update_user_profile(user_id, {
            "last_document_text": doc_text[:50000], # Store a good chunk in DB
            "last_document_name": document.file_name
        })
        
        # Build the analysis prompt
        if caption:
            user_instruction = caption
        else:
            user_instruction = "Provide an executive summary of this document."
        
        prompt = (
            f"[DOCUMENT UPLOADED: '{document.file_name}' ({total_pages} pages)]\n\n"
            f"--- DOCUMENT TEXT ---\n"
            f"{doc_text}\n"
            f"--- END DOCUMENT TEXT ---\n\n"
            f"USER REQUEST: {user_instruction}\n\n"
            "EVIDENCE DISCIPLINE RULES:\n"
            "1. Extract exact verified figures from the text. Calculate growth and margins accurately.\n"
            "2. Distinguish FACT from INFERENCE. NEVER claim revenue growth proves 'strong demand' or margin expansion proves 'operational efficiency' unless explicitly established in the text.\n"
            "3. Under '⚠️ Interpretation', state what the numbers show AND explicitly mention what the document does NOT establish (drivers, missing context).\n"
            "4. If the provided data does not contain the answer, explicitly state 'I do not have verified data to determine this'. DO NOT guess or infer numbers.\n\n"
            "Follow this EXACT clean layout:\n\n"
            f"📄 {document.file_name}\n\n"
            "💰 Financial Highlights\n"
            "[Key metrics, periods, growth rates, and calculated margins]\n\n"
            "💡 Key Takeaway\n"
            "[Mathematical & factual observations only — 1-2 concise sentences]\n\n"
            "⚠️ Interpretation\n"
            "[State what the report shows, but explicitly note unverified drivers or limitations]\n\n"
            f"Source: Uploaded {document.file_name}"
        )
        
        response = await atlas_agent.process_message(user_id, prompt)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        await update.message.reply_text(f"I encountered an issue analyzing '{document.file_name}'. Please ensure it contains readable text.")


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
            await update.message.reply_text("I couldn't quite catch that. Could you try speaking a bit closer to the microphone, or type your request?")
            return

        response = await atlas_agent.process_message(user_id, transcription)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error handling voice message: {e}")
        await update.message.reply_text("I had trouble processing that voice note. Please try again or type your request.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles financial charts, table screenshots, and document images using Vision analysis."""
    user_id = update.effective_user.id
    photos = update.message.photo
    if not photos:
        return

    await update.message.chat.send_action("typing")
    photo = photos[-1]  # Highest resolution
    file = await context.bot.get_file(photo.file_id)
    img_bytes = await file.download_as_bytearray()
    
    caption = update.message.caption or "Analyze this financial chart or document."
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
                        {"type": "text", "text": (
                            f"You are Atlas, an institutional financial analyst with strict evidence discipline. {caption}\n\n"
                            "EVIDENCE RULES:\n"
                            "1. Perform exact mathematical calculations where relevant (e.g. Growth %, Margins = Net Profit / Revenue * 100).\n"
                            "2. Distinguish FACT from INFERENCE. NEVER claim revenue growth proves 'strong demand' or margin expansion proves 'operational efficiency' unless explicitly established in the image.\n"
                            "3. Under '⚠️ Interpretation', state what the numbers show AND explicitly mention what the image does NOT establish (drivers, missing context).\n"
                            "4. If the provided data does not contain the answer, explicitly state 'I do not have verified data to determine this'. DO NOT guess or infer numbers.\n\n"
                            "Follow this EXACT clean layout:\n\n"
                            "📄 [Company / Subject Title from Image]\n\n"
                            "💰 Financial Highlights\n"
                            "[Exact metrics, periods, growth rates, and calculated margins]\n\n"
                            "💡 Key Takeaway\n"
                            "[Mathematical & factual observations only — 1-2 concise sentences]\n\n"
                            "⚠️ Interpretation\n"
                            "[State what the report shows, but explicitly note unverified drivers or limitations]\n\n"
                            "Source: Uploaded financial image"
                        )},
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
            if len(analysis_text) < 20 or "cannot read" in analysis_text.lower() or "not clear" in analysis_text.lower():
                await update.message.reply_text("I couldn't extract clear financial data from this image. Could you try sending a higher-resolution screenshot or closer crop?")
                return
            await update.message.reply_text(analysis_text)
        else:
            logger.error(f"Vision API error: {resp.text}")
            await update.message.reply_text("I couldn't extract clear financial data from this image. Could you try sending a higher-resolution screenshot or closer crop?")
    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        await update.message.reply_text("I had trouble analyzing that image. Could you try sending a higher-resolution screenshot or closer crop?")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    if not user_message:
        return

    await update.message.chat.send_action("typing")
    
    user = await get_or_create_user(user_id)
    lower_msg = user_message.lower()

    # Password Gateway
    if not user.is_authorized:
        if user_message.strip() == settings.bot_password:
            await update_user_profile(user_id, {"is_authorized": True})
            user.is_authorized = True
            await update.message.reply_text("✅ Access granted. Welcome to Atlas. How can I help you today?")
        else:
            await update.message.reply_text("🔒 Welcome to Atlas. This is a private financial intelligence bot. Please enter the access code to continue.")
        return

    # Conversational Onboarding Flow
    if user.onboarding_stage != "completed":
        is_question = "?" in user_message or len(user_message.split()) > 6 or any(w in lower_msg for w in ["what", "how", "why", "who", "when", "tell me", "compare"])
        if is_question:
            await update_user_profile(user_id, {"onboarding_stage": "completed"})
            user.onboarding_stage = "completed"
        else:
            if lower_msg == "skip":
                await update_user_profile(user_id, {"onboarding_stage": "completed"})
                await update.message.reply_text("Setup skipped! You can ask me about stocks or markets anytime.")
                return

            if user.onboarding_stage == "initial":
                await update_user_profile(user_id, {"role": user_message, "onboarding_stage": "asked_role"})
                await update.message.reply_text(f"Got it. You're focusing on {user_message}. Which specific stocks or sectors would you like me to track for your watchlist? (e.g. 'NVDA, TSLA, AI chips')")
                return
                
            if user.onboarding_stage == "asked_role":
                await update_user_profile(user_id, {"interests": [user_message], "onboarding_stage": "asked_watchlist"})
                await update.message.reply_text("Watchlist noted. I'll prepare a morning briefing for you daily. What time would you like to receive it? (e.g. '8:30 AM EST')")
                return
                
            if user.onboarding_stage == "asked_watchlist":
                await update_user_profile(user_id, {"briefing_time": user_message, "onboarding_stage": "completed"})
                await update.message.reply_text(f"Briefing time set to {user_message}. Setup complete! How can I help you right now?")
                return
        
    # Check if user has a document in context and the message seems like a follow-up
    doc_ctx = _DOCUMENT_CONTEXT.get(user_id)
    
    is_external_query = any(phrase in lower_msg for phrase in [
        "email", "calendar", "meeting", "morning brief", "evening wrap", "watchlist", "schedule"
    ]) or (
        any(phrase in lower_msg for phrase in ["stock price", "price of", "how much is", "why is", "tell me about", "compare", "versus", " vs "]) and not any(w in lower_msg for w in ["this", "document", "report", "pdf", "table", "above", "file"])
    )
    
    if doc_ctx and not is_external_query:
        enriched_message = (
            f"[The user previously uploaded '{doc_ctx['name']}' ({doc_ctx['pages']} pages). "
            f"Here is the document text for reference:\n"
            f"--- DOCUMENT TEXT ---\n{doc_ctx['text']}\n--- END ---]\n\n"
            f"USER QUESTION: {user_message}\n\n"
            f"Instruction: Answer the user's question directly, accurately, and concisely based strictly on the document text. Quote exactly from the text when citing numbers or facts. If the provided data does not contain the answer, explicitly state 'I do not have verified data to determine this'. DO NOT guess or infer numbers. Keep your response brief, clear, and high-signal (1-3 sentences or short bullet points)."
        )
    else:
        enriched_message = user_message
    
    try:
        response = await atlas_agent.process_message(user_id, enriched_message)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await update.message.reply_text(
            "I encountered a momentary issue. Please try your request again."
        )

def setup_bot():
    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app

get_application = setup_bot
