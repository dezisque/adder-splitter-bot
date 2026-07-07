from datetime import datetime

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import Room
from src.infrastructure.db.models import ExpenseModel, ParticipantModel, RoomModel, utcnow


def _to_domain(model: RoomModel) -> Room:
    return Room(
        id=model.id,
        title=model.title,
        owner_user_id=model.owner_user_id,
        invite_token=model.invite_token,
        currency=model.currency,
        is_archived=model.is_archived,
        created_at=model.created_at,
        last_activity_at=model.last_activity_at,
        deletion_notified_at=model.deletion_notified_at,
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

    async def delete(self, room_id: int) -> None:
        # порядок важен: expenses ссылаются на participants;
        # expense_shares уходят каскадом на уровне БД
        await self._session.execute(sql_delete(ExpenseModel).where(ExpenseModel.room_id == room_id))
        await self._session.execute(
            sql_delete(ParticipantModel).where(ParticipantModel.room_id == room_id)
        )
        await self._session.execute(sql_delete(RoomModel).where(RoomModel.id == room_id))

    async def touch_activity(self, room_id: int) -> None:
        await self._session.execute(
            update(RoomModel)
            .where(RoomModel.id == room_id)
            .values(last_activity_at=utcnow(), deletion_notified_at=None)
        )

    async def mark_deletion_notified(self, room_id: int) -> None:
        await self._session.execute(
            update(RoomModel).where(RoomModel.id == room_id).values(deletion_notified_at=utcnow())
        )

    async def list_to_notify(self, inactive_since: datetime) -> list[Room]:
        models = await self._session.scalars(
            select(RoomModel).where(
                ~RoomModel.is_archived,
                RoomModel.deletion_notified_at.is_(None),
                RoomModel.last_activity_at < inactive_since,
            )
        )
        return [_to_domain(m) for m in models]

    async def list_to_delete(self, notified_before: datetime) -> list[Room]:
        models = await self._session.scalars(
            select(RoomModel).where(
                ~RoomModel.is_archived,
                RoomModel.deletion_notified_at.is_not(None),
                RoomModel.deletion_notified_at < notified_before,
            )
        )
        return [_to_domain(m) for m in models]
