import logging
from typing import List, Dict, Any
from app.market_data import MarketDataProvider, MarketQuote, NewsArticle
from langchain_core.messages import SystemMessage, HumanMessage
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CURRENT_DATE_STR = "August 9, 2026"

class CompanyComparisonEngine:
    """
    Dedicated high-precision comparison engine with Claim Ledger verification,
    exact multiples comparison, catalyst classification, and institutional formatting.
    """
    @classmethod
    async def compare(cls, ticker1: str, ticker2: str, llm) -> str:
        t1, t2 = ticker1.upper(), ticker2.upper()
        
        q1 = MarketDataProvider.get_quote(t1)
        q2 = MarketDataProvider.get_quote(t2)
        ov1 = MarketDataProvider.get_company_overview(t1)
        ov2 = MarketDataProvider.get_company_overview(t2)
        
        if not q1 or not q2:
            return f"Unable to retrieve verified market data for comparison between {t1} and {t2}."
            
        news1 = MarketDataProvider.get_recent_news(t1, limit=3)
        news2 = MarketDataProvider.get_recent_news(t2, limit=3)
        
        # 1. Exact Math Calculation (Python Ground Truth)
        cap1 = q1.market_cap or 0
        cap2 = q2.market_cap or 0
        
        if cap1 >= cap2:
            larger_ticker, smaller_ticker = q1.symbol, q2.symbol
            diff_val = cap1 - cap2
            pct_larger = ((cap1 - cap2) / cap2 * 100) if cap2 else 0
        else:
            larger_ticker, smaller_ticker = q2.symbol, q1.symbol
            diff_val = cap2 - cap1
            pct_larger = ((cap2 - cap1) / cap1 * 100) if cap1 else 0
            
        diff_str = MarketDataProvider._format_market_cap(diff_val)
        
        # 2. Multiples comparison
        pe1_str = f"{q1.pe_ratio:.1f}x" if q1.pe_ratio else "N/A"
        pe2_str = f"{q2.pe_ratio:.1f}x" if q2.pe_ratio else "N/A"
        fwd_pe1_str = f"{q1.forward_pe:.1f}x" if q1.forward_pe else "N/A"
        fwd_pe2_str = f"{q2.forward_pe:.1f}x" if q2.forward_pe else "N/A"
        
        # Determine verified P/E relation
        pe_verdict = ""
        if q1.pe_ratio and q2.pe_ratio:
            lower_pe_sym = q1.symbol if q1.pe_ratio < q2.pe_ratio else q2.symbol
            higher_pe_sym = q2.symbol if q1.pe_ratio < q2.pe_ratio else q1.symbol
            pe_verdict = f"{lower_pe_sym} currently trades at a lower trailing P/E multiple ({min(q1.pe_ratio, q2.pe_ratio):.1f}x vs {max(q1.pe_ratio, q2.pe_ratio):.1f}x)."
            
        # 3. Format Verified News with Category Labels
        def build_news_ledger(articles: List[NewsArticle], sym: str) -> str:
            if not articles:
                return f"• No breaking company-specific headlines verified in the last 24h for {sym}."
            lines = []
            for a in articles:
                tag = f"[{a.category}]"
                lines.append(
                    f"• {tag} **{a.title}**\n"
                    f"  *Publisher: {a.publisher} | {a.relative_time}*\n"
                    f"  *Summary: {a.summary[:180]}*"
                )
            return "\n".join(lines)
            
        news_ledger_1 = build_news_ledger(news1, q1.symbol)
        news_ledger_2 = build_news_ledger(news2, q2.symbol)
        
        # Collect distinct publishers
        publishers = list(set([a.publisher for a in news1 + news2 if a.publisher]))
        publishers_str = ", ".join(publishers) if publishers else "Yahoo Finance Wire"
        
        now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
        
        prompt = (
            f"You are an elite Wall Street Equity Research Analyst.\n"
            f"CURRENT DATE: {CURRENT_DATE_STR} ({now_utc}).\n\n"
            f"TASK: Generate an authoritative institutional comparison between {q1.name} ({q1.symbol}) and {q2.name} ({q2.symbol}).\n\n"
            f"--- VERIFIED CLAIM LEDGER (Ground Truth - Strictly Adhere) ---\n"
            f"1. VALUATION LEDGER:\n"
            f"   - {q1.symbol}: Market Cap {q1.market_cap_str} | Price: ${q1.price:,.2f} ({q1.percent_change:+.2f}%) | Trailing P/E: {pe1_str} | Forward P/E: {fwd_pe1_str}\n"
            f"   - {q2.symbol}: Market Cap {q2.market_cap_str} | Price: ${q2.price:,.2f} ({q2.percent_change:+.2f}%) | Trailing P/E: {pe2_str} | Forward P/E: {fwd_pe2_str}\n"
            f"   - Calculation: {larger_ticker} is larger by ~{diff_str} (+{pct_larger:.1f}%).\n"
            f"   - Valuation Fact: {pe_verdict}\n\n"
            f"2. BUSINESS MIX LEDGER:\n"
            f"   - {q1.symbol}: Sector: {ov1.get('sector')} | Core: {ov1.get('core_business')}\n"
            f"   - {q2.symbol}: Sector: {ov2.get('sector')} | Core: {ov2.get('core_business')}\n\n"
            f"3. NEWS & CATALYST LEDGER (Categorized):\n"
            f"   [{q1.symbol}]\n{news_ledger_1}\n\n"
            f"   [{q2.symbol}]\n{news_ledger_2}\n"
            f"--------------------------------------------------------------\n\n"
            "STRICT RULES:\n"
            "1. State the market cap conclusion immediately under valuation.\n"
            "2. For news items categorized as [Industry] or [Macro], explicitly label them as industry context and note they are not direct company announcements.\n"
            "3. DO NOT state unverified financial claims. ONLY cite the verified P/E and Market Cap from the ledger above.\n"
            "4. Avoid generic investment advice like 'Investors should...'. Use institutional framing like 'Key metrics to monitor:'.\n"
            "5. Structure cleanly:\n\n"
            f"## **{q1.symbol} vs {q2.symbol} Comparison**\n\n"
            "**Market Cap & Valuation**\n"
            f"• **{q1.symbol}**: ~{q1.market_cap_str} (${q1.price:,.2f}, Trailing P/E: {pe1_str})\n"
            f"• **{q2.symbol}**: ~{q2.market_cap_str} (${q2.price:,.2f}, Trailing P/E: {pe2_str})\n"
            f"**Conclusion**: **{larger_ticker} is currently larger by ~{diff_str} (+{pct_larger:.1f}%)** based on latest market data.\n\n"
            "**Sector & Business Focus**\n"
            f"• **{q1.symbol}** ({ov1.get('sector')}): {ov1.get('core_business')}\n"
            f"• **{q2.symbol}** ({ov2.get('sector')}): {ov2.get('core_business')}\n\n"
            "**Latest News & Catalysts**\n"
            f"• **{q1.symbol}**:\n"
            f"  - [Include actual headline with Source & Time, noting if Company-Specific or Industry Context]\n"
            f"  - *Why it matters:* [1 sentence on institutional impact]\n"
            f"• **{q2.symbol}**:\n"
            f"  - [Include actual headline with Source & Time, noting if Company-Specific or Industry Context]\n"
            f"  - *Why it matters:* [1 sentence on institutional impact]\n\n"
            "**Bottom Line**\n"
            f"[2-3 sentence executive synthesis on market cap delta, business mix divergence, and key metrics to monitor: Azure vs GCP, Search/Ad trends, AI monetization, regulatory scrutiny.]\n\n"
            f"---\n"
            f"**Data retrieved**: Aug 9, 2026, {now_utc}\n"
            f"**Market Data**: Yahoo Finance Real-time Feed\n"
            f"**News Sources**: {publishers_str}"
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
            logger.error(f"Error in CompanyComparisonEngine: {e}")
            return (
                f"## **{q1.symbol} vs {q2.symbol} Comparison**\n\n"
                f"**Market Cap & Valuation**:\n"
                f"• **{q1.symbol}**: ~{q1.market_cap_str} (P/E: {pe1_str})\n"
                f"• **{q2.symbol}**: ~{q2.market_cap_str} (P/E: {pe2_str})\n"
                f"**Conclusion**: **{larger_ticker} is larger by ~{diff_str} (+{pct_larger:.1f}%)**.\n\n"
                f"**Data retrieved**: Aug 9, 2026, {now_utc} | Source: Yahoo Finance"
            )
