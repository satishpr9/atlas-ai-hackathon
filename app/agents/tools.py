from typing import List, Optional
from langchain_core.tools import tool
from app.market_data import MarketDataProvider
from datetime import datetime, timezone

CURRENT_DATE_STR = "August 8, 2026"

@tool
def get_stock_quote(ticker: str) -> str:
    """
    Get the verified, real-time stock price, percentage change, and volume for a company.
    Always includes the retrieval timestamp and source.
    """
    quote = MarketDataProvider.get_quote(ticker)
    if not quote:
        return f"Unable to retrieve verified market quote for ticker '{ticker.upper()}'. Please ensure it is a valid US/Global symbol."
    
    sign = "+" if quote.percent_change >= 0 else ""
    return (
        f"**{quote.symbol}** ({quote.name})\n"
        f"Price: **${quote.price:,.2f}** ({sign}{quote.percent_change:.2f}%)\n"
        f"Change: ${quote.change:.2f} | Volume: {quote.volume:,}\n"
        f"Market Cap: **{quote.market_cap_str}**\n"
        f"*Data as of: {quote.timestamp} | Source: {quote.source}*"
    )

@tool
def compare_companies_data(tickers: List[str]) -> str:
    """
    Compare multiple companies side by side on valuation, market cap, and recent performance.
    Pass ONLY the list of tickers to compare (e.g. ['NVDA', 'AMD', 'TSM']).
    """
    if not tickers:
        return "No tickers provided for comparison."
        
    results = []
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    results.append(f"### Comparative Valuation (As of {timestamp})")
    results.append("| Company | Price | Change (Today) | Market Cap | P/E Ratio |")
    results.append("| :--- | :--- | :--- | :--- | :--- |")
    
    for symbol in tickers:
        quote = MarketDataProvider.get_quote(symbol)
        if quote:
            sign = "+" if quote.percent_change >= 0 else ""
            pe_str = f"{quote.pe_ratio:.1f}x" if quote.pe_ratio else "N/A"
            results.append(
                f"| **{quote.symbol}** | ${quote.price:,.2f} | {sign}{quote.percent_change:.2f}% | **{quote.market_cap_str}** | {pe_str} |"
            )
        else:
            results.append(f"| **{symbol.upper()}** | N/A | N/A | N/A | N/A |")
            
    results.append("\n*Source: MarketDataProvider (Yahoo Finance Live Feed)*")
    return "\n".join(results)

@tool
def get_company_news(ticker: str) -> str:
    """
    Get the latest verified news articles with publisher and publication timestamps.
    """
    articles = MarketDataProvider.get_recent_news(ticker, limit=4)
    if not articles:
        return f"No breaking news articles found for {ticker.upper()} in the last 24-48 hours."
        
    output = [f"**Latest Verified Headlines for {ticker.upper()}:**"]
    for i, a in enumerate(articles, 1):
        output.append(f"{i}. **{a.title}**\n   *Publisher: {a.publisher} | Published: {a.published_at}*")
        
    return "\n\n".join(output)

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
