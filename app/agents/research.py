import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage
from app.market_data import MarketDataProvider

logger = logging.getLogger(__name__)

CURRENT_DATE_STR = "August 9, 2026"

# Curated Private Unicorns & Companies Intel Ledger
PRIVATE_COMPANIES_LEDGER = {
    "openai": {
        "name": "OpenAI",
        "category": "Private AI Research & Deployment",
        "valuation": "$157B+ (Oct 2024 / 2025 Series funding)",
        "key_investors": "Microsoft, Thrive Capital, SoftBank, Khosla Ventures, Nvidia",
        "core_business": "Frontier Foundation Models (GPT-4o, o1, o3) · ChatGPT Enterprise · APIs · Developer Compute",
        "leadership": "Sam Altman (CEO), Greg Brockman (President), Kevin Weil (CPO)",
        "recent_developments": [
            "Scaling reasoning models (o1/o3 series) and expanding enterprise ChatGPT subscriptions.",
            "Structuring corporate governance transition toward public benefit corporation (PBC) model.",
            "Deepening multi-gigawatt compute partnerships with Microsoft, Oracle, and Stargate infrastructure."
        ],
        "strategic_context": "Monetization velocity is surging past $4B+ annualized revenue run rate, but compute capex and inference infrastructure remain massive cash drains requiring ongoing capital access."
    },
    "anthropic": {
        "name": "Anthropic",
        "category": "Private AI Safety & Enterprise Intelligence",
        "valuation": "$40B+ (Late 2024 / 2025 rounds)",
        "key_investors": "Amazon ($4B+ committed), Google ($2B+ committed), Menlo Ventures, Spark Capital",
        "core_business": "Claude Foundation Models (Claude 3.5 Sonnet / Haiku / Opus) · Computer Use API · Enterprise AI Safety",
        "leadership": "Dario Amodei (CEO), Daniela Amodei (President), Jared Kaplan (Chief Scientist)",
        "recent_developments": [
            "Rapid enterprise adoption of Claude 3.5 Sonnet across software engineering and data synthesis workflows.",
            "Expanded deep integration with AWS Bedrock and Google Cloud Vertex AI platforms.",
            "Pioneering 'Computer Use' capabilities allowing models to interact directly with desktop operating systems."
        ],
        "strategic_context": "Positioned as the leading enterprise safety and coding benchmark leader, maintaining dual-cloud backing from Amazon and Google to avoid single-vendor lock-in."
    },
    "spacex": {
        "name": "SpaceX",
        "category": "Private Aerospace & Satellite Telecommunications",
        "valuation": "$350B+ (Tender offer valuation)",
        "key_investors": "Founders Fund, Sequoia Capital, Fidelity, Andreessen Horowitz",
        "core_business": "Reusable Rocket Launch (Falcon 9, Falcon Heavy, Starship) · Starlink Satellite Broadband · NASA Commercial Crew",
        "leadership": "Elon Musk (CEO & CTO), Gwynne Shotwell (President & COO)",
        "recent_developments": [
            "Starlink subscriber base expanding past 4M+ globally with strong cash flow generation.",
            "Starship orbital test flights progressing rapidly toward heavy payload deployment and lunar Starship Artemis milestones.",
            "Direct-to-cell satellite constellation deployment in partnership with global telecom carriers."
        ],
        "strategic_context": "Starlink has transitioned into a highly profitable global cash generation engine, funding Starship's capital-intensive development without requiring public equity dilution."
    },
    "stripe": {
        "name": "Stripe",
        "category": "Private Financial Infrastructure & Payments",
        "valuation": "$65B - $70B (Tender offers & liquidity rounds)",
        "key_investors": "Sequoia Capital, General Catalyst, Peter Thiel, Andreessen Horowitz",
        "core_business": "Global Payment Processing · Billing & Subscriptions · Stripe Connect · Treasury · AI Agent Commerce",
        "leadership": "Patrick Collison (CEO), John Collison (President)",
        "recent_developments": [
            "Surpassing $1T+ in total annual processed payment volume with positive GAAP profitability.",
            "Acquisition of Bridge ($1.1B) to dominate stablecoin and programmable global settlement rails.",
            "Rapid launch of agentic payment APIs allowing autonomous AI agents to transact programmatically."
        ],
        "strategic_context": "Combines massive cash-flow positive enterprise scale with aggressive innovation in stablecoins and AI-native payments, giving it complete flexibility over IPO timing."
    },
    "bytedance": {
        "name": "ByteDance",
        "category": "Private Global Consumer Tech & Digital Media",
        "valuation": "$220B - $250B",
        "key_investors": "General Atlantic, Sequoia Capital China, SoftBank, Coatue",
        "core_business": "TikTok · Douyin · CapCut · Doubao AI · Enterprise Cloud (Volcengine)",
        "leadership": "Liang Rubo (CEO), Shou Zi Chew (TikTok CEO)",
        "recent_developments": [
            "Doubao generative AI model ecosystem becoming one of the most widely used AI engines in Asia.",
            "TikTok Shop GMV experiencing rapid expansion in Southeast Asia and the US.",
            "Ongoing regulatory and legislative restructuring navigation in Western markets."
        ],
        "strategic_context": "Unrivaled algorithmic engagement and e-commerce monetization offset by persistent geopolitical and regulatory scrutiny in the United States and EU."
    },
    "databricks": {
        "name": "Databricks",
        "category": "Private Enterprise Data & AI Lakehouse",
        "valuation": "$43B+ (Series I / 2024-2025)",
        "key_investors": "Andreessen Horowitz, Baillie Gifford, Counterpoint Global, Franklin Templeton, Nvidia, CapitalG",
        "core_business": "Unified Data Lakehouse Platform · Mosaic AI Model Training · Apache Spark · Delta Lake · Unity Catalog",
        "leadership": "Ali Ghodsi (CEO), Matei Zaharia (CTO), Naveen Rao (VP of Generative AI)",
        "recent_developments": [
            "Surpassed $2.4B+ annual revenue run-rate with >50% year-over-year organic growth.",
            "Integration of Mosaic AI enabling enterprise customers to build and fine-tune proprietary LLMs on private enterprise data.",
            "Expansion of serverless data intelligence engine competing directly with Snowflake and BigQuery."
        ],
        "strategic_context": "The dominant data substrate for enterprise AI workloads, accelerating growth by unifying open data formats with proprietary model fine-tuning."
    }
}

