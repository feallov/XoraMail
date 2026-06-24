import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config.settings import settings
from src.handlers import router
from src.middleware import ThrottlingMiddleware, SubscriptionMiddleware
from src.database import Database
from src.mail_checker import MailChecker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    db = Database()
    await db.init()

    bot = Bot(token=settings.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.message.middleware(ThrottlingMiddleware())
    dp.message.middleware(SubscriptionMiddleware(bot, db))
    dp.callback_query.middleware(SubscriptionMiddleware(bot, db))

    dp.include_router(router)

    # Pass shared objects via workflow data
    dp["db"] = db
    dp["bot"] = bot

    mail_checker = MailChecker(bot, db)
    asyncio.create_task(mail_checker.start_polling())

    logger.info("Bot started!")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
