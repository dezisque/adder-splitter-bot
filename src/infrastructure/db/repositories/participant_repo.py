from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import Participant
from src.infrastructure.db.models import ParticipantModel, UserModel


def _to_domain(model: ParticipantModel) -> Participant:
    return Participant(
        id=model.id,
        room_id=model.room_id,
        user_id=model.user_id,
        display_name=model.display_name,
        is_active=model.is_active,
    )


class SqlParticipantRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, room_id: int, user_id: int | None, display_name: str) -> Participant:
        model = ParticipantModel(room_id=room_id, user_id=user_id, display_name=display_name)
        self._session.add(model)
        await self._session.flush()
        return _to_domain(model)

    async def get(self, participant_id: int) -> Participant | None:
        model = await self._session.get(ParticipantModel, participant_id)
        return _to_domain(model) if model is not None else None

    async def get_by_room_and_user(self, room_id: int, user_id: int) -> Participant | None:
        model = await self._session.scalar(
            select(ParticipantModel).where(
                ParticipantModel.room_id == room_id, ParticipantModel.user_id == user_id
            )
        )
        return _to_domain(model) if model is not None else None

    async def list_by_room(self, room_id: int, include_inactive: bool = False) -> list[Participant]:
        stmt = select(ParticipantModel).where(ParticipantModel.room_id == room_id)
        if not include_inactive:
            stmt = stmt.where(ParticipantModel.is_active)
        stmt = stmt.order_by(ParticipantModel.id)
        return [_to_domain(m) for m in await self._session.scalars(stmt)]

    async def list_with_usernames(
        self, room_id: int, include_inactive: bool = False
    ) -> list[tuple[Participant, str | None]]:
        stmt = (
            select(ParticipantModel, UserModel.username)
            .join(UserModel, ParticipantModel.user_id == UserModel.id, isouter=True)
            .where(ParticipantModel.room_id == room_id)
        )
        if not include_inactive:
            stmt = stmt.where(ParticipantModel.is_active)
        stmt = stmt.order_by(ParticipantModel.id)
        rows = await self._session.execute(stmt)
        return [(_to_domain(row[0]), row[1]) for row in rows]

    async def count_active(self, room_id: int) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(ParticipantModel)
            .where(ParticipantModel.room_id == room_id, ParticipantModel.is_active)
        )
        return count or 0

    async def set_active(self, participant_id: int, active: bool) -> None:
        await self._session.execute(
            update(ParticipantModel)
            .where(ParticipantModel.id == participant_id)
            .values(is_active=active)
        )
