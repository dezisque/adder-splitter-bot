"""Общие проверки доступа для сервисов."""

from src.application.interfaces import ParticipantRepo, RoomRepo
from src.domain.entities import Participant, Room, User
from src.domain.exceptions import AccessDenied, NotFound

ROOM_NOT_FOUND = "Комната не найдена"
NOT_A_MEMBER = "Вы не участник этой комнаты"
ROOM_ARCHIVED = "Комната в архиве — изменения недоступны"
OWNER_ONLY = "Действие доступно только владельцу комнаты"


async def get_room_and_member(
    rooms: RoomRepo, participants: ParticipantRepo, user: User, room_id: int
) -> tuple[Room, Participant]:
    room = await rooms.get(room_id)
    if room is None:
        raise NotFound(ROOM_NOT_FOUND)
    me = await participants.get_by_room_and_user(room.id, user.id)
    if me is None or not me.is_active:
        raise AccessDenied(NOT_A_MEMBER)
    return room, me


def ensure_writable(room: Room) -> None:
    if room.is_archived:
        raise AccessDenied(ROOM_ARCHIVED)


def ensure_owner(room: Room, user: User) -> None:
    if room.owner_user_id != user.id:
        raise AccessDenied(OWNER_ONLY)
