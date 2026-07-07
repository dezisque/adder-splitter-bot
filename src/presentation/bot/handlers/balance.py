from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.application.services.balance_service import BalanceService
from src.application.services.expense_service import ExpenseService
from src.application.services.member_service import MemberService
from src.application.services.room_service import RoomService
from src.domain.entities import User
from src.presentation.bot import formatters, texts
from src.presentation.bot.callbacks import RepayFromCB, RepayToCB, RoomAction, RoomCB
from src.presentation.bot.keyboards.balance import (
    balance_kb,
    repay_payer_kb,
    repay_recipient_kb,
)
from src.presentation.bot.keyboards.expense import cancel_kb
from src.presentation.bot.states import AddRepayment
from src.presentation.bot.utils import edit_or_answer, parse_amount

router = Router(name="balance")


@router.callback_query(RoomCB.filter(F.action == RoomAction.BALANCE))
async def cb_balance(
    callback: CallbackQuery, callback_data: RoomCB, user: User, balance_service: BalanceService
) -> None:
    view = await balance_service.get(user, callback_data.room_id)
    await edit_or_answer(
        callback,
        formatters.balance(view),
        balance_kb(callback_data.room_id, can_repay=not view.room.is_archived),
    )
    await callback.answer()


# ---------- возврат долга ----------


@router.callback_query(RoomCB.filter(F.action == RoomAction.REPAY))
async def cb_repay_start(
    callback: CallbackQuery,
    callback_data: RoomCB,
    state: FSMContext,
    user: User,
    room_service: RoomService,
    member_service: MemberService,
) -> None:
    overview = await room_service.get_overview(user, callback_data.room_id)
    if overview.room.is_archived:
        await callback.answer(texts.ROOM_ARCHIVED_ALERT, show_alert=True)
        return
    participants = await member_service.list_members(user, callback_data.room_id)
    await state.set_state(AddRepayment.payer)
    await state.update_data(room_id=callback_data.room_id)
    await edit_or_answer(
        callback, texts.REPAY_FROM_PROMPT, repay_payer_kb(participants, overview.me.id)
    )
    await callback.answer()


@router.callback_query(AddRepayment.payer, RepayFromCB.filter())
async def cb_repay_from(
    callback: CallbackQuery,
    callback_data: RepayFromCB,
    state: FSMContext,
    user: User,
    member_service: MemberService,
) -> None:
    data = await state.get_data()
    participants = await member_service.list_members(user, data["room_id"])
    await state.update_data(from_id=callback_data.participant_id)
    await state.set_state(AddRepayment.recipient)
    await edit_or_answer(
        callback,
        texts.REPAY_TO_PROMPT,
        repay_recipient_kb(participants, callback_data.participant_id),
    )
    await callback.answer()


@router.callback_query(AddRepayment.recipient, RepayToCB.filter())
async def cb_repay_to(
    callback: CallbackQuery,
    callback_data: RepayToCB,
    state: FSMContext,
    user: User,
    balance_service: BalanceService,
) -> None:
    data = await state.get_data()
    await state.update_data(to_id=callback_data.participant_id)
    await state.set_state(AddRepayment.amount)

    # подсказка: сколько по расчёту должен вернуть выбранный участник
    view = await balance_service.get(user, data["room_id"])
    suggestion = next(
        (
            t.amount
            for t in view.transfers
            if t.from_participant.id == data["from_id"]
            and t.to_participant.id == callback_data.participant_id
        ),
        None,
    )
    hint = "Какую сумму вернули?"
    if suggestion is not None:
        hint += f"\n\nПо расчёту долг: <b>{formatters.money(suggestion, view.room.currency)}</b>"
    await edit_or_answer(callback, hint, cancel_kb())
    await callback.answer()


@router.message(AddRepayment.amount, F.text)
async def repay_amount(
    message: Message,
    state: FSMContext,
    user: User,
    expense_service: ExpenseService,
    balance_service: BalanceService,
) -> None:
    amount = parse_amount(message.text or "")
    data = await state.get_data()
    await expense_service.add_repayment(
        user,
        room_id=data["room_id"],
        from_participant_id=data["from_id"],
        to_participant_id=data["to_id"],
        amount=amount,
    )
    await state.clear()
    view = await balance_service.get(user, data["room_id"])
    await message.answer(
        f"{texts.REPAY_SAVED}\n\n{formatters.balance(view)}",
        reply_markup=balance_kb(data["room_id"], can_repay=True),
    )
