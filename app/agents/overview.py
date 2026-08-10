from typing import Dict, Any, List
from app.market_data import MarketDataProvider, MarketQuote, NewsArticle
from langchain_core.messages import HumanMessage
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from app.market_data import get_current_date_str

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
    Dedicated institutional company overview engine for queries like 'Tell me about Google'.
    Strict evidence discipline: only outputs verified market data, verified company news,
    and ground-truth business segments. No synthetic hallucinated claims.
    """
    @classmethod
    async def get_overview(cls, symbol: str, llm) -> str:
        sym = symbol.upper()
        quote = MarketDataProvider.get_quote(sym)
        overview = MarketDataProvider.get_company_overview(sym)
        
        if not quote:
            return f"Could not retrieve verified market data for '{sym}'."
            
        comp_news, _ = MarketDataProvider.get_company_news_classified(sym, limit=2)
        
        brand_name = BRAND_MAP.get(quote.symbol, quote.name.split(',')[0].split('(')[0].strip() if quote.name else quote.symbol)
        emoji = BRAND_EMOJIS.get(quote.symbol, "🏢")
        
        sign = "+" if quote.percent_change >= 0 else ""
        pe_str = f"{quote.pe_ratio:.1f}x" if quote.pe_ratio else "N/A"
        date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
        now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
        curr_sym = "₹" if quote.currency == "INR" or quote.symbol.endswith((".NS", ".BO")) else ("€" if quote.currency == "EUR" else ("£" if quote.currency == "GBP" else "$"))
        
        # Build strict news section
        used_publishers = []
        if comp_news:
            news_lines = []
            for n in comp_news:
                news_lines.append(f"• {n.title} ({n.publisher} · {n.relative_time})")
                if n.publisher and n.publisher != "Financial Media" and n.publisher not in used_publishers:
                    used_publishers.append(n.publisher)
            news_block = "\n".join(news_lines)
        else:
            news_block = "• No breaking company-specific catalyst verified today."
            
        sources_list = [quote.source] + used_publishers
        sources_str = " · ".join(sources_list)
        
        sector = overview.get("sector", "N/A")
        business_line = overview.get("core_business", overview.get("industry", "N/A"))
        summary = overview.get("business_summary", "")

        prompt = (
            f"You are Atlas, an elite institutional financial intelligence partner.\n"
            f"CURRENT DATE: {date_str} ({now_utc}).\n\n"
            f"TASK: Generate a concise, evidence-disciplined company overview for {brand_name} ({quote.symbol}).\n\n"
            f"--- DATA LEDGER (Ground Truth Only) ---\n"
            f"Company: {brand_name} ({quote.symbol})\n"
            f"Price: {curr_sym}{quote.price:,.2f} ({sign}{quote.percent_change:.2f}% today)\n"
            f"Market Cap: {quote.market_cap_str}\n"
            f"Trailing P/E: {pe_str}\n"
            f"Sector: {sector}\n"
            f"Business/Industry: {business_line}\n"
            f"Summary Profile: {summary[:300]}\n"
            f"Verified Company-Specific Headlines:\n{news_block}\n"
            f"---------------------------------------\n\n"
            "EVIDENCE DISCIPLINE RULES:\n"
            "1. Output ONLY verified factual points backed by the data ledger.\n"
            "2. Under 'Business', list key segments/offerings concisely (e.g. Search · Advertising · YouTube · Cloud · AI).\n"
            "3. Under 'Key Takeaways', clearly separate FACT from INFERENCE. Tell the user *why it matters* (e.g. impact on fundamentals, valuation, or macro conditions). Provide 1-2 bullet points derived STRICTLY from current metrics or verified news.\n"
            "4. Under 'Risks', provide 1 bullet point on known structural or regulatory factors directly relevant to this business.\n"
            "5. NO generic fluff, NO unverified forward-looking speculation. Read like an objective analysis, not trade advice.\n"
            "6. If the provided data does not contain the answer, explicitly state 'I do not have verified data to determine this'. DO NOT guess or infer numbers.\n"
            "7. DO NOT act like a news reader. DO NOT list headlines. Instead, synthesize recent data into a highly informative 'Strategic Context' summary that explains the fundamental drivers and broader context to the user.\n"
            "8. Follow the EXACT layout below.\n\n"
            "EXACT OUTPUT TEMPLATE:\n\n"
            f"{emoji} {brand_name} ({quote.symbol})\n\n"
            "💰 Market\n"
            f"{curr_sym}{quote.price:,.2f} · {sign}{quote.percent_change:.2f}%\n"
            f"Market cap: {quote.market_cap_str}\n"
            f"P/E: {pe_str}\n\n"
            "🏢 Business\n"
            "[Key segments / product lines separated by middots]\n\n"
            "📌 Strategic Context\n"
            "[1-2 sentence deep, informative analysis of the underlying fundamental drivers affecting the company right now. Focus on the 'why' and the actionable intelligence.]\n\n"
            "💡 Key Takeaways\n"
            "[1-2 concise, evidence-grounded bullet points]\n\n"
            "⚠️ Risks\n"
            "[1 concise, evidence-grounded risk point]\n\n"
            "📚 Sources\n"
            f"{sources_str}\n"
            f"Retrieved: {date_str} · {now_utc}"
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
                f"{curr_sym}{quote.price:,.2f} · {sign}{quote.percent_change:.2f}%\n"
                f"Market cap: {quote.market_cap_str}\n"
                f"P/E: {pe_str}\n\n"
                f"🏢 Business\n"
                f"{business_line}\n\n"
                f"📰 Latest\n"
                f"{news_block}\n\n"
                f"📚 Sources\n"
                f"{sources_str}\n"
                f"Retrieved: {date_str} · {now_utc}"
            )
