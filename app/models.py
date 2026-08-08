from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime

class MessageRecord(BaseModel):
    role: str # "user", "assistant", "system"
    content: Union[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class UserProfile(BaseModel):
    telegram_id: int
    first_name: Optional[str] = None
    username: Optional[str] = None
    
    # Preferences extracted from conversation
    role: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
    watch_list: List[str] = Field(default_factory=list)
    
    # Context summary (a paragraph summarizing who they are)
    context_summary: str = ""
    
    # History
    chat_history: List[MessageRecord] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

