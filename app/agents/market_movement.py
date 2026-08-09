from typing import Dict, Any, List
from app.market_data import MarketDataProvider, MarketQuote, NewsArticle
from langchain_core.messages import SystemMessage, HumanMessage
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CURRENT_DATE_STR = "August 9, 2026"

class MarketMovementAnalyzer:
    """
    Dedicated ultra-clean, icon-driven market movement analyzer.
    """
    @classmethod
    async def analyze_movement(cls, symbol: str, llm) -> str:
        quote = MarketDataProvider.get_quote(symbol)
        if not quote:
            return f"Could not retrieve real-time market data for {symbol.upper()}."
            
        news_items = MarketDataProvider.get_recent_news(symbol, limit=3)
        
        # Build strict evidence block
        news_lines = []
        if news_items:
            for n in news_items:
                tag = "Industry: " if n.category == "Industry" else ("Macro: " if n.category == "Macro" else "")
                news_lines.append(f"{quote.symbol} → {tag}{n.title} ({n.publisher} · {n.relative_time})")
            news_block = "\n".join(news_lines)
        else:
            news_block = f"{quote.symbol} → No major breaking headlines verified in the last 24h."

        direction = "up" if quote.percent_change >= 0 else "down"
        sign = "+" if quote.percent_change >= 0 else ""
        now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
        
        publishers = list(set([n.publisher for n in news_items if n.publisher]))
        sources_str = " · ".join(["Yahoo Finance"] + publishers[:3])
        
        prompt = (
            f"You are Atlas, an elite institutional financial assistant communicating on Telegram.\n"
            f"CURRENT DATE: {CURRENT_DATE_STR} ({now_utc}).\n\n"
            f"TASK: Generate the movement analysis for {quote.symbol} using the ultra-clean, icon-driven format below.\n"
            "Keep it under 120 words. No heavy markdown headers. Clean, fast to scan.\n\n"
            f"--- DATA ---\n"
            f"Symbol: {quote.symbol} ({quote.name})\n"
            f"Price: ${quote.price:,.2f} ({sign}{quote.percent_change:.2f}% today) | Volume: {quote.volume:,}\n"
            f"News:\n{news_block}\n"
            f"------------\n\n"
            "REQUIRED LAYOUT:\n\n"
            f"📈 {quote.symbol} Movement\n\n"
            "💰 Price Action\n"
            f"{quote.symbol}  ${quote.price:,.2f} ({sign}{quote.percent_change:.2f}% today) · Vol: {quote.volume:,}\n\n"
            "🎯 Primary Catalyst\n"
            "[1 sharp sentence identifying the core driver from news, or sector/macro sentiment if no direct company news]\n\n"
            "📰 Latest\n"
            f"{news_block}\n\n"
            "💡 Bottom line\n"
            "[1-2 sentence executive takeaway on momentum and key levels/catalysts to watch]\n\n"
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
            logger.error(f"Error in MarketMovementAnalyzer: {e}")
            return (
                f"📈 {quote.symbol} Movement\n\n"
                f"💰 Price Action\n"
                f"{quote.symbol}  ${quote.price:,.2f} ({sign}{quote.percent_change:.2f}% today) · Vol: {quote.volume:,}\n\n"
                f"📚 Sources\n"
                f"Yahoo Finance · Aug 9, 2026, {now_utc}"
            )
