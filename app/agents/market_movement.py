from typing import Dict, Any, List
from app.market_data import MarketDataProvider, MarketQuote, NewsArticle
from langchain_core.messages import SystemMessage, HumanMessage
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from app.market_data import get_current_date_str

class MarketMovementAnalyzer:
    """
    Dedicated institutional market movement analyzer.
    Strictly separates FACT (Price/Volume) from EVIDENCE (Headlines) and ANALYSIS (Causality vs Correlation).
    Never invents unverified technical levels or assumes causality without explicit proof.
    """
    @classmethod
    async def analyze_movement(cls, symbol: str, llm) -> str:
        quote = MarketDataProvider.get_quote(symbol)
        if not quote:
            return f"Could not retrieve real-time market data for {symbol.upper()}."
            
        comp_news, ind_news = MarketDataProvider.get_company_news_classified(symbol, limit=3)
        
        # Build evidence block
        news_lines = []
        if comp_news:
            for n in comp_news:
                news_lines.append(f"• {n.title}\n  {n.publisher} · {n.relative_time}")
        elif ind_news:
            for n in ind_news:
                news_lines.append(f"• [Industry] {n.title}\n  {n.publisher} · {n.relative_time}")
        else:
            news_lines.append("• No breaking company-specific headlines verified in the last 24h.")
            
        news_block = "\n\n".join(news_lines)

        sign = "+" if quote.percent_change >= 0 else ""
        vol_str = f"{quote.volume / 1_000_000:.1f}M" if quote.volume >= 1_000_000 else f"{quote.volume:,}"
        date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
        now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
        curr_sym = "₹" if quote.currency == "INR" or quote.symbol.endswith((".NS", ".BO")) else ("€" if quote.currency == "EUR" else ("£" if quote.currency == "GBP" else "$"))
        
        all_articles = comp_news + ind_news
        publishers = list(set([n.publisher for n in all_articles if n.publisher]))
        sources_list = ["Yahoo Finance"] + [p for p in publishers if p != "Financial Media"]
        sources_str = " · ".join(sources_list[:3])
        
        prompt = (
            f"You are Atlas, an elite institutional financial intelligence partner.\n"
            f"CURRENT DATE: {date_str} ({now_utc}).\n\n"
            f"TASK: Analyze the price action and latest developments for {quote.symbol} ({quote.name}).\n\n"
            f"--- DATA LEDGER (Strict Ground Truth) ---\n"
            f"Price: {curr_sym}{quote.price:,.2f} ({sign}{quote.percent_change:.2f}% today)\n"
            f"Volume: {vol_str}\n"
            f"52-Week Range: {curr_sym}{quote.fifty_two_week_low or 0:.2f} - {curr_sym}{quote.fifty_two_week_high or 0:.2f}\n"
            f"Verified Recent Headlines:\n{news_block}\n"
            f"-----------------------------------------\n\n"
            "CRITICAL OPERATIONAL RULES:\n"
            "1. NEVER ASSUME CAUSALITY: Do not state that an article 'caused' the price move unless there is explicit confirmed proof (e.g. earnings release or regulatory filing today). Acknowledge relevant news while clarifying if causality is unproven.\n"
            "2. Focus on institutional analysis (e.g., macro discount-rate dynamics, sector rotation, structural tailwinds) rather than retail-style fact dumps. Tell the user *why it matters*.\n"
            "3. NO HALLUCINATED TECHNICAL LEVELS: Do NOT invent arbitrary price support or resistance levels (like '$320 support'). Mention general watch items like price momentum, volume, or business factors.\n"
            "4. CLEAN TELEGRAM LAYOUT: Follow the EXACT template below.\n\n"
            "REQUIRED OUTPUT STRUCTURE:\n\n"
            f"📈 {quote.symbol} Movement\n\n"
            "💰 Price Action\n"
            f"{quote.symbol}  {curr_sym}{quote.price:,.2f} · {sign}{quote.percent_change:.2f}%\n"
            f"Volume: {vol_str}\n\n"
            "📰 Key Developments\n\n"
            f"{news_block}\n\n"
            "💡 What Matters\n"
            "[2-3 sentence intellectual synthesis: Discuss whether the headlines represent proven direct catalysts vs general background sentiment, and identify tangible operational factors.]\n\n"
            "📊 Bottom line\n"
            f"• {quote.symbol} is {sign}{quote.percent_change:.2f}% today with {vol_str} in volume.\n"
            "[1 sentence summarizing broader momentum vs fundamental risks.]\n\n"
            "Watch: Price momentum · [2-3 key business or macro factors to track]\n\n"
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
            logger.error(f"Error in MarketMovementAnalyzer: {e}")
            return (
                f"📈 {quote.symbol} Movement\n\n"
                f"💰 Price Action\n"
                f"{quote.symbol}  {curr_sym}{quote.price:,.2f} · {sign}{quote.percent_change:.2f}%\n"
                f"Volume: {vol_str}\n\n"
                "📚 Sources\n"
                f"Yahoo Finance · {date_str} · {now_utc}"
            )
