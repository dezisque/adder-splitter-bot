from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import User
from src.infrastructure.db.models import UserModel


def _to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        telegram_id=model.telegram_id,
        username=model.username,
        first_name=model.first_name,
        created_at=model.created_at,
        current_room_id=model.current_room_id,
    )


class SqlUserRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: int) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return _to_domain(model) if model is not None else None

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        model = await self._session.scalar(
            select(UserModel).where(UserModel.telegram_id == telegram_id)
        )
        return _to_domain(model) if model is not None else None

    async def create(self, telegram_id: int, username: str | None, first_name: str) -> User:
        model = UserModel(telegram_id=telegram_id, username=username, first_name=first_name)
        self._session.add(model)
        await self._session.flush()
        return _to_domain(model)

    async def update_profile(self, user_id: int, username: str | None, first_name: str) -> None:
        await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(username=username, first_name=first_name)
        )

    async def set_current_room(self, user_id: int, room_id: int | None) -> None:
        await self._session.execute(
            update(UserModel).where(UserModel.id == user_id).values(current_room_id=room_id)
        )
