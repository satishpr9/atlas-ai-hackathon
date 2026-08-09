from datetime import datetime, timezone
from app.market_data import FinancialDataRouter
from app.agents.overview import BRAND_MAP

class StockPriceEngine:
    """
    Dedicated minimal engine for instant PRICE_LOOKUP queries.
    Strictly adheres to minimum reliable information: no AI hallucination,
    instant speed, exact verification.
    """
    @classmethod
    def get_price(cls, symbol: str) -> str:
        quote = FinancialDataRouter.get_quote(symbol)
        if not quote:
            return f"Unable to retrieve verified market quote for '{symbol.upper()}'."
        
        brand_name = BRAND_MAP.get(quote.symbol, quote.name.split(',')[0].split('(')[0].strip() if quote.name else quote.symbol)
        sign = "+" if quote.percent_change >= 0 else ""
        vol_str = f"{quote.volume / 1_000_000:.1f}M" if quote.volume >= 1_000_000 else f"{quote.volume:,}"
        pe_str = f"\nP/E: {quote.pe_ratio:.1f}x" if quote.pe_ratio else ""
        vol_line = f"\nVolume: {vol_str}" if quote.volume > 0 else ""
        
        curr_sym = "₹" if quote.symbol.endswith((".NS", ".BO")) else "$"
        now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
        
        return (
            f"📈 {brand_name} ({quote.symbol})\n\n"
            f"{curr_sym}{quote.price:,.2f} · {sign}{quote.percent_change:.2f}% today\n\n"
            f"Market cap: {quote.market_cap_str}{pe_str}{vol_line}\n\n"
            f"As of Aug 9, 2026 · {now_utc}\n"
            f"Source: {quote.source}\n\n"
            f"Want the latest {brand_name} news or an explanation of today's move?"
        )
