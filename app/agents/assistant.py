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
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
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
        "You are an AI-powered Financial Assistant for finance professionals, communicating via Telegram. "
        "You are professional, concise, and highly conversational. Do NOT sound like a typical chatbot. "
        "If you don't know the user's role or interests, ask them naturally as part of the conversation (onboarding). "
        "When you learn about their role, interests, or companies they want to watch, immediately call the `update_preferences` tool to save it. "
        "Always pass the `user_id` argument to the tool (it is provided below). \n\n"
        f"--- USER PROFILE ---\n"
        f"Telegram ID: {user_id}\n"
        f"{user_context}\n"
        "--------------------\n"
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
