import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram import Update
from app.database import db
from app.bot import get_application

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# We initialize the bot application globally so we can access it inside the webhook
bot_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up FastAPI application...")
    db.connect()
    
    global bot_app
    bot_app = get_application()
    await bot_app.initialize()
    await bot_app.start()
    
    # Optional: If you want to use webhooks instead of polling, you would set the webhook URL here.
    # For local testing, we'll start polling if not using webhooks.
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI application...")
    await bot_app.stop()
    db.disconnect()

app = FastAPI(lifespan=lifespan, title="Atlas AI Financial Assistant")

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Endpoint for Telegram webhooks.
    """
    if bot_app is None:
        return {"status": "bot not initialized"}
        
    try:
        data = await request.json()
    except Exception:
        return {"status": "bad request", "reason": "invalid or missing JSON body"}
        
    if data:
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
    return {"status": "ok"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
