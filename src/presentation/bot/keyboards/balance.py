from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.domain.entities import Participant
from src.presentation.bot import formatters
from src.presentation.bot.callbacks import (
    CancelCB,
    RepayFromCB,
    RepayToCB,
    RoomAction,
    RoomCB,
)


def balance_kb(room_id: int, can_repay: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if can_repay:
        kb.button(
            text="✅ Отметить возврат",
            callback_data=RoomCB(action=RoomAction.REPAY, room_id=room_id),
        )
    kb.button(text="⬅️ К комнате", callback_data=RoomCB(action=RoomAction.OPEN, room_id=room_id))
    kb.adjust(1)
    return kb.as_markup()


def repay_payer_kb(participants: list[Participant], self_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in participants:
        mark = "👉 " if p.id == self_id else ""
        kb.button(
            text=f"{mark}{formatters.button_name(p)}",
            callback_data=RepayFromCB(participant_id=p.id),
        )
    kb.adjust(2)
    ctrl = InlineKeyboardBuilder()
    ctrl.button(text="✖️ Отмена", callback_data=CancelCB())
    kb.attach(ctrl)
    return kb.as_markup()


def repay_recipient_kb(participants: list[Participant], exclude_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in participants:
        if p.id == exclude_id:
            continue
        kb.button(text=formatters.button_name(p), callback_data=RepayToCB(participant_id=p.id))
    kb.adjust(2)
    ctrl = InlineKeyboardBuilder()
    ctrl.button(text="✖️ Отмена", callback_data=CancelCB())
    kb.attach(ctrl)
    return kb.as_markup()
