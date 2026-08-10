import logging
from typing import Dict, Any, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.market_data import MarketDataProvider, NewsArticle
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def _synthesize_catalyst_impact(symbol: str, title: str, summary: str = "") -> str:
    """
    Dynamically generates a concise institutional 'Why it matters' explanation.
    """
    title_lower = (title + " " + summary).lower()
    if any(k in title_lower for k in ["earnings", "revenue", "profit", "quarter", "ebitda", "guidance", "beat", "miss"]):
        return "Direct fundamental validation of quarterly revenue and margin durability."
    elif any(k in title_lower for k in ["ai", "chips", "gpu", "datacenter", "cloud", "compute"]):
        return "Hyperscaler data-center demand & AI infrastructure deployment velocity."
    elif any(k in title_lower for k in ["sec", "antitrust", "investigation", "probe", "lawsuit", "regulat"]):
        return "Structural regulatory scrutiny impacting operational freedom or margins."
    elif any(k in title_lower for k in ["acquisition", "merger", "deal", "buyout", "partnership"]):
        return "Strategic consolidation and TAM expansion into adjacent verticals."
    elif any(k in title_lower for k in ["fed", "rate", "inflation", "cpi", "macro", "treasury"]):
        return "Macro discount-rate dynamics and equity valuation multiple sensitivity."
    return "Material sentiment driver impacting near-term market expectations."

async def generate_curated_morning_brief(user: Dict[str, Any]) -> str:
    """
    Generates an ultra-clean, high-signal morning intelligence brief formatted natively for Telegram.
    Explains WHY developments matter instead of forwarding raw headlines.
    """
    watch_list = user.get("watch_list", [])
    role = user.get("role", "Investor")
    
    # 1. Real-time market regime proxies
    spy_quote = MarketDataProvider.get_quote("SPY")
    qqq_quote = MarketDataProvider.get_quote("QQQ")
    
    spy_change = f"{spy_quote.percent_change:+.2f}%" if spy_quote else "N/A"
    qqq_change = f"{qqq_quote.percent_change:+.2f}%" if qqq_quote else "N/A"
    
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

    # 2. Watchlist Catalysts & 'Why it matters'
    watchlist_blocks = []
    sources = ["Yahoo Finance"]
    significant_movers = 0
    
    for symbol in watch_list[:5]:
        q = MarketDataProvider.get_quote(symbol)
        if q:
            sign = "+" if q.percent_change >= 0 else ""
            curr = "₹" if q.currency == "INR" or q.symbol.endswith((".NS", ".BO")) else ("€" if q.currency == "EUR" else ("£" if q.currency == "GBP" else "$"))
            comp_news, _ = MarketDataProvider.get_company_news_classified(symbol, limit=1)
            
            if comp_news:
                top_story = comp_news[0]
                if top_story.publisher and top_story.publisher != "Financial Media":
                    sources.append(top_story.publisher)
                why_matters = _synthesize_catalyst_impact(q.symbol, top_story.title, top_story.summary)
                watchlist_blocks.append(
                    f"• {q.symbol}  {curr}{q.price:,.2f} ({sign}{q.percent_change:.2f}%)\n"
                    f"  Headline: {top_story.title[:80]}...\n"
                    f"  Why it matters: {why_matters}"
                )
                significant_movers += 1
            else:
                if abs(q.percent_change) >= 1.0:
                    watchlist_blocks.append(f"• {q.symbol}  {curr}{q.price:,.2f} ({sign}{q.percent_change:.2f}%) → Noteworthy price momentum; no breaking company filings.")
                    significant_movers += 1
                else:
                    watchlist_blocks.append(f"• {q.symbol}  {curr}{q.price:,.2f} ({sign}{q.percent_change:.2f}%) → Quiet session; range-bound consolidation.")
                    
    watchlist_text = "\n\n".join(watchlist_blocks) if watchlist_blocks else "• Tracking broader equity indices"
    
    clean_sources = list(set([s for s in sources if s != "Financial Media"]))
    sources_str = " · ".join(clean_sources[:3])
    date_str = datetime.now(timezone.utc).strftime("%b %d, %Y")
    now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")

    briefing = (
        f"☀️ Morning Intelligence Briefing\n\n"
        f"🚦 Market Regime\n"
        f"{regime_icon} {regime_title} · S&P 500 ({spy_change}) · Nasdaq ({qqq_change})\n\n"
        f"📋 Watchlist Catalysts\n\n"
        f"{watchlist_text}\n\n"
        f"💡 Key Focus\n"
        f"• Central bank policy cues and global liquidity conditions\n"
        f"• Tech/AI infrastructure capex cadence and margin durability\n\n"
        f"📚 Sources\n"
        f"{sources_str} · {date_str} · {now_utc}"
    )
    
    return briefing

