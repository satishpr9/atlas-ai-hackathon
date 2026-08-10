from typing import List, Optional
from langchain_core.tools import tool
from app.market_data import MarketDataProvider
from datetime import datetime, timezone

from app.market_data import get_current_date_str

@tool
def get_stock_quote(ticker: str) -> str:
    """
    Get the verified, real-time stock price, percentage change, and volume for a company.
    Returns strictly the stock price and key market stats without unnecessary analysis.
    """
    from app.agents.price_engine import StockPriceEngine
    return StockPriceEngine.get_price(ticker)

@tool
def get_market_overview(scope: str = "us") -> str:
    """
    Get a broad market overview showing major index performance (S&P 500, Nasdaq, Dow Jones, Russell 2000).
    Use this when the user asks about 'the market', 'market today', 'indices', or broad market conditions.
    """
    indices = {
        "^GSPC": "S&P 500",
        "^IXIC": "Nasdaq Composite", 
        "^DJI": "Dow Jones",
        "^RUT": "Russell 2000",
        "^VIX": "VIX (Fear Index)"
    }
    
    now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
    lines = ["📊 Market Overview\n"]
    
    for sym, name in indices.items():
        quote = MarketDataProvider.get_quote(sym)
        if quote:
            sign = "+" if quote.percent_change >= 0 else ""
            if sym == "^VIX":
                lines.append(f"  {name}: {quote.price:.2f} ({sign}{quote.percent_change:.2f}%)")
            else:
                lines.append(f"  {name}: {quote.price:,.2f} ({sign}{quote.percent_change:.2f}%)")
    
    lines.append(f"\n📚 Yahoo Finance · {get_current_date_str()} · {now_utc}")
    return "\n".join(lines)

@tool
def get_earnings_calendar(ticker: str) -> str:
    """
    Get upcoming earnings dates and key financial metrics for a company.
    Use when users ask about earnings, earnings dates, upcoming calls, or financial results.
    """
    import yfinance as yf
    try:
        t = yf.Ticker(ticker.upper())
        info = t.info or {}
        cal = t.calendar or {}
        
        now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
        name = info.get('longName', ticker.upper())
        
        lines = [f"📅 {name} ({ticker.upper()}) · Earnings Info\n"]
        
        # Earnings date
        earnings_dates = cal.get('Earnings Date', [])
        if earnings_dates:
            for d in earnings_dates:
                lines.append(f"  Next Earnings: {d}")
        else:
            lines.append("  Next Earnings: Not yet announced")
        
        # Key financial metrics from info
        eps_trail = info.get('trailingEps')
        eps_fwd = info.get('forwardEps')
        rev = info.get('totalRevenue')
        rev_growth = info.get('revenueGrowth')
        profit_margin = info.get('profitMargins')
        
        lines.append("")
        if eps_trail:
            lines.append(f"  Trailing EPS: ${eps_trail:.2f}")
        if eps_fwd:
            lines.append(f"  Forward EPS: ${eps_fwd:.2f}")
        if rev:
            rev_str = f"${rev/1e9:.2f}B" if rev >= 1e9 else f"${rev/1e6:.0f}M"
            lines.append(f"  Revenue (TTM): {rev_str}")
        if rev_growth is not None:
            lines.append(f"  Revenue Growth: {rev_growth*100:.1f}%")
        if profit_margin is not None:
            lines.append(f"  Profit Margin: {profit_margin*100:.1f}%")
        
        # Analyst estimates
        target_mean = info.get('targetMeanPrice')
        target_high = info.get('targetHighPrice')
        target_low = info.get('targetLowPrice')
        rec = info.get('recommendationKey')
        
        if target_mean or rec:
            lines.append("")
            lines.append("  📈 Analyst Consensus")
            if rec:
                lines.append(f"  Rating: {rec.upper()}")
            if target_mean:
                lines.append(f"  Price Target: ${target_low:.0f} – ${target_high:.0f} (Mean: ${target_mean:.0f})")
        
        lines.append(f"\n📚 Yahoo Finance · {get_current_date_str()} · {now_utc}")
        return "\n".join(lines)
    except Exception as e:
        return f"Unable to retrieve earnings data for {ticker.upper()}: {str(e)}"

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
            
    lines.append(f"\n📚 Yahoo Finance · {get_current_date_str()} · {now_utc}")
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
    source_apis = set()
    for a in articles:
        tag = f"[{a.category}] " if a.category != "Company-Specific" else ""
        output.append(f"{ticker.upper()} → {tag}{a.title}\n  ({a.publisher} · {a.relative_time})")
        source_apis.add(a.source_api)
        
    source_str = " / ".join(list(source_apis)) if source_apis else "Yahoo Finance"
    output.append(f"\n📚 Sources: {source_str} News · {get_current_date_str()} · {now_utc}")
    return "\n".join(output)

@tool
async def update_user_facts(
    role: Optional[str] = None,
    interests: Optional[List[str]] = None,
    watch_list: Optional[List[str]] = None,
    preferred_insights: Optional[List[str]] = None,
    briefing_time: Optional[str] = None,
    connected_accounts: Optional[List[str]] = None,
    user_id: Optional[int] = None
) -> str:
    """
    Store explicitly stated facts and preferences about the user (e.g. role = 'Investor', watchlist = ['NVDA', 'TSM'], preferred_insights = ['earnings', 'SEC filings']).
    Call this whenever the user shares their background, focus areas, or notification preferences.
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

    if preferred_insights:
        current_insights = list(user.preferred_insights) if user.preferred_insights else []
        for ins in preferred_insights:
            if ins not in current_insights:
                current_insights.append(ins)
        updates["preferred_insights"] = current_insights

    if briefing_time:
        updates["briefing_time"] = briefing_time

    if connected_accounts:
        current_accs = list(user.connected_accounts) if user.connected_accounts else []
        for acc in connected_accounts:
            if acc not in current_accs:
                current_accs.append(acc)
        updates["connected_accounts"] = current_accs

    updates["onboarding_stage"] = "profiled"

    await update_user_profile(user_id, updates)
    return f"Saved verified preferences for user {user_id}."

financial_tools = [get_stock_quote, get_market_overview, get_earnings_calendar, compare_companies_data, get_company_news, update_user_facts]
