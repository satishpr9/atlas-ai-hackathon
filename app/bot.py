import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from app.config import settings

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Onboarding: No slash commands needed typically, but /start is the entry point.
    """
    welcome_text = (
        "Hello! I am your AI Financial Assistant.\n\n"
        "To get started, what best describes your role? (e.g., Investor, Analyst, Founder)"
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle natural language conversations.
    """
    user_text = update.message.text
    telegram_id = update.message.from_user.id
    first_name = update.message.from_user.first_name
    username = update.message.from_user.username
    
    # Send typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    try:
        from app.agents.assistant import process_user_input
        from app.services import get_or_create_user, add_message_to_history
        
        # 1. Get or Create User
        user = await get_or_create_user(telegram_id, first_name, username)
        
        # 2. Build User Context String
        user_context = f"Role: {user.role or 'Unknown'}\n"
        user_context += f"Interests: {', '.join(user.interests) if user.interests else 'Unknown'}\n"
        user_context += f"Watchlist: {', '.join(user.watch_list) if user.watch_list else 'Unknown'}\n"
        
        # 3. Get history (limit to last 10 for context window efficiency)
        chat_history = [{"role": msg.role, "content": msg.content} for msg in user.chat_history[-10:]]
        
        # 4. Save User Message
        await add_message_to_history(telegram_id, "user", user_text)
        
        # 5. Process through LangGraph
        response_text = await process_user_input(telegram_id, user_text, chat_history, user_context)
        
        # 6. Save AI Response
        await add_message_to_history(telegram_id, "assistant", response_text)
        
        # 7. Reply
        await update.message.reply_text(response_text)
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text("I'm sorry, I encountered an error while processing your request.")

async def get_application() -> Application:
    """
    Build and return the telegram application.
    """
    app = Application.builder().token(settings.telegram_bot_token).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    return app
