from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from src.application.services.balance_service import BalanceService
from src.application.services.member_service import MemberService
from src.application.services.room_service import RoomService
from src.domain.entities import Room, User
from src.presentation.bot import formatters, texts
from src.presentation.bot.callbacks import KeepRoomCB, MenuCB, MenuTarget, RoomAction, RoomCB
from src.presentation.bot.keyboards.expense import cancel_kb
from src.presentation.bot.keyboards.menu import main_menu_kb
from src.presentation.bot.keyboards.room import (
    archived_rooms_kb,
    confirm_kb,
    invite_kb,
    room_card_kb,
    room_settings_kb,
    rooms_list_kb,
)
from src.presentation.bot.states import CreateRoom
from src.presentation.bot.utils import edit_or_answer

router = Router(name="rooms")


def _rooms_screen(rooms: list[Room]) -> tuple[str, InlineKeyboardMarkup]:
    """Список комнат: активные + папка «Архив», если есть что прятать."""
    active = [r for r in rooms if not r.is_archived]
    text = texts.ROOMS_LIST if rooms else texts.NO_ROOMS
    return text, rooms_list_kb(active, archived_count=len(rooms) - len(active))


# ---------- навигация ----------


@router.callback_query(MenuCB.filter(F.to == MenuTarget.MAIN))
async def cb_main_menu(callback: CallbackQuery) -> None:
    await edit_or_answer(callback, texts.START, main_menu_kb())
    await callback.answer()


@router.message(Command("rooms"))
async def cmd_rooms(
    message: Message, state: FSMContext, user: User, room_service: RoomService
) -> None:
    await state.clear()
    text, kb = _rooms_screen(await room_service.list_for_user(user))
    await message.answer(text, reply_markup=kb)


@router.callback_query(MenuCB.filter(F.to == MenuTarget.ROOMS))
async def cb_rooms(callback: CallbackQuery, user: User, room_service: RoomService) -> None:
    text, kb = _rooms_screen(await room_service.list_for_user(user))
    await edit_or_answer(callback, text, kb)
    await callback.answer()


@router.callback_query(MenuCB.filter(F.to == MenuTarget.ARCHIVED))
async def cb_rooms_archived(callback: CallbackQuery, user: User, room_service: RoomService) -> None:
    archived = [r for r in await room_service.list_for_user(user) if r.is_archived]
    await edit_or_answer(callback, texts.ARCHIVED_LIST, archived_rooms_kb(archived))
    await callback.answer()


# ---------- создание комнаты ----------


@router.message(Command("newroom"))
async def cmd_newroom(message: Message, state: FSMContext) -> None:
    await state.set_state(CreateRoom.title)
    await message.answer(texts.ROOM_TITLE_PROMPT, reply_markup=cancel_kb())


@router.callback_query(MenuCB.filter(F.to == MenuTarget.NEW_ROOM))
async def cb_newroom(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CreateRoom.title)
    await edit_or_answer(callback, texts.ROOM_TITLE_PROMPT, cancel_kb())
    await callback.answer()


@router.message(CreateRoom.title, F.text)
async def create_room_title(
    message: Message, state: FSMContext, user: User, room_service: RoomService
) -> None:
    room = await room_service.create(user, message.text or "")
    await state.clear()
    overview = await room_service.get_overview(user, room.id)
    await message.answer(formatters.room_card(overview), reply_markup=room_card_kb(overview))


# ---------- карточка комнаты ----------


@router.callback_query(RoomCB.filter(F.action == RoomAction.OPEN))
async def cb_room_open(
    callback: CallbackQuery, callback_data: RoomCB, user: User, room_service: RoomService
) -> None:
    overview = await room_service.get_overview(user, callback_data.room_id)
    await edit_or_answer(callback, formatters.room_card(overview), room_card_kb(overview))
    await callback.answer()


@router.callback_query(RoomCB.filter(F.action == RoomAction.REFRESH))
async def cb_room_refresh(
    callback: CallbackQuery, callback_data: RoomCB, user: User, room_service: RoomService
) -> None:
    overview = await room_service.get_overview(user, callback_data.room_id)
    await edit_or_answer(callback, formatters.room_card(overview), room_card_kb(overview))
    await callback.answer("Обновлено ✅")


@router.callback_query(KeepRoomCB.filter())
async def cb_keep_room(
    callback: CallbackQuery, callback_data: KeepRoomCB, user: User, room_service: RoomService
) -> None:
    await room_service.keep_alive(user, callback_data.room_id)
    overview = await room_service.get_overview(user, callback_data.room_id)
    await edit_or_answer(
        callback,
        f"{texts.ROOM_KEPT}\n\n{formatters.room_card(overview)}",
        room_card_kb(overview),
    )
    await callback.answer()


# ---------- приглашение ----------


async def _show_invite(
    callback: CallbackQuery, user: User, room_service: RoomService, room_id: int, bot: Bot
) -> None:
    overview = await room_service.get_overview(user, room_id)
    me = await bot.me()
    link = f"https://t.me/{me.username}?start=join_{overview.room.invite_token}"
    await edit_or_answer(callback, formatters.invite_text(overview.room, link), invite_kb(overview))


