import logging
from typing import List, Dict, Any
from app.market_data import MarketDataProvider, MarketQuote, NewsArticle
from langchain_core.messages import SystemMessage, HumanMessage
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CURRENT_DATE_STR = "August 9, 2026"

class CompanyComparisonEngine:
    """
    Ultra-clean, icon-driven institutional comparison engine designed natively for Telegram.
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
            
        news1 = MarketDataProvider.get_recent_news(t1, limit=2)
        news2 = MarketDataProvider.get_recent_news(t2, limit=2)
        
        # 1. Delta Math
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
        pe1_str = f"{q1.pe_ratio:.1f}x" if q1.pe_ratio else "N/A"
        pe2_str = f"{q2.pe_ratio:.1f}x" if q2.pe_ratio else "N/A"
        
        # 2. Simplified Business Labels
        def clean_biz(full_text: str) -> str:
            # e.g. "Azure Cloud Infrastructure, Office 365, Windows" -> "Cloud · Enterprise Software · AI"
            if "Azure" in full_text: return "Cloud · Enterprise Software · Office · AI"
            if "Search" in full_text: return "Search & Ads · YouTube · Cloud · AI"
            if "Blackwell" in full_text: return "AI Accelerators · GPUs · CUDA Platform"
            if "iPhone" in full_text: return "Hardware Ecosystem · Services · Apple Silicon"
            if "Electric" in full_text: return "EVs · Full Self-Driving · Energy Storage"
            if "EPYC" in full_text: return "Server Processors · AI Instinct Chips · GPUs"
            if "Foundry" in full_text: return "Advanced Semiconductor Foundry · CoWoS Packaging"
            return full_text[:40]

        biz1 = clean_biz(ov1.get('core_business', ''))
        biz2 = clean_biz(ov2.get('core_business', ''))

        # 3. News Headlines
        def format_news_snippet(articles: List[NewsArticle], sym: str) -> str:
            if not articles:
                return f"{sym} → No major breaking catalysts in the last 24h"
            lines = []
            for a in articles:
                tag = "Industry: " if a.category == "Industry" else ("Macro: " if a.category == "Macro" else "")
                lines.append(f"{sym} → {tag}{a.title} ({a.publisher} · {a.relative_time})")
            return "\n".join(lines)

        news_text_1 = format_news_snippet(news1, q1.symbol)
        news_text_2 = format_news_snippet(news2, q2.symbol)
        
        publishers = list(set([a.publisher for a in news1 + news2 if a.publisher]))
        all_sources = ["Yahoo Finance"] + publishers
        sources_str = " · ".join(all_sources[:4])
        
        now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")

        prompt = (
            f"You are Atlas, an elite institutional financial assistant communicating via Telegram.\n"
            f"CURRENT DATE: {CURRENT_DATE_STR} ({now_utc}).\n\n"
            "TASK: Generate the comparison using the EXACT ultra-clean, icon-driven Telegram layout below.\n"
            "DO NOT use heavy markdown headers like '##' or excessive bolding. Keep it fast to scan.\n\n"
            f"--- VERIFIED DATA ---\n"
            f"{q1.symbol}: ${q1.price:,.2f} · {q1.market_cap_str} ({pe1_str} P/E) · Business: {biz1}\n"
            f"{q2.symbol}: ${q2.price:,.2f} · {q2.market_cap_str} ({pe2_str} P/E) · Business: {biz2}\n"
            f"Delta: {larger_ticker} is ~{diff_str} larger (+{pct_larger:.1f}%).\n\n"
            f"Recent News:\n{news_text_1}\n{news_text_2}\n"
            f"---------------------\n\n"
            "REQUIRED OUTPUT TEMPLATE (Follow exactly):\n\n"
            f"📊 {q1.symbol} vs {q2.symbol}\n\n"
            "💰 Market\n"
            f"{q1.symbol}  ${q1.price:,.2f} · {q1.market_cap_str} ({pe1_str} P/E)\n"
            f"{q2.symbol}  ${q2.price:,.2f} · {q2.market_cap_str} ({pe2_str} P/E)\n\n"
            f"{larger_ticker} is ~{diff_str} larger (+{pct_larger:.1f}%).\n\n"
            "🏢 Business\n"
            f"{q1.symbol} → {biz1}\n"
            f"{q2.symbol} → {biz2}\n\n"
            "📰 Latest\n"
            f"{news_text_1}\n"
            f"{news_text_2}\n\n"
            "💡 Bottom line\n"
            f"• {larger_ticker} holds the larger market cap while trading at a {'lower' if q1.pe_ratio and q2.pe_ratio and min(q1.pe_ratio, q2.pe_ratio) == (q1.pe_ratio if larger_ticker == q1.symbol else q2.pe_ratio) else 'higher'} trailing multiple.\n"
            f"• {q1.symbol} is primarily exposed to enterprise software & cloud, while {q2.symbol} relies on advertising/search alongside cloud and AI.\n"
            "• Key metrics to watch: Cloud growth divergence (Azure vs GCP), AI monetization, and advertising margins.\n\n"
            "📚 Sources\n"
            f"{sources_str} · Aug 9, 2026, {now_utc}"
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
                f"📊 {q1.symbol} vs {q2.symbol}\n\n"
                f"💰 Market\n"
                f"{q1.symbol}  ${q1.price:,.2f} · {q1.market_cap_str} ({pe1_str} P/E)\n"
                f"{q2.symbol}  ${q2.price:,.2f} · {q2.market_cap_str} ({pe2_str} P/E)\n\n"
                f"{larger_ticker} is ~{diff_str} larger (+{pct_larger:.1f}%).\n\n"
                f"🏢 Business\n"
                f"{q1.symbol} → {biz1}\n"
                f"{q2.symbol} → {biz2}\n\n"
                f"📚 Sources\n"
                f"Yahoo Finance · Aug 9, 2026, {now_utc}"
            )
