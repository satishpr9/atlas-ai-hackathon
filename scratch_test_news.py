import yfinance as yf
import json

for sym in ["MSFT", "GOOGL", "AAPL", "NVDA", "TSLA"]:
    t = yf.Ticker(sym)
    news = t.news
    print(f"=== {sym} News Count: {len(news) if news else 0} ===")
    if news:
        print("Sample item keys:", list(news[0].keys()))
        print("Sample item:", json.dumps(news[0], indent=2, default=str)[:500])
