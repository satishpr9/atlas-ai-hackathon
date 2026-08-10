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
        
    # 2. Try PostgreSQL
    try:
        from app.database import db
        if db.pool is not None:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT profile_data FROM users WHERE telegram_id = $1", telegram_id)
                if row:
                    user_dict = json.loads(row['profile_data'])
                    _LOCAL_USERS_CACHE[telegram_id] = user_dict
                    return UserProfile(**user_dict)
    except Exception as e:
        logger.debug(f"PostgreSQL lookup bypassed: {e}")
        
    # 3. Create new user profile
    new_user = UserProfile(
        telegram_id=telegram_id,
        first_name=first_name,
        username=username
    )
    user_dict = new_user.model_dump()
    _LOCAL_USERS_CACHE[telegram_id] = user_dict
    _save_local_store()
    
    try:
        from app.database import db
        if db.pool is not None:
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO users (telegram_id, profile_data) 
                    VALUES ($1, $2) 
                    ON CONFLICT (telegram_id) 
                    DO UPDATE SET profile_data = EXCLUDED.profile_data
                    """,
                    telegram_id,
                    json.dumps(user_dict, default=str)
                )
    except Exception as e:
        logger.error(f"Failed to insert new user in PostgreSQL: {e}")
        
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
        if db.pool is not None and telegram_id in _LOCAL_USERS_CACHE:
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO users (telegram_id, profile_data) 
                    VALUES ($1, $2) 
                    ON CONFLICT (telegram_id) 
                    DO UPDATE SET profile_data = EXCLUDED.profile_data
                    """,
                    telegram_id,
                    json.dumps(_LOCAL_USERS_CACHE[telegram_id], default=str)
                )
    except Exception as e:
        logger.error(f"Failed to update chat history in PostgreSQL: {e}")

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
        if db.pool is not None and telegram_id in _LOCAL_USERS_CACHE:
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO users (telegram_id, profile_data) 
                    VALUES ($1, $2) 
                    ON CONFLICT (telegram_id) 
                    DO UPDATE SET profile_data = EXCLUDED.profile_data
                    """,
                    telegram_id,
                    json.dumps(_LOCAL_USERS_CACHE[telegram_id], default=str)
                )
    except Exception as e:
        logger.error(f"Failed to update user profile in PostgreSQL: {e}")

def get_all_users() -> List[Dict[str, Any]]:
    return list(_LOCAL_USERS_CACHE.values())
