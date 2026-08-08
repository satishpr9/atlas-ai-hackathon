from typing import Dict, Any, List
from app.market_data import MarketDataProvider, MarketQuote, NewsArticle
from langchain_core.messages import SystemMessage, HumanMessage
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CURRENT_DATE_STR = "August 8, 2026"

class MarketMovementAnalyzer:
    """
    Dedicated agent for analyzing why a stock is moving today,
    grounded strictly in today's price action and recent news.
    """
    @classmethod
    async def analyze_movement(cls, symbol: str, llm) -> str:
        quote = MarketDataProvider.get_quote(symbol)
        if not quote:
            return f"Could not retrieve real-time market data for {symbol.upper()} to analyze today's movement."
            
        news_items = MarketDataProvider.get_recent_news(symbol, limit=4)
        
        # Build strict evidence block
        news_block = ""
        if news_items:
            for i, n in enumerate(news_items, 1):
                news_block += f"{i}. [{n.publisher} | {n.published_at}] {n.title}\n"
        else:
            news_block = "No breaking news articles detected in the past 24 hours."

        direction = "up" if quote.percent_change >= 0 else "down"
        sign = "+" if quote.percent_change >= 0 else ""
        
        prompt = (
            f"You are a Senior Wall Street Equity Research Analyst.\n"
            f"CURRENT CALENDAR DATE: {CURRENT_DATE_STR}.\n\n"
            f"TASK: Explain why {quote.name} ({quote.symbol}) is trading {direction} today.\n\n"
            f"--- VERIFIED REAL-TIME EVIDENCE ---\n"
            f"Symbol: {quote.symbol}\n"
            f"Price: ${quote.price:,.2f} ({sign}{quote.percent_change:.2f}% today)\n"
            f"Volume: {quote.volume:,} (Source: {quote.source}, As of: {quote.timestamp})\n\n"
            f"Recent Verified News Headlines:\n{news_block}\n"
            f"------------------------------------\n\n"
            "STRICT RULES:\n"
            "1. Focus ONLY on current and recent catalysts. Do NOT cite historical 2024/2025 election or political speculation unless it is a confirmed headline from today.\n"
            "2. State the confirmed facts first (Price move, percentage, volume).\n"
            "3. Clearly identify the Primary Catalyst if verified by news. If there is no single confirmed catalyst, explicitly state that the move appears driven by broader sector/macro sentiment.\n"
            "4. Include exact sources and timestamps for the data points.\n"
            "5. Keep the total output under 150 words. Punchy, professional, no fluff."
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
                f"**{quote.symbol}** is trading at **${quote.price:,.2f}** ({sign}{quote.percent_change:.2f}% today).\n"
                f"Volume: {quote.volume:,} | Data as of: {quote.timestamp}\n\n"
                f"I encountered a temporary reasoning bottleneck, but live data indicates standard market volatility."
            )
