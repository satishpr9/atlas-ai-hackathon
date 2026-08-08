from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import yfinance as yf
import logging

logger = logging.getLogger(__name__)

class EvidenceItem(BaseModel):
    metric: str
    symbol: str
    value: Any
    display_value: str
    source: str = "Yahoo Finance"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
    confidence: float = 1.0
    data_type: str = "market_data"

class MarketQuote(BaseModel):
    symbol: str
    name: str
    price: float
    prev_close: float
    change: float
    percent_change: float
    volume: int
    avg_volume: Optional[int] = None
    market_cap: Optional[int] = None
    market_cap_str: str
    pe_ratio: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    timestamp: str
    source: str = "Yahoo Finance (Real-time)"

class NewsArticle(BaseModel):
    title: str
    publisher: str
    link: str
    published_at: Optional[str] = None
    summary: Optional[str] = None

class MarketDataProvider:
    @staticmethod
    def _format_market_cap(val: Optional[int]) -> str:
        if not val:
            return "N/A"
        if val >= 1_000_000_000_000:
            return f"${val / 1_000_000_000_000:.2f}T"
        elif val >= 1_000_000_000:
            return f"${val / 1_000_000_000:.2f}B"
        elif val >= 1_000_000:
            return f"${val / 1_000_000:.2f}M"
        return f"${val:,}"

    @classmethod
    def get_quote(cls, symbol: str) -> Optional[MarketQuote]:
        try:
            ticker = yf.Ticker(symbol.upper())
            hist = ticker.history(period="2d")
            if hist.empty:
                return None
            
            info = ticker.info or {}
            current_price = float(hist['Close'].iloc[-1])
            prev_close = float(info.get('previousClose', hist['Close'].iloc[0] if len(hist) > 1 else current_price))
            
            change = current_price - prev_close
            pct_change = (change / prev_close) * 100 if prev_close else 0.0
            
            mkt_cap = info.get('marketCap')
            
            return MarketQuote(
                symbol=symbol.upper(),
                name=info.get('longName', symbol.upper()),
                price=round(current_price, 2),
                prev_close=round(prev_close, 2),
                change=round(change, 2),
                percent_change=round(pct_change, 2),
                volume=int(hist['Volume'].iloc[-1]),
                avg_volume=info.get('averageVolume'),
                market_cap=mkt_cap,
                market_cap_str=cls._format_market_cap(mkt_cap),
                pe_ratio=round(info.get('trailingPE'), 2) if info.get('trailingPE') else None,
                fifty_two_week_high=info.get('fiftyTwoWeekHigh'),
                fifty_two_week_low=info.get('fiftyTwoWeekLow'),
                timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            )
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None

    @classmethod
    def get_recent_news(cls, symbol: str, limit: int = 5) -> List[NewsArticle]:
        try:
            ticker = yf.Ticker(symbol.upper())
            news = ticker.news or []
            articles = []
            for item in news[:limit]:
                # yfinance provides publish time as timestamp
                pub_time = item.get('providerPublishTime')
                pub_date_str = datetime.fromtimestamp(pub_time, timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if pub_time else "Recent"
                
                articles.append(NewsArticle(
                    title=item.get('title', 'No Title'),
                    publisher=item.get('publisher', 'Financial Wire'),
                    link=item.get('link', ''),
                    published_at=pub_date_str,
                    summary=item.get('summary')
                ))
            return articles
        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return []

    @classmethod
    def get_company_overview(cls, symbol: str) -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info or {}
            return {
                "symbol": symbol.upper(),
                "name": info.get('longName', symbol.upper()),
                "sector": info.get('sector', 'N/A'),
                "industry": info.get('industry', 'N/A'),
                "market_cap_str": cls._format_market_cap(info.get('marketCap')),
                "summary": info.get('longBusinessSummary', 'No description available.'),
                "revenue_growth": info.get('revenueGrowth'),
                "profit_margins": info.get('profitMargins'),
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            }
        except Exception as e:
            logger.error(f"Error fetching overview for {symbol}: {e}")
            return {"symbol": symbol.upper(), "error": str(e)}
