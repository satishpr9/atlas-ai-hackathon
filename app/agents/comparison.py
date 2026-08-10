import logging
from typing import List, Dict, Any
from app.market_data import MarketDataProvider, MarketQuote, NewsArticle
from langchain_core.messages import SystemMessage, HumanMessage
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)

from app.market_data import get_current_date_str

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

class CompanyComparisonEngine:
    """
    Dedicated high-precision comparison engine using clear brand names (e.g. Tesla vs Rivian, Microsoft vs Google)
    with strict entity-specific news segregation, explicit trailing P/E values, dynamic business divergence,
    and institutional bottom line.
    """
    @classmethod
    async def compare(cls, ticker1: str, ticker2: str, llm, mode: str = "standard") -> str:
        t1, t2 = ticker1.upper(), ticker2.upper()
        
        q1, q2, ov1, ov2, news1, news2 = await asyncio.gather(
            asyncio.to_thread(MarketDataProvider.get_quote, t1),
            asyncio.to_thread(MarketDataProvider.get_quote, t2),
            asyncio.to_thread(MarketDataProvider.get_company_overview, t1),
            asyncio.to_thread(MarketDataProvider.get_company_overview, t2),
            asyncio.to_thread(MarketDataProvider.get_company_news_classified, t1, limit=2),
            asyncio.to_thread(MarketDataProvider.get_company_news_classified, t2, limit=2)
        )
        comp1, ind1 = news1
        comp2, ind2 = news2
        
        if not q1 or not q2:
            return f"Unable to retrieve verified market data for {t1} vs {t2}."
            
        name1 = BRAND_MAP.get(q1.symbol, q1.name.split(',')[0].split('(')[0].strip() if q1.name else q1.symbol)
        name2 = BRAND_MAP.get(q2.symbol, q2.name.split(',')[0].split('(')[0].strip() if q2.name else q2.symbol)
        
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
        
        biz1 = ov1.get('core_business', 'N/A')
        biz2 = ov2.get('core_business', 'N/A')

        # 2. Strict News Section Assembly
        def build_company_news_line(articles: List[NewsArticle], brand: str) -> str:
            if not articles:
                return f"{brand}\n• No major breaking company-specific catalyst verified today."
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
        
        curr1 = "₹" if q1.currency == "INR" or q1.symbol.endswith((".NS", ".BO")) else ("€" if q1.currency == "EUR" else ("£" if q1.currency == "GBP" else "$"))
        curr2 = "₹" if q2.currency == "INR" or q2.symbol.endswith((".NS", ".BO")) else ("€" if q2.currency == "EUR" else ("£" if q2.currency == "GBP" else "$"))
        
        date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
        now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")

        # Extract extra investment data
        def fmt_val(v): return "unavailable" if v is None else str(v)
        
        fwd_pe1 = fmt_val(ov1.get('forward_pe'))
        fwd_pe2 = fmt_val(ov2.get('forward_pe'))
        ev_ebitda1 = fmt_val(ov1.get('ev_ebitda'))
        ev_ebitda2 = fmt_val(ov2.get('ev_ebitda'))
        ps1 = fmt_val(ov1.get('price_to_sales'))
        ps2 = fmt_val(ov2.get('price_to_sales'))
        rev_gr1 = f"{ov1.get('revenue_growth')*100:.1f}%" if ov1.get('revenue_growth') else "unavailable"
        rev_gr2 = f"{ov2.get('revenue_growth')*100:.1f}%" if ov2.get('revenue_growth') else "unavailable"
        eps_gr1 = f"{ov1.get('earnings_growth')*100:.1f}%" if ov1.get('earnings_growth') else "unavailable"
        eps_gr2 = f"{ov2.get('earnings_growth')*100:.1f}%" if ov2.get('earnings_growth') else "unavailable"
        op_margin1 = f"{ov1.get('operating_margin')*100:.1f}%" if ov1.get('operating_margin') else "unavailable"
        op_margin2 = f"{ov2.get('operating_margin')*100:.1f}%" if ov2.get('operating_margin') else "unavailable"
        fcf1 = f"${ov1.get('free_cashflow')/1e9:.1f}B" if ov1.get('free_cashflow') else "unavailable"
        fcf2 = f"${ov2.get('free_cashflow')/1e9:.1f}B" if ov2.get('free_cashflow') else "unavailable"

        if mode == "investment":
            prompt = (
                f"You are Atlas, an elite institutional financial intelligence partner communicating on Telegram.\n"
                f"CURRENT DATE: {date_str} ({now_utc}).\n\n"
                f"TASK: Generate the deep INVESTMENT comparative breakdown for {name1} ({q1.symbol}) vs {name2} ({q2.symbol}).\n\n"
                f"--- VERIFIED DATA LEDGER ---\n"
                f"{name1}:\n"
                f"Price: {curr1}{q1.price:,.2f} | Cap: {q1.market_cap_str} | P/E: {pe1_str} | FWD P/E: {fwd_pe1} | EV/EBITDA: {ev_ebitda1} | P/S: {ps1}\n"
                f"Growth: Rev {rev_gr1}, EPS {eps_gr1} | Op Margin: {op_margin1} | FCF: {fcf1}\n"
                f"Business: {biz1}\n\n"
                f"{name2}:\n"
                f"Price: {curr2}{q2.price:,.2f} | Cap: {q2.market_cap_str} | P/E: {pe2_str} | FWD P/E: {fwd_pe2} | EV/EBITDA: {ev_ebitda2} | P/S: {ps2}\n"
                f"Growth: Rev {rev_gr2}, EPS {eps_gr2} | Op Margin: {op_margin2} | FCF: {fcf2}\n"
                f"Business: {biz2}\n\n"
                f"Verified Company News:\n{company_news_1}\n\n{company_news_2}\n"
                f"----------------------------\n\n"
                "RULES:\n"
                f"1. Focus on evaluating WHICH is a better investment, weighing valuation against growth, margins, and risk.\n"
                f"2. Use the exact data provided. If data says 'unavailable', DO NOT invent numbers. Explicitly state they are unavailable if they are critical to the comparison.\n"
                "3. DO NOT make an explicit 'buy this stock' recommendation. Instead, provide a balanced 'Investment Takeaway'.\n"
                "4. Follow the EXACT Telegram template below without raw markdown '##' headers.\n\n"
                "EXACT OUTPUT TEMPLATE:\n\n"
                f"📊 {name1} vs {name2}\n"
                "Investment Perspective\n\n"
                "💰 Valuation\n"
                f"{name1} → {curr1}{q1.price:,.2f} · {q1.market_cap_str}\n"
                f"{name2} → {curr2}{q2.price:,.2f} · {q2.market_cap_str}\n\n"
                "[2-3 sentences comparing P/E, FWD P/E, EV/EBITDA, P/S. If key metrics are unavailable, mention it here.]\n\n"
                "📈 Growth Drivers\n"
                f"{name1} → [3-4 words max on core drivers, e.g. Azure · Copilot]\n"
                f"{name2} → [3-4 words max on core drivers]\n\n"
                "[2-3 sentences comparing Rev Growth, EPS Growth, Margins, and FCF.]\n\n"
                "💵 Business Quality\n"
                f"{name1}\n"
                "→ [Bullet 1 on moat/business quality]\n"
                "→ [Bullet 2]\n\n"
                f"{name2}\n"
                "→ [Bullet 1 on moat/business quality]\n"
                "→ [Bullet 2]\n\n"
                "⚠️ Key Risks\n"
                f"{name1}\n"
                "→ [Risk 1]\n"
                "→ [Risk 2]\n\n"
                f"{name2}\n"
                "→ [Risk 1]\n"
                "→ [Risk 2]\n\n"
                "🚀 Key Catalysts\n"
                f"{name1} → [Catalyst 1] · [Catalyst 2]\n"
                f"{name2} → [Catalyst 1] · [Catalyst 2]\n\n"
                "💡 Investment Takeaway\n"
                "[1 paragraph summarizing which offers stronger exposure to what, and what the better investment depends heavily on.]\n\n"
                "👀 Watch Next\n"
                "[3-4 metrics to monitor, e.g. 'Azure vs Google Cloud growth', 'Operating margins']\n\n"
                "📚 Sources\n"
                f"{sources_str}\n"
                f"{date_str} · {now_utc}"
            )
        else:
            prompt = (
                f"You are Atlas, an elite institutional financial intelligence partner communicating on Telegram.\n"
                f"CURRENT DATE: {date_str} ({now_utc}).\n\n"
                f"TASK: Generate the comparative business breakdown for {name1} ({q1.symbol}) vs {name2} ({q2.symbol}).\n\n"
                f"--- VERIFIED DATA LEDGER ---\n"
                f"{name1} ({q1.symbol}): {curr1}{q1.price:,.2f} · Market Cap: {q1.market_cap_str} · Trailing P/E: {pe1_str} · Business: {biz1}\n"
                f"{name2} ({q2.symbol}): {curr2}{q2.price:,.2f} · Market Cap: {q2.market_cap_str} · Trailing P/E: {pe2_str} · Business: {biz2}\n"
                f"Valuation Delta: {larger_name} ({larger_ticker}) is ~{diff_str} larger (+{pct_larger:.1f}%).\n\n"
                f"Verified Company News:\n{company_news_1}\n\n{company_news_2}\n"
                f"----------------------------\n\n"
                "RULES:\n"
                f"1. Tailor the '🌐 Industry', '💡 Bottom line', and 'Watch' items SPECIFICALLY to the actual business models of {name1} and {name2}.\n"
                "2. Focus on structural comparative advantages (e.g. TAM, margins, economic moats, capital allocation) rather than just stating who is bigger. Tell the user *why it matters*.\n"
                "3. If the provided data does not contain the answer, explicitly state 'I do not have verified data to determine this'. DO NOT guess or infer numbers.\n"
                "4. DO NOT act like a news reader. DO NOT list headlines. Instead, synthesize recent data into a highly informative 'Strategic Context' summary that explains the fundamental drivers and broader context to the user.\n"
                "5. Follow the EXACT Telegram template below without raw markdown '##' headers.\n\n"
                "EXACT OUTPUT TEMPLATE:\n\n"
                f"📊 {name1} vs {name2}\n\n"
                "💰 Market\n"
                f"{name1} ({q1.symbol})  {curr1}{q1.price:,.2f} · {q1.market_cap_str} · {pe1_str}\n"
                f"{name2} ({q2.symbol})  {curr2}{q2.price:,.2f} · {q2.market_cap_str} · {pe2_str}\n\n"
                f"{larger_name} is ~{diff_str} larger (+{pct_larger:.1f}%).\n\n"
                "🏢 Business\n"
                f"{name1} → {biz1}\n"
                f"{name2} → {biz2}\n\n"
                "📌 Strategic Context\n"
                "[1-2 sentence deep, informative analysis of the underlying fundamental drivers affecting both companies right now. Focus on the 'why' and the actionable intelligence.]\n\n"
                "🌐 Industry\n"
                f"[1 concise sentence describing the shared macro/industry dynamic relevant to {name1} and {name2}.]\n\n"
                "💡 Bottom line\n"
                f"{larger_name} is larger by market capitalization.\n\n"
                f"{name1} → [1 concise phrase describing core strategic focus / moat]\n"
                f"{name2} → [1 concise phrase describing core strategic focus / moat]\n\n"
                "Watch:\n"
                f"[3 key operational metrics to track for {name1} and {name2}]\n\n"
                "📚 Sources\n"
                f"{sources_str}\n"
                f"{date_str} · {now_utc}"
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
                f"{name1} ({q1.symbol})  {curr1}{q1.price:,.2f} · {q1.market_cap_str} · {pe1_str}\n"
                f"{name2} ({q2.symbol})  {curr2}{q2.price:,.2f} · {q2.market_cap_str} · {pe2_str}\n\n"
                f"{larger_name} is ~{diff_str} larger (+{pct_larger:.1f}%).\n\n"
                f"🏢 Business\n"
                f"{name1} → {biz1}\n"
                f"{name2} → {biz2}\n\n"
                f"📚 Sources\n"
                f"Yahoo Finance · {date_str} · {now_utc}"
            )
