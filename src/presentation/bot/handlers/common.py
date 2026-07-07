from aiogram import Router
from aiogram.filters import Command, ExceptionTypeFilter, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ErrorEvent, InlineKeyboardMarkup, Message

from src.application.services.balance_service import BalanceService
from src.application.services.expense_service import ExpenseService
from src.application.services.member_service import MemberService
from src.application.services.room_service import RoomService
from src.domain.entities import User
from src.domain.exceptions import DomainError
from src.presentation.bot import formatters, texts
from src.presentation.bot.callbacks import CancelCB
from src.presentation.bot.keyboards.balance import balance_kb
from src.presentation.bot.keyboards.expense import expense_card_kb
from src.presentation.bot.keyboards.menu import main_menu_kb
from src.presentation.bot.keyboards.room import members_kb, room_card_kb
from src.presentation.bot.states import AddExpense, AddRepayment, AddVirtualMember, EditExpense
from src.presentation.bot.utils import edit_or_answer

router = Router(name="common")

_EDIT_EXPENSE_STATES = {s.state for s in EditExpense.__all_states__}
_ADD_EXPENSE_STATES = {s.state for s in AddExpense.__all_states__}
_ADD_REPAYMENT_STATES = {s.state for s in AddRepayment.__all_states__}
_ADD_MEMBER_STATES = {s.state for s in AddVirtualMember.__all_states__}


async def _screen_after_cancel(
    user: User,
    current_state: str | None,
    data: dict[str, int],
    expense_service: ExpenseService,
    room_service: RoomService,
    member_service: MemberService,
    balance_service: BalanceService,
) -> tuple[str, InlineKeyboardMarkup]:
    """Отмена возвращает на экран, с которого начался диалог, а не в главное меню."""
    try:
        if current_state in _EDIT_EXPENSE_STATES and "expense_id" in data:
            card = await expense_service.get_card(user, data["expense_id"])
            return (
                f"{texts.CANCELLED}\n\n{formatters.expense_card(card)}",
                expense_card_kb(card),
            )
        room_id = data.get("room_id")
        if room_id is not None:
            if current_state in _ADD_REPAYMENT_STATES:
                view = await balance_service.get(user, room_id)
                return (
                    f"{texts.CANCELLED}\n\n{formatters.balance(view)}",
                    balance_kb(room_id, can_repay=not view.room.is_archived),
                )
            if current_state in _ADD_MEMBER_STATES:
                overview = await room_service.get_overview(user, room_id)
                members = await member_service.list_members_view(user, room_id)
                return (
                    f"{texts.CANCELLED}\n\n{formatters.members_list(overview.room, members)}",
                    members_kb(overview, [m.participant for m in members]),
                )
            if current_state in _ADD_EXPENSE_STATES:
                overview = await room_service.get_overview(user, room_id)
                return (
                    f"{texts.CANCELLED}\n\n{formatters.room_card(overview)}",
                    room_card_kb(overview),
                )
    except DomainError:
        pass  # контекст исчез (запись/комнату удалили) — падаем в меню
    return texts.CANCELLED, main_menu_kb()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP)


@router.message(Command("cancel"))
async def cmd_cancel(
    message: Message,
    state: FSMContext,
    user: User,
    expense_service: ExpenseService,
    room_service: RoomService,
    member_service: MemberService,
    balance_service: BalanceService,
) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer(texts.NOTHING_TO_CANCEL)
        return
    data = await state.get_data()
    await state.clear()
    text, kb = await _screen_after_cancel(
        user, current, data, expense_service, room_service, member_service, balance_service
    )
    await message.answer(text, reply_markup=kb)


@router.callback_query(CancelCB.filter())
async def cb_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    expense_service: ExpenseService,
    room_service: RoomService,
    member_service: MemberService,
    balance_service: BalanceService,
) -> None:
    current = await state.get_state()
    data = await state.get_data()
    await state.clear()
    text, kb = await _screen_after_cancel(
        user, current, data, expense_service, room_service, member_service, balance_service
    )
    await edit_or_answer(callback, text, kb)
    await callback.answer()


# Постоянный fallback: неизвестные и устаревшие кнопки. Должен регистрироваться последним.
@router.callback_query()
async def stale_callback(callback: CallbackQuery) -> None:
    await callback.answer(texts.STALE_BUTTON)


@router.message(StateFilter(None))
async def unknown_message(message: Message) -> None:
    await message.answer(texts.UNKNOWN)


# Активный диалог, но прислали не текст (стикер, фото и т.п.)
@router.message()
async def non_text_in_dialog(message: Message) -> None:
    await message.answer(texts.SEND_TEXT_HINT)


@router.errors(ExceptionTypeFilter(DomainError))
async def on_domain_error(event: ErrorEvent) -> None:
    """Ожидаемые бизнес-ошибки показываем пользователю, а не роняем апдейт."""
    message_text = str(event.exception)
    if event.update.callback_query is not None:
        await event.update.callback_query.answer(message_text, show_alert=True)
    elif event.update.message is not None:
        await event.update.message.answer(message_text)
