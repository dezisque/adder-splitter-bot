"""Фоновая уборка: предупреждает владельцев неактивных комнат и удаляет брошенные.

Архивные комнаты не трогаем — архив и есть способ сохранить историю навсегда.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain import limits
from src.infrastructure.db.repositories.room_repo import SqlRoomRepo
from src.infrastructure.db.repositories.user_repo import SqlUserRepo
from src.presentation.bot import formatters
from src.presentation.bot.keyboards.room import inactive_room_kb

logger = logging.getLogger(__name__)


async def cleanup_loop(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            await run_cleanup_once(bot, session_factory)
        except Exception:
            logger.exception("Ошибка фоновой уборки комнат")
        await asyncio.sleep(limits.CLEANUP_INTERVAL_SECONDS)


async def run_cleanup_once(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> None:
    now = datetime.now(UTC)
    async with session_factory() as session:
        rooms = SqlRoomRepo(session)
        users = SqlUserRepo(session)

        inactive_cutoff = now - timedelta(days=limits.ROOM_INACTIVITY_DAYS)
        for room in await rooms.list_to_notify(inactive_cutoff):
            owner = await users.get(room.owner_user_id)
            if owner is not None:
                await _send_safe(
                    bot,
                    owner.telegram_id,
                    formatters.inactive_room_notice(room),
                    inactive_room_kb(room.id),
                )
            await rooms.mark_deletion_notified(room.id)
            logger.info("Комната %s помечена к удалению (неактивность)", room.id)

        grace_cutoff = now - timedelta(days=limits.ROOM_DELETION_GRACE_DAYS)
        for room in await rooms.list_to_delete(grace_cutoff):
            owner = await users.get(room.owner_user_id)
            await rooms.delete(room.id)
            if owner is not None:
                await _send_safe(bot, owner.telegram_id, formatters.room_auto_deleted(room), None)
            logger.info("Комната %s удалена по неактивности", room.id)

        await session.commit()


async def _send_safe(
    bot: Bot, chat_id: int, text: str, reply_markup: InlineKeyboardMarkup | None
) -> None:
    try:
        await bot.send_message(chat_id, text, reply_markup=reply_markup)
    except TelegramAPIError:
        logger.warning("Не удалось доставить уведомление в чат %s", chat_id)
