import asyncpg
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class Database:
    pool: asyncpg.Pool = None

    @classmethod
    async def connect(cls):
        try:
            cls.pool = await asyncpg.create_pool(
                dsn=settings.postgres_uri,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            logger.info("Connected to PostgreSQL via asyncpg")
            
            # Create users table if it doesn't exist
            async with cls.pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        telegram_id BIGINT PRIMARY KEY,
                        profile_data JSONB NOT NULL
                    );
                """)
                logger.info("Checked/Created users table in PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")

    @classmethod
    async def disconnect(cls):
        if cls.pool:
            await cls.pool.close()
            logger.info("Disconnected from PostgreSQL")

db = Database()
