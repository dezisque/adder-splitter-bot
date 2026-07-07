from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.application.services.balance_service import BalanceService
from src.application.services.expense_service import ExpenseService
from src.application.services.member_service import MemberService
from src.application.services.room_service import RoomService
from src.application.services.user_service import UserService
from src.infrastructure.db.repositories.expense_repo import SqlExpenseRepo
from src.infrastructure.db.repositories.participant_repo import SqlParticipantRepo
from src.infrastructure.db.repositories.room_repo import SqlRoomRepo
from src.infrastructure.db.repositories.user_repo import SqlUserRepo


class DiMiddleware(BaseMiddleware):
    """Сессия БД и сервисы на один апдейт; commit по успешному завершении."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._session_factory() as session:
            users = SqlUserRepo(session)
            rooms = SqlRoomRepo(session)
            participants = SqlParticipantRepo(session)
            expenses = SqlExpenseRepo(session)
            data["user_service"] = UserService(users)
            data["room_service"] = RoomService(rooms, participants, expenses)
            data["member_service"] = MemberService(rooms, participants)
            data["expense_service"] = ExpenseService(rooms, participants, expenses, users)
            data["balance_service"] = BalanceService(rooms, participants, expenses)
            result = await handler(event, data)
            await session.commit()
            return result
