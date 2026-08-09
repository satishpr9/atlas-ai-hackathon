from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import yfinance as yf
import logging

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
    category: str = "Company-Specific" # "Company-Specific", "Industry", "Macro"
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
    def classify_catalyst(cls, symbol: str, name: str, title: str, summary: str) -> str:
        """
        Classifies whether an article is Company-Specific, Industry Context, or Macro Market news.
        """
        title_lower = title.lower()
        summary_lower = summary.lower()
        sym_lower = symbol.lower()
        
        name_parts = [p.lower() for p in name.split() if len(p) > 2 and p.lower() not in ["inc", "corp", "corporation", "ltd", "class", "com"]]
        
        # Check if entity is explicitly named
        explicit_match = (sym_lower in title_lower) or any(p in title_lower for p in name_parts)
        
        if explicit_match:
            return "Company-Specific"
            
        # Check if it's general market / economy
        macro_keywords = ["fed", "rate cut", "inflation", "cpi", "warsh", "powell", "treasury", "jobs report", "gdp", "s&p 500", "nasdaq rally", "stock rally"]
        if any(k in title_lower for k in macro_keywords):
            return "Macro"
            
        # Otherwise it's industry / competitor news
        return "Industry"

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
    def get_recent_news(cls, symbol: str, limit: int = 4) -> List[NewsArticle]:
        try:
            ticker = yf.Ticker(symbol.upper())
            name = ticker.info.get('longName', symbol) if ticker.info else symbol
            raw_news = ticker.news or []
            articles = []
            
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
                
                category = cls.classify_catalyst(symbol, name, title, summary)
                is_direct = (category == "Company-Specific")
                
                articles.append(NewsArticle(
                    symbol=symbol.upper(),
                    title=title.strip(),
                    publisher=publisher.strip(),
                    link=url,
                    published_at=pub_date or "Recent",
                    relative_time=relative_time,
                    summary=summary.strip(),
                    category=category,
                    is_direct_catalyst=is_direct
                ))
                
                if len(articles) >= limit:
                    break
                    
            return articles
        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return []

    @classmethod
    def get_company_overview(cls, symbol: str) -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info or {}
            
            core_business_map = {
                "MSFT": "Azure Cloud Infrastructure, Office 365 / Copilot, Windows, Enterprise Software & AI",
                "GOOGL": "Google Search & Advertising, YouTube Ads, Google Cloud Platform (GCP), DeepMind AI",
                "GOOG": "Google Search & Advertising, YouTube Ads, Google Cloud Platform (GCP), DeepMind AI",
                "AAPL": "iPhone & Hardware Ecosystem, Apple Services (App Store/iCloud), Apple Silicon, AI Intelligence",
                "NVDA": "Data Center AI Accelerators (Blackwell/Hopper GPUs), CUDA Software Platform, Networking",
                "TSLA": "Electric Vehicles (Model 3/Y/Cyber), Full Self-Driving (FSD) Software, Energy Storage & Supercharging",
                "AMD": "EPYC Server Processors, Instinct AI Accelerators (MI300), Ryzen CPUs, Radeon GPUs",
                "TSM": "Leading-edge Semiconductor Foundry (3nm/2nm Wafers), Advanced Packaging (CoWoS) for AI"
            }
            
            core_biz = core_business_map.get(symbol.upper(), info.get('industry', 'Technology & Commercial Operations'))
            
            return {
                "symbol": symbol.upper(),
                "name": info.get('longName', symbol.upper()),
                "sector": info.get('sector', 'Technology'),
                "industry": info.get('industry', 'Software/Hardware'),
                "core_business": core_biz,
                "market_cap": info.get('marketCap'),
                "market_cap_str": cls._format_market_cap(info.get('marketCap')),
                "pe_ratio": info.get('trailingPE'),
                "forward_pe": info.get('forwardPE'),
                "timestamp": datetime.now(timezone.utc).strftime("%H:%M UTC")
            }
        except Exception as e:
            logger.error(f"Error fetching overview for {symbol}: {e}")
            return {"symbol": symbol.upper(), "error": str(e)}
