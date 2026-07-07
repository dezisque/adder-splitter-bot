from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.application.dto import RoomOverview
from src.domain.entities import Participant, Room
from src.presentation.bot import formatters
from src.presentation.bot.callbacks import (
    MemberAction,
    MemberCB,
    MenuCB,
    MenuTarget,
    RoomAction,
    RoomCB,
)


def rooms_list_kb(rooms: list[Room]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for room in rooms:
        prefix = "📦 " if room.is_archived else ""
        kb.button(
            text=f"{prefix}{room.title[:40]}",
            callback_data=RoomCB(action=RoomAction.OPEN, room_id=room.id),
        )
    kb.button(text="➕ Создать комнату", callback_data=MenuCB(to=MenuTarget.NEW_ROOM))
    kb.button(text="⬅️ Меню", callback_data=MenuCB(to=MenuTarget.MAIN))
    kb.adjust(1)
    return kb.as_markup()


def room_card_kb(o: RoomOverview) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    room_id = o.room.id
    if not o.room.is_archived:
        kb.button(
            text="💸 Добавить расход",
            callback_data=RoomCB(action=RoomAction.ADD_EXPENSE, room_id=room_id),
        )
    kb.button(text="📊 Баланс", callback_data=RoomCB(action=RoomAction.BALANCE, room_id=room_id))
    kb.button(text="📜 История", callback_data=RoomCB(action=RoomAction.HISTORY, room_id=room_id))
    kb.button(text="👥 Участники", callback_data=RoomCB(action=RoomAction.MEMBERS, room_id=room_id))
    if not o.room.is_archived:
        kb.button(
            text="🔗 Пригласить", callback_data=RoomCB(action=RoomAction.INVITE, room_id=room_id)
        )
    kb.button(text="⚙️ Настройки", callback_data=RoomCB(action=RoomAction.SETTINGS, room_id=room_id))
    kb.button(text="⬅️ К списку комнат", callback_data=MenuCB(to=MenuTarget.ROOMS))
    kb.adjust(1, 2, 2, 1, 1)
    return kb.as_markup()


def room_settings_kb(o: RoomOverview) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    room_id = o.room.id
    if o.is_owner:
        if not o.room.is_archived:
            kb.button(
                text="🔄 Перевыпустить ссылку",
                callback_data=RoomCB(action=RoomAction.INVITE_REGEN, room_id=room_id),
            )
            kb.button(
                text="📦 Архивировать комнату",
                callback_data=RoomCB(action=RoomAction.ARCHIVE, room_id=room_id),
            )
    else:
        kb.button(
            text="🚪 Выйти из комнаты",
            callback_data=RoomCB(action=RoomAction.LEAVE, room_id=room_id),
        )
    kb.button(text="⬅️ Назад", callback_data=RoomCB(action=RoomAction.OPEN, room_id=room_id))
    kb.adjust(1)
    return kb.as_markup()


def confirm_kb(yes: CallbackData, no: CallbackData) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да", callback_data=yes)
    kb.button(text="↩️ Нет", callback_data=no)
    kb.adjust(2)
    return kb.as_markup()


def invite_kb(o: RoomOverview) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data=RoomCB(action=RoomAction.OPEN, room_id=o.room.id))
    kb.adjust(1)
    return kb.as_markup()


def members_kb(o: RoomOverview, participants: list[Participant]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    room_id = o.room.id
    if not o.room.is_archived:
        kb.button(
            text="➕ Добавить вручную",
            callback_data=MemberCB(
                action=MemberAction.ADD_VIRTUAL, room_id=room_id, participant_id=0
            ),
        )
    if o.is_owner:
        for p in participants:
            if p.user_id == o.room.owner_user_id:
                continue
            kb.button(
                text=f"❌ {formatters.button_name(p)}",
                callback_data=MemberCB(
                    action=MemberAction.REMOVE, room_id=room_id, participant_id=p.id
                ),
            )
    kb.button(text="⬅️ Назад", callback_data=RoomCB(action=RoomAction.OPEN, room_id=room_id))
    kb.adjust(1)
    return kb.as_markup()
