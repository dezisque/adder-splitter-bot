from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.application.services.member_service import MemberService
from src.application.services.room_service import RoomService
from src.domain.entities import User
from src.presentation.bot import formatters, texts
from src.presentation.bot.callbacks import MemberAction, MemberCB, RoomAction, RoomCB
from src.presentation.bot.keyboards.expense import cancel_kb
from src.presentation.bot.keyboards.room import confirm_kb, members_kb
from src.presentation.bot.states import AddVirtualMember
from src.presentation.bot.utils import edit_or_answer

router = Router(name="members")


@router.callback_query(RoomCB.filter(F.action == RoomAction.MEMBERS))
async def cb_members(
    callback: CallbackQuery,
    callback_data: RoomCB,
    user: User,
    room_service: RoomService,
    member_service: MemberService,
) -> None:
    overview = await room_service.get_overview(user, callback_data.room_id)
    participants = await member_service.list_members(user, callback_data.room_id)
    await edit_or_answer(
        callback,
        formatters.members_list(overview.room, participants),
        members_kb(overview, participants),
    )
    await callback.answer()


@router.callback_query(MemberCB.filter(F.action == MemberAction.ADD_VIRTUAL))
async def cb_add_virtual(
    callback: CallbackQuery, callback_data: MemberCB, state: FSMContext
) -> None:
    await state.set_state(AddVirtualMember.name)
    await state.update_data(room_id=callback_data.room_id)
    await edit_or_answer(callback, texts.MEMBER_NAME_PROMPT, cancel_kb())
    await callback.answer()


@router.message(AddVirtualMember.name, F.text)
async def add_virtual_name(
    message: Message,
    state: FSMContext,
    user: User,
    member_service: MemberService,
    room_service: RoomService,
) -> None:
    data = await state.get_data()
    room_id: int = data["room_id"]
    await member_service.add_virtual(user, room_id, message.text or "")
    await state.clear()
    overview = await room_service.get_overview(user, room_id)
    participants = await member_service.list_members(user, room_id)
    await message.answer(
        formatters.members_list(overview.room, participants),
        reply_markup=members_kb(overview, participants),
    )


@router.callback_query(MemberCB.filter(F.action == MemberAction.REMOVE))
async def cb_remove_member(
    callback: CallbackQuery, callback_data: MemberCB, user: User, member_service: MemberService
) -> None:
    participants = await member_service.list_members(user, callback_data.room_id)
    target = next((p for p in participants if p.id == callback_data.participant_id), None)
    if target is None:
        await callback.answer(texts.STALE_BUTTON, show_alert=True)
        return
    await edit_or_answer(
        callback,
        f"Удалить {formatters.name(target)} из комнаты?\n\n"
        "История расходов сохранится, а долги останутся в балансе, пока не будут закрыты.",
        confirm_kb(
            yes=MemberCB(
                action=MemberAction.REMOVE_YES,
                room_id=callback_data.room_id,
                participant_id=callback_data.participant_id,
            ),
            no=RoomCB(action=RoomAction.MEMBERS, room_id=callback_data.room_id),
        ),
    )
    await callback.answer()


@router.callback_query(MemberCB.filter(F.action == MemberAction.REMOVE_YES))
async def cb_remove_member_yes(
    callback: CallbackQuery,
    callback_data: MemberCB,
    user: User,
    member_service: MemberService,
    room_service: RoomService,
) -> None:
    await member_service.remove_member(user, callback_data.room_id, callback_data.participant_id)
    overview = await room_service.get_overview(user, callback_data.room_id)
    participants = await member_service.list_members(user, callback_data.room_id)
    await edit_or_answer(
        callback,
        formatters.members_list(overview.room, participants),
        members_kb(overview, participants),
    )
    await callback.answer("Участник удалён")
