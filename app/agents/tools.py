from typing import List, Optional
from langchain_core.tools import tool
from app.market_data import MarketDataProvider
from datetime import datetime, timezone

CURRENT_DATE_STR = "August 9, 2026"

@tool
def get_stock_quote(ticker: str) -> str:
    """
    Get the verified, real-time stock price, percentage change, and volume for a company.
    Formatted cleanly for Telegram with timestamps.
    """
    quote = MarketDataProvider.get_quote(ticker)
    if not quote:
        return f"Unable to retrieve verified market quote for '{ticker.upper()}'."
    
    sign = "+" if quote.percent_change >= 0 else ""
    now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
    pe_str = f" · {quote.pe_ratio:.1f}x P/E" if quote.pe_ratio else ""
    
    return (
        f"💰 {quote.symbol}  ${quote.price:,.2f} ({sign}{quote.percent_change:.2f}% today)\n"
        f"Market Cap: {quote.market_cap_str}{pe_str}\n"
        f"Volume: {quote.volume:,}\n\n"
        f"📚 Yahoo Finance · Aug 9, 2026, {now_utc}"
    )

@tool
def compare_companies_data(tickers: List[str]) -> str:
    """
    Compare multiple companies on valuation, market cap, and recent performance.
    """
    if not tickers:
        return "No tickers provided for comparison."
        
    lines = ["📊 Market Comparison\n"]
    now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
    
    for symbol in tickers:
        quote = MarketDataProvider.get_quote(symbol)
        if quote:
            sign = "+" if quote.percent_change >= 0 else ""
            pe_str = f" ({quote.pe_ratio:.1f}x P/E)" if quote.pe_ratio else ""
            lines.append(f"{quote.symbol}  ${quote.price:,.2f} · {quote.market_cap_str}{pe_str}")
            
    lines.append(f"\n📚 Yahoo Finance · Aug 9, 2026, {now_utc}")
    return "\n".join(lines)

@tool
def get_company_news(ticker: str) -> str:
    """
    Get the latest verified news articles with publisher and relative timestamps.
    """
    articles = MarketDataProvider.get_recent_news(ticker, limit=3)
    if not articles:
        return f"📰 Latest: No breaking headlines verified for {ticker.upper()} in the last 24h."
        
    now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
    output = ["📰 Latest News\n"]
    for a in articles:
        tag = f"[{a.category}] " if a.category != "Company-Specific" else ""
        output.append(f"{ticker.upper()} → {tag}{a.title}\n  ({a.publisher} · {a.relative_time})")
        
    output.append(f"\n📚 Sources: Yahoo Finance News · Aug 9, 2026, {now_utc}")
    return "\n".join(output)

@tool
async def update_user_facts(role: Optional[str] = None, interests: Optional[List[str]] = None, watch_list: Optional[List[str]] = None, user_id: Optional[int] = None) -> str:
    """
    Store ONLY explicitly stated facts about the user (e.g. role = 'Founder', watchlist = ['NVDA', 'TSM']).
    Never combine or hallucinate roles (e.g. do not turn 'Founder' into 'Founder and Analyst').
    """
    if not user_id:
        return "Error: user_id required."
        
    from app.services import update_user_profile, get_or_create_user
    user = await get_or_create_user(user_id)
    
    updates = {}
    if role:
        updates["role"] = role
        
    current_interests = list(user.interests) if user.interests else []
    if interests:
        for item in interests:
            if item not in current_interests:
                current_interests.append(item)
        updates["interests"] = current_interests
        
    current_watchlist = list(user.watch_list) if user.watch_list else []
    if watch_list:
        for ticker in watch_list:
            t = ticker.upper()
            if t not in current_watchlist:
                current_watchlist.append(t)
        updates["watch_list"] = current_watchlist

    await update_user_profile(user_id, updates)
    return f"Saved verified user preferences for {user_id}."

financial_tools = [get_stock_quote, compare_companies_data, get_company_news, update_user_facts]
