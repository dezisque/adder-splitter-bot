from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.application.dto import ExpenseCard, HistoryPage
from src.domain.entities import Participant
from src.domain.enums import ExpenseKind
from src.presentation.bot import formatters
from src.presentation.bot.callbacks import (
    CancelCB,
    ConfirmCB,
    EditPayerCB,
    ExpAction,
    ExpCB,
    ExpListCB,
    PayerCB,
    RoomAction,
    RoomCB,
    SplitAction,
    SplitCB,
)


def cancel_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✖️ Отмена", callback_data=CancelCB())
    return kb.as_markup()


def payer_kb(participants: list[Participant], suggested_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in participants:
        mark = "👉 " if p.id == suggested_id else ""
        kb.button(
            text=f"{mark}{formatters.button_name(p)}",
            callback_data=PayerCB(participant_id=p.id),
        )
    kb.adjust(2)
    ctrl = InlineKeyboardBuilder()
    ctrl.button(text="✖️ Отмена", callback_data=CancelCB())
    kb.attach(ctrl)
    return kb.as_markup()


def split_kb(participants: list[Participant], selected: set[int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in participants:
        mark = "☑️" if p.id in selected else "⬜️"
        kb.button(
            text=f"{mark} {formatters.button_name(p)}",
            callback_data=SplitCB(action=SplitAction.TOGGLE, participant_id=p.id),
        )
    kb.adjust(2)
    ctrl = InlineKeyboardBuilder()
    ctrl.button(
        text="Выбрать всех", callback_data=SplitCB(action=SplitAction.ALL, participant_id=0)
    )
    ctrl.button(text="✅ Готово", callback_data=SplitCB(action=SplitAction.DONE, participant_id=0))
    ctrl.button(text="✖️ Отмена", callback_data=CancelCB())
    ctrl.adjust(2, 1)
    kb.attach(ctrl)
    return kb.as_markup()


def confirm_expense_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Сохранить", callback_data=ConfirmCB())
    kb.button(text="✖️ Отмена", callback_data=CancelCB())
    kb.adjust(2)
    return kb.as_markup()


def history_kb(page: HistoryPage, room_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for item in page.items:
        kb.button(
            text=formatters.history_button(item.kind, item.description, item.amount, page.currency),
            callback_data=ExpCB(action=ExpAction.VIEW, expense_id=item.expense_id),
        )
    kb.adjust(1)
    if page.total_pages > 1:
        nav = InlineKeyboardBuilder()
        if page.page > 0:
            nav.button(text="⬅️", callback_data=ExpListCB(room_id=room_id, page=page.page - 1))
        if page.page < page.total_pages - 1:
            nav.button(text="➡️", callback_data=ExpListCB(room_id=room_id, page=page.page + 1))
        nav.adjust(2)
        kb.attach(nav)
    back = InlineKeyboardBuilder()
    back.button(text="⬅️ К комнате", callback_data=RoomCB(action=RoomAction.OPEN, room_id=room_id))
    kb.attach(back)
    return kb.as_markup()


def expense_card_kb(card: ExpenseCard) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    eid = card.expense.id
    if card.can_edit and not card.room.is_archived:
        kb.button(
            text="✏️ Описание", callback_data=ExpCB(action=ExpAction.EDIT_DESC, expense_id=eid)
        )
        kb.button(
            text="💰 Сумма", callback_data=ExpCB(action=ExpAction.EDIT_AMOUNT, expense_id=eid)
        )
        if card.expense.kind is ExpenseKind.EXPENSE:
            kb.button(
                text="👤 Плательщик",
                callback_data=ExpCB(action=ExpAction.EDIT_PAYER, expense_id=eid),
            )
            kb.button(
                text="👥 Делёжка", callback_data=ExpCB(action=ExpAction.EDIT_SPLIT, expense_id=eid)
            )
        kb.button(text="🗑 Удалить", callback_data=ExpCB(action=ExpAction.DELETE, expense_id=eid))
    kb.button(text="⬅️ К истории", callback_data=ExpListCB(room_id=card.expense.room_id, page=0))
    kb.adjust(2)
    return kb.as_markup()


def edit_payer_kb(participants: list[Participant], expense_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in participants:
        kb.button(
            text=formatters.button_name(p),
            callback_data=EditPayerCB(expense_id=expense_id, participant_id=p.id),
        )
    kb.adjust(2)
    back = InlineKeyboardBuilder()
    back.button(text="⬅️ Назад", callback_data=ExpCB(action=ExpAction.VIEW, expense_id=expense_id))
    kb.attach(back)
    return kb.as_markup()
