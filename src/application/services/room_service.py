import secrets

from src.application.dto import RoomOverview
from src.application.interfaces import ExpenseRepo, ParticipantRepo, RoomRepo
from src.application.services._access import ensure_owner, ensure_writable, get_room_and_member
from src.domain import limits
from src.domain.entities import Room, User
from src.domain.exceptions import InvalidInput, LimitExceeded


def _new_token() -> str:
    return secrets.token_urlsafe(limits.INVITE_TOKEN_BYTES)


class RoomService:
    def __init__(
        self, rooms: RoomRepo, participants: ParticipantRepo, expenses: ExpenseRepo
    ) -> None:
        self._rooms = rooms
        self._participants = participants
        self._expenses = expenses

    async def create(self, owner: User, title: str) -> Room:
        title = title.strip()
        if not title or len(title) > limits.MAX_ROOM_TITLE_LEN:
            raise InvalidInput(
                f"Название — от 1 до {limits.MAX_ROOM_TITLE_LEN} символов. Попробуйте ещё раз."
            )
        if await self._rooms.count_for_user(owner.id) >= limits.MAX_ROOMS_PER_USER:
            raise LimitExceeded("Достигнут лимит комнат — заархивируйте неиспользуемые")
        room = await self._rooms.create(
            title=title,
            owner_user_id=owner.id,
            invite_token=_new_token(),
            currency=limits.DEFAULT_CURRENCY,
        )
        await self._participants.add(
            room.id, owner.id, owner.first_name[: limits.MAX_MEMBER_NAME_LEN]
        )
        return room

    async def list_for_user(self, user: User) -> list[Room]:
        return await self._rooms.list_for_user(user.id)

    async def get_overview(self, user: User, room_id: int) -> RoomOverview:
        room, me = await get_room_and_member(self._rooms, self._participants, user, room_id)
        members_count = await self._participants.count_active(room.id)
        expenses_count, expenses_sum = await self._expenses.expense_stats(room.id)
        return RoomOverview(
            room=room,
            me=me,
            is_owner=room.owner_user_id == user.id,
            members_count=members_count,
            expenses_count=expenses_count,
            expenses_sum=expenses_sum,
        )

    async def archive(self, user: User, room_id: int) -> None:
        room, _ = await get_room_and_member(self._rooms, self._participants, user, room_id)
        ensure_owner(room, user)
        await self._rooms.set_archived(room_id, True)

    async def keep_alive(self, user: User, room_id: int) -> None:
        """Сбрасывает таймер авто-удаления (кнопка «Оставить» в уведомлении)."""
        await get_room_and_member(self._rooms, self._participants, user, room_id)
        await self._rooms.touch_activity(room_id)

    async def delete(self, user: User, room_id: int) -> None:
        """Безвозвратно удаляет комнату со всеми расходами. Только владелец."""
        room, _ = await get_room_and_member(self._rooms, self._participants, user, room_id)
        ensure_owner(room, user)
        await self._rooms.delete(room_id)

    async def regenerate_invite(self, user: User, room_id: int) -> str:
        room, _ = await get_room_and_member(self._rooms, self._participants, user, room_id)
        ensure_owner(room, user)
        ensure_writable(room)
        token = _new_token()
        await self._rooms.set_invite_token(room_id, token)
        return token
