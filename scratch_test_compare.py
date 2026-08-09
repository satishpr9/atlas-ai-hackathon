import asyncio
from app.config import settings
from langchain_openai import ChatOpenAI
from app.agents.comparison import CompanyComparisonEngine

llm = ChatOpenAI(
    model=settings.model_name or "gpt-4o-mini",
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
    temperature=0.1
)

async def test():
    print("Testing Microsoft vs Alphabet Comparison...")
    res = await CompanyComparisonEngine.compare("MSFT", "GOOGL", llm)
    print("\n=== COMPARISON RESULT ===")
    print(res)

if __name__ == "__main__":
    asyncio.run(test())
