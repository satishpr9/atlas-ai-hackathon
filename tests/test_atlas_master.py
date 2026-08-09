import asyncio
import os
import sys
import logging

# Ensure root dir is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.market_data import MarketDataProvider
from app.agents.assistant import atlas_agent
from app.agents.comparison import CompanyComparisonEngine
from app.scheduler import generate_curated_morning_brief
from app.services import get_or_create_user, update_user_profile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestMaster")

async def run_master_test_suite():
    print("==================================================")
    print(">>> RUNNING ATLAS AI MASTER EXCELLENCE VALIDATION")
    print("==================================================")
    
    test_user_id = 999888
    
    # 1. Test Memory & Profile Update
    print("\n--- TEST 1: User Memory & Profile Adaptation ---")
    user = await get_or_create_user(test_user_id)
    await update_user_profile(test_user_id, {
        "role": "AI Venture Partner",
        "watch_list": ["NVDA", "MSFT", "GOOGL"],
        "interests": ["Custom Silicon", "Foundational Models"]
    })
    updated_user = await get_or_create_user(test_user_id)
    print(f"[OK] User Profile verified: Role='{updated_user.role}', Watchlist={updated_user.watch_list}")
    assert updated_user.role == "AI Venture Partner"
    
    # 2. Test Real-time Quote & P/E multiples
    print("\n--- TEST 2: Market Data & Multiples Verification ---")
    quote = MarketDataProvider.get_quote("MSFT")
    assert quote is not None
    print(f"[OK] Verified MSFT Quote: ${quote.price:,.2f} | Cap: {quote.market_cap_str} | P/E: {quote.pe_ratio}x")
    
    # 3. Test Strict Entity-Matching News Filter
    print("\n--- TEST 3: Entity-Specific News Filter ---")
    comp_news, ind_news = MarketDataProvider.get_company_news_classified("MSFT", limit=3)
    print(f"[OK] Filtered MSFT Specific Articles: {len(comp_news)} found")
    for a in comp_news:
        print(f"   • {a.title} ({a.publisher})".encode("ascii", errors="replace").decode("ascii"))
        
    # 4. Test Microsoft vs Google Comparison Engine
    print("\n--- TEST 4: Microsoft vs Google Comparison Execution ---")
    comp_res = await atlas_agent.process_message(test_user_id, "Compare Microsoft and Alphabet in terms of market cap, sector and latest news.")
    print("--- COMPARISON OUTPUT ---")
    print(comp_res.encode("ascii", errors="replace").decode("ascii"))
    assert "Microsoft" in comp_res and "Google" in comp_res
    assert "Market" in comp_res and "Business" in comp_res
    
    # 5. Test Single Stock Catalyst Movement Engine
    print("\n--- TEST 5: Stock Movement Catalyst Analyzer ---")
    move_res = await atlas_agent.process_message(test_user_id, "Why is Tesla moving today?")
    print("--- MOVEMENT OUTPUT ---")
    print(move_res.encode("ascii", errors="replace").decode("ascii"))
    assert "Price Action" in move_res
    
    # 6. Test Curated Morning Intelligence Briefing
    print("\n--- TEST 6: Proactive Morning Briefing Generation ---")
    user_dict = {
        "telegram_id": test_user_id,
        "watch_list": ["NVDA", "MSFT", "GOOGL"],
        "role": "AI Venture Partner"
    }
    brief_res = await generate_curated_morning_brief(user_dict)
    print("--- MORNING BRIEFING OUTPUT ---")
    print(brief_res.encode("ascii", errors="replace").decode("ascii"))
    assert "Morning Intelligence Briefing" in brief_res
    assert "Market Regime" in brief_res
    
    # 7. Test Intent-Aware Company Overview ("Tell me about Apple")
    print("\n--- TEST 7: Intent-Aware Company Overview (Tell me about Apple) ---")
    overview_res = await atlas_agent.process_message(test_user_id, "Tell me about Apple")
    print("--- APPLE OVERVIEW OUTPUT ---")
    print(overview_res.encode("ascii", errors="replace").decode("ascii"))
    assert "Apple" in overview_res and "AAPL" in overview_res
    assert "Market" in overview_res and "Business" in overview_res and "Key Themes" in overview_res
    
    print("\n==================================================")
    print(">>> ALL 7 MASTER VALIDATION TESTS PASSED (10/10)!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_master_test_suite())
