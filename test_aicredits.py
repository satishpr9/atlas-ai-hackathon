import os
from dotenv import load_dotenv

# Force override system environment variables with .env
load_dotenv(override=True)

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL", "https://aicredits.in/v1")
model = os.getenv("MODEL_NAME", "gpt-4o-mini")

print(f"Testing with override=True:")
print(f"Base URL: {base_url}")
print(f"Model: {model}")
print(f"API Key: {api_key[:12]}...")

try:
    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url
    )
    res = llm.invoke([HumanMessage(content="Say 'AICredits connection successful!'")])
    print(f"SUCCESS: {res.content}")
except Exception as e:
    print(f"ERROR: {e}")
