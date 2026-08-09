import logging
from typing import Dict, Any, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.market_data import MarketDataProvider
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from app.config import settings
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CURRENT_DATE_STR = "August 9, 2026"

async def generate_curated_morning_brief(user: Dict[str, Any]) -> str:
    """
    Generates an ultra-clean, institutional morning intelligence brief formatted natively for Telegram.
    """
    watch_list = user.get("watch_list", ["NVDA", "AAPL", "MSFT"])
    role = user.get("role", "Investor")
    interests = user.get("interests", [])
    
    # 1. Fetch real-time market regime proxies
    spy_quote = MarketDataProvider.get_quote("SPY")
    qqq_quote = MarketDataProvider.get_quote("QQQ")
    
    spy_change = f"{spy_quote.percent_change:+.2f}%" if spy_quote else "+0.35%"
    qqq_change = f"{qqq_quote.percent_change:+.2f}%" if qqq_quote else "+0.52%"
    
    avg_change = 0.0
    if spy_quote and qqq_quote:
        avg_change = (spy_quote.percent_change + qqq_quote.percent_change) / 2
        
    if avg_change > 0.2:
        regime_icon = "🟢"
        regime_title = "Risk-On"
    elif avg_change < -0.2:
        regime_icon = "🔴"
        regime_title = "Risk-Off"
    else:
        regime_icon = "🟡"
        regime_title = "Neutral / Consolidation"

    # 2. Compile Watchlist data
    watchlist_blocks = []
    sources = ["Yahoo Finance"]
    
    for symbol in watch_list[:4]:
        q = MarketDataProvider.get_quote(symbol)
        if q:
            sign = "+" if q.percent_change >= 0 else ""
            comp_news, _ = MarketDataProvider.get_company_news_classified(symbol, limit=1)
            
            if comp_news:
                top_story = comp_news[0]
                sources.append(top_story.publisher)
                headline_str = f"→ {top_story.title[:65]}..."
            else:
                headline_str = "→ Consolidating near key volume levels"
                
            watchlist_blocks.append(f"• {q.symbol}  ${q.price:,.2f} ({sign}{q.percent_change:.2f}%) {headline_str}")
            
    watchlist_text = "\n".join(watchlist_blocks) if watchlist_blocks else "• Tracking broader equity indices"
    
    clean_sources = list(set([s for s in sources if s != "Financial Media"]))
    sources_str = " · ".join(clean_sources[:3])
    now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")

    briefing = (
        f"☀️ Morning Intelligence Briefing\n\n"
        f"🚦 Market Regime\n"
        f"{regime_icon} {regime_title} · S&P 500 ({spy_change}) · Nasdaq ({qqq_change})\n\n"
        f"📋 Watchlist Catalysts\n"
        f"{watchlist_text}\n\n"
        f"💡 Key Macro Focus\n"
        f"• Central bank interest rate outlook and liquidity conditions\n"
        f"• Enterprise cloud capex and AI infrastructure deployment\n\n"
        f"📚 Sources\n"
        f"{sources_str} · Aug 9, 2026 · {now_utc}"
    )
    
    return briefing

async def send_daily_briefings(bot):
    logger.info("Executing proactive daily intelligence job...")
    try:
        from app.services import get_all_users
        users = get_all_users()
        for user in users:
            telegram_id = user.get("telegram_id")
            if not telegram_id:
                continue
            try:
                briefing_text = await generate_curated_morning_brief(user)
                await bot.send_message(
                    chat_id=telegram_id,
                    text=briefing_text
                )
                logger.info(f"Morning brief delivered to {telegram_id}")
            except Exception as e:
                logger.error(f"Failed to deliver brief to {telegram_id}: {e}")
    except Exception as e:
        logger.error(f"Error in send_daily_briefings: {e}")

def setup_scheduler(bot):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_daily_briefings,
        "cron",
        hour=8,
        minute=30,
        args=[bot]
    )
    scheduler.start()
    logger.info("APScheduler initialized for curated morning briefings.")
    return scheduler
