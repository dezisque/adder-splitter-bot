"""Быстрое добавление расхода одной строкой: «Мясо 2450».

Текст без активного диалога трактуется как черновик расхода в «текущей»
комнате (последней открытой). Без суммы — отдельный шаг «Сколько стоило?».
По умолчанию платит автор, делится на всех; перед сохранением всегда превью.
"""

from html import escape

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from src.application.services.member_service import MemberService
from src.application.services.room_service import RoomService
from src.domain import limits
from src.domain.entities import Room, User
from src.domain.exceptions import InvalidInput
from src.presentation.bot import formatters, texts
from src.presentation.bot.callbacks import QuickAdjustCB, QuickRoomCB
from src.presentation.bot.keyboards.expense import (
    cancel_kb,
    payer_kb,
    quick_confirm_kb,
    quick_room_picker_kb,
)
from src.presentation.bot.states import AddExpense, QuickAdd
from src.presentation.bot.utils import edit_or_answer, is_amount_only, parse_quick_expense

router = Router(name="quick_add")


async def build_quick_preview(
    state: FSMContext, user: User, member_service: MemberService
) -> tuple[str, InlineKeyboardMarkup]:
    """Превью с умолчаниями: платит автор, делится на всех. Ставит state=confirm."""
    data = await state.get_data()
    participants = await member_service.list_members(user, data["room_id"])
    payer = next((p for p in participants if p.id == data["me_id"]), participants[0])
    selected = [p.id for p in participants]
    await state.update_data(payer_id=payer.id, split_ids=selected)
    await state.set_state(AddExpense.confirm)
    text = formatters.expense_preview(
        data["description"],
        data["amount"],
        data["currency"],
        payer,
        participants,
        room_title=data.get("room_title"),
    )
    return text, quick_confirm_kb()


def _amount_prompt(description: str) -> str:
    return (
        f"Сколько стоило «<b>{escape(description)}</b>»?\n\n"
        "Отправьте сумму, например: <b>2450</b> или <b>2450,50</b>"
    )


async def _start_draft(
    message: Message,
    state: FSMContext,
    user: User,
    room: Room,
    description: str,
    amount: int | None,
    member_service: MemberService,
) -> None:
    participants = await member_service.list_members(user, room.id)
    me = next((p for p in participants if p.user_id == user.id), None)
    if me is None:
        await message.answer(texts.UNKNOWN)
        return
    await state.update_data(
        room_id=room.id,
        me_id=me.id,
        currency=room.currency,
        room_title=room.title,
        description=description,
        quick=True,
    )
    if amount is None:
        await state.set_state(AddExpense.amount)
        await message.answer(_amount_prompt(description), reply_markup=cancel_kb())
        return
    await state.update_data(amount=amount)
    text, kb = await build_quick_preview(state, user, member_service)
    await message.answer(text, reply_markup=kb)


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def quick_add_entry(
    message: Message,
    state: FSMContext,
    user: User,
    room_service: RoomService,
    member_service: MemberService,
) -> None:
    raw = (message.text or "").strip()
    if not raw:
        return
    if is_amount_only(raw):
        await message.answer(texts.QUICK_NEED_DESC)
        return
    description, amount = parse_quick_expense(raw)
    if len(description) > limits.MAX_EXPENSE_DESCRIPTION_LEN:
        raise InvalidInput(
            f"Описание — до {limits.MAX_EXPENSE_DESCRIPTION_LEN} символов. Попробуйте короче."
        )

    rooms = [r for r in await room_service.list_for_user(user) if not r.is_archived]
    if not rooms:
        await message.answer(texts.QUICK_NO_ROOMS)
        return
    room = next((r for r in rooms if r.id == user.current_room_id), None)
    if room is None and len(rooms) == 1:
        room = rooms[0]
    if room is None:
        await state.set_state(QuickAdd.room)
        await state.update_data(description=description, amount=amount)
        label = formatters.money(amount, limits.DEFAULT_CURRENCY) if amount is not None else "…"
        await message.answer(
            f"В какую комнату добавить «<b>{escape(description)}</b> — {label}»?",
            reply_markup=quick_room_picker_kb(rooms),
        )
        return
    await _start_draft(message, state, user, room, description, amount, member_service)


@router.callback_query(QuickAdd.room, QuickRoomCB.filter())
async def quick_pick_room(
    callback: CallbackQuery,
    callback_data: QuickRoomCB,
    state: FSMContext,
    user: User,
    room_service: RoomService,
    member_service: MemberService,
) -> None:
    data = await state.get_data()
    overview = await room_service.get_overview(user, callback_data.room_id)
    if overview.room.is_archived:
        await callback.answer(texts.ROOM_ARCHIVED_ALERT, show_alert=True)
        return
    description: str = data["description"]
    amount: int | None = data.get("amount")
    await state.update_data(
        room_id=overview.room.id,
        me_id=overview.me.id,
        currency=overview.room.currency,
        room_title=overview.room.title,
        quick=True,
    )
    if amount is None:
        await state.set_state(AddExpense.amount)
        await edit_or_answer(callback, _amount_prompt(description), cancel_kb())
    else:
        text, kb = await build_quick_preview(state, user, member_service)
        await edit_or_answer(callback, text, kb)
    await callback.answer()


@router.callback_query(AddExpense.confirm, QuickAdjustCB.filter())
async def quick_adjust(
    callback: CallbackQuery, state: FSMContext, user: User, member_service: MemberService
) -> None:
    """«Настроить»: переход в обычные шаги выбора плательщика и делёжки."""
    data = await state.get_data()
    participants = await member_service.list_members(user, data["room_id"])
    await state.set_state(AddExpense.payer)
    await edit_or_answer(
        callback, texts.EXPENSE_PAYER_PROMPT, payer_kb(participants, data["me_id"])
    )
    await callback.answer()
