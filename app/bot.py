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
    user = await get_or_create_user(user_id, first_name=user_name, username=update.effective_user.username)

    welcome_text = (
        f"👋 Welcome to Atlas AI, {user_name}!\n\n"
        "I am your institutional financial intelligence partner, built to deliver real-time market data, company comparisons, breaking catalyst analysis, and daily morning intelligence.\n\n"
        "To tailor your research experience, tell me a little about yourself:\n"
        "• What best describes your role? *(e.g. Investor, Analyst, Founder, Finance Professional)*\n"
        "• Which companies, sectors, or topics do you actively follow?\n\n"
        "*(You can also skip right ahead and ask any market question, request a morning briefing, or upload an earnings/10-K PDF for instant breakdown!)*"
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
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app

get_application = setup_bot
