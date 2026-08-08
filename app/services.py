from typing import Optional
from datetime import datetime
from app.database import db
from app.models import UserProfile, MessageRecord

async def get_or_create_user(telegram_id: int, first_name: Optional[str] = None, username: Optional[str] = None) -> UserProfile:
    users_collection = db.get_db()["users"]
    user_dict = await users_collection.find_one({"telegram_id": telegram_id})
    
    if user_dict:
        return UserProfile(**user_dict)
    
    new_user = UserProfile(
        telegram_id=telegram_id,
        first_name=first_name,
        username=username
    )
    await users_collection.insert_one(new_user.model_dump())
    return new_user

async def add_message_to_history(telegram_id: int, role: str, content: str):
    users_collection = db.get_db()["users"]
    msg = MessageRecord(role=role, content=content)
    await users_collection.update_one(
        {"telegram_id": telegram_id},
        {"$push": {"chat_history": msg.model_dump()}, "$set": {"updated_at": datetime.utcnow()}}
    )

async def update_user_profile(telegram_id: int, updates: dict):
    users_collection = db.get_db()["users"]
    updates["updated_at"] = datetime.utcnow()
    await users_collection.update_one(
        {"telegram_id": telegram_id},
        {"$set": updates}
    )
