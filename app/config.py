import os
from typing import Optional
from dotenv import load_dotenv

# Force load .env over any stale system environment variables
load_dotenv(override=True)

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    telegram_bot_token: str
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.aicredits.in/v1"
    model_name: str = "gpt-4o-mini"
    mongodb_uri: str = "mongodb://localhost:27017"
    database_name: str = "atlas_finance_db"
    finnhub_api_key: Optional[str] = None
    bot_password: str = "Atlas2024"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
