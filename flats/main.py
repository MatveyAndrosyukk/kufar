import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

import net
import monitor
from config import BOT_TOKEN
from db import db
from handlers import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def main():
    await db.connect()
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await bot.set_my_commands([BotCommand(command="start", description="Главное меню")])
    task = asyncio.create_task(monitor.loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        task.cancel()
        await net.close()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
