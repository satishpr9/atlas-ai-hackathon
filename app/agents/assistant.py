import logging
from typing import Dict, TypedDict, Annotated, Sequence, Any, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from app.config import settings
from app.agents.tools import financial_tools, update_user_facts
from app.agents.market_movement import MarketMovementAnalyzer
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CURRENT_DATE_STR = "August 8, 2026"

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

# System Prompt with Strict Financial Principles
def build_system_prompt(user_id: int, user_context: str) -> str:
    return (
        "You are Atlas, an elite AI Financial Assistant designed for institutional and private equity investors, analysts, and founders.\n"
        f"CURRENT DATE & TIME: {CURRENT_DATE_STR} (Current Year is 2026).\n\n"
        "--- CRITICAL OPERATIONAL PRINCIPLES ---\n"
        "1. TEMPORAL ACCURACY: Never treat past events (e.g. 2024 elections, 2025 events) as today's catalysts. Always anchor analysis to August 2026.\n"
        "2. CONCISE & PURPOSEFUL: Answer the exact question asked and STOP. Do NOT add unnecessary conversational fluff, unsolicited questions, or generic small talk at the end of answers.\n"
        "3. CITATIONS & TIMESTAMPS: Every market metric or price must clearly state its source and timestamp (e.g. 'Data as of: Aug 8, 2026 | Source: Yahoo Finance').\n"
        "4. CONTEXT RESOLUTION: When the user asks to compare 'the companies I just mentioned' (e.g. NVDA, AMD, TSM), compare ONLY those exact companies. Do not pull in other unmentioned watchlist items unless requested.\n"
        "5. SEPARATION OF FACTS VS ANALYSIS: Clearly distinguish verified hard data (revenue, market cap, % move) from analyst interpretation/sentiment.\n"
        "6. FACTUAL MEMORY ONLY: If the user says they are a 'Founder', record ONLY 'Founder'. Never hallucinate or merge roles (e.g. 'Founder and Analyst') unless explicitly confirmed.\n"
        "7. SPECIALIZED CATALYST ANALYSIS: When asked 'Why did a stock move?' or 'What are the catalysts?', use your financial tools to verify today's price action and recent news first.\n\n"
        f"--- USER CONTEXT & EXPLICIT PREFERENCES ---\n"
        f"Telegram ID: {user_id}\n"
        f"{user_context}\n"
        "--------------------------------------------\n"
    )

async def agent_node(state: AgentState):
    messages = state["messages"]
    user_context = state.get("user_context", "")
    user_id = state.get("user_id")
    
    sys_content = build_system_prompt(user_id, user_context)
    sys_msg = SystemMessage(content=sys_content)
    
    # Filter out old system messages to ensure the latest current date prompt is active
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

# Build StateGraph
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

app = workflow.compile()

async def process_user_input(user_id: int, user_input: str, chat_history: List[Dict[str, str]], user_context: str) -> str:
    """
    Main entry point for processing conversational requests with single-response ownership.
    """
    # 1. Specialized Fast-Path for Catalyst / Movement Questions (e.g. "Why is Tesla moving?")
    lower_input = user_input.lower()
    if any(phrase in lower_input for phrase in ["why is", "why did", "what moved", "catalyst", "catalysts", "moving today", "dropping today", "surging today"]):
        # Extract potential ticker
        words = [w.strip("?,.!") for w in user_input.split()]
        known_tickers = ["TSLA", "AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "AMD", "TSM", "PLTR", "INTC"]
        target_ticker = None
        for w in words:
            if w.upper() in known_tickers:
                target_ticker = w.upper()
                break
            # Check for names
            if "tesla" in lower_input: target_ticker = "TSLA"
            elif "nvidia" in lower_input: target_ticker = "NVDA"
            elif "apple" in lower_input: target_ticker = "AAPL"
            elif "microsoft" in lower_input: target_ticker = "MSFT"
            elif "google" in lower_input or "alphabet" in lower_input: target_ticker = "GOOGL"
            elif "amd" in lower_input: target_ticker = "AMD"
            elif "tsmc" in lower_input: target_ticker = "TSM"
            
        if target_ticker:
            logger.info(f"Routing to specialized MarketMovementAnalyzer for {target_ticker}")
            return await MarketMovementAnalyzer.analyze_movement(target_ticker, llm)

    # 2. Standard Conversational & Multi-tool Pipeline
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
    
    # Extract the final AI response (single response owner)
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
                return "".join(text_parts)
            return str(content)
            
    return "I processed your request, but could not synthesize a verified response. Please try rephrasing."
