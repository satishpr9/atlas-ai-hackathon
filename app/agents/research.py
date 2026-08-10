import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage
from app.market_data import MarketDataProvider

logger = logging.getLogger(__name__)

CURRENT_DATE_STR = "August 9, 2026"

# --- Epistemic Calibration Prompt ---
# This is the core intellectual engine: it forces the LLM to distinguish
# Known / Reported / Estimated / Inferred / Unknown for every claim.

EPISTEMIC_CALIBRATION_RULES = """
--- EPISTEMIC CALIBRATION RULES (MANDATORY) ---

You MUST classify every factual claim you make into one of these confidence tiers:

  Known       → Verified from official public filings, earnings reports, or regulatory disclosures.
  Reported    → Stated by credible journalism (e.g. Bloomberg, Reuters, WSJ, FT) with a specific date.
  Estimated   → Based on analyst consensus, tender-offer pricing, or industry benchmarks. State the basis.
  Inferred    → Logical conclusion from available evidence. Label it clearly as inference.
  Unknown     → Insufficient public information to make a reliable claim. Say so explicitly.

STRICT RULES:
1. Never present an Estimated or Inferred claim as a Known fact.
2. Never state profitability, revenue, or cash generation as fact for a private company unless you have a specific, dated, credible source.
3. Never mix a current capability with a future plan/milestone. Separate "Current" from "Planned/Future".
4. Never fabricate investor lists. If you are not confident about specific investors, say "Investors include [names you are confident about]" or omit the section.
5. For private companies, always include a transparency note about limited financial visibility.
6. For valuations from private transactions, state the transaction basis and approximate date. Note that private valuations are point-in-time and not continuously updated.
7. If you don't know something, say "Not publicly disclosed" or "Insufficient public data to verify." Never fill gaps with plausible-sounding fabrications.

SOURCE ATTRIBUTION:
For each major claim, mentally track:
  - source_name (e.g. "Bloomberg", "SEC Filing", "Company Press Release")
  - approximate date of the source
  - what specific claim it supports

In the Sources section, list the actual sources that support your claims, not generic database names like "PitchBook" unless you are citing a specific PitchBook report.
"""


