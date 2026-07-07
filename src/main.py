import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config import Settings
from src.infrastructure.db.session import create_engine, create_session_factory
from src.presentation.bot import texts
from src.presentation.bot.cleanup import cleanup_loop
from src.presentation.bot.handlers import balance, common, expenses, members, rooms, start
from src.presentation.bot.middlewares.di import DiMiddleware
from src.presentation.bot.middlewares.user_upsert import UserUpsertMiddleware

BOT_COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="rooms", description="Мои комнаты"),
    BotCommand(command="newroom", description="Создать комнату"),
    BotCommand(command="cancel", description="Отменить текущее действие"),
    BotCommand(command="help", description="Справка"),
]


def _create_storage(settings: Settings) -> BaseStorage:
    if settings.redis_url:
        return RedisStorage.from_url(settings.redis_url)
    return MemoryStorage()


def create_dispatcher(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> Dispatcher:
    dp = Dispatcher(storage=_create_storage(settings))
    dp.update.middleware(DiMiddleware(session_factory))
    dp.update.middleware(UserUpsertMiddleware())
    # common подключается последним: в нём catch-all для устаревших кнопок
    dp.include_routers(
        start.router,
        rooms.router,
        members.router,
        expenses.router,
        balance.router,
        common.router,
    )
    dp.startup.register(_on_startup)
    return dp


async def _on_startup(bot: Bot) -> None:
    await bot.set_my_commands(BOT_COMMANDS)
    # экран «Что умеет этот бот?» до нажатия «Запустить»
    await bot.set_my_description(texts.BOT_DESCRIPTION)
    await bot.set_my_short_description(texts.BOT_SHORT_DESCRIPTION)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = create_dispatcher(settings, session_factory)
    cleanup_task = asyncio.create_task(cleanup_loop(bot, session_factory))
    try:
        await dp.start_polling(bot)
    finally:
        cleanup_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
