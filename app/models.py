from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class MessageRecord(BaseModel):
    role: str # "user", "assistant", "system"
    content: Union[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserProfile(BaseModel):
    telegram_id: int
    first_name: Optional[str] = None
    username: Optional[str] = None
    
    # Preferences extracted naturally from conversation
    role: Optional[str] = None # e.g. "Investor", "Analyst", "Founder", "Student", "Finance Professional"
    interests: List[str] = Field(default_factory=list) # Sectors or topics (e.g. "AI Chips", "Cloud SaaS")
    watch_list: List[str] = Field(default_factory=list) # e.g. ["NVDA", "AAPL", "MSFT"]
    preferred_insights: List[str] = Field(default_factory=list) # e.g. ["Earnings", "SEC Filings", "Market News", "Macro"]
    domains_of_interest: List[str] = Field(default_factory=lambda: ["Finance", "Technology"])
    briefing_time: str = "08:30 UTC"
    connected_accounts: List[str] = Field(default_factory=list) # e.g. ["Google Drive", "Google Calendar"]
    onboarding_stage: str = "initial" # "initial", "profiled", "completed"
    
    # Context summary (a persistent synthesis of who they are and their workflow)
    context_summary: str = ""
    
    # Uploaded document context for conversational Q&A
    last_document_text: str = ""
    last_document_name: str = ""
    
    # History
    chat_history: List[MessageRecord] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
