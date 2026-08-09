import json
import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from app.models import UserProfile, MessageRecord

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
STORE_FILE = os.path.join(DATA_DIR, "users_store.json")

# In-Memory Cache for ultra-fast fallback access
_LOCAL_USERS_CACHE: Dict[int, Dict[str, Any]] = {}

def _load_local_store():
    global _LOCAL_USERS_CACHE
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(STORE_FILE):
            with open(STORE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                _LOCAL_USERS_CACHE = {int(k): v for k, v in data.items()}
    except Exception as e:
        logger.error(f"Error loading local user store: {e}")

def _save_local_store():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(_LOCAL_USERS_CACHE, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error saving local user store: {e}")

_load_local_store()

async def get_or_create_user(telegram_id: int, first_name: Optional[str] = None, username: Optional[str] = None) -> UserProfile:
    # 1. Check local cache first for instant retrieval
    if telegram_id in _LOCAL_USERS_CACHE:
        return UserProfile(**_LOCAL_USERS_CACHE[telegram_id])
        
    # 2. Try MongoDB with fast timeout
    try:
        from app.database import db
        db_instance = db.get_db()
        if db_instance is not None:
            user_dict = await db_instance["users"].find_one({"telegram_id": telegram_id})
            if user_dict:
                _LOCAL_USERS_CACHE[telegram_id] = user_dict
                return UserProfile(**user_dict)
    except Exception as e:
        logger.debug(f"MongoDB lookup bypassed: {e}")
        
    # 3. Create new user profile
    new_user = UserProfile(
        telegram_id=telegram_id,
        first_name=first_name,
        username=username
    )
    _LOCAL_USERS_CACHE[telegram_id] = new_user.model_dump()
    _save_local_store()
    
    try:
        from app.database import db
        db_instance = db.get_db()
        if db_instance is not None:
            await db_instance["users"].insert_one(new_user.model_dump())
    except Exception:
        pass
        
    return new_user

async def add_message_to_history(telegram_id: int, role: str, content: str):
    msg = MessageRecord(role=role, content=content)
    if telegram_id in _LOCAL_USERS_CACHE:
        if "chat_history" not in _LOCAL_USERS_CACHE[telegram_id]:
            _LOCAL_USERS_CACHE[telegram_id]["chat_history"] = []
        _LOCAL_USERS_CACHE[telegram_id]["chat_history"].append(msg.model_dump())
        _LOCAL_USERS_CACHE[telegram_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_local_store()
        
    try:
        from app.database import db
        db_instance = db.get_db()
        if db_instance is not None:
            await db_instance["users"].update_one(
                {"telegram_id": telegram_id},
                {"$push": {"chat_history": msg.model_dump()}, "$set": {"updated_at": datetime.now(timezone.utc)}}
            )
    except Exception:
        pass

async def save_message(telegram_id: int, role: str, content: str):
    await add_message_to_history(telegram_id, role, content)

async def get_recent_chat_history(telegram_id: int, limit: int = 6) -> List[Dict[str, str]]:
    if telegram_id in _LOCAL_USERS_CACHE:
        history = _LOCAL_USERS_CACHE[telegram_id].get("chat_history", [])
        return history[-limit:]
    return []

async def update_user_profile(telegram_id: int, updates: dict):
    if telegram_id in _LOCAL_USERS_CACHE:
        _LOCAL_USERS_CACHE[telegram_id].update(updates)
        _LOCAL_USERS_CACHE[telegram_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_local_store()
        
    try:
        from app.database import db
        db_instance = db.get_db()
        if db_instance is not None:
            updates["updated_at"] = datetime.now(timezone.utc)
            await db_instance["users"].update_one(
                {"telegram_id": telegram_id},
                {"$set": updates}
            )
    except Exception:
        pass

def get_all_users() -> List[Dict[str, Any]]:
    return list(_LOCAL_USERS_CACHE.values())
