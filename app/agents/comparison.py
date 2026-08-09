import logging
from typing import List, Dict, Any
from app.market_data import MarketDataProvider, MarketQuote, NewsArticle
from langchain_core.messages import SystemMessage, HumanMessage
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CURRENT_DATE_STR = "August 9, 2026"

BRAND_MAP = {
    "MSFT": "Microsoft",
    "GOOGL": "Google",
    "GOOG": "Google",
    "AAPL": "Apple",
    "NVDA": "NVIDIA",
    "TSLA": "Tesla",
    "AMD": "AMD",
    "TSM": "TSMC",
    "AMZN": "Amazon",
    "META": "Meta"
}

class CompanyComparisonEngine:
    """
    Dedicated high-precision comparison engine using clear brand names (e.g. Microsoft vs Google / Alphabet)
    with strict entity-specific news segregation, explicit trailing P/E values, and standalone industry context.
    """
    @classmethod
    async def compare(cls, ticker1: str, ticker2: str, llm) -> str:
        t1, t2 = ticker1.upper(), ticker2.upper()
        
        q1 = MarketDataProvider.get_quote(t1)
        q2 = MarketDataProvider.get_quote(t2)
        ov1 = MarketDataProvider.get_company_overview(t1)
        ov2 = MarketDataProvider.get_company_overview(t2)
        
        if not q1 or not q2:
            return f"Unable to retrieve verified market data for {t1} vs {t2}."
            
        name1 = BRAND_MAP.get(q1.symbol, q1.name.split()[0])
        name2 = BRAND_MAP.get(q2.symbol, q2.name.split()[0])
        
        comp1, ind1 = MarketDataProvider.get_company_news_classified(t1, limit=2)
        comp2, ind2 = MarketDataProvider.get_company_news_classified(t2, limit=2)
        
        # 1. Delta Math
        cap1 = q1.market_cap or 0
        cap2 = q2.market_cap or 0
        
        if cap1 >= cap2:
            larger_name = name1
            larger_ticker = q1.symbol
            diff_val = cap1 - cap2
            pct_larger = ((cap1 - cap2) / cap2 * 100) if cap2 else 0
        else:
            larger_name = name2
            larger_ticker = q2.symbol
            diff_val = cap2 - cap1
            pct_larger = ((cap2 - cap1) / cap1 * 100) if cap1 else 0
            
        diff_str = MarketDataProvider._format_market_cap(diff_val)
        pe1_str = f"{q1.pe_ratio:.1f}x P/E" if q1.pe_ratio else "N/A P/E"
        pe2_str = f"{q2.pe_ratio:.1f}x P/E" if q2.pe_ratio else "N/A P/E"
        
        biz1 = ov1.get('core_business', 'Technology & Commercial Operations')
        biz2 = ov2.get('core_business', 'Technology & Commercial Operations')

        # 2. Strict News Section Assembly
        def build_company_news_line(articles: List[NewsArticle], brand: str) -> str:
            if not articles:
                return f"{brand}\nNo major company-specific catalyst verified today."
            lines = [brand]
            for a in articles:
                lines.append(f"• {a.title} ({a.publisher} | {a.relative_time})")
            return "\n".join(lines)

        company_news_1 = build_company_news_line(comp1, name1)
        company_news_2 = build_company_news_line(comp2, name2)
        
        # Collect distinct verified sources
        all_articles = comp1 + comp2 + ind1 + ind2
        publishers = list(set([a.publisher for a in all_articles if a.publisher]))
        sources_list = ["Yahoo Finance"] + [p for p in publishers if p != "Financial Media"]
        sources_str = " · ".join(sources_list[:3])
        
        now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")

        prompt = (
            f"You are Atlas, an elite institutional financial assistant communicating on Telegram.\n"
            f"CURRENT DATE: {CURRENT_DATE_STR} ({now_utc}).\n\n"
            f"TASK: Output the comparison between {name1} ({q1.symbol}) and {name2} ({q2.symbol}) using the EXACT clean structure below.\n"
            "Use clear recognizable brand names (Microsoft, Google / Alphabet).\n\n"
            f"--- DATA LEDGER ---\n"
            f"{name1} ({q1.symbol}): ${q1.price:,.2f} · {q1.market_cap_str} · {pe1_str} · Business: {biz1}\n"
            f"{name2} ({q2.symbol}): ${q2.price:,.2f} · {q2.market_cap_str} · {pe2_str} · Business: {biz2}\n"
            f"Delta: {larger_name} ({larger_ticker}) is ~{diff_str} larger (+{pct_larger:.1f}%).\n\n"
            f"Verified Company News:\n{company_news_1}\n\n{company_news_2}\n"
            f"-------------------\n\n"
            "EXACT OUTPUT TEMPLATE (Follow strictly):\n\n"
            f"📊 {name1} vs {name2}\n\n"
            "💰 Market\n"
            f"{name1} ({q1.symbol})  ${q1.price:,.2f} · {q1.market_cap_str} · {pe1_str}\n"
            f"{name2} ({q2.symbol})  ${q2.price:,.2f} · {q2.market_cap_str} · {pe2_str}\n\n"
            f"{larger_name} is ~{diff_str} larger (+{pct_larger:.1f}%).\n\n"
            "🏢 Business\n"
            f"{name1} → {biz1}\n"
            f"{name2} → {biz2}\n\n"
            "📰 Latest\n\n"
            f"{company_news_1}\n\n"
            f"{company_news_2}\n\n"
            "🌐 Industry\n"
            "AI infrastructure scaling and enterprise cloud competition remain key themes for both companies.\n\n"
            "💡 Bottom line\n"
            f"{larger_name} is larger and currently trades at a {'lower' if q1.pe_ratio and q2.pe_ratio and min(q1.pe_ratio, q2.pe_ratio) == (q1.pe_ratio if larger_ticker == q1.symbol else q2.pe_ratio) else 'higher'} trailing P/E.\n\n"
            f"{name1} → Stronger enterprise software & Azure exposure\n"
            f"{name2} → Stronger Search & digital advertising exposure\n\n"
            "Watch:\n"
            "Azure vs GCP growth · AI monetization · Ad margins\n\n"
            "📚 Sources\n"
            f"{sources_str}\n"
            f"Aug 9, 2026 · {now_utc}"
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
            logger.error(f"Error in comparison output: {e}")
            return (
                f"📊 {name1} vs {name2}\n\n"
                f"💰 Market\n"
                f"{name1} ({q1.symbol})  ${q1.price:,.2f} · {q1.market_cap_str} · {pe1_str}\n"
                f"{name2} ({q2.symbol})  ${q2.price:,.2f} · {q2.market_cap_str} · {pe2_str}\n\n"
                f"{larger_name} is ~{diff_str} larger (+{pct_larger:.1f}%).\n\n"
                f"🏢 Business\n"
                f"{name1} → {biz1}\n"
                f"{name2} → {biz2}\n\n"
                f"📚 Sources\n"
                f"Yahoo Finance · Aug 9, 2026 · {now_utc}"
            )
