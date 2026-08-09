from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field
import yfinance as yf
import logging
import re

logger = logging.getLogger(__name__)

CURRENT_DATE_STR = "August 9, 2026"

class NewsArticle(BaseModel):
    symbol: str
    title: str
    publisher: str
    link: str
    published_at: str
    relative_time: str
    summary: str
    category: str = "Company-Specific" # "Company-Specific", "Industry", "Macro", "Irrelevant"
    is_direct_catalyst: bool = True

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
    forward_pe: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    timestamp: str
    source: str = "Yahoo Finance (Real-time)"

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

    @staticmethod
    def _calculate_relative_time(pub_iso_str: Optional[str]) -> str:
        if not pub_iso_str:
            return "Recently"
        try:
            dt = datetime.fromisoformat(pub_iso_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            diff = now - dt
            hours = int(diff.total_seconds() // 3600)
            minutes = int((diff.total_seconds() % 3600) // 60)
            
            if hours < 1:
                return f"{max(1, minutes)} minutes ago"
            elif hours < 24:
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            else:
                days = hours // 24
                return f"{days} day{'s' if days != 1 else ''} ago"
        except Exception:
            return "Recent"

    @classmethod
    def is_strictly_company_specific(cls, symbol: str, name: str, title: str) -> bool:
        """
        Strictly tests if the headline directly refers to the company (in the title).
        Filters out generic listicles and other companies' earnings.
        """
        title_lower = title.lower()
        sym_lower = symbol.lower()
        
        # Core company identifiers
        company_aliases = {
            "MSFT": ["microsoft", "msft", "azure", "windows", "copilot"],
            "GOOGL": ["google", "alphabet", "googl", "goog", "youtube", "deepmind", "gemini"],
            "GOOG": ["google", "alphabet", "googl", "goog", "youtube", "deepmind", "gemini"],
            "AAPL": ["apple", "aapl", "iphone", "tim cook", "ipad", "macbook"],
            "NVDA": ["nvidia", "nvda", "blackwell", "jensen huang", "hopper"],
            "TSLA": ["tesla", "tsla", "elon musk", "cybertruck", "full self-driving", "fsd"],
            "AMD": ["amd", "lisa su", "ryzen", "epyc", "instinct"],
            "TSM": ["tsmc", "taiwan semiconductor", "tsm"]
        }
        
        aliases = company_aliases.get(symbol.upper(), [sym_lower, name.lower().split()[0]])
        
        # Must contain one of the direct aliases as a whole word / phrase
        for alias in aliases:
            if re.search(r'\b' + re.escape(alias) + r'\b', title_lower):
                # Filter out generic listicles like "How many of the largest companies..."
                if "how many of" in title_lower or "which stocks" in title_lower or "best stocks to buy" in title_lower:
                    return False
                return True
                
        return False

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
                forward_pe=round(info.get('forwardPE'), 2) if info.get('forwardPE') else None,
                fifty_two_week_high=info.get('fiftyTwoWeekHigh'),
                fifty_two_week_low=info.get('fiftyTwoWeekLow'),
                timestamp=datetime.now(timezone.utc).strftime("%H:%M UTC")
            )
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None

    @classmethod
    def get_company_news_classified(cls, symbol: str, limit: int = 5) -> Tuple[List[NewsArticle], List[NewsArticle]]:
        """
        Returns (company_specific_articles, industry_articles) strictly segregated.
        """
        try:
            ticker = yf.Ticker(symbol.upper())
            name = ticker.info.get('longName', symbol) if ticker.info else symbol
            raw_news = ticker.news or []
            
            company_specific = []
            industry_items = []
            
            for item in raw_news:
                content = item.get('content', item) if isinstance(item, dict) else {}
                title = content.get('title') or item.get('title')
                if not title:
                    continue
                    
                provider = content.get('provider')
                if isinstance(provider, dict):
                    publisher = provider.get('displayName', 'Financial Media')
                else:
                    publisher = content.get('publisher') or item.get('publisher') or 'Financial Media'
                    
                canon_url = content.get('canonicalUrl')
                url = canon_url.get('url', '') if isinstance(canon_url, dict) else content.get('clickThroughUrl', {}).get('url', '')
                
                pub_date = content.get('pubDate') or content.get('displayTime')
                relative_time = cls._calculate_relative_time(pub_date)
                summary = content.get('summary', '') or content.get('description', '')
                
                is_company = cls.is_strictly_company_specific(symbol, name, title)
                
                article = NewsArticle(
                    symbol=symbol.upper(),
                    title=title.strip(),
                    publisher=publisher.strip(),
                    link=url,
                    published_at=pub_date or "Recent",
                    relative_time=relative_time,
                    summary=summary.strip(),
                    category="Company-Specific" if is_company else "Industry",
                    is_direct_catalyst=is_company
                )
                
                if is_company:
                    if len(company_specific) < limit:
                        company_specific.append(article)
                else:
                    # Filter out completely unrelated third-party tickers (like Geron or listicles)
                    if not any(noise in title.lower() for noise in ["how many", "which stocks", "best stocks", "top 10"]):
                        if len(industry_items) < 2:
                            industry_items.append(article)
                            
            return company_specific, industry_items
        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return [], []

    @classmethod
    def get_recent_news(cls, symbol: str, limit: int = 4) -> List[NewsArticle]:
        comp, ind = cls.get_company_news_classified(symbol, limit)
        return comp if comp else ind

    @classmethod
    def get_company_overview(cls, symbol: str) -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info or {}
            
            # Build core business dynamically from yfinance API data
            industry = info.get('industry', '')
            sector = info.get('sector', 'Technology')
            summary = info.get('longBusinessSummary', '')
            
            # Extract a concise business line from the API industry field
            core_biz = industry if industry else f"{sector} & Operations"
            
            return {
                "symbol": symbol.upper(),
                "name": info.get('longName', symbol.upper()),
                "sector": sector,
                "industry": industry or 'Technology',
                "core_business": core_biz,
                "business_summary": summary[:500] if summary else "",
                "market_cap": info.get('marketCap'),
                "market_cap_str": cls._format_market_cap(info.get('marketCap')),
                "pe_ratio": info.get('trailingPE'),
                "forward_pe": info.get('forwardPE'),
                "revenue": info.get('totalRevenue'),
                "profit_margin": info.get('profitMargins'),
                "employees": info.get('fullTimeEmployees'),
                "timestamp": datetime.now(timezone.utc).strftime("%H:%M UTC")
            }
        except Exception as e:
            logger.error(f"Error fetching overview for {symbol}: {e}")
            return {"symbol": symbol.upper(), "error": str(e)}
