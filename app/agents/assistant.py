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
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CURRENT_DATE_STR = "August 9, 2026"

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
llm_with_tools = llm.bind_tools(financial_tools)

# Define State
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_context: str
    user_id: int

def build_system_prompt(user_id: int, user_context: str) -> str:
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        "You are Atlas, an elite institutional AI Financial Assistant designed for investors, analysts, founders, and finance professionals.\n"
        f"CURRENT CALENDAR DATE: {CURRENT_DATE_STR} (Current Time: {now_utc}). Year is 2026.\n\n"
        "--- ONBOARDING & CONVERSATIONAL INTELLIGENCE ---\n"
        "1. WELCOMING & NATURAL ONBOARDING: When a user introduces themselves or shares their background (role, watchlist, sectors, or preferred notification time):\n"
        "   - Always use the 'update_user_facts' tool to store their role, interests, watchlist, or preferences.\n"
        "   - Respond warmly and acknowledge their focus. Naturally mention that they can connect accounts (Google Drive for earnings reports/models, Google Calendar for earnings events) and receive daily morning briefings.\n"
        "   - Keep it conversational—never present a rigid registration form.\n"
        "2. ZERO BOT FLUFF ON ANALYSIS: When answering market analysis, comparisons, or quotes, use the ultra-clean Telegram format with intuitive icons (📊, 💰, 🏢, 📰, 💡, 📚). Never use raw markdown '##' headers.\n"
        "3. GROUND TRUTH & ACCURACY: Never hallucinate unverified financial numbers, technical support levels, or causal relationships.\n"
        "4. CONTINUOUS LEARNING: Over time, remember and adapt to the user's explicit preferences and workflow.\n\n"
        f"--- USER PROFILE & MEMORY ---\n"
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

tool_node = ToolNode(financial_tools)

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

# Helper to identify tickers in text
KNOWN_TICKER_MAP = {
    "microsoft": "MSFT", "msft": "MSFT",
    "alphabet": "GOOGL", "google": "GOOGL", "googl": "GOOGL", "goog": "GOOGL",
    "apple": "AAPL", "aapl": "AAPL",
    "nvidia": "NVDA", "nvda": "NVDA",
    "tesla": "TSLA", "tsla": "TSLA",
    "amazon": "AMZN", "amzn": "AMZN",
    "meta": "META", "facebook": "META",
    "amd": "AMD",
    "tsmc": "TSM", "tsm": "TSM",
    "palantir": "PLTR", "pltr": "PLTR",
    "intel": "INTC", "intc": "INTC"
}

def extract_tickers(text: str) -> List[str]:
    found = []
    words = re.findall(r'\b[A-Za-z0-9\.\-]+\b', text.lower())
    for w in words:
        if w in KNOWN_TICKER_MAP:
            sym = KNOWN_TICKER_MAP[w]
            if sym not in found:
                found.append(sym)
    return found

class AtlasAgentService:
    @staticmethod
    async def process_message(user_id: int, user_input: str) -> str:
        from app.services import get_or_create_user, save_message, get_recent_chat_history
        
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
            
        user_context = "\n".join(ctx_parts) if ctx_parts else "Standard Investor Profile"
        
        lower_input = user_input.lower()
        tickers = extract_tickers(user_input)
        
        # 0. Natural Morning & Evening Briefing Intents
        if any(phrase in lower_input for phrase in ["morning brief", "morning briefing", "daily brief", "daily briefing", "market overview", "market brief"]):
            from app.scheduler import generate_curated_morning_brief
            user_dict = {
                "telegram_id": user_id,
                "watch_list": user.watch_list or ["NVDA", "AAPL", "MSFT"],
                "role": user.role,
                "interests": user.interests
            }
            brief_res = await generate_curated_morning_brief(user_dict)
            await save_message(user_id, "user", user_input)
            await save_message(user_id, "assistant", brief_res)
            return brief_res

        if any(phrase in lower_input for phrase in ["evening wrap", "evening summary", "market close", "market summary", "end of day"]):
            from app.scheduler import generate_curated_evening_wrap
            user_dict = {
                "telegram_id": user_id,
                "watch_list": user.watch_list or ["NVDA", "AAPL", "MSFT"],
                "role": user.role,
                "interests": user.interests
            }
            wrap_res = await generate_curated_evening_wrap(user_dict)
            await save_message(user_id, "user", user_input)
            await save_message(user_id, "assistant", wrap_res)
            return wrap_res

        # Contextual resolution: If user asks "Compare with Google" and prior message was about MSFT
        if len(tickers) == 1 and ("compare" in lower_input or "versus" in lower_input or " vs " in lower_input):
            for prev_msg in reversed(chat_history):
                prev_tickers = extract_tickers(prev_msg.get("content", ""))
                for pt in prev_tickers:
                    if pt not in tickers:
                        tickers.append(pt)
                        break
                if len(tickers) >= 2:
                    break
                    
        # 1. Specialized Comparison Engine
        if ("compare" in lower_input or "versus" in lower_input or " vs " in lower_input) and len(tickers) >= 2:
            logger.info(f"Routing to specialized CompanyComparisonEngine for {tickers[0]} and {tickers[1]}")
            response = await CompanyComparisonEngine.compare(tickers[0], tickers[1], llm)
            await save_message(user_id, "user", user_input)
            await save_message(user_id, "assistant", response)
            return response
            
        # 2. Specialized Catalyst / Movement Engine
        if any(phrase in lower_input for phrase in ["why is", "why did", "what moved", "catalyst", "moving today", "dropping today", "surging today"]) and tickers:
            logger.info(f"Routing to specialized MarketMovementAnalyzer for {tickers[0]}")
            response = await MarketMovementAnalyzer.analyze_movement(tickers[0], llm)
            await save_message(user_id, "user", user_input)
            await save_message(user_id, "assistant", response)
            return response
            
        # 3. Standard Stateful LangGraph Engine (handles natural onboarding, questions, facts)
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
