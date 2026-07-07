from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.types import User as TgUser

from src.application.services.user_service import UserService

_MAX_NAME_LEN = 128  # соответствует users.first_name в БД


class UserUpsertMiddleware(BaseMiddleware):
    """Регистрирует/обновляет пользователя и кладёт domain-User в data["user"]."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is not None and not tg_user.is_bot:
            user_service: UserService = data["user_service"]
            data["user"] = await user_service.upsert_from_telegram(
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.full_name[:_MAX_NAME_LEN],
            )
        return await handler(event, data)