async def generate_curated_evening_wrap(user: Dict[str, Any]) -> str:
    """
    Generates an institutional market close summary.
    """
    watch_list = user.get("watch_list", [])
    
    spy_quote = MarketDataProvider.get_quote("SPY")
    qqq_quote = MarketDataProvider.get_quote("QQQ")
    
    spy_change = f"{spy_quote.percent_change:+.2f}%" if spy_quote else "N/A"
    qqq_change = f"{qqq_quote.percent_change:+.2f}%" if qqq_quote else "N/A"
    
    watchlist_lines = []
    for symbol in watch_list[:5]:
        q = MarketDataProvider.get_quote(symbol)
        if q:
            sign = "+" if q.percent_change >= 0 else ""
            curr = "₹" if q.currency == "INR" or q.symbol.endswith((".NS", ".BO")) else ("€" if q.currency == "EUR" else ("£" if q.currency == "GBP" else "$"))
            watchlist_lines.append(f"• {q.symbol}  {curr}{q.price:,.2f} ({sign}{q.percent_change:.2f}%)")
            
    wl_str = "\n".join(watchlist_lines) if watchlist_lines else "• Broader market indices tracked"
    date_str = datetime.now(timezone.utc).strftime("%b %d, %Y")
    now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")

    wrap = (
        f"🌙 Evening Market Summary\n\n"
        f"📊 Market Close\n"
        f"S&P 500: {spy_change} · Nasdaq 100: {qqq_change}\n\n"
        f"📋 Watchlist Close\n"
        f"{wl_str}\n\n"
        f"💡 Overnight Watch\n"
        f"• Global index futures & Asian market opening tone\n"
        f"• Upcoming economic prints and earnings announcements\n\n"
        f"📚 Sources\n"
        f"Yahoo Finance Real-time Feed · {date_str} · {now_utc}"
    )
    return wrap

async def send_daily_briefings(bot):
    logger.info("Executing proactive daily intelligence job...")
    try:
        from app.services import get_all_users
        from app.agents.assistant import llm
        from langchain_core.messages import HumanMessage
        
        users = get_all_users()
        for user in users:
            telegram_id = user.get("telegram_id")
            if not telegram_id:
                continue
            try:
                briefing_text = await generate_curated_morning_brief(user)
                
                # --- MATERIALITY FILTER ---
                filter_prompt = (
                    "You are a strict financial news filter for institutional professionals.\n"
                    "Evaluate the following briefing and answer ONLY 'YES' or 'NO'.\n"
                    "Is there ANY material data, significant price movement, or actionable catalyst present? "
                    "If it's mostly empty or low-signal filler (e.g. tracking stocks with no major news), output NO. "
                    "Silence is strongly preferred over noise. Only say YES if there is something worth interrupting them for.\n\n"
                    f"BRIEFING:\n{briefing_text}"
                )
                eval_res = await llm.ainvoke([HumanMessage(content=filter_prompt)])
                
                if "NO" in str(eval_res.content).upper() and "YES" not in str(eval_res.content).upper()[:5]:
                    logger.info(f"Materiality filter suppressed morning brief for {telegram_id} (low signal/noise ratio)")
                    continue
                    
                await bot.send_message(
                    chat_id=telegram_id,
                    text=briefing_text
                )
                logger.info(f"Morning brief delivered to {telegram_id}")
            except Exception as e:
                logger.error(f"Failed to deliver brief to {telegram_id}: {e}")
    except Exception as e:
        logger.error(f"Error in send_daily_briefings: {e}")

async def check_price_alerts(bot):
    logger.info("Checking persistent price alerts...")
    try:
        from app.services import get_all_users, update_user_profile
        users = get_all_users()
        for user in users:
            telegram_id = user.get("telegram_id")
            alerts = user.get("alerts")
            if not telegram_id or not alerts:
                continue
                
            active_alerts = []
            for alert in alerts:
                symbol = alert.get("ticker")
                condition = alert.get("condition")
                threshold = float(alert.get("threshold", 0))
                base_price = float(alert.get("base_price", 0))
                
                q = MarketDataProvider.get_quote(symbol)
                if not q or not base_price:
                    active_alerts.append(alert)
                    continue
                    
                pct_change = ((q.price - base_price) / base_price) * 100
                
                triggered = False
                if condition == "drop_percent" and pct_change <= -threshold:
                    triggered = True
                elif condition == "up_percent" and pct_change >= threshold:
                    triggered = True
                    
                if triggered:
                    sign = "+" if pct_change > 0 else ""
                    msg = f"🚨 **Price Alert** 🚨\n\n{symbol} has moved {sign}{pct_change:.2f}% from your set price of ${base_price:.2f}. Current price: ${q.price:.2f}."
                    await bot.send_message(chat_id=telegram_id, text=msg)
                    logger.info(f"Triggered alert for {telegram_id}: {symbol} {pct_change:.2f}%")
                else:
                    active_alerts.append(alert)
                    
            if len(active_alerts) != len(alerts):
                await update_user_profile(telegram_id, {"alerts": active_alerts})
                
    except Exception as e:
        logger.error(f"Error checking price alerts: {e}")

def setup_scheduler(bot):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_daily_briefings,
        "cron",
        hour=8,
        minute=30,
        args=[bot]
    )
    scheduler.add_job(
        check_price_alerts,
        "interval",
        minutes=5,
        args=[bot]
    )
    scheduler.start()
    logger.info("APScheduler initialized for curated morning briefings and alerts.")
    return scheduler
