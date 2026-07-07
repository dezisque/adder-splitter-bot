from aiogram import Router
from aiogram.filters import Command, ExceptionTypeFilter, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ErrorEvent, Message

from src.domain.exceptions import DomainError
from src.presentation.bot import texts
from src.presentation.bot.callbacks import CancelCB
from src.presentation.bot.keyboards.menu import main_menu_kb
from src.presentation.bot.utils import edit_or_answer

router = Router(name="common")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(texts.NOTHING_TO_CANCEL)
        return
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=main_menu_kb())


@router.callback_query(CancelCB.filter())
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await edit_or_answer(callback, texts.CANCELLED, main_menu_kb())
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
