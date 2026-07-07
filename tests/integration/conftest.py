"""Интеграционные тесты сервисов на живом PostgreSQL.

Запуск: TEST_DATABASE_URL=postgresql+asyncpg://adder:adder@localhost:5433/adder_splitter_test
Без переменной окружения тесты пропускаются.
"""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.application.services.balance_service import BalanceService
from src.application.services.expense_service import ExpenseService
from src.application.services.member_service import MemberService
from src.application.services.room_service import RoomService
from src.domain.entities import User
from src.infrastructure.db.base import Base
from src.infrastructure.db.repositories.expense_repo import SqlExpenseRepo
from src.infrastructure.db.repositories.participant_repo import SqlParticipantRepo
from src.infrastructure.db.repositories.room_repo import SqlRoomRepo
from src.infrastructure.db.repositories.user_repo import SqlUserRepo

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(TEST_DATABASE_URL is None, reason="TEST_DATABASE_URL не задан")


@dataclass(slots=True)
class Services:
    session: AsyncSession
    rooms: RoomService
    members: MemberService
    expenses: ExpenseService
    balance: BalanceService
    users: SqlUserRepo


@pytest.fixture
async def services() -> AsyncIterator[Services]:
    if TEST_DATABASE_URL is None:
        pytest.skip("TEST_DATABASE_URL не задан")
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = SqlUserRepo(session)
        rooms = SqlRoomRepo(session)
        participants = SqlParticipantRepo(session)
        expenses = SqlExpenseRepo(session)
        yield Services(
            session=session,
            rooms=RoomService(rooms, participants, expenses, users),
            members=MemberService(rooms, participants),
            expenses=ExpenseService(rooms, participants, expenses, users),
            balance=BalanceService(rooms, participants, expenses),
            users=users,
        )
    await engine.dispose()


async def make_user(services: Services, telegram_id: int, name: str) -> User:
    return await services.users.create(telegram_id, None, name)
