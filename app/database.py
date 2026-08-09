from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    def connect(cls):
        cls.client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=2000
        )
        cls.db = cls.client[settings.database_name]
        logger.info(f"Connected to MongoDB: {settings.database_name}")

    @classmethod
    def disconnect(cls):
        if cls.client:
            cls.client.close()
            print("Disconnected from MongoDB")

    @classmethod
    def get_db(cls):
        return cls.db

db = Database()
