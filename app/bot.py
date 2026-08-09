from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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
from langchain_core.messages import HumanMessage, AIMessage

logger = logging.getLogger(__name__)

def get_quote_keyboard(ticker: str) -> InlineKeyboardMarkup:
    """Returns quick action buttons for a single stock."""
    keyboard = [
        [
            InlineKeyboardButton(f"📈 Why is {ticker} moving?", callback_data=f"move_{ticker}"),
            InlineKeyboardButton(f"⭐ Add {ticker} to Watchlist", callback_data=f"watch_{ticker}")
        ],
        [
            InlineKeyboardButton("☀️ Morning Briefing", callback_data="btn_briefing"),
            InlineKeyboardButton("📋 My Watchlist", callback_data="btn_watchlist")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_general_keyboard() -> InlineKeyboardMarkup:
    """Returns general navigation buttons."""
    keyboard = [
        [
            InlineKeyboardButton("☀️ Morning Briefing", callback_data="btn_briefing"),
            InlineKeyboardButton("📋 My Watchlist", callback_data="btn_watchlist")
        ],
        [
            InlineKeyboardButton("📊 Compare MSFT vs Google", callback_data="compare_MSFT_GOOGL"),
            InlineKeyboardButton("❓ Help & Commands", callback_data="btn_help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "there"
    await get_or_create_user(user_id)

    welcome_text = (
        f"👋 **Welcome to Atlas AI, {user_name}!**\n\n"
        "I am your institutional-grade financial intelligence partner.\n\n"
        "**What I can do for you:**\n"
        "• 📊 **Company & Peer Comparisons**: Valuation deltas, trailing multiples, and business focus.\n"
        "• 📈 **Movement & Catalyst Analysis**: 'Why is Tesla moving today?'\n"
        "• 📰 **Verified News Pipeline**: Zero noise, entity-filtered breaking catalysts.\n"
        "• ☀️ **Proactive Morning Briefings**: Macro regimes and personalized watchlist alerts.\n"
        "• 📑 **10-K & PDF Document Reader**: Drop any earnings report or research PDF here!\n\n"
        "Tap a quick action below or ask me anything directly:"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_general_keyboard())

async def briefing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.chat.send_action("typing")
    user = await get_or_create_user(user_id)
    user_dict = {
        "telegram_id": user_id,
        "watch_list": user.watch_list or ["NVDA", "AAPL", "MSFT"],
        "role": user.role,
        "interests": user.interests
    }
    briefing_text = await generate_curated_morning_brief(user_dict)
    await update.message.reply_text(briefing_text, reply_markup=get_general_keyboard())

async def watchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_or_create_user(user_id)
    watchlist = user.watch_list or []
    
    if not watchlist:
        text = (
            "📋 **Your Watchlist is empty.**\n\n"
            "Tell me which stocks you follow (e.g. *'Add NVDA and TSLA to my watchlist'*) "
            "and I will monitor them for you during daily morning briefings!"
        )
    else:
        quotes_summary = []
        for sym in watchlist:
            q = MarketDataProvider.get_quote(sym)
            if q:
                sign = "+" if q.percent_change >= 0 else ""
                quotes_summary.append(f"• **{q.symbol}**: ${q.price:,.2f} ({sign}{q.percent_change:.2f}% today)")
            else:
                quotes_summary.append(f"• **{sym}**: Tracking")
                
        text = (
            f"📋 **Your Personalized Watchlist** ({len(watchlist)} stocks)\n\n"
            + "\n".join(quotes_summary) +
            "\n\n💡 *Tip: Tell me 'Remove AAPL' or 'Add AMZN' anytime.*"
        )
        
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_general_keyboard())

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == "btn_briefing":
        user = await get_or_create_user(user_id)
        user_dict = {
            "telegram_id": user_id,
            "watch_list": user.watch_list or ["NVDA", "AAPL", "MSFT"],
            "role": user.role,
            "interests": user.interests
        }
        text = await generate_curated_morning_brief(user_dict)
        await query.message.reply_text(text, reply_markup=get_general_keyboard())
        
    elif data == "btn_watchlist":
        user = await get_or_create_user(user_id)
        wl = user.watch_list or []
        if not wl:
            text = "📋 Your Watchlist is currently empty. Tell me: *'Add NVDA and AAPL to my watchlist'*"
        else:
            lines = [f"• {sym}" for sym in wl]
            text = f"📋 **Your Watchlist:**\n\n" + "\n".join(lines)
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=get_general_keyboard())
        
    elif data == "btn_help":
        help_text = (
            "💡 **Atlas AI Quick Commands & Examples:**\n\n"
            "• `/briefing` — Generate your custom morning intelligence brief\n"
            "• `/watchlist` — View and manage your tracked stocks\n\n"
            "**Natural queries you can ask:**\n"
            "• *'Compare Microsoft and Google on market cap and latest news'*\n"
            "• *'Why is Tesla moving today?'*\n"
            "• *'What is Apple's current valuation and P/E?'*\n"
            "• *'I am a venture investor focused on AI chips, track NVDA and TSM'* (Atlas remembers!)\n"
            "• *Upload any 10-K or earnings PDF for instant executive breakdown.*"
        )
        await query.message.reply_text(help_text, parse_mode="Markdown", reply_markup=get_general_keyboard())
        
    elif data.startswith("move_"):
        ticker = data.split("_")[1]
        await query.message.chat.send_action("typing")
        response = await atlas_agent.process_message(user_id, f"Why is {ticker} moving today?")
        await query.message.reply_text(response, reply_markup=get_quote_keyboard(ticker))
        
    elif data.startswith("watch_"):
        ticker = data.split("_")[1]
        user = await get_or_create_user(user_id)
        current_wl = list(user.watch_list) if user.watch_list else []
        if ticker not in current_wl:
            current_wl.append(ticker)
            await update_user_profile(user_id, {"watch_list": current_wl})
            await query.message.reply_text(f"⭐ Added **{ticker}** to your watchlist! It is now monitored in your daily briefings.", parse_mode="Markdown")
        else:
            await query.message.reply_text(f"⭐ **{ticker}** is already in your watchlist.", parse_mode="Markdown")
            
    elif data.startswith("compare_"):
        parts = data.split("_")
        t1, t2 = parts[1], parts[2]
        await query.message.chat.send_action("typing")
        response = await atlas_agent.process_message(user_id, f"Compare {t1} and {t2} in terms of market cap, sector and latest news.")
        await query.message.reply_text(response, reply_markup=get_general_keyboard())

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
        await update.message.reply_text(response, reply_markup=get_general_keyboard())
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
        
        # Check if single ticker was discussed to show custom action buttons
        import re
        tickers_found = re.findall(r'\b[A-Z]{2,5}\b', user_message.upper())
        keyboard = get_quote_keyboard(tickers_found[0]) if len(tickers_found) == 1 else get_general_keyboard()
        
        await update.message.reply_text(response, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await update.message.reply_text(
            "I encountered a momentary data feed hiccup. Please try your request again.",
            reply_markup=get_general_keyboard()
        )

def setup_bot():
    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("briefing", briefing_command))
    app.add_handler(CommandHandler("watchlist", watchlist_command))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app

get_application = setup_bot