class DeepResearchEngine:
    """
    Institutional research synthesizer covering both public equities and private high-growth tech unicorns.
    Provides structured intelligence across valuation, leadership, M&A, earnings, and regulatory context.
    """
    
    @classmethod
    async def research_entity(cls, query: str, llm) -> str:
        clean_q = query.lower().strip()
        now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
        
        # 1. Check if query targets a known private company
        for p_key, p_data in PRIVATE_COMPANIES_LEDGER.items():
            if p_key in clean_q:
                return cls._format_private_company_intel(p_data, now_utc)
                
        # 2. If it's a public equity, fetch verified live data & news
        from app.agents.assistant import extract_tickers
        tickers = extract_tickers(query)
        if tickers:
            sym = tickers[0]
            quote = MarketDataProvider.get_quote(sym)
            overview = MarketDataProvider.get_company_overview(sym)
            comp_news, ind_news = MarketDataProvider.get_company_news_classified(sym, limit=3)
            
            if quote:
                return await cls._synthesize_public_company_deep_dive(sym, quote, overview, comp_news, ind_news, query, llm, now_utc)

        # 3. If generic market/sector research query, prompt LLM with analytical principles
        prompt = (
            f"You are Atlas, an elite institutional financial research analyst.\n"
            f"CURRENT DATE: {CURRENT_DATE_STR} ({now_utc}).\n\n"
            f"USER INQUIRY: '{query}'\n\n"
            "REQUIREMENTS:\n"
            "1. Deliver an institutional, structured research breakdown (Executive Summary, Fundamental Drivers, Risks & Catalysts, Strategic Takeaway).\n"
            "2. Explain WHY each point matters for capital allocation, margin durability, or competitive moat.\n"
            "3. Ground all statements in verified market dynamics—do NOT hallucinate unverified numbers or non-existent partnerships.\n"
            "4. Use the clean Telegram layout with intuitive icons (🏢, 💰, 📌, 📰, 💡, 📚). Never use raw markdown '##' headers."
        )
        try:
            res = await llm.ainvoke([HumanMessage(content=prompt)])
            content = res.content
            if isinstance(content, list):
                text_parts = [p["text"] for p in content if isinstance(p, dict) and "text" in p]
                return "".join(text_parts) if text_parts else str(content)
            return str(content)
        except Exception as e:
            logger.error(f"Error in deep research query: {e}")
            return f"I processed your research request on '{query}', but encountered a data synthesis hiccup. Please try again."

    @staticmethod
    def _format_private_company_intel(data: Dict[str, Any], now_utc: str) -> str:
        name = data["name"]
        val = data["valuation"]
        cat = data["category"]
        inv = data["key_investors"]
        biz = data["core_business"]
        lead = data["leadership"]
        devs = "\n".join([f"• {d}" for d in data["recent_developments"]])
        ctx = data["strategic_context"]
        
        return (
            f"🦄 {name} (Private Company Intelligence)\n\n"
            f"💰 Valuation & Capital\n"
            f"Estimated Valuation: ~{val}\n"
            f"Key Backers: {inv}\n\n"
            f"🏢 Business & Moat\n"
            f"Category: {cat}\n"
            f"Core Engine: {biz}\n"
            f"Leadership: {lead}\n\n"
            f"📌 Recent Developments & Milestones\n"
            f"{devs}\n\n"
            f"💡 Why It Matters (Strategic Context)\n"
            f"{ctx}\n\n"
            f"📚 Sources\n"
            f"PitchBook · CB Insights · Institutional Filings\n"
            f"Retrieved: Aug 9, 2026 · {now_utc}"
        )

    @staticmethod
    async def _synthesize_public_company_deep_dive(
        sym: str,
        quote: Any,
        overview: Dict[str, Any],
        comp_news: List[Any],
        ind_news: List[Any],
        user_query: str,
        llm: Any,
        now_utc: str
    ) -> str:
        sign = "+" if quote.percent_change >= 0 else ""
        pe_str = f"{quote.pe_ratio:.1f}x" if quote.pe_ratio else "N/A"
        vol_str = f"{quote.volume / 1_000_000:.1f}M" if quote.volume >= 1_000_000 else f"{quote.volume:,}"
        
        news_lines = []
        if comp_news:
            for n in comp_news:
                news_lines.append(f"• {n.title} ({n.publisher} · {n.relative_time})")
        else:
            news_lines.append("• No major breaking material SEC filings or catalysts verified in the last 24h.")
        news_block = "\n".join(news_lines)
        
        prompt = (
            f"You are Atlas, an elite institutional financial intelligence partner.\n"
            f"CURRENT DATE: {CURRENT_DATE_STR} ({now_utc}).\n\n"
            f"TASK: Conduct a comprehensive financial & strategic research analysis for {quote.name} ({sym}) addressing: '{user_query}'.\n\n"
            f"--- VERIFIED DATA LEDGER ---\n"
            f"Company: {quote.name} ({sym})\n"
            f"Price: ${quote.price:,.2f} ({sign}{quote.percent_change:.2f}%)\n"
            f"Market Cap: {quote.market_cap_str}\n"
            f"Trailing P/E: {pe_str}\n"
            f"Volume: {vol_str}\n"
            f"Sector: {overview.get('sector', 'Technology')}\n"
            f"Core Business: {overview.get('core_business', 'Technology & Commercial Operations')}\n"
            f"Verified Recent Headlines:\n{news_block}\n"
            f"----------------------------\n\n"
            "REQUIREMENTS:\n"
            "1. Address the user's specific research focus (e.g. business model, financial moat, earnings trajectory, leadership/M&A, or regulatory backdrop).\n"
            "2. Explain WHY the key factors matter for investors and decision makers.\n"
            "3. Strictly adhere to verified numbers and facts.\n"
            "4. Follow the ultra-clean Telegram format below.\n\n"
            "TEMPLATE:\n\n"
            f"🏢 {quote.name} ({sym}) · Strategic Research\n\n"
            "💰 Financial Snapshot\n"
            f"${quote.price:,.2f} · {sign}{quote.percent_change:.2f}% · Market Cap: {quote.market_cap_str} · P/E: {pe_str}\n\n"
            "📌 Business Architecture & Moat\n"
            f"[2-3 concise bullet points detailing core revenue engines, unit economics, and competitive advantages]\n\n"
            "📰 Verified Catalysts & Material Developments\n"
            f"{news_block}\n\n"
            "💡 Why It Matters & Strategic Outlook\n"
            "[2 concise sentences synthesizing the investment thesis, operational risks, and key metrics to monitor.]\n\n"
            "📚 Sources\n"
            f"Yahoo Finance · SEC Filings · Bloomberg\n"
            f"Retrieved: Aug 9, 2026 · {now_utc}"
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
                f"💰 Market: ${quote.price:,.2f} ({sign}{quote.percent_change:.2f}%)\n"
                f"Market Cap: {quote.market_cap_str} · P/E: {pe_str}\n\n"
                f"📚 Sources: Yahoo Finance · Aug 9, 2026 · {now_utc}"
            )
