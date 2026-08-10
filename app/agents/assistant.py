import logging
import re
from typing import Dict, TypedDict, Annotated, Sequence, Any, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from app.config import settings
from app.agents.tools import financial_tools, update_user_facts
from app.agents.market_movement import MarketMovementAnalyzer
from app.agents.comparison import CompanyComparisonEngine
from app.agents.overview import CompanyOverviewEngine
from app.agents.price_engine import StockPriceEngine
from app.agents.research import DeepResearchEngine
from app.agents.productivity import productivity_tools
from app.market_data import FinancialDataRouter, MarketDataProvider
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# --- AGENT SETUP ---
if settings.openai_api_key:
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model=settings.model_name or "gpt-4o-mini",
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.1
    )
else:
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0.1
    )

# Bind tools to LLM
llm_with_tools = llm.bind_tools(financial_tools + productivity_tools)

# Define State
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_context: str
    user_id: int

def build_system_prompt(user_id: int, user_context: str) -> str:
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    current_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
    return (
        "You are Atlas, an elite institutional AI Financial Analyst and Executive Intelligence Partner.\n"
        f"CURRENT DATE: {current_date} (Time: {now_utc}).\n\n"
        "--- LIVE DATA PRINCIPLES (CRITICAL) ---\n"
        "1. LIVE DATA FIRST: Always use your tools (get_stock_quote, get_market_overview, get_earnings_calendar, get_company_news) to retrieve LIVE data before answering. Never rely on training knowledge for prices, market caps, P/E ratios, or recent events.\n"
        "2. NEVER FABRICATE NUMBERS: If a tool returns no data or the provided context does not contain the answer, explicitly state 'I do not have verified data to determine this'. DO NOT guess or infer numbers.\n"
        "3. UNCERTAINTY OVER CONFIDENCE: If you cannot verify information from live tools, clearly communicate uncertainty: 'Based on available data...' or 'Unable to verify current...' Never present unverified claims as facts.\n"
        "4. SOURCE ATTRIBUTION: Every financial data point must cite its source (Yahoo Finance, Finnhub, specific news publisher, etc.).\n\n"
        "--- CONVERSATIONAL & TIME-SAVING PRINCIPLES ---\n"
        "5. COMMUNICATE NATURALLY: Speak naturally as an experienced financial analyst. Users should never need commands, slash shortcuts, or predefined keywords.\n"
        "6. CONCISE & PURPOSE-DRIVEN: Respect user time. Deliver high-signal, minimum reliable information without AI fluff, conversational stalling, or repetitive disclaimers. DO NOT act like a generic news reader. Synthesize events into actionable intelligence.\n"
        "7. EXECUTIVE ASSISTANCE: Help users with meeting preparation, upcoming schedule checks, or actions using productivity tools.\n"
        "8. DYNAMIC MEMORY & WATCHLIST PERSONALIZATION: Remember the user's role, tracked stocks, and preferences seamlessly. Proactively relate market trends back to their specific watchlist when answering general queries.\n"
        "9. CLEAN FORMATTING: Use ultra-clean Telegram layout with clear icons (📊, 💰, 🏢, 📌, 📰, 💡, 📚). Never output raw markdown '##' headers.\n\n"
        f"--- USER PROFILE & CONTEXT ---\n"
        f"Telegram ID: {user_id}\n"
        f"{user_context}\n"
        "------------------------------\n"
    )

async def agent_node(state: AgentState):
    messages = state["messages"]
    user_context = state.get("user_context", "")
    user_id = state.get("user_id")
    
    sys_content = build_system_prompt(user_id, user_context)
    sys_msg = SystemMessage(content=sys_content)
    
    filtered_messages = [m for m in messages if not isinstance(m, SystemMessage)]
    response = await llm_with_tools.ainvoke([sys_msg] + filtered_messages)
    return {"messages": [response]}

tool_node = ToolNode(financial_tools + productivity_tools)

