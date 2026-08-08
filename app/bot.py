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
    user_id = update.message.from_user.id
    
    # Optional: Send a typing indicator while processing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    try:
        from app.agents.assistant import process_user_input
        # Mock user context for now (e.g., loaded from MongoDB based on user_id)
        user_context = "Role: Investor. Interests: Tech, AI."
        
        response_text = await process_user_input(user_id, user_text, user_context)
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
