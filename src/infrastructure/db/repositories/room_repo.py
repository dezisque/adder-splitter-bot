from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import Room
from src.infrastructure.db.models import ParticipantModel, RoomModel


def _to_domain(model: RoomModel) -> Room:
    return Room(
        id=model.id,
        title=model.title,
        owner_user_id=model.owner_user_id,
        invite_token=model.invite_token,
        currency=model.currency,
        is_archived=model.is_archived,
        created_at=model.created_at,
    )


class SqlRoomRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, *, title: str, owner_user_id: int, invite_token: str, currency: str
    ) -> Room:
        model = RoomModel(
            title=title,
            owner_user_id=owner_user_id,
            invite_token=invite_token,
            currency=currency,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_domain(model)

    async def get(self, room_id: int) -> Room | None:
        model = await self._session.get(RoomModel, room_id)
        return _to_domain(model) if model is not None else None

    async def get_by_invite_token(self, token: str) -> Room | None:
        model = await self._session.scalar(select(RoomModel).where(RoomModel.invite_token == token))
        return _to_domain(model) if model is not None else None

    async def list_for_user(self, user_id: int) -> list[Room]:
        models = await self._session.scalars(
            select(RoomModel)
            .join(ParticipantModel, ParticipantModel.room_id == RoomModel.id)
            .where(ParticipantModel.user_id == user_id, ParticipantModel.is_active)
            .order_by(RoomModel.created_at.desc())
        )
        return [_to_domain(m) for m in models]

    async def count_for_user(self, user_id: int) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(RoomModel)
            .join(ParticipantModel, ParticipantModel.room_id == RoomModel.id)
            .where(
                ParticipantModel.user_id == user_id,
                ParticipantModel.is_active,
                ~RoomModel.is_archived,
            )
        )
        return count or 0

    async def set_archived(self, room_id: int, archived: bool) -> None:
        await self._session.execute(
            update(RoomModel).where(RoomModel.id == room_id).values(is_archived=archived)
        )

    async def set_invite_token(self, room_id: int, token: str) -> None:
        await self._session.execute(
            update(RoomModel).where(RoomModel.id == room_id).values(invite_token=token)
        )
