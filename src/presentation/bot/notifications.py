"""Уведомления участникам комнаты о новых записях."""

import logging
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.domain.entities import Expense, Participant, Room
from src.presentation.bot import formatters
from src.presentation.bot.callbacks import RoomAction, RoomCB

logger = logging.getLogger(__name__)

NotifyTargets = list[tuple[Participant, int | None]]


def _open_room_kb(room_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Открыть комнату", callback_data=RoomCB(action=RoomAction.OPEN, room_id=room_id))
    return kb.as_markup()


async def send_safe(
    bot: Bot, chat_id: int, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    """Отправка без падения апдейта: бот может быть заблокирован получателем."""
    try:
        await bot.send_message(chat_id, text, reply_markup=reply_markup)
    except TelegramAPIError:
        logger.warning("Не удалось доставить сообщение в чат %s", chat_id)


async def notify_expense_added(
    bot: Bot,
    room: Room,
    expense: Expense,
    payer: Participant,
    targets: NotifyTargets,
    actor_telegram_id: int,
) -> None:
    """Сообщает затронутым участникам о новом расходе (кроме автора записи)."""
    currency = room.currency
    shares = {s.participant_id: s.amount for s in expense.shares}
    header = (
        f"➕ Новый расход в «{escape(room.title)}»\n\n"
        f"🧾 {escape(expense.description)} — "
        f"<b>{formatters.money(expense.amount.amount, currency)}</b>\n"
        f"Оплатил: {formatters.name(payer)}"
    )
    for participant, tg_id in targets:
        if tg_id is None or tg_id == actor_telegram_id:
            continue
        share = shares.get(participant.id)
        if share is None and participant.id != expense.paid_by_participant_id:
            continue  # расход человека не касается — не шумим
        share_line = (
            f"\nВаша доля: <b>{formatters.money(share, currency)}</b>" if share is not None else ""
        )
        await send_safe(bot, tg_id, header + share_line, _open_room_kb(room.id))


async def notify_repayment_added(
    bot: Bot,
    room: Room,
    expense: Expense,
    payer: Participant,
    recipient: Participant,
    targets: NotifyTargets,
    actor_telegram_id: int,
) -> None:
    """Сообщает обеим сторонам возврата (кроме того, кто его записал)."""
    text = (
        f"↩️ Возврат в «{escape(room.title)}»\n\n"
        f"{formatters.name(payer)} → {formatters.name(recipient)}: "
        f"<b>{formatters.money(expense.amount.amount, room.currency)}</b>"
    )
    involved = {payer.id, recipient.id}
    for participant, tg_id in targets:
        if tg_id is None or tg_id == actor_telegram_id or participant.id not in involved:
            continue
        await send_safe(bot, tg_id, text, _open_room_kb(room.id))
