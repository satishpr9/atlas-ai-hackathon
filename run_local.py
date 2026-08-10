import asyncio
import logging
from app.database import db
from app.bot import get_application

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting Atlas AI Bot Local Daemon...")
    await db.connect()
    
    logger.info("Starting Telegram bot (polling mode)...")
    app = get_application()
    
    # Start APScheduler for daily proactive intelligence
    from app.scheduler import setup_scheduler
    scheduler = setup_scheduler(app.bot)
    
    await app.initialize()
    await app.start()
    
    # We use updater.start_polling under the hood, but in v20+, it's simpler
    await app.updater.start_polling()
    logger.info("Bot is polling. Press Ctrl+C to stop.")
    
    # Keep the application running
    try:
        # Run forever until interrupted
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Stopping bot...")
        await app.updater.stop()
        await app.stop()
        await db.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down.")
