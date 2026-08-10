import logging
from typing import Dict, Any, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.market_data import MarketDataProvider, NewsArticle
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

async def generate_curated_morning_brief(user: Dict[str, Any]) -> str:
    """
    Generates an ultra-clean, high-signal morning intelligence brief formatted natively for Telegram.
    Uses a dynamic Event Intelligence Engine instead of hardcoded categories.
    """
    from app.agents.assistant import llm
    from langchain_core.messages import HumanMessage
    import json
    
    watch_list = user.get("watch_list", [])
    
    # 1. Aggregation
    raw_events = []
    for sym in ["SPY", "QQQ"] + watch_list[:8]:
        news, _ = MarketDataProvider.get_company_news_classified(sym, limit=3)
        for n in news:
            raw_events.append({
                "symbol": sym,
                "title": n.title,
                "summary": n.summary,
                "source": n.publisher
            })
            
    # 2. Deduplication
    seen_titles = set()
    unique_events = []
    for e in raw_events:
        if e["title"] not in seen_titles:
            seen_titles.add(e["title"])
            unique_events.append(e)
            
    # 3. Verification & Scoring Layer (LLM Engine)
    prompt = f"""
You are the Atlas Event Intelligence Engine. 
Your job is to process raw news events, discard noise, rank the most impactful events, and generate a strict summary.

USER WATCHLIST: {watch_list}
RAW EVENTS:
{json.dumps(unique_events, indent=2)}

INSTRUCTIONS:
1. Evaluate all RAW EVENTS. Score their macro/market impact from 0-100.
2. Discard any event with a score < 60 or that is low-quality filler.
3. Select the TOP 3 to 5 most important events.
4. If there are NO events > 60 impact, output EXACTLY the string: "NO_EVENTS" and nothing else.
5. DO NOT act like a news reader reporting headlines. Instead, synthesize the event into an actionable intelligence insight.
Format each event EXACTLY like this (NO HEADLINES):

[Number]. [Symbol] → [One-sentence synthesis of the actual event and its immediate operational/financial impact. E.g. "TSMC's 44.7% monthly revenue jump validates sustained AI infrastructure demand."]
Impact: [1 concise sentence on how this specifically affects the market or the user's watchlist. E.g. "This reinforces structural momentum for NVDA and AMD ahead of their earnings."]

Output ONLY the formatted list of events (or NO_EVENTS). No intro, no outro.
"""
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    engine_output = response.content.strip()
    
    if engine_output == "NO_EVENTS" or not engine_output:
        events_str = "No major market-moving events detected for your watchlist right now."
    else:
        events_str = engine_output
        
    wl_str = " · ".join(watch_list[:5]) if watch_list else "No active tickers tracked"
    date_str = datetime.now(timezone.utc).strftime("%b %d, %Y")
    
    briefing = (
        f"🌅 Morning Intelligence\n\n"
        f"{events_str}\n\n"
        f"👀 Watchlist Check\n"
        f"{wl_str}\n\n"
        f"Sources: Market Data Feed · {date_str}"
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
