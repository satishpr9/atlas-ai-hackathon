import logging
from typing import Dict, TypedDict, Annotated, Sequence, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from app.config import settings
from app.services import update_user_profile

logger = logging.getLogger(__name__)

# --- TOOLS ---
@tool
async def update_preferences(role: str = None, interests: list[str] = None, watch_list: list[str] = None, user_id: int = None) -> str:
    """
    Call this tool whenever you learn new information about the user's professional role, financial interests, or specific stocks/companies they want to watch.
    Only pass the fields that need to be updated.
    """
    if not user_id:
        return "Error: Missing user_id"
    
    updates = {}
    if role: updates["role"] = role
    
    # We use MongoDB $addToSet logic or just fetch and append in the service, 
    # but for simplicity we will just log it here and use a specific service function if needed.
    # To keep it simple, we'll let the service handle the $push
    from app.database import db
    users_collection = db.get_db()["users"]
    
    update_ops = {"$set": {"updated_at": __import__('datetime').datetime.utcnow()}}
    if role: update_ops["$set"]["role"] = role
    
    push_ops = {}
    if interests:
        push_ops["interests"] = {"$each": interests}
    if watch_list:
        push_ops["watch_list"] = {"$each": watch_list}
        
    if push_ops:
        update_ops["$addToSet"] = push_ops

    await users_collection.update_one({"telegram_id": user_id}, update_ops)
    return f"Successfully updated preferences for user {user_id}."

from app.agents.tools import financial_tools
tools = [update_preferences] + financial_tools

# --- AGENT SETUP ---
if settings.openai_api_key:
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model=settings.model_name or "gpt-4o-mini",
        openai_api_key=settings.openai_api_key,
        openai_api_base=settings.openai_base_url,
        temperature=0.2
    )
else:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0.2
    )

# Bind tools to LLM
llm_with_tools = llm.bind_tools(tools)

# Define State
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_context: str
    user_id: int

# Define Nodes
async def agent_node(state: AgentState):
    messages = state["messages"]
    user_context = state.get("user_context", "")
    user_id = state.get("user_id")
    
    sys_content = (
        "You are an AI-powered Financial Assistant for finance professionals, communicating via Telegram.\n"
        "You are conversational, intelligent, highly articulate, and concise. Never act like a generic chatbot or command-line bot.\n\n"
        "--- ONBOARDING & CONVERSATION GUIDELINES ---\n"
        "1. If this is a new user (or their profile has Unknowns), guide them naturally through a smooth, conversational onboarding.\n"
        "2. Don't ask all onboarding questions at once. Ask one or two natural questions at a time:\n"
        "   - Understand their role (e.g., Investor, Analyst, Founder, Portfolio Manager).\n"
        "   - Ask what specific companies, sectors, or macro themes they actively track.\n"
        "   - Ask what insights matter most to them (e.g., Earnings calls, SEC filings, Breaking News, Daily Morning Briefings).\n"
        "3. Whenever they mention their role, companies of interest, or watchlist tickers, ALWAYS immediately invoke the `update_preferences` tool to save it.\n"
        "4. The user can skip any onboarding question at any time and ask direct financial questions—seamlessly switch to answering them with live data tools.\n\n"
        f"--- CURRENT USER PROFILE ---\n"
        f"Telegram ID: {user_id}\n"
        f"{user_context}\n"
        "----------------------------\n"
    )
    
    # Ensure system message is first
    sys_msg = SystemMessage(content=sys_content)
    # Filter out old system messages to prevent duplication
    filtered_messages = [m for m in messages if not isinstance(m, SystemMessage)]
    
    response = await llm_with_tools.ainvoke([sys_msg] + filtered_messages)
    return {"messages": [response]}

# Tool Node
tool_node = ToolNode(tools)

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

async def process_user_input(user_id: int, user_input: str, chat_history: list[Dict[str, str]], user_context: str) -> str:
    """
    Process input with history.
    chat_history: list of dicts like {"role": "user", "content": "hello"}
    """
    # Convert history dicts to LangChain messages
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
    
    # Ainvoke the graph
    result = await app.ainvoke(inputs, config=config)
    
    # Extract the final AI response (ignoring tool messages)
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            if isinstance(msg.content, list):
                text_parts = []
                for part in msg.content:
                    if isinstance(part, dict) and "text" in part:
                        text_parts.append(part["text"])
                    elif isinstance(part, str):
                        text_parts.append(part)
                return "".join(text_parts)
            return str(msg.content)
            
    return "I processed your request but have no textual response."
