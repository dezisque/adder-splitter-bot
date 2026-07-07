from src.application.dto import MemberView
from src.application.interfaces import ParticipantRepo, RoomRepo
from src.application.services._access import ensure_owner, ensure_writable, get_room_and_member
from src.domain import limits
from src.domain.entities import Participant, Room, User
from src.domain.exceptions import AccessDenied, InvalidInput, LimitExceeded, NotFound

MEMBERS_LIMIT_MESSAGE = "В комнате уже максимум участников"


class MemberService:
    def __init__(self, rooms: RoomRepo, participants: ParticipantRepo) -> None:
        self._rooms = rooms
        self._participants = participants

    async def join_by_token(self, user: User, token: str) -> tuple[Room, bool]:
        """Вступление по инвайт-ссылке. Возвращает (комната, вступил ли сейчас)."""
        room = await self._rooms.get_by_invite_token(token)
        if room is None:
            raise NotFound("Ссылка недействительна — попросите новую у владельца комнаты")
        if room.is_archived:
            raise AccessDenied("Комната в архиве, вступить нельзя")
        existing = await self._participants.get_by_room_and_user(room.id, user.id)
        if existing is not None:
            if existing.is_active:
                return room, False
            # выходил раньше — возвращаем того же участника, история сохранена
            await self._participants.set_active(existing.id, True)
            await self._rooms.touch_activity(room.id)
            return room, True
        if await self._participants.count_active(room.id) >= limits.MAX_MEMBERS_PER_ROOM:
            raise LimitExceeded(MEMBERS_LIMIT_MESSAGE)
        await self._participants.add(
            room.id, user.id, user.first_name[: limits.MAX_MEMBER_NAME_LEN]
        )
        await self._rooms.touch_activity(room.id)
        return room, True

    async def add_virtual(self, actor: User, room_id: int, name: str) -> Participant:
        room, _ = await get_room_and_member(self._rooms, self._participants, actor, room_id)
        ensure_writable(room)
        name = name.strip()
        if not name or len(name) > limits.MAX_MEMBER_NAME_LEN:
            raise InvalidInput(
                f"Имя — от 1 до {limits.MAX_MEMBER_NAME_LEN} символов. Попробуйте ещё раз."
            )
        if await self._participants.count_active(room.id) >= limits.MAX_MEMBERS_PER_ROOM:
            raise LimitExceeded(MEMBERS_LIMIT_MESSAGE)
        participant = await self._participants.add(room.id, None, name)
        await self._rooms.touch_activity(room.id)
        return participant

    async def list_members(
        self, user: User, room_id: int, include_inactive: bool = False
    ) -> list[Participant]:
        await get_room_and_member(self._rooms, self._participants, user, room_id)
        return await self._participants.list_by_room(room_id, include_inactive)

    async def list_members_view(self, user: User, room_id: int) -> list[MemberView]:
        """Активные участники с username привязанных аккаунтов."""
        await get_room_and_member(self._rooms, self._participants, user, room_id)
        rows = await self._participants.list_with_usernames(room_id)
        return [MemberView(participant=p, username=username) for p, username in rows]

    async def leave(self, user: User, room_id: int) -> None:
        room, me = await get_room_and_member(self._rooms, self._participants, user, room_id)
        if room.owner_user_id == user.id:
            raise AccessDenied("Владелец не может выйти — заархивируйте комнату в настройках")
        await self._participants.set_active(me.id, False)

    async def remove_member(self, actor: User, room_id: int, participant_id: int) -> Participant:
        room, _ = await get_room_and_member(self._rooms, self._participants, actor, room_id)
        ensure_owner(room, actor)
        target = await self._participants.get(participant_id)
        if target is None or target.room_id != room.id or not target.is_active:
            raise NotFound("Участник не найден")
        if target.user_id == room.owner_user_id:
            raise AccessDenied("Нельзя удалить владельца комнаты")
        await self._participants.set_active(target.id, False)
        return target