def should_continue(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

# Build Graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

app = workflow.compile()

# Comprehensive baseline map for fast resolution
KNOWN_TICKER_MAP = {
    # Tech Giants
    "microsoft": "MSFT", "msft": "MSFT",
    "alphabet": "GOOGL", "google": "GOOGL", "googl": "GOOGL", "goog": "GOOGL",
    "apple": "AAPL", "aapl": "AAPL",
    "nvidia": "NVDA", "nvda": "NVDA",
    "tesla": "TSLA", "tsla": "TSLA",
    "amazon": "AMZN", "amzn": "AMZN",
    "meta": "META", "facebook": "META",
    # EVs & Mobility
    "rivian": "RIVN", "rivn": "RIVN",
    "lucid": "LCID", "lcid": "LCID",
    "nio": "NIO",
    "ford": "F",
    "gm": "GM", "general motors": "GM",
    "uber": "UBER",
    # Semiconductors
    "amd": "AMD",
    "tsmc": "TSM", "tsm": "TSM",
    "intel": "INTC", "intc": "INTC",
    "broadcom": "AVGO", "avgo": "AVGO",
    "qualcomm": "QCOM", "qcom": "QCOM",
    "arm": "ARM",
    "asml": "ASML",
    "micron": "MU", "mu": "MU",
    "smci": "SMCI", "super micro": "SMCI",
    # Enterprise & Cloud Software
    "palantir": "PLTR", "pltr": "PLTR",
    "oracle": "ORCL", "orcl": "ORCL",
    "salesforce": "CRM", "crm": "CRM",
    "adobe": "ADBE", "adbe": "ADBE",
    "snowflake": "SNOW", "snow": "SNOW",
    "crowdstrike": "CRWD", "crwd": "CRWD",
    "servicenow": "NOW",
    # Streaming & Crypto
    "netflix": "NFLX", "nflx": "NFLX",
    "spotify": "SPOT", "spot": "SPOT",
    "coinbase": "COIN", "coin": "COIN",
    # Indian Market (NSE)
    "reliance": "RELIANCE.NS", "ril": "RELIANCE.NS",
    "tcs": "TCS.NS",
    "hdfc": "HDFCBANK.NS", "hdfc bank": "HDFCBANK.NS",
    "sbi": "SBIN.NS", "state bank": "SBIN.NS",
    "infosys": "INFY.NS", "infy": "INFY.NS",
    "itc": "ITC.NS",
    "bharti airtel": "BHARTIARTL.NS", "airtel": "BHARTIARTL.NS",
    "icici": "ICICIBANK.NS", "icici bank": "ICICIBANK.NS",
    "zomato": "ZOMATO.NS",
    "tata motors": "TATAMOTORS.NS",
    "tata steel": "TATASTEEL.NS"
}

def extract_tickers(text: str) -> List[str]:
    """
    Extracts tickers dynamically using direct mapping, uppercase symbols regex,
    and fallback symbol search for global equities.
    """
    found = []
    # If text is a long document injection, do NOT perform aggressive extraction
    if "[DOCUMENT UPLOADED:" in text or "--- DOCUMENT TEXT" in text or "[The user previously uploaded" in text:
        words = re.findall(r'\b[A-Za-z0-9\.\-]+\b', text.lower())
        for w in words:
            if w in KNOWN_TICKER_MAP:
                sym = KNOWN_TICKER_MAP[w]
                if sym not in found:
                    found.append(sym)
        return found

    # 1. Match against known names & aliases
    text_lower = text.lower()
    for name, sym in KNOWN_TICKER_MAP.items():
        if re.search(r'\b' + re.escape(name) + r'\b', text_lower):
            if sym not in found:
                found.append(sym)
                
    # 2. Check for explicit uppercase tickers in original text (e.g. RIVN, TSLA, AAPL, RELIANCE.NS)
    stopwords = [
        "A", "I", "AN", "THE", "AND", "OR", "VS", "IS", "ON", "IN", "AT", "TO", "FOR", "OF", "WITH", "BY",
        "DOCUMENT", "UPLOADED", "TEXT", "END", "USER", "REQUEST", "QUESTION", "PDF", "REPORT", "EXECUTIVE",
        "SUMMARY", "IMPORTANT", "FINANCIAL", "FY", "Q1", "Q2", "Q3", "Q4", "CEO", "CFO", "CTO", "AI", "EPS",
        "USD", "INR", "EUR", "GBP", "ALL", "NEW", "TODAY", "YESTERDAY", "NOW", "CHECK", "WHAT", "HOW", "WHY"
    ]
    raw_upper_words = re.findall(r'\b[A-Z]{1,10}(?:\.[A-Z]{1,2})?\b', text)
    for w in raw_upper_words:
        if w not in stopwords:
            if w not in found:
                found.append(w)
                
    # 3. Dynamic lookup if still not found and user query appears company-specific
    if not found and len(text.split()) <= 6:
        clean_name = re.sub(r'\b(what is|the|stock|share|price|of|tell me about|how much is|cmp|rate|quote)\b', '', text_lower).strip()
        if clean_name and len(clean_name) > 2:
            resolved = FinancialDataRouter.search_symbol(clean_name)
            if resolved and resolved not in found:
                found.append(resolved)
                
    return found

class AtlasAgentService:
    @staticmethod
    async def process_message(user_id: int, user_input: str) -> str:
        from app.services import get_or_create_user, save_message, get_recent_chat_history, update_user_profile
        user = await get_or_create_user(user_id)
        chat_history = await get_recent_chat_history(user_id, limit=6)
        
        # Build dynamic context block
        ctx_parts = []
        if user.role:
            ctx_parts.append(f"User Role: {user.role}")
        if user.watch_list:
            ctx_parts.append(f"Active Watchlist: {', '.join(user.watch_list)}")
        if user.interests:
            ctx_parts.append(f"Focus Sectors: {', '.join(user.interests)}")
        if user.preferred_insights:
            ctx_parts.append(f"Preferred Insights: {', '.join(user.preferred_insights)}")
        if user.briefing_time:
            ctx_parts.append(f"Briefing Time: {user.briefing_time}")
        if user.connected_accounts:
            ctx_parts.append(f"Connected Integrations: {', '.join(user.connected_accounts)}")
            
        lower_input = user_input.lower().strip()

        # --- DYNAMIC BACKGROUND LEARNING: Natural Role / Sector / Watchlist Extraction ---
        if any(w in lower_input for w in ["i am a", "i'm a", "as an investor", "as a founder", "as an analyst"]):
            for role_candidate in ["Investor", "Analyst", "Founder", "Trader", "Portfolio Manager", "Executive", "Student"]:
                if role_candidate.lower() in lower_input:
                    await update_user_profile(user_id, {"role": role_candidate})
                    user.role = role_candidate
                    break

        # --- SPECIAL CASE: Financial Document Intelligence ---
        # When a document is uploaded or queried, answer directly from document context
        if "[DOCUMENT UPLOADED:" in user_input or "--- DOCUMENT TEXT" in user_input or "[The user previously uploaded" in user_input:
            logger.info("Routing to direct Document Intelligence processor.")
            doc_response = await llm.ainvoke([HumanMessage(content=user_input)])
            content = doc_response.content
            if isinstance(content, list):
                text_parts = [p["text"] if isinstance(p, dict) and "text" in p else str(p) for p in content]
                final_res = "".join(text_parts)
            else:
                final_res = str(content)
            await save_message(user_id, "user", user_input)
            await save_message(user_id, "assistant", final_res)
            return final_res

        tickers = extract_tickers(user_input)
        
        if tickers:
            ctx_parts.append(f"Detected Tickers in Context: {', '.join(tickers)}")
            
            # --- AMBIGUITY CHECK (Clarify before guessing) ---
            info_markers = ["price", "news", "compare", "vs", "earnings", "financials", "overview", "chart", "trend", "buy", "sell", "dividend", "performance", "add", "track", "remove"]
            has_info_marker = any(marker in lower_input for marker in info_markers)
            
            is_generic_tell = "tell me about" in lower_input and not has_info_marker
            is_bare_ticker = len(user_input.split()) <= 3 and not has_info_marker
            
            if is_generic_tell or is_bare_ticker:
                response = f"What specifically would you like to know about {tickers[0]}? (e.g. latest price, recent news, or a general overview)"
                await save_message(user_id, "user", user_input)
                await save_message(user_id, "assistant", response)
                return response
                
        user_context = "\n".join(ctx_parts) if ctx_parts else "Standard Investor Profile"
        
        # --- CONVERSATIONAL WATCHLIST MANAGEMENT (Zero command navigation) ---
        if any(phrase in lower_input for phrase in ["add to my watchlist", "track this stock", "add to watchlist", "track stock"]):
            if tickers:
                current_wl = list(user.watch_list or [])
                added = []
                for t in tickers:
                    if t not in current_wl:
                        current_wl.append(t)
                        added.append(t)
                await update_user_profile(user_id, {"watch_list": current_wl})
                added_str = ", ".join(added) if added else tickers[0]
                response = f"✅ Added {added_str} to your watchlist.\nI will monitor updates for your morning briefings."
                await save_message(user_id, "user", user_input)
                await save_message(user_id, "assistant", response)
                return response

        if any(phrase in lower_input for phrase in ["my watchlist", "show my watchlist", "view watchlist", "what am i tracking"]):
            wl = user.watch_list or []
            if not wl:
                response = "Your watchlist is empty. Tell me which stocks you'd like to track (e.g. 'Add NVDA and TSLA to my watchlist')."
                await save_message(user_id, "user", user_input)
                await save_message(user_id, "assistant", response)
                return response
            quotes_summary = []
            for sym in wl:
                q = MarketDataProvider.get_quote(sym)
                if q:
                    sign = "+" if q.percent_change >= 0 else ""
                    curr = "₹" if q.currency == "INR" or q.symbol.endswith((".NS", ".BO")) else ("€" if q.currency == "EUR" else ("£" if q.currency == "GBP" else "$"))
                    quotes_summary.append(f"• {q.symbol}: {curr}{q.price:,.2f} ({sign}{q.percent_change:.2f}%)")
                else:
                    quotes_summary.append(f"• {sym}: Tracking")
            response = f"📋 Your Watchlist ({len(wl)} stocks)\n\n" + "\n".join(quotes_summary)
            await save_message(user_id, "user", user_input)
            await save_message(user_id, "assistant", response)
            return response
            
        # --- ALERT CREATION ---
        if any(phrase in lower_input for phrase in ["notify me", "alert me", "tell me if", "let me know if"]):
            if tickers:
                symbol = tickers[0]
                q = MarketDataProvider.get_quote(symbol)
                
                condition = "drop_percent" if any(w in lower_input for w in ["drop", "fall", "down"]) else "up_percent"
                
                import re
                nums = re.findall(r'\d+(?:\.\d+)?', lower_input)
                threshold = float(nums[0]) if nums else 5.0 # Default 5%
                
                new_alert = {
                    "ticker": symbol,
                    "condition": condition,
                    "threshold": threshold,
                    "base_price": q.price if q else 0.0
                }
                
                current_alerts = list(user.alerts or [])
                current_alerts.append(new_alert)
                await update_user_profile(user_id, {"alerts": current_alerts})
                
                dir_str = "drops" if condition == "drop_percent" else "moves up"
                response = f"🔔 Alert set: I will notify you if {symbol} {dir_str} by {threshold}% from its current price."
                if not q:
                    response += " (Waiting for market data connection to set base price)."
                    
                await save_message(user_id, "user", user_input)
                await save_message(user_id, "assistant", response)
                return response

        # --- INTENT 0: Morning & Evening Briefings ---
        if any(phrase in lower_input for phrase in ["morning brief", "morning briefing", "daily brief", "daily briefing", "market overview", "market brief", "what should i know today", "what's happening today", "market-moving events", "biggest market-moving", "market intelligence"]):
            await save_message(user_id, "assistant", "Generating your curated morning brief...")
            from app.scheduler import generate_curated_morning_brief
            user_dict = {
                "telegram_id": user_id,
                "watch_list": user.watch_list or [],
                "role": user.role,
                "interests": user.interests
            }
            brief_res = await generate_curated_morning_brief(user_dict)
            await save_message(user_id, "user", user_input)
            await save_message(user_id, "assistant", brief_res)
            return brief_res

        if any(phrase in lower_input for phrase in ["evening wrap", "evening summary", "market close", "market summary", "end of day", "close wrap"]):
            from app.scheduler import generate_curated_evening_wrap
            user_dict = {
                "telegram_id": user_id,
                "watch_list": user.watch_list or [],
                "role": user.role,
                "interests": user.interests
            }
            wrap_res = await generate_curated_evening_wrap(user_dict)
            await save_message(user_id, "user", user_input)
            await save_message(user_id, "assistant", wrap_res)
            return wrap_res

        # Contextual multi-turn comparison resolution ONLY when user says "compare it with X" or "compare with X"
        if len(tickers) == 1 and any(phrase in lower_input for phrase in ["compare it with", "compare with", "versus it", "vs it", "now compare to", "compare against"]):
            for prev_msg in reversed(chat_history):
                prev_tickers = extract_tickers(prev_msg.get("content", ""))
                for pt in prev_tickers:
                    if pt not in tickers:
                        tickers.append(pt)
                        break
                if len(tickers) >= 2:
                    break
                    
        # --- INTENT 1: Company Comparison ---
        if ("compare" in lower_input or "versus" in lower_input or " vs " in lower_input) and len(tickers) >= 2:
            logger.info(f"Routing to specialized CompanyComparisonEngine for {tickers[0]} and {tickers[1]}")
            response = await CompanyComparisonEngine.compare(tickers[0], tickers[1], llm)
            await save_message(user_id, "user", user_input)
            await save_message(user_id, "assistant", response)
            return response
            
        # --- INTENT 2: Price Action & Catalyst Movement ---
        if any(phrase in lower_input for phrase in ["why is", "why did", "what moved", "catalyst", "moving today", "dropping today", "surging today"]) and tickers:
            logger.info(f"Routing to specialized MarketMovementAnalyzer for {tickers[0]}")
            response = await MarketMovementAnalyzer.analyze_movement(tickers[0], llm)
            await save_message(user_id, "user", user_input)
            await save_message(user_id, "assistant", response)
            return response

        # --- INTENT 3: Deep Research (public OR private, any entity, any question) ---
        is_productivity_query = any(word in lower_input for word in [
            "email", "emails", "inbox", "calendar", "meeting", "schedule",
            "sync", "remind", "to-do", "task"
        ])
        
        PRIVATE_ENTITY_NAMES = ["openai", "anthropic", "spacex", "stripe", "databricks", "bytedance", "anduril", "figma", "canva", "discord", "notion", "scale ai", "hugging face", "mistral", "cohere", "perplexity"]
        is_private_entity = any(name in lower_input for name in PRIVATE_ENTITY_NAMES)
        is_deep_research = any(phrase in lower_input for phrase in [
            "deep dive", "research", "financial performance", "earnings summary",
            "leadership", "funding", "valuation", "m&a", "merger", "acquisition",
            "regulatory filing", "10-k", "10-q", "sec filing", "market sentiment",
            "industry trends", "risks", "moat", "competitive"
        ])
        if not is_productivity_query and (is_private_entity or (is_deep_research and (tickers or len(lower_input.split()) <= 5))):
            logger.info(f"Routing to DeepResearchEngine for query: {user_input}")
            response = await DeepResearchEngine.research_entity(user_input, llm)
            await save_message(user_id, "user", user_input)
            await save_message(user_id, "assistant", response)
            return response

        # --- INTENT 3.5: Instant Price Lookup (Minimum Reliable Info) ---
        is_price_query = any(phrase in lower_input for phrase in [
            "price", "quote", "how much is", "trading at", "what is the price",
            "stock price", "share price", "ka price", "price kya", "current price",
            "cmp", "market price", "rate kya", "kya bhav", "bhav kya"
        ]) or (len(tickers) == 1 and any(w in lower_input.split() for w in ["price", "quote", "cmp", "rate", "cost"]))
        is_movement_or_deep = any(phrase in lower_input for phrase in [
            "why is", "why did", "what moved", "catalyst", "deep dive", "research",
            "compare", "versus", "tell me about", "overview"
        ])
        if is_price_query and not is_movement_or_deep and tickers:
            logger.info(f"Routing to StockPriceEngine for {tickers[0]}")
            response = StockPriceEngine.get_price(tickers[0])
            await save_message(user_id, "user", user_input)
            await save_message(user_id, "assistant", response)
            return response

        # --- INTENT 4: Company Overview / Research Profile ---
        is_overview_prompt = any(phrase in lower_input for phrase in ["tell me about", "overview of", "profile of", "analyze", "summary of"]) or (
            len(tickers) == 1 and not is_price_query and any(phrase in lower_input for phrase in ["what is", "who is"])
        ) or (len(tickers) == 1 and len(lower_input.split()) <= 2 and not is_price_query)
        if is_overview_prompt and tickers:
            logger.info(f"Routing to specialized CompanyOverviewEngine for {tickers[0]}")
            response = await CompanyOverviewEngine.get_overview(tickers[0], llm)
            await save_message(user_id, "user", user_input)
            await save_message(user_id, "assistant", response)
            return response
            
        # --- INTENT 5: Standard Stateful LangGraph Engine (Conversational Intelligence) ---
        messages = []
        for msg in chat_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
                
        messages.append(HumanMessage(content=user_input))
        
        inputs = {
            "messages": messages,
            "user_context": user_context,
            "user_id": user_id
        }
        
        config = {"configurable": {"thread_id": str(user_id)}}
        result = await app.ainvoke(inputs, config=config)
        
        final_answer = "I processed your request, but could not synthesize a verified response. Please try rephrasing."
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                content = msg.content
                if isinstance(content, list):
                    text_parts = []
                    for p in content:
                        if isinstance(p, dict) and "text" in p:
                            text_parts.append(p["text"])
                        elif isinstance(p, str):
                            text_parts.append(p)
                    final_answer = "".join(text_parts)
                else:
                    final_answer = str(content)
                break
                
        await save_message(user_id, "user", user_input)
        await save_message(user_id, "assistant", final_answer)
        return final_answer

atlas_agent = AtlasAgentService()
