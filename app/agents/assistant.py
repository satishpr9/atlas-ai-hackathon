import logging
from typing import Dict, TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize the Gemini Model
# We use gemini-1.5-pro for complex reasoning
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",
    google_api_key=settings.gemini_api_key,
    temperature=0.2
)

# Define the State
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    # We can add user preferences or profile data here
    user_context: str

# Define nodes
def call_model(state: AgentState):
    messages = state["messages"]
    user_context = state.get("user_context", "")
    
    # Prepend System Prompt
    system_prompt = SystemMessage(
        content=(
            "You are an AI-powered Financial Assistant for finance professionals. "
            "You communicate naturally, concisely, and professionally. "
            "Do NOT act like a generic AI chatbot. You act as an experienced financial analyst. "
            "Avoid formatting with markdown unless absolutely necessary for tables or lists. "
            "When answering questions, provide the 'why' behind the facts.\n\n"
            f"User Context:\n{user_context}"
        )
    )
    
    # We shouldn't duplicate the system prompt if it's already there, but for simplicity:
    # A robust approach filters out existing system messages and prepends the latest.
    filtered_messages = [m for m in messages if not isinstance(m, SystemMessage)]
    messages_with_sys = [system_prompt] + filtered_messages
    
    response = llm.invoke(messages_with_sys)
    return {"messages": [response]}

# Build the Graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_edge(START, "agent")
workflow.add_edge("agent", END)

# Compile
app = workflow.compile()

async def process_user_input(user_id: int, user_input: str, user_context: str = "") -> str:
    """
    Process the user's input through the LangGraph workflow.
    """
    # In a real app, we would load the history from MongoDB here using user_id
    # For now, we just pass the human message
    inputs = {
        "messages": [HumanMessage(content=user_input)],
        "user_context": user_context
    }
    
    config = {"configurable": {"thread_id": str(user_id)}}
    
    # Stream or invoke
    result = app.invoke(inputs, config=config)
    
    # The last message is the AI's response
    last_message = result["messages"][-1]
    return last_message.content