@router.callback_query(RoomCB.filter(F.action == RoomAction.INVITE))
async def cb_invite(
    callback: CallbackQuery,
    callback_data: RoomCB,
    user: User,
    room_service: RoomService,
    bot: Bot,
) -> None:
    await _show_invite(callback, user, room_service, callback_data.room_id, bot)
    await callback.answer()


@router.callback_query(RoomCB.filter(F.action == RoomAction.INVITE_REGEN))
async def cb_invite_regen(
    callback: CallbackQuery,
    callback_data: RoomCB,
    user: User,
    room_service: RoomService,
    bot: Bot,
) -> None:
    await room_service.regenerate_invite(user, callback_data.room_id)
    await _show_invite(callback, user, room_service, callback_data.room_id, bot)
    await callback.answer(texts.INVITE_REGENERATED)


# ---------- настройки ----------


@router.callback_query(RoomCB.filter(F.action == RoomAction.SETTINGS))
async def cb_settings(
    callback: CallbackQuery, callback_data: RoomCB, user: User, room_service: RoomService
) -> None:
    overview = await room_service.get_overview(user, callback_data.room_id)
    await edit_or_answer(callback, "⚙️ <b>Настройки</b>", room_settings_kb(overview))
    await callback.answer()


@router.callback_query(RoomCB.filter(F.action == RoomAction.ARCHIVE))
async def cb_archive(callback: CallbackQuery, callback_data: RoomCB) -> None:
    room_id = callback_data.room_id
    await edit_or_answer(
        callback,
        "Архивировать комнату? Она станет доступна только для просмотра.",
        confirm_kb(
            yes=RoomCB(action=RoomAction.ARCHIVE_YES, room_id=room_id),
            no=RoomCB(action=RoomAction.SETTINGS, room_id=room_id),
        ),
    )
    await callback.answer()


@router.callback_query(RoomCB.filter(F.action == RoomAction.ARCHIVE_YES))
async def cb_archive_yes(
    callback: CallbackQuery, callback_data: RoomCB, user: User, room_service: RoomService
) -> None:
    await room_service.archive(user, callback_data.room_id)
    overview = await room_service.get_overview(user, callback_data.room_id)
    await edit_or_answer(callback, formatters.room_card(overview), room_card_kb(overview))
    await callback.answer("Комната в архиве")


# ---------- удаление комнаты ----------


@router.callback_query(RoomCB.filter(F.action == RoomAction.DELETE))
async def cb_delete_room(
    callback: CallbackQuery, callback_data: RoomCB, user: User, room_service: RoomService
) -> None:
    overview = await room_service.get_overview(user, callback_data.room_id)
    title = escape(overview.room.title)
    await edit_or_answer(
        callback,
        f"Удалить комнату «{title}» <b>безвозвратно</b>?\n\n"
        "Все расходы, участники и история будут стёрты. Отменить это нельзя.",
        confirm_kb(
            yes=RoomCB(action=RoomAction.DELETE_YES, room_id=callback_data.room_id),
            no=RoomCB(action=RoomAction.SETTINGS, room_id=callback_data.room_id),
        ),
    )
    await callback.answer()


@router.callback_query(RoomCB.filter(F.action == RoomAction.DELETE_YES))
async def cb_delete_room_yes(
    callback: CallbackQuery, callback_data: RoomCB, user: User, room_service: RoomService
) -> None:
    await room_service.delete(user, callback_data.room_id)
    text, kb = _rooms_screen(await room_service.list_for_user(user))
    await edit_or_answer(callback, f"🗑 Комната удалена.\n\n{text}", kb)
    await callback.answer("Комната удалена")


# ---------- выход из комнаты ----------


@router.callback_query(RoomCB.filter(F.action == RoomAction.LEAVE))
async def cb_leave(
    callback: CallbackQuery,
    callback_data: RoomCB,
    user: User,
    room_service: RoomService,
    balance_service: BalanceService,
) -> None:
    room_id = callback_data.room_id
    overview = await room_service.get_overview(user, room_id)
    view = await balance_service.get(user, room_id)
    my_net = next((e.net for e in view.lines if e.participant.id == overview.me.id), 0)
    warning = ""
    if my_net != 0:
        amount = formatters.signed_money(my_net, overview.room.currency)
        warning = f"\n\n⚠️ Ваш баланс не закрыт: <b>{amount}</b>"
    await edit_or_answer(
        callback,
        f"Выйти из комнаты?{warning}",
        confirm_kb(
            yes=RoomCB(action=RoomAction.LEAVE_YES, room_id=room_id),
            no=RoomCB(action=RoomAction.OPEN, room_id=room_id),
        ),
    )
    await callback.answer()


@router.callback_query(RoomCB.filter(F.action == RoomAction.LEAVE_YES))
async def cb_leave_yes(
    callback: CallbackQuery,
    callback_data: RoomCB,
    user: User,
    member_service: MemberService,
    room_service: RoomService,
) -> None:
    await member_service.leave(user, callback_data.room_id)
    text, kb = _rooms_screen(await room_service.list_for_user(user))
    await edit_or_answer(callback, f"Вы вышли из комнаты.\n\n{text}", kb)
    await callback.answer()
