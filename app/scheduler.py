import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import db
from app.agents.tools import get_stock_price, get_company_news
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import settings

logger = logging.getLogger(__name__)

if settings.openai_api_key:
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model=settings.model_name or "gpt-4o-mini",
        openai_api_key=settings.openai_api_key,
        openai_api_base=settings.openai_base_url,
        temperature=0.3
    )
else:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0.3
    )

async def generate_briefing_for_user(user_doc: dict) -> str:
    telegram_id = user_doc.get("telegram_id")
    watchlist = user_doc.get("watch_list", [])
    role = user_doc.get("role", "Finance Professional")
    
    if not watchlist:
        watchlist = ["AAPL", "NVDA", "MSFT"] # Default watchlist for demo
        
    market_data = []
    for ticker in watchlist[:3]:
        price_info = get_stock_price.invoke({"ticker": ticker})
        news_info = get_company_news.invoke({"ticker": ticker})
        market_data.append(f"--- {ticker} ---\n{price_info}\n\nNews:\n{news_info}\n")
        
    combined_data = "\n".join(market_data)
    
    prompt = (
        f"You are an executive financial assistant preparing a morning briefing for a {role}.\n"
        "Here is the latest market and news data for their watchlist:\n\n"
        f"{combined_data}\n\n"
        "Task: Create a concise, high-impact Morning Briefing. "
        "Highlight the most important market movements and explain WHY they matter. "
        "Keep it under 250 words, clean, and directly actionable. Avoid fluff."
    )
    
    response = await llm.ainvoke([SystemMessage(content=prompt)])
    
    # Process text output cleanly
    if isinstance(response.content, list):
        text_parts = []
        for part in response.content:
            if isinstance(part, dict) and "text" in part:
                text_parts.append(part["text"])
            elif isinstance(part, str):
                text_parts.append(part)
        return "".join(text_parts)
    return str(response.content)

async def send_daily_briefings(bot):
    logger.info("Starting proactive daily briefings job...")
    try:
        users_collection = db.get_db()["users"]
        cursor = users_collection.find({})
        async for user in cursor:
            telegram_id = user.get("telegram_id")
            if not telegram_id:
                continue
            try:
                briefing_text = await generate_briefing_for_user(user)
                header = "🌅 *Your Daily Financial Intelligence Briefing*\n\n"
                await bot.send_message(
                    chat_id=telegram_id,
                    text=f"{header}{briefing_text}",
                    parse_mode="Markdown"
                )
                logger.info(f"Briefing successfully sent to user {telegram_id}")
            except Exception as e:
                logger.error(f"Failed to send briefing to {telegram_id}: {e}")
    except Exception as e:
        logger.error(f"Error in send_daily_briefings: {e}")

def setup_scheduler(bot):
    scheduler = AsyncIOScheduler()
    # Runs everyday at 8:30 AM
    scheduler.add_job(send_daily_briefings, 'cron', hour=8, minute=30, args=[bot])
    scheduler.start()
    logger.info("APScheduler initialized for proactive briefings.")
    return scheduler
