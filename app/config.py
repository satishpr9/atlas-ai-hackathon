import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables (system env vars take precedence)
load_dotenv()

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    telegram_bot_token: str
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.aicredits.in/v1"
    model_name: str = "gpt-4o-mini"
    postgres_uri: str = "postgresql://postgres:Satishpr92@!?@db.fakywnmyjduhfwfttixa.supabase.co:5432/postgres"
    finnhub_api_key: Optional[str] = None
    bot_password: str = "Atlas2024"
    port: int = 8000
    webhook_url: Optional[str] = None
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
