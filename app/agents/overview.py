from typing import Dict, Any, List
from app.market_data import MarketDataProvider, MarketQuote, NewsArticle
from langchain_core.messages import HumanMessage
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CURRENT_DATE_STR = "August 9, 2026"

BRAND_EMOJIS = {
    "AAPL": "🍎",
    "MSFT": "💻",
    "GOOGL": "🌐",
    "GOOG": "🌐",
    "NVDA": "⚡",
    "TSLA": "🚗",
    "RIVN": "🚙",
    "LCID": "🏎️",
    "AMZN": "📦",
    "META": "👥",
    "AMD": "🔷",
    "TSM": "🏭",
    "NFLX": "🎬"
}

BRAND_MAP = {
    "MSFT": "Microsoft",
    "GOOGL": "Google",
    "GOOG": "Google",
    "AAPL": "Apple",
    "NVDA": "NVIDIA",
    "TSLA": "Tesla",
    "RIVN": "Rivian",
    "LCID": "Lucid",
    "NIO": "NIO",
    "F": "Ford",
    "GM": "General Motors",
    "AMD": "AMD",
    "TSM": "TSMC",
    "AMZN": "Amazon",
    "META": "Meta",
    "NFLX": "Netflix",
    "ORCL": "Oracle",
    "CRM": "Salesforce",
    "UBER": "Uber",
    "COIN": "Coinbase"
}

class CompanyOverviewEngine:
    """
    Dedicated institutional company overview engine for queries like 'Tell me about Apple'.
    Separates verified market facts, official sector classification, structural key themes,
    and verified breaking headlines without hallucinated future claims.
    """
    @classmethod
    async def get_overview(cls, symbol: str, llm) -> str:
        sym = symbol.upper()
        quote = MarketDataProvider.get_quote(sym)
        overview = MarketDataProvider.get_company_overview(sym)
        
        if not quote:
            return f"Could not retrieve verified market data for '{sym}'."
            
        comp_news, ind_news = MarketDataProvider.get_company_news_classified(sym, limit=2)
        
        brand_name = BRAND_MAP.get(quote.symbol, quote.name.split()[0])
        emoji = BRAND_EMOJIS.get(quote.symbol, "🏢")
        
        sign = "+" if quote.percent_change >= 0 else ""
        vol_str = f"{quote.volume / 1_000_000:.1f}M" if quote.volume >= 1_000_000 else f"{quote.volume:,}"
        pe_str = f"{quote.pe_ratio:.1f}x" if quote.pe_ratio else "N/A"
        now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
        
        # Build strict news section
        if comp_news:
            news_lines = []
            for n in comp_news:
                news_lines.append(f"• {n.title} ({n.publisher} · {n.relative_time})")
            news_block = "\n".join(news_lines)
        else:
            news_block = "• No major breaking company-specific catalyst verified today."
            
        all_articles = comp_news + ind_news
        publishers = list(set([n.publisher for n in all_articles if n.publisher]))
        sources_list = ["Yahoo Finance"] + [p for p in publishers if p != "Financial Media"]
        sources_str = " · ".join(sources_list[:3])
        
        sector = overview.get("sector", "Technology")
        business_line = overview.get("core_business", "Hardware · Software · Digital Operations")

        prompt = (
            f"You are Atlas, an elite institutional financial intelligence partner.\n"
            f"CURRENT DATE: {CURRENT_DATE_STR} ({now_utc}).\n\n"
            f"TASK: Generate a high-signal institutional company overview for {brand_name} ({quote.symbol}).\n\n"
            f"--- DATA LEDGER (Ground Truth) ---\n"
            f"Company: {brand_name} ({quote.symbol})\n"
            f"Price: ${quote.price:,.2f} ({sign}{quote.percent_change:.2f}% today)\n"
            f"Market Cap: {quote.market_cap_str}\n"
            f"Trailing P/E: {pe_str}\n"
            f"Volume: {vol_str}\n"
            f"Sector: {sector}\n"
            f"Business: {business_line}\n"
            f"Verified Recent Headlines:\n{news_block}\n"
            f"----------------------------------\n\n"
            "RULES:\n"
            "1. Do NOT make unverified forward-looking product claims (e.g. 'upcoming product launches with augmented reality').\n"
            "2. State key structural business themes (e.g. Services monetization, AI ecosystem integration, supply chain/regional demand) as established profile facts.\n"
            "3. Follow the EXACT clean Telegram layout below.\n\n"
            "EXACT OUTPUT TEMPLATE:\n\n"
            f"{emoji} {brand_name} ({quote.symbol})\n\n"
            "💰 Market\n"
            f"${quote.price:,.2f} · {sign}{quote.percent_change:.2f}%\n"
            f"Market cap: {quote.market_cap_str}\n"
            f"P/E: {pe_str}\n"
            f"Volume: {vol_str}\n\n"
            "🏢 Business\n"
            f"{sector}\n"
            f"{business_line}\n\n"
            "📌 Key Themes\n"
            f"• [1 sentence on core revenue engine / ecosystem strength]\n"
            f"• [1 sentence on AI / technology strategy]\n"
            f"• [1 sentence on regional demand or key operational factors to monitor]\n\n"
            "📰 Latest\n"
            f"{news_block}\n\n"
            "💡 Bottom line\n"
            f"[2 sentence institutional summary on business moat, margin drivers, and key valuation metrics to watch.]\n\n"
            "📚 Sources\n"
            f"{sources_str}\n"
            f"Retrieved: Aug 9, 2026 · {now_utc}"
        )
        
        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content
            if isinstance(content, list):
                text_parts = []
                for p in content:
                    if isinstance(p, dict) and "text" in p:
                        text_parts.append(p["text"])
                    elif isinstance(p, str):
                        text_parts.append(p)
                return "".join(text_parts)
            return str(content)
        except Exception as e:
            logger.error(f"Error in CompanyOverviewEngine: {e}")
            return (
                f"{emoji} {brand_name} ({quote.symbol})\n\n"
                f"💰 Market\n"
                f"${quote.price:,.2f} · {sign}{quote.percent_change:.2f}%\n"
                f"Market cap: {quote.market_cap_str}\n"
                f"P/E: {pe_str}\n"
                f"Volume: {vol_str}\n\n"
                f"🏢 Business\n"
                f"{sector}\n"
                f"{business_line}\n\n"
                f"📚 Sources\n"
                f"Yahoo Finance · Aug 9, 2026 · {now_utc}"
            )