class DeepResearchEngine:
    """
    Fully dynamic research engine with epistemic calibration.
    Works for ANY company — public, private, or pre-IPO.
    No hardcoded company data. All intelligence is synthesized dynamically
    with strict confidence-tier labeling.
    """
    
    @classmethod
    async def research_entity(cls, query: str, llm) -> str:
        """Route to public or general research based on whether we can get live market data."""
        clean_q = query.lower().strip()
        date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
        now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
        
        # Try to extract a public ticker
        from app.agents.assistant import extract_tickers
        tickers = extract_tickers(query)
        
        if tickers:
            sym = tickers[0]
            quote = MarketDataProvider.get_quote(sym)
            if quote:
                # Public company with live data
                overview = MarketDataProvider.get_company_overview(sym)
                comp_news, ind_news = MarketDataProvider.get_company_news_classified(sym, limit=3)
                return await cls._synthesize_public_deep_dive(sym, quote, overview, comp_news, ind_news, query, llm, now_utc, date_str)

        # No live market data → treat as private/general research
        return await cls._synthesize_general_research(query, llm, now_utc, date_str)

    @staticmethod
    async def _synthesize_general_research(query: str, llm, now_utc: str, date_str: str) -> str:
        """
        Fully dynamic research synthesis for private companies, sectors, or any entity
        without live market data. Uses strict epistemic calibration.
        """
        prompt = (
            f"You are Atlas, an elite institutional financial intelligence partner.\n"
            f"CURRENT DATE: {date_str} ({now_utc}).\n\n"
            f"USER RESEARCH QUERY: \"{query}\"\n\n"
            f"{EPISTEMIC_CALIBRATION_RULES}\n\n"
            "TASK: Produce a comprehensive, epistemically honest research brief for this query.\n\n"
            "FORMAT (clean Telegram style, no markdown ## headers):\n\n"
            "Use this structure, adapting sections to the entity type:\n\n"
            "🦄 [Company Name] (if private) or 🏢 [Company Name] (if public/other)\n\n"
            "💰 Valuation\n"
            "[State the latest reported valuation with basis, date, and confidence level.]\n"
            "[For private companies, note: 'This is a transaction-based private valuation, not a live market price.']\n\n"
            "🏢 Business\n"
            "[Core business segments, stated factually.]\n"
            "[Leadership: only names you are confident about.]\n\n"
            "📌 Key Developments\n"
            "[Each bullet should state what is known, with approximate source/date if possible.]\n"
            "[Separate current facts from planned/future milestones.]\n\n"
            "💡 Why It Matters\n"
            "[Strategic context — what this means for investors, competitors, or the market.]\n"
            "[Be honest about what is unknown or unverifiable.]\n\n"
            "⚠️ Important\n"
            "[For private companies: note limited financial visibility.]\n"
            "[For any entity: note which claims are Estimated vs Known.]\n\n"
            "📚 Sources\n"
            "[List specific sources that support your claims. Do NOT list generic database names.]\n"
            f"Retrieved: {date_str} · {now_utc}\n\n"
            "REMEMBER: It is far better to say 'Not publicly disclosed' than to state an unverified claim as fact."
        )
        
        try:
            res = await llm.ainvoke([HumanMessage(content=prompt)])
            content = res.content
            if isinstance(content, list):
                text_parts = [p["text"] for p in content if isinstance(p, dict) and "text" in p]
                return "".join(text_parts) if text_parts else str(content)
            return str(content)
        except Exception as e:
            logger.error(f"Error in general research: {e}")
            return f"I processed your research request on '{query}', but encountered a synthesis issue. Please try again."

    @staticmethod
    async def _synthesize_public_deep_dive(
        sym: str,
        quote: Any,
        overview: Dict[str, Any],
        comp_news: List[Any],
        ind_news: List[Any],
        user_query: str,
        llm: Any,
        now_utc: str,
        date_str: str
    ) -> str:
        """
        Public company deep dive with verified live data as ground truth,
        plus epistemic calibration for any forward-looking or analyst-derived claims.
        """
        sign = "+" if quote.percent_change >= 0 else ""
        curr = "₹" if quote.currency == "INR" or quote.symbol.endswith((".NS", ".BO")) else ("€" if quote.currency == "EUR" else ("£" if quote.currency == "GBP" else "$"))
        pe_str = f"{quote.pe_ratio:.1f}x" if quote.pe_ratio else "N/A"
        fwd_pe_str = f"{quote.forward_pe:.1f}x" if quote.forward_pe else "N/A"
        vol_str = f"{quote.volume / 1_000_000:.1f}M" if quote.volume >= 1_000_000 else f"{quote.volume:,}"
        
        news_lines = []
        if comp_news:
            for n in comp_news:
                news_lines.append(f"• {n.title}\n  Source: {n.publisher} · {n.relative_time}")
        else:
            news_lines.append("• No major breaking company-specific headlines verified in the last 24h.")
        news_block = "\n".join(news_lines)
        
        sector = overview.get('sector', 'Technology')
        industry = overview.get('industry', '')
        biz = overview.get('core_business', 'Technology & Operations')
        
        prompt = (
            f"You are Atlas, an elite institutional financial intelligence partner.\n"
            f"CURRENT DATE: {date_str} ({now_utc}).\n\n"
            f"USER RESEARCH QUERY: \"{user_query}\"\n\n"
            f"{EPISTEMIC_CALIBRATION_RULES}\n\n"
            f"--- VERIFIED GROUND TRUTH (Known confidence) ---\n"
            f"Company: {quote.name} ({sym})\n"
            f"Price: {curr}{quote.price:,.2f} ({sign}{quote.percent_change:.2f}%)\n"
            f"Market Cap: {quote.market_cap_str}\n"
            f"Trailing P/E: {pe_str}\n"
            f"Forward P/E: {fwd_pe_str}\n"
            f"Volume: {vol_str}\n"
            f"Sector: {sector}\n"
            f"Industry: {industry}\n"
            f"Core Business: {biz}\n\n"
            f"Verified Recent Headlines:\n{news_block}\n"
            f"---------------------------------------------------------------\n\n"
            "TASK: Produce a comprehensive institutional research brief addressing the user's query.\n\n"
            "FORMAT:\n\n"
            f"🏢 {quote.name} ({sym}) · Research Brief\n\n"
            "💰 Financial Snapshot (Known)\n"
            f"{curr}{quote.price:,.2f} · {sign}{quote.percent_change:.2f}%\n"
            f"Market Cap: {quote.market_cap_str}\n"
            f"Trailing P/E: {pe_str} · Forward P/E: {fwd_pe_str}\n"
            f"Volume: {vol_str}\n\n"
            "🏢 Business Architecture\n"
            f"Sector: {sector}\n"
            f"Core: {biz}\n"
            "[Add 2-3 bullet points on revenue engines and competitive moat — label any forward-looking claims.]\n\n"
            "📌 Verified Developments\n"
            f"{news_block}\n\n"
            "💡 Strategic Assessment\n"
            "[Address the user's specific research focus. Explain WHY each factor matters.]\n"
            "[Separate Known facts from Estimated/Inferred analysis.]\n\n"
            "📚 Sources\n"
            f"{quote.source}\n"
            "[List specific news sources cited above]\n"
            f"Retrieved: {date_str} · {now_utc}"
        )
        
        try:
            res = await llm.ainvoke([HumanMessage(content=prompt)])
            content = res.content
            if isinstance(content, list):
                text_parts = [p["text"] for p in content if isinstance(p, dict) and "text" in p]
                return "".join(text_parts) if text_parts else str(content)
            return str(content)
        except Exception as e:
            logger.error(f"Error synthesizing deep research for {sym}: {e}")
            return (
                f"🏢 {quote.name} ({sym})\n\n"
                f"💰 Market: {curr}{quote.price:,.2f} ({sign}{quote.percent_change:.2f}%)\n"
                f"Market Cap: {quote.market_cap_str} · P/E: {pe_str}\n\n"
                f"📚 Sources: {quote.source} · {date_str} · {now_utc}"
            )
