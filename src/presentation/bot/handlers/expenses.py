from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.application.services.expense_service import ExpenseService
from src.application.services.member_service import MemberService
from src.application.services.room_service import RoomService
from src.domain import limits
from src.domain.entities import User
from src.domain.exceptions import InvalidInput
from src.presentation.bot import formatters, texts
from src.presentation.bot.callbacks import (
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
from src.presentation.bot.keyboards.expense import (
    cancel_kb,
    confirm_expense_kb,
    edit_payer_kb,
    expense_card_kb,
    history_kb,
    payer_kb,
    split_kb,
)
from src.presentation.bot.keyboards.room import confirm_kb, room_card_kb
from src.presentation.bot.states import AddExpense, EditExpense
from src.presentation.bot.utils import edit_or_answer, parse_amount

router = Router(name="expenses")


# ---------- добавление расхода ----------


@router.callback_query(RoomCB.filter(F.action == RoomAction.ADD_EXPENSE))
async def add_expense_start(
    callback: CallbackQuery,
    callback_data: RoomCB,
    state: FSMContext,
    user: User,
    room_service: RoomService,
) -> None:
    overview = await room_service.get_overview(user, callback_data.room_id)
    if overview.room.is_archived:
        await callback.answer(texts.ROOM_ARCHIVED_ALERT, show_alert=True)
        return
    await state.set_state(AddExpense.description)
    await state.update_data(
        room_id=overview.room.id, me_id=overview.me.id, currency=overview.room.currency
    )
    await edit_or_answer(callback, texts.EXPENSE_DESC_PROMPT, cancel_kb())
    await callback.answer()


@router.message(AddExpense.description, F.text)
async def add_expense_description(message: Message, state: FSMContext) -> None:
    description = (message.text or "").strip()
    if not description or len(description) > limits.MAX_EXPENSE_DESCRIPTION_LEN:
        raise InvalidInput(
            f"Описание — от 1 до {limits.MAX_EXPENSE_DESCRIPTION_LEN} символов. Попробуйте ещё раз."
        )
    await state.update_data(description=description)
    await state.set_state(AddExpense.amount)
    await message.answer(texts.EXPENSE_AMOUNT_PROMPT, reply_markup=cancel_kb())


@router.message(AddExpense.amount, F.text)
async def add_expense_amount(
    message: Message, state: FSMContext, user: User, member_service: MemberService
) -> None:
    amount = parse_amount(message.text or "")
    data = await state.get_data()
    participants = await member_service.list_members(user, data["room_id"])
    await state.update_data(amount=amount)
    await state.set_state(AddExpense.payer)
    await message.answer(
        texts.EXPENSE_PAYER_PROMPT, reply_markup=payer_kb(participants, data["me_id"])
    )


@router.callback_query(AddExpense.payer, PayerCB.filter())
async def add_expense_payer(
    callback: CallbackQuery,
    callback_data: PayerCB,
    state: FSMContext,
    user: User,
    member_service: MemberService,
) -> None:
    data = await state.get_data()
    participants = await member_service.list_members(user, data["room_id"])
    selected = [p.id for p in participants]  # по умолчанию делим на всех
    await state.update_data(payer_id=callback_data.participant_id, split_ids=selected)
    await state.set_state(AddExpense.split)
    await edit_or_answer(
        callback, texts.EXPENSE_SPLIT_PROMPT, split_kb(participants, set(selected))
    )
    await callback.answer()


async def _toggle_split(
    callback: CallbackQuery,
    callback_data: SplitCB,
    state: FSMContext,
    user: User,
    member_service: MemberService,
) -> None:
    data = await state.get_data()
    participants = await member_service.list_members(user, data["room_id"])
    selected = set(data.get("split_ids", []))
    if callback_data.action is SplitAction.ALL:
        selected = {p.id for p in participants}
    else:
        pid = callback_data.participant_id
        selected.symmetric_difference_update({pid})
    await state.update_data(split_ids=list(selected))
    await edit_or_answer(callback, texts.EXPENSE_SPLIT_PROMPT, split_kb(participants, selected))
    await callback.answer()


@router.callback_query(AddExpense.split, SplitCB.filter(F.action != SplitAction.DONE))
async def add_expense_split_toggle(
    callback: CallbackQuery,
    callback_data: SplitCB,
    state: FSMContext,
    user: User,
    member_service: MemberService,
) -> None:
    await _toggle_split(callback, callback_data, state, user, member_service)


@router.callback_query(AddExpense.split, SplitCB.filter(F.action == SplitAction.DONE))
async def add_expense_split_done(
    callback: CallbackQuery, state: FSMContext, user: User, member_service: MemberService
) -> None:
    data = await state.get_data()
    selected: list[int] = data.get("split_ids", [])
    if not selected:
        await callback.answer(texts.SPLIT_NEED_ONE, show_alert=True)
        return
    participants = await member_service.list_members(user, data["room_id"])
    by_id = {p.id: p for p in participants}
    payer = by_id.get(data["payer_id"])
    split_between = [by_id[pid] for pid in selected if pid in by_id]
    if payer is None or len(split_between) != len(selected):
        await callback.answer(texts.STALE_BUTTON, show_alert=True)
        return
    await state.set_state(AddExpense.confirm)
    preview = formatters.expense_preview(
        data["description"], data["amount"], data["currency"], payer, split_between
    )
    await edit_or_answer(callback, preview, confirm_expense_kb())
    await callback.answer()


@router.callback_query(AddExpense.confirm, ConfirmCB.filter())
async def add_expense_save(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    expense_service: ExpenseService,
    room_service: RoomService,
) -> None:
    data = await state.get_data()
    await expense_service.add(
        user,
        room_id=data["room_id"],
        payer_participant_id=data["payer_id"],
        amount=data["amount"],
        description=data["description"],
        participant_ids=data["split_ids"],
    )
    await state.clear()
    overview = await room_service.get_overview(user, data["room_id"])
    await edit_or_answer(
        callback,
        f"{texts.EXPENSE_SAVED}\n\n{formatters.room_card(overview)}",
        room_card_kb(overview),
    )
    await callback.answer(texts.EXPENSE_SAVED)


# ---------- история ----------


async def _show_history(
    callback: CallbackQuery, user: User, expense_service: ExpenseService, room_id: int, page: int
) -> None:
    history = await expense_service.get_history_page(user, room_id, page)
    await edit_or_answer(
        callback,
        formatters.history_header(history.page, history.total_pages),
        history_kb(history, room_id),
    )
    await callback.answer()


@router.callback_query(RoomCB.filter(F.action == RoomAction.HISTORY))
async def cb_history(
    callback: CallbackQuery, callback_data: RoomCB, user: User, expense_service: ExpenseService
) -> None:
    await _show_history(callback, user, expense_service, callback_data.room_id, 0)


@router.callback_query(ExpListCB.filter())
async def cb_history_page(
    callback: CallbackQuery, callback_data: ExpListCB, user: User, expense_service: ExpenseService
) -> None:
    await _show_history(callback, user, expense_service, callback_data.room_id, callback_data.page)


# ---------- карточка расхода ----------


@router.callback_query(ExpCB.filter(F.action == ExpAction.VIEW))
async def cb_expense_view(
    callback: CallbackQuery, callback_data: ExpCB, user: User, expense_service: ExpenseService
) -> None:
    card = await expense_service.get_card(user, callback_data.expense_id)
    await edit_or_answer(callback, formatters.expense_card(card), expense_card_kb(card))
    await callback.answer()


# ---------- редактирование ----------


@router.callback_query(ExpCB.filter(F.action == ExpAction.EDIT_DESC))
async def cb_edit_desc(callback: CallbackQuery, callback_data: ExpCB, state: FSMContext) -> None:
    await state.set_state(EditExpense.description)
    await state.update_data(expense_id=callback_data.expense_id)
    await edit_or_answer(callback, texts.EXPENSE_NEW_DESC_PROMPT, cancel_kb())
    await callback.answer()


@router.message(EditExpense.description, F.text)
async def edit_desc_value(
    message: Message, state: FSMContext, user: User, expense_service: ExpenseService
) -> None:
    data = await state.get_data()
    await expense_service.edit_description(user, data["expense_id"], message.text or "")
    await state.clear()
    card = await expense_service.get_card(user, data["expense_id"])
    await message.answer(formatters.expense_card(card), reply_markup=expense_card_kb(card))


@router.callback_query(ExpCB.filter(F.action == ExpAction.EDIT_AMOUNT))
async def cb_edit_amount(callback: CallbackQuery, callback_data: ExpCB, state: FSMContext) -> None:
    await state.set_state(EditExpense.amount)
    await state.update_data(expense_id=callback_data.expense_id)
    await edit_or_answer(callback, texts.EXPENSE_NEW_AMOUNT_PROMPT, cancel_kb())
    await callback.answer()


@router.message(EditExpense.amount, F.text)
async def edit_amount_value(
    message: Message, state: FSMContext, user: User, expense_service: ExpenseService
) -> None:
    amount = parse_amount(message.text or "")
    data = await state.get_data()
    await expense_service.edit_amount(user, data["expense_id"], amount)
    await state.clear()
    card = await expense_service.get_card(user, data["expense_id"])
    await message.answer(formatters.expense_card(card), reply_markup=expense_card_kb(card))


@router.callback_query(ExpCB.filter(F.action == ExpAction.EDIT_PAYER))
async def cb_edit_payer(
    callback: CallbackQuery,
    callback_data: ExpCB,
    user: User,
    expense_service: ExpenseService,
    member_service: MemberService,
) -> None:
    card = await expense_service.get_card(user, callback_data.expense_id)
    participants = await member_service.list_members(user, card.expense.room_id)
    await edit_or_answer(
        callback,
        texts.EXPENSE_PAYER_PROMPT,
        edit_payer_kb(participants, callback_data.expense_id),
    )
    await callback.answer()


@router.callback_query(EditPayerCB.filter())
async def cb_edit_payer_value(
    callback: CallbackQuery, callback_data: EditPayerCB, user: User, expense_service: ExpenseService
) -> None:
    await expense_service.edit_payer(user, callback_data.expense_id, callback_data.participant_id)
    card = await expense_service.get_card(user, callback_data.expense_id)
    await edit_or_answer(callback, formatters.expense_card(card), expense_card_kb(card))
    await callback.answer()


@router.callback_query(ExpCB.filter(F.action == ExpAction.EDIT_SPLIT))
async def cb_edit_split(
    callback: CallbackQuery,
    callback_data: ExpCB,
    state: FSMContext,
    user: User,
    expense_service: ExpenseService,
    member_service: MemberService,
) -> None:
    card = await expense_service.get_card(user, callback_data.expense_id)
    participants = await member_service.list_members(user, card.expense.room_id)
    active_ids = {p.id for p in participants}
    selected = [s.participant_id for s in card.expense.shares if s.participant_id in active_ids]
    await state.set_state(EditExpense.split)
    await state.update_data(
        expense_id=callback_data.expense_id,
        room_id=card.expense.room_id,
        split_ids=selected,
    )
    await edit_or_answer(
        callback, texts.EXPENSE_SPLIT_PROMPT, split_kb(participants, set(selected))
    )
    await callback.answer()


@router.callback_query(EditExpense.split, SplitCB.filter(F.action != SplitAction.DONE))
async def edit_split_toggle(
    callback: CallbackQuery,
    callback_data: SplitCB,
    state: FSMContext,
    user: User,
    member_service: MemberService,
) -> None:
    await _toggle_split(callback, callback_data, state, user, member_service)


@router.callback_query(EditExpense.split, SplitCB.filter(F.action == SplitAction.DONE))
async def edit_split_done(
    callback: CallbackQuery, state: FSMContext, user: User, expense_service: ExpenseService
) -> None:
    data = await state.get_data()
    selected: list[int] = data.get("split_ids", [])
    if not selected:
        await callback.answer(texts.SPLIT_NEED_ONE, show_alert=True)
        return
    await expense_service.edit_split(user, data["expense_id"], selected)
    await state.clear()
    card = await expense_service.get_card(user, data["expense_id"])
    await edit_or_answer(callback, formatters.expense_card(card), expense_card_kb(card))
    await callback.answer()


# ---------- удаление ----------


@router.callback_query(ExpCB.filter(F.action == ExpAction.DELETE))
async def cb_delete(
    callback: CallbackQuery, callback_data: ExpCB, user: User, expense_service: ExpenseService
) -> None:
    card = await expense_service.get_card(user, callback_data.expense_id)
    amount = formatters.money(card.expense.amount.amount, card.room.currency)
    await edit_or_answer(
        callback,
        f"Удалить запись «{card.expense.description}» на {amount}?",
        confirm_kb(
            yes=ExpCB(action=ExpAction.DELETE_YES, expense_id=callback_data.expense_id),
            no=ExpCB(action=ExpAction.VIEW, expense_id=callback_data.expense_id),
        ),
    )
    await callback.answer()


@router.callback_query(ExpCB.filter(F.action == ExpAction.DELETE_YES))
async def cb_delete_yes(
    callback: CallbackQuery, callback_data: ExpCB, user: User, expense_service: ExpenseService
) -> None:
    room_id = await expense_service.delete(user, callback_data.expense_id)
    await callback.answer(texts.EXPENSE_DELETED)
    await _show_history(callback, user, expense_service, room_id, 0)
