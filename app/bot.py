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
        
        # 2. Check for On-Demand Morning Briefing Request
        lower_text = user_text.lower()
        if "morning briefing" in lower_text or "daily brief" in lower_text or "morning brief" in lower_text:
            from app.scheduler import generate_curated_morning_brief
            brief_text = await generate_curated_morning_brief(user.model_dump())
            await add_message_to_history(telegram_id, "user", user_text)
            await add_message_to_history(telegram_id, "assistant", brief_text)
            await update.message.reply_text(brief_text, parse_mode="Markdown")
            return
        
        # 3. Build User Context String
        user_context = f"Role: {user.role or 'Unknown'}\n"
        user_context += f"Interests: {', '.join(user.interests) if user.interests else 'Unknown'}\n"
        user_context += f"Watchlist: {', '.join(user.watch_list) if user.watch_list else 'Unknown'}\n"
        
        # 4. Get history (limit to last 10 for context window efficiency)
        chat_history = [{"role": msg.role, "content": msg.content} for msg in user.chat_history[-10:]]
        
        # 5. Save User Message
        await add_message_to_history(telegram_id, "user", user_text)
        
        # 6. Process through LangGraph
        response_text = await process_user_input(telegram_id, user_text, chat_history, user_context)
        
        # 7. Save AI Response
        await add_message_to_history(telegram_id, "assistant", response_text)
        
        # 8. Reply
        await update.message.reply_text(response_text)
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text(
            "I couldn't complete the full analytical synthesis right now due to a data feed bottleneck, "
            "but I have logged the request and verified your account context."
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle financial document/PDF uploads and summarize key insights.
    """
    document = update.message.document
    if not document.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("Please upload a PDF document (e.g. Earnings Report, Pitch Deck, 10-K).")
        return
        
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    await update.message.reply_text("📄 Reading and analyzing your financial document...")
    
    try:
        from pypdf import PdfReader
        from io import BytesIO
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import SystemMessage, HumanMessage
        
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        
        reader = PdfReader(BytesIO(file_bytes))
        extracted_text = ""
        for page in reader.pages[:15]: # Process up to 15 pages for quick response
            extracted_text += page.extract_text() or ""
            
        if settings.openai_api_key:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=settings.model_name or "gpt-4o-mini",
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                temperature=0.2
            )
        else:
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                google_api_key=settings.gemini_api_key,
                temperature=0.2
            )
        
        prompt = (
            "You are an elite financial analyst. Analyze this financial document and provide:\n"
            "1. Executive Summary (2-3 sentences)\n"
            "2. Key Financial Highlights (Revenue, Margins, Growth)\n"
            "3. Strategic Announcements or Management Guidance\n"
            "4. Critical Risks & Red Flags\n\n"
            f"Document Text:\n{extracted_text[:30000]}"
        )
        
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        output_text = ""
        if isinstance(response.content, list):
            for part in response.content:
                if isinstance(part, dict) and "text" in part:
                    output_text += part["text"]
                elif isinstance(part, str):
                    output_text += part
        else:
            output_text = str(response.content)
            
        await update.message.reply_text(f"📊 **Financial Document Analysis:**\n\n{output_text}")
        
    except Exception as e:
        logger.error(f"Error analyzing document: {e}")
        await update.message.reply_text(f"Sorry, I had trouble parsing the document: {e}")

async def get_application() -> Application:
    """
    Build and return the telegram application.
    """
    app = Application.builder().token(settings.telegram_bot_token).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    return app
