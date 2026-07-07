from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.application.services.member_service import MemberService
from src.application.services.room_service import RoomService
from src.domain.entities import User
from src.presentation.bot import formatters, texts
from src.presentation.bot.keyboards.menu import main_menu_kb
from src.presentation.bot.keyboards.room import room_card_kb

router = Router(name="start")

_JOIN_PREFIX = "join_"


@router.message(CommandStart(deep_link=True))
async def cmd_start_deep_link(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    user: User,
    member_service: MemberService,
    room_service: RoomService,
) -> None:
    await state.clear()
    payload = command.args or ""
    if not payload.startswith(_JOIN_PREFIX):
        await message.answer(texts.START, reply_markup=main_menu_kb())
        return
    room, joined = await member_service.join_by_token(user, payload.removeprefix(_JOIN_PREFIX))
    overview = await room_service.get_overview(user, room.id)
    notice = texts.JOINED if joined else texts.ALREADY_MEMBER
    await message.answer(
        f"{notice}\n\n{formatters.room_card(overview)}", reply_markup=room_card_kb(overview)
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.START, reply_markup=main_menu_kb())
