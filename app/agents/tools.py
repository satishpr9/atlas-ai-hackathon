import yfinance as yf
from langchain_core.tools import tool

@tool
def get_stock_price(ticker: str) -> str:
    """
    Get the current stock price and basic market data for a given ticker symbol (e.g., AAPL, TSLA, NVDA).
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if hist.empty:
            return f"Could not find price data for ticker: {ticker}"
        
        current_price = hist['Close'].iloc[-1]
        prev_close = stock.info.get('previousClose', 0)
        
        change = current_price - prev_close
        percent_change = (change / prev_close) * 100 if prev_close else 0
        
        return (
            f"Ticker: {ticker.upper()}\n"
            f"Current Price: ${current_price:.2f}\n"
            f"Change: ${change:.2f} ({percent_change:.2f}%)\n"
            f"Volume: {hist['Volume'].iloc[-1]}"
        )
    except Exception as e:
        return f"Error fetching price for {ticker}: {str(e)}"

@tool
def get_company_news(ticker: str) -> str:
    """
    Get the latest news articles for a specific company using its ticker symbol.
    """
    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        if not news:
            return f"No recent news found for {ticker}."
            
        news_summary = f"Latest news for {ticker.upper()}:\n\n"
        for i, article in enumerate(news[:5]): # Get top 5
            title = article.get('title', 'No Title')
            publisher = article.get('publisher', 'Unknown Publisher')
            link = article.get('link', '')
            news_summary += f"{i+1}. {title} ({publisher})\nLink: {link}\n\n"
            
        return news_summary
    except Exception as e:
        return f"Error fetching news for {ticker}: {str(e)}"

@tool
def get_company_info(ticker: str) -> str:
    """
    Get a brief overview of a company, its sector, industry, and key fundamentals.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        name = info.get('longName', ticker.upper())
        sector = info.get('sector', 'Unknown Sector')
        industry = info.get('industry', 'Unknown Industry')
        summary = info.get('longBusinessSummary', 'No summary available.')
        market_cap = info.get('marketCap', 'N/A')
        
        return (
            f"Company: {name} ({ticker.upper()})\n"
            f"Sector: {sector} | Industry: {industry}\n"
            f"Market Cap: {market_cap}\n"
            f"Summary: {summary[:500]}..." # Truncate summary
        )
    except Exception as e:
        return f"Error fetching info for {ticker}: {str(e)}"

# A list of all financial tools to easily import
financial_tools = [get_stock_price, get_company_news, get_company_info]
