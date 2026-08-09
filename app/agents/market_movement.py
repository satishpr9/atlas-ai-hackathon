from typing import Dict, Any, List
from app.market_data import MarketDataProvider, MarketQuote, NewsArticle
from langchain_core.messages import SystemMessage, HumanMessage
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CURRENT_DATE_STR = "August 9, 2026"

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
                news_block += f"{i}. **{n.title}**\n   *Publisher: {n.publisher} · {n.relative_time}*\n   *Summary: {n.summary[:200]}*\n   *Link: {n.link}*\n"
        else:
            news_block = "No breaking company-specific headlines verified in the past 24-48 hours."

        direction = "up" if quote.percent_change >= 0 else "down"
        sign = "+" if quote.percent_change >= 0 else ""
        
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        
        prompt = (
            f"You are a Senior Wall Street Equity Research Analyst.\n"
            f"CURRENT CALENDAR DATE: {CURRENT_DATE_STR} (Current Time: {timestamp}).\n\n"
            f"TASK: Explain why {quote.name} ({quote.symbol}) is trading {direction} today.\n\n"
            f"--- VERIFIED REAL-TIME EVIDENCE (Ground Truth) ---\n"
            f"Symbol: {quote.symbol} ({quote.name})\n"
            f"Current Price: ${quote.price:,.2f} ({sign}{quote.percent_change:.2f}% today)\n"
            f"Volume: {quote.volume:,} | 52-Wk Range: ${quote.fifty_two_week_low or 0:.2f} - ${quote.fifty_two_week_high or 0:.2f}\n"
            f"Market Cap: {quote.market_cap_str} | Source: {quote.source} (As of: {quote.timestamp})\n\n"
            f"Verified News Feed:\n{news_block}\n"
            f"---------------------------------------------------\n\n"
            "OUTPUT STRUCTURE:\n"
            f"📈 **{quote.symbol} Movement Analysis**\n\n"
            f"• **Current Action**: **${quote.price:,.2f}** ({sign}{quote.percent_change:.2f}% today) on volume of {quote.volume:,}.\n"
            "• **Primary Catalyst**: [Identify the strongest catalyst from the verified news. If no company-specific news explains the move, state that it is tracking broader sector sentiment / tech macro].\n"
            "• **Key Developments to Watch**:\n"
            "  - [Highlight 1-2 verified recent headlines with Publisher and relative time].\n"
            "  - *Why it matters:* [1 sentence on margins, deliveries, AI compute, or earnings impact].\n"
            "• **Bottom Line**: [1-2 sentence executive verdict].\n\n"
            f"*Data verified as of {CURRENT_DATE_STR} {timestamp} | Source: Yahoo Finance Real-time*"
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
                f"📈 **{quote.symbol} Movement Summary**\n\n"
                f"**{quote.symbol}** is trading at **${quote.price:,.2f}** ({sign}{quote.percent_change:.2f}% today).\n"
                f"Volume: {quote.volume:,} | Market Cap: {quote.market_cap_str}\n\n"
                f"*Data retrieved at {timestamp} | Source: MarketDataProvider*"
            )
