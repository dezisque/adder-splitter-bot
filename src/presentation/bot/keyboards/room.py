from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.application.dto import RoomOverview
from src.domain.entities import Participant, Room
from src.presentation.bot import formatters
from src.presentation.bot.callbacks import (
    KeepRoomCB,
    MemberAction,
    MemberCB,
    MenuCB,
    MenuTarget,
    RoomAction,
    RoomCB,
)


def _btn(text: str, cb: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=cb.pack())


def rooms_list_kb(active: list[Room], archived_count: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for room in active:
        kb.row(_btn(room.title[:40], RoomCB(action=RoomAction.OPEN, room_id=room.id)))
    if archived_count:
        kb.row(_btn(f"📦 Архив ({archived_count})", MenuCB(to=MenuTarget.ARCHIVED)))
    kb.row(_btn("➕ Создать комнату", MenuCB(to=MenuTarget.NEW_ROOM)))
    kb.row(_btn("⬅️ Меню", MenuCB(to=MenuTarget.MAIN)))
    return kb.as_markup()


def archived_rooms_kb(rooms: list[Room]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for room in rooms:
        kb.row(_btn(f"📦 {room.title[:38]}", RoomCB(action=RoomAction.OPEN, room_id=room.id)))
    kb.row(_btn("⬅️ К комнатам", MenuCB(to=MenuTarget.ROOMS)))
    return kb.as_markup()


def room_card_kb(o: RoomOverview) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    rid = o.room.id
    if not o.room.is_archived:
        kb.row(_btn("➕ Добавить расход", RoomCB(action=RoomAction.ADD_EXPENSE, room_id=rid)))
    kb.row(
        _btn("📊 Баланс", RoomCB(action=RoomAction.BALANCE, room_id=rid)),
        _btn("🕓 История", RoomCB(action=RoomAction.HISTORY, room_id=rid)),
    )
    members_btn = _btn("👥 Участники", RoomCB(action=RoomAction.MEMBERS, room_id=rid))
    if o.room.is_archived:
        kb.row(members_btn)
    else:
        kb.row(members_btn, _btn("🔗 Пригласить", RoomCB(action=RoomAction.INVITE, room_id=rid)))
    if o.is_owner:
        second = _btn("⚙️ Настройки", RoomCB(action=RoomAction.SETTINGS, room_id=rid))
    else:
        second = _btn("🚪 Выйти", RoomCB(action=RoomAction.LEAVE, room_id=rid))
    kb.row(_btn("🔄 Обновить", RoomCB(action=RoomAction.REFRESH, room_id=rid)), second)
    kb.row(_btn("⬅️ К списку комнат", MenuCB(to=MenuTarget.ROOMS)))
    return kb.as_markup()


def room_settings_kb(o: RoomOverview) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    rid = o.room.id
    if o.is_owner:
        if not o.room.is_archived:
            kb.row(
                _btn("🔄 Перевыпустить ссылку", RoomCB(action=RoomAction.INVITE_REGEN, room_id=rid))
            )
            kb.row(_btn("📦 Архивировать комнату", RoomCB(action=RoomAction.ARCHIVE, room_id=rid)))
        kb.row(_btn("🗑 Удалить комнату", RoomCB(action=RoomAction.DELETE, room_id=rid)))
    kb.row(_btn("⬅️ Назад", RoomCB(action=RoomAction.OPEN, room_id=rid)))
    return kb.as_markup()


def inactive_room_kb(room_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(_btn("✋ Оставить", KeepRoomCB(room_id=room_id)))
    kb.row(
        _btn(
            "📦 В архив (сохранить историю)", RoomCB(action=RoomAction.ARCHIVE_YES, room_id=room_id)
        )
    )
    kb.row(_btn("🗑 Удалить сейчас", RoomCB(action=RoomAction.DELETE_YES, room_id=room_id)))
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
