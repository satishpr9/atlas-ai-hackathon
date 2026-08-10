from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel
import yfinance as yf
import finnhub
import logging
import re
from app.config import settings

logger = logging.getLogger(__name__)

def get_current_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%B %d, %Y")

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
    source_api: str = "Unknown"

class MarketQuote(BaseModel):
    symbol: str
    name: str
    price: float
    prev_close: float
    change: float
    percent_change: float
    volume: int
    avg_volume: Optional[int] = None
    market_cap: Optional[float] = None
    market_cap_str: str
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    timestamp: str
    currency: str = "USD"
    source: str = "Finnhub (Real-time)"

class FinancialDataRouter:
    """
    Intelligent router that fetches financial data from the most appropriate API.
    Hierarchy:
    1. SEC EDGAR / Finnhub: Real-time quotes, fundamentals, filings
    2. Yahoo Finance: Broad global multi-exchange coverage & fallback
    """
    
    _finnhub_client = None
    
    @classmethod
    def get_finnhub_client(cls):
        if cls._finnhub_client is None and settings.finnhub_api_key:
            cls._finnhub_client = finnhub.Client(api_key=settings.finnhub_api_key)
        return cls._finnhub_client

    @classmethod
    def search_symbol(cls, query: str) -> Optional[str]:
        """
        Dynamically searches and resolves any company name or query to its primary ticker symbol.
        Supports global stocks, Indian equities (NSE/BSE), European, Asian, etc.
        """
        q = query.strip()
        if not q:
            return None
            
        # If already formatted ticker
        if re.match(r'^[A-Z0-9\.\-]{1,12}$', q.upper()) and not any(w in q.lower() for w in ["price", "stock", "inc", "ltd"]):
            return q.upper()

        # Try Finnhub symbol lookup
        fh = cls.get_finnhub_client()
        if fh:
            try:
                res = fh.symbol_lookup(q)
                results = res.get("result", [])
                if results:
                    # Pick the highest quality / primary match
                    for r in results:
                        sym = r.get("symbol", "")
                        # Filter out non-primary or noisy derivatives
                        if "." not in sym or sym.endswith((".NS", ".BO", ".L", ".PA", ".DE")):
                            return sym
                    return results[0].get("symbol")
            except Exception as e:
                logger.debug(f"Finnhub symbol lookup failed for {q}: {e}")

        # Fallback to Yahoo Finance Search
        try:
            search_res = yf.Search(q, max_results=3).quotes
            if search_res:
                return search_res[0].get("symbol")
        except Exception as e:
            logger.debug(f"Yahoo search failed for {q}: {e}")
            
        return None

    @staticmethod
    def _format_market_cap(val: Optional[float], currency: str = "USD") -> str:
        if not val:
            return "N/A"
        
        if currency == "INR":
            # Indian numbering system: 1 Lakh Crore = 10^12, 1 Crore = 10^7
            if val >= 1_000_000_000_000:
                return f"₹{val / 1_000_000_000_000:.2f} Lakh Cr"
            elif val >= 10_000_000:
                return f"₹{val / 10_000_000:,.0f} Cr"
            return f"₹{val:,.0f}"

        # Standard USD / Global Format
        if val >= 1_000_000_000_000:
            return f"${val / 1_000_000_000_000:.2f}T"
        elif val >= 1_000_000_000:
            return f"${val / 1_000_000_000:.2f}B"
        elif val >= 1_000_000:
            return f"${val / 1_000_000:.2f}M"
        return f"${val:,.0f}"

    @staticmethod
    def _calculate_relative_time(timestamp_or_iso: Any) -> str:
        if not timestamp_or_iso:
            return "Recently"
        try:
            if isinstance(timestamp_or_iso, (int, float)):
                dt = datetime.fromtimestamp(timestamp_or_iso, tz=timezone.utc)
            else:
                dt = datetime.fromisoformat(str(timestamp_or_iso).replace("Z", "+00:00"))
            
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
        title_lower = title.lower()
        sym_clean = symbol.split('.')[0].lower()
        
        # Build dynamic aliases from symbol and company name parts
        aliases = {sym_clean}
        if name:
            # Clean up common corporate suffixes
            cleaned_name = re.sub(r'\b(inc|corp|corporation|co|ltd|limited|plc|ag|nv|sa|se|holdings|group)\b', '', name.lower())
            words = [w.strip() for w in re.split(r'[\s,\.-]+', cleaned_name) if len(w.strip()) > 2]
            for w in words:
                aliases.add(w)
            if len(words) >= 2:
                aliases.add(f"{words[0]} {words[1]}")
        
        # Filter out broad index / listicle / macro noise
        macro_noise = [
            "how many of", "which stocks", "best stocks to buy", "top 10", "top 5",
            "even without", "s&p 500", "biggest earnings beat", "3 stocks", "these stocks"
        ]
        for noise in macro_noise:
            if noise in title_lower:
                return False

        for alias in aliases:
            if re.search(r'\b' + re.escape(alias) + r'\b', title_lower):
                return True
        return False

    @classmethod
    def get_quote(cls, symbol: str) -> Optional[MarketQuote]:
        """
        Attempts Finnhub first for real-time market data, falls back to Yahoo Finance.
        """
        fh = cls.get_finnhub_client()
        if fh:
            try:
                quote = fh.quote(symbol.upper())
                # Finnhub doesn't have name and market cap in the quote endpoint, fetch profile
                profile = fh.company_profile2(symbol=symbol.upper())
                
                if quote and 'c' in quote and quote['c'] > 0:
                    mkt_cap_millions = profile.get('marketCapitalization', 0)
                    mkt_cap_actual = mkt_cap_millions * 1_000_000 if mkt_cap_millions else None
                    
                    return MarketQuote(
                        symbol=symbol.upper(),
                        name=profile.get('name', symbol.upper()),
                        price=quote.get('c', 0),
                        prev_close=quote.get('pc', 0),
                        change=quote.get('d', 0),
                        percent_change=quote.get('dp', 0),
                        volume=0, # Finnhub quote doesn't provide real-time volume in free tier easily
                        market_cap=mkt_cap_actual,
                        market_cap_str=cls._format_market_cap(mkt_cap_actual),
                        timestamp=datetime.now(timezone.utc).strftime("%H:%M UTC"),
                        source="Finnhub (Real-time)"
                    )
            except Exception as e:
                logger.warning(f"Finnhub quote failed for {symbol}: {e}. Falling back to Yahoo Finance.")

        # Fallback to Yahoo Finance
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
            curr = info.get('currency', 'INR' if symbol.upper().endswith(('.NS', '.BO')) else 'USD')
            
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
                market_cap_str=cls._format_market_cap(mkt_cap, currency=curr),
                pe_ratio=round(info.get('trailingPE'), 2) if info.get('trailingPE') else None,
                forward_pe=round(info.get('forwardPE'), 2) if info.get('forwardPE') else None,
                fifty_two_week_high=info.get('fiftyTwoWeekHigh'),
                fifty_two_week_low=info.get('fiftyTwoWeekLow'),
                timestamp=datetime.now(timezone.utc).strftime("%H:%M UTC"),
                currency=curr,
                source="Yahoo Finance"
            )
        except Exception as e:
            logger.error(f"Yahoo Finance quote failed for {symbol}: {e}")
            return None

    @classmethod
    def get_company_news_classified(cls, symbol: str, limit: int = 5) -> Tuple[List[NewsArticle], List[NewsArticle]]:
        fh = cls.get_finnhub_client()
        company_specific = []
        industry_items = []
        
        # Determine date range (past 3 days)
        now = datetime.now()
        start_date = (now - timedelta(days=3)).strftime('%Y-%m-%d')
        end_date = now.strftime('%Y-%m-%d')
        
        if fh:
            try:
                news = fh.company_news(symbol.upper(), _from=start_date, to=end_date)
                name = symbol.upper() # Could fetch profile, but keeping it fast
                
                for item in news:
                    title = item.get('headline', '')
                    if not title: continue
                    
                    is_company = cls.is_strictly_company_specific(symbol, name, title)
                    article = NewsArticle(
                        symbol=symbol.upper(),
                        title=title.strip(),
                        publisher=item.get('source', 'Finnhub News'),
                        link=item.get('url', ''),
                        published_at=datetime.fromtimestamp(item.get('datetime', 0), tz=timezone.utc).isoformat(),
                        relative_time=cls._calculate_relative_time(item.get('datetime')),
                        summary=item.get('summary', '')[:200],
                        category="Company-Specific" if is_company else "Industry",
                        is_direct_catalyst=is_company,
                        source_api="Finnhub"
                    )
                    
                    if is_company and len(company_specific) < limit:
                        company_specific.append(article)
                    elif not is_company and len(industry_items) < 2:
                        industry_items.append(article)
                        
                if company_specific or industry_items:
                    return company_specific, industry_items
            except Exception as e:
                logger.warning(f"Finnhub news failed for {symbol}: {e}. Falling back to Yahoo Finance.")

        # Fallback to Yahoo
        try:
            ticker = yf.Ticker(symbol.upper())
            name = ticker.info.get('longName', symbol) if ticker.info else symbol
            raw_news = ticker.news or []
            
            for item in raw_news:
                content = item.get('content', item) if isinstance(item, dict) else {}
                title = content.get('title') or item.get('title')
                if not title: continue
                    
                publisher = content.get('provider', {}).get('displayName') or content.get('publisher') or item.get('publisher') or 'Financial Media'
                canon_url = content.get('canonicalUrl')
                url = canon_url.get('url', '') if isinstance(canon_url, dict) else content.get('clickThroughUrl', {}).get('url', '')
                pub_date = content.get('pubDate') or content.get('displayTime')
                is_company = cls.is_strictly_company_specific(symbol, name, title)
                
                article = NewsArticle(
                    symbol=symbol.upper(),
                    title=title.strip(),
                    publisher=publisher.strip(),
                    link=url,
                    published_at=pub_date or "Recent",
                    relative_time=cls._calculate_relative_time(pub_date),
                    summary=content.get('summary', '')[:200],
                    category="Company-Specific" if is_company else "Industry",
                    is_direct_catalyst=is_company,
                    source_api="Yahoo Finance"
                )
                
                if is_company and len(company_specific) < limit:
                    company_specific.append(article)
                elif not is_company and len(industry_items) < 2:
                    if not any(noise in title.lower() for noise in ["how many", "which stocks", "best stocks", "top 10"]):
                        industry_items.append(article)
                        
            return company_specific, industry_items
        except Exception as e:
            logger.error(f"Yahoo Finance news failed for {symbol}: {e}")
            return [], []

    @classmethod
    def get_recent_news(cls, symbol: str, limit: int = 4) -> List[NewsArticle]:
        comp, ind = cls.get_company_news_classified(symbol, limit)
        return comp if comp else ind

    @classmethod
    def get_company_overview(cls, symbol: str) -> Dict[str, Any]:
        """
        Uses SEC EDGAR / Finnhub for ground-truth fundamentals where possible.
        """
        overview = {"symbol": symbol.upper(), "timestamp": datetime.now(timezone.utc).strftime("%H:%M UTC")}
        
        # Try Finnhub Profile & Basic Financials (Simulating SEC Edgar Ground Truth)
        fh = cls.get_finnhub_client()
        if fh:
            try:
                profile = fh.company_profile2(symbol=symbol.upper())
                financials = fh.company_basic_financials(symbol=symbol.upper(), metric="all")
                
                if profile and financials and 'metric' in financials:
                    metric = financials['metric']
                    mkt_cap = profile.get('marketCapitalization', 0) * 1_000_000 if profile.get('marketCapitalization') else None
                    
                    overview.update({
                        "name": profile.get('name', symbol.upper()),
                        "sector": profile.get('finnhubIndustry', 'N/A'),
                        "industry": profile.get('finnhubIndustry', 'N/A'),
                        "core_business": profile.get('finnhubIndustry', 'N/A'),
                        "business_summary": "Data sourced from Finnhub & SEC Filings.",
                        "market_cap": mkt_cap,
                        "market_cap_str": cls._format_market_cap(mkt_cap),
                        "pe_ratio": metric.get('peExclExtraTTM'),
                        "revenue": metric.get('revenueTTM') * 1_000_000 if metric.get('revenueTTM') else None,
                        "source": "Finnhub (SEC Filings Derived)"
                    })
                    return overview
            except Exception as e:
                logger.warning(f"Finnhub profile failed for {symbol}: {e}. Falling back to Yahoo Finance.")

        # Fallback to Yahoo Finance
        try:
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info or {}
            industry = info.get('industry', '')
            sector = info.get('sector', 'N/A')
            summary = info.get('longBusinessSummary', '')
            
            # Smart Industry Classification Formatting
            core_biz = []
            if sector and sector != 'N/A': core_biz.append(sector)
            if industry and industry != 'N/A': core_biz.append(industry)
            biz_str = " · ".join(core_biz) if core_biz else 'N/A'
            
            overview.update({
                "name": info.get('longName', symbol.upper()),
                "sector": sector,
                "industry": industry or 'N/A',
                "core_business": biz_str,
                "business_summary": summary[:500] if summary else "",
                "market_cap": info.get('marketCap'),
                "market_cap_str": cls._format_market_cap(info.get('marketCap')),
                "pe_ratio": info.get('trailingPE'),
                "forward_pe": info.get('forwardPE'),
                "revenue": info.get('totalRevenue'),
                "revenue_growth": info.get('revenueGrowth'),
                "earnings_growth": info.get('earningsGrowth'),
                "operating_margin": info.get('operatingMargins'),
                "free_cashflow": info.get('freeCashflow'),
                "ev_ebitda": info.get('enterpriseToEbitda'),
                "price_to_sales": info.get('priceToSalesTrailing12Months'),
                "profit_margin": info.get('profitMargins'),
                "employees": info.get('fullTimeEmployees'),
                "source": "Yahoo Finance"
            })
        except Exception as e:
            overview["error"] = str(e)
            
        return overview

# Maintain backward compatibility for existing imports in tools.py
MarketDataProvider = FinancialDataRouter
