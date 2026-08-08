import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import db
from app.market_data import MarketDataProvider, MarketQuote
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import settings

logger = logging.getLogger(__name__)

CURRENT_DATE_STR = "August 8, 2026"

if settings.openai_api_key:
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model=settings.model_name or "gpt-4o-mini",
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.2
    )
else:
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0.2
    )

async def generate_curated_morning_brief(user_doc: dict) -> str:
    """
    Synthesizes a high-impact, curated Morning Briefing.
    Rather than summarizing dozens of news items, it highlights the 2-3 factors that actually matter.
    """
    first_name = user_doc.get("first_name", "there")
    watchlist = user_doc.get("watch_list", [])
    role = user_doc.get("role", "Investor")
    
    if not watchlist:
        watchlist = ["NVDA", "AAPL", "TSM", "MSFT"]
        
    watchlist_data = []
    for symbol in watchlist[:4]:
        quote = MarketDataProvider.get_quote(symbol)
        if quote:
            news = MarketDataProvider.get_recent_news(symbol, limit=2)
            news_titles = [f"• {n.title} ({n.publisher})" for n in news]
            news_str = "\n".join(news_titles) if news_titles else "No major breaking catalysts in the last 24h."
            watchlist_data.append(
                f"Ticker: {quote.symbol} | Price: ${quote.price:,.2f} | 24h Change: {quote.percent_change:+.2f}% | Market Cap: {quote.market_cap_str}\n"
                f"Recent News:\n{news_str}\n"
            )
            
    combined_watchlist_str = "\n".join(watchlist_data)
    now_utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    prompt = (
        f"You are Atlas, an elite institutional financial intelligence assistant.\n"
        f"CURRENT DATE: {CURRENT_DATE_STR} (Current Time: {now_utc_str}).\n\n"
        f"USER: {first_name} ({role})\n\n"
        f"--- LIVE MARKET & WATCHLIST FEED ---\n"
        f"{combined_watchlist_str}\n"
        f"-------------------------------------\n\n"
        "TASK: Write a curated, high-impact Morning Briefing for the user. Do NOT summarize all headlines. Highlight ONLY the 2-3 developments that actually matter.\n\n"
        "REQUIRED STRUCTURE:\n"
        f"🌅 **Atlas Morning Briefing — {CURRENT_DATE_STR}**\n\n"
        f"Good morning, {first_name}. Here are the core developments driving your watchlist today:\n\n"
        "• **[TICKER] (Change%)**: [Key Catalyst].\n"
        "  *Why it matters:* [1-2 sharp sentences on institutional impact / revenue / margins].\n\n"
        "(Repeat for up to 3 key companies with traffic lights: 🔴 for high volatility/catalysts, 🟡 for strategic shifts, 🟢 for quiet/steady)\n\n"
        "📊 **Market Macro Context**: [1 sentence on broader tech/semiconductor sentiment].\n"
        "👀 **Watch Today**: [1-2 key tickers or levels to monitor].\n\n"
        "RULES:\n"
        "- Grounded strictly in August 2026.\n"
        "- Clean, concise, under 220 words.\n"
        "- Highly actionable for a professional."
    )
    
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content
        if isinstance(content, list):
            text_parts = []
            for p in content:
                if isinstance(p, dict) and "text" in p:
                    text_parts.append(p["text"])
                elif isinstance(p, str):
                    text_parts.append(p)
            return "".join(text_parts)
        return str(content)
    except Exception as e:
        logger.error(f"Error generating brief with LLM: {e}")
        # Graceful fallback briefing
        items = []
        for sym in watchlist[:3]:
            q = MarketDataProvider.get_quote(sym)
            if q:
                items.append(f"• **{q.symbol}**: ${q.price:,.2f} ({q.percent_change:+.2f}%)")
        return (
            f"🌅 **Atlas Morning Market Snapshot — {CURRENT_DATE_STR}**\n\n"
            "Here is the real-time snapshot for your primary watchlist:\n\n" +
            "\n".join(items) +
            f"\n\n*Data retrieved at {now_utc_str} | Source: MarketDataProvider*"
        )

async def send_daily_briefings(bot):
    logger.info("Executing proactive daily intelligence job...")
    try:
        users_collection = db.get_db()["users"]
        cursor = users_collection.find({})
        async for user in cursor:
            telegram_id = user.get("telegram_id")
            if not telegram_id:
                continue
            try:
                briefing_text = await generate_curated_morning_brief(user)
                await bot.send_message(
                    chat_id=telegram_id,
                    text=briefing_text,
                    parse_mode="Markdown"
                )
                logger.info(f"Morning brief delivered to {telegram_id}")
            except Exception as e:
                logger.error(f"Failed to deliver brief to {telegram_id}: {e}")
    except Exception as e:
        logger.error(f"Error in send_daily_briefings: {e}")

def setup_scheduler(bot):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_briefings, 'cron', hour=8, minute=30, args=[bot])
    scheduler.start()
    logger.info("APScheduler initialized for curated morning briefings.")
    return scheduler
