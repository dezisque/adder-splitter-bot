from math import ceil

from src.application.dto import ExpenseCard, HistoryItem, HistoryPage
from src.application.interfaces import ExpenseRepo, ParticipantRepo, RoomRepo, UserRepo
from src.application.services._access import ensure_writable, get_room_and_member
from src.domain import limits
from src.domain.entities import Expense, Participant, Room, User
from src.domain.enums import ExpenseKind, SplitType
from src.domain.exceptions import AccessDenied, InvalidInput, LimitExceeded, NotFound
from src.domain.services.split import split_evenly
from src.domain.value_objects import Money

REPAYMENT_DESCRIPTION = "Возврат долга"


def _validate_amount(amount: int) -> None:
    if not limits.MIN_AMOUNT <= amount <= limits.MAX_AMOUNT:
        low = Money(limits.MIN_AMOUNT).format()
        high = Money(limits.MAX_AMOUNT).format()
        raise InvalidInput(f"Сумма должна быть от {low} до {high}")


def _validate_description(description: str) -> str:
    description = description.strip()
    if not description or len(description) > limits.MAX_EXPENSE_DESCRIPTION_LEN:
        raise InvalidInput(
            f"Описание — от 1 до {limits.MAX_EXPENSE_DESCRIPTION_LEN} символов. Попробуйте ещё раз."
        )
    return description


class ExpenseService:
    def __init__(
        self,
        rooms: RoomRepo,
        participants: ParticipantRepo,
        expenses: ExpenseRepo,
        users: UserRepo,
    ) -> None:
        self._rooms = rooms
        self._participants = participants
        self._expenses = expenses
        self._users = users

    async def _active_map(self, room_id: int) -> dict[int, Participant]:
        return {p.id: p for p in await self._participants.list_by_room(room_id)}

    async def add(
        self,
        actor: User,
        *,
        room_id: int,
        payer_participant_id: int,
        amount: int,
        description: str,
        participant_ids: list[int],
    ) -> Expense:
        room, _ = await get_room_and_member(self._rooms, self._participants, actor, room_id)
        ensure_writable(room)
        description = _validate_description(description)
        _validate_amount(amount)
        active = await self._active_map(room.id)
        if payer_participant_id not in active:
            raise InvalidInput("Плательщик не является участником комнаты")
        if not participant_ids or set(participant_ids) - active.keys():
            raise InvalidInput("Список участников делёжки устарел — попробуйте заново")
        if await self._expenses.count(room.id) >= limits.MAX_EXPENSES_PER_ROOM:
            raise LimitExceeded("Достигнут лимит записей в комнате")
        shares = split_evenly(amount, participant_ids)
        return await self._expenses.add(
            room_id=room.id,
            kind=ExpenseKind.EXPENSE,
            paid_by_participant_id=payer_participant_id,
            amount=amount,
            description=description,
            split_type=SplitType.EQUAL,
            created_by_user_id=actor.id,
            shares=shares,
            currency=room.currency,
        )

    async def add_repayment(
        self,
        actor: User,
        *,
        room_id: int,
        from_participant_id: int,
        to_participant_id: int,
        amount: int,
    ) -> Expense:
        room, _ = await get_room_and_member(self._rooms, self._participants, actor, room_id)
        ensure_writable(room)
        _validate_amount(amount)
        if from_participant_id == to_participant_id:
            raise InvalidInput("Нельзя вернуть долг самому себе")
        active = await self._active_map(room.id)
        if from_participant_id not in active or to_participant_id not in active:
            raise InvalidInput("Участник не найден — попробуйте заново")
        return await self._expenses.add(
            room_id=room.id,
            kind=ExpenseKind.REPAYMENT,
            paid_by_participant_id=from_participant_id,
            amount=amount,
            description=REPAYMENT_DESCRIPTION,
            split_type=SplitType.EQUAL,
            created_by_user_id=actor.id,
            shares={to_participant_id: amount},
            currency=room.currency,
        )

    async def _get_with_room(self, actor: User, expense_id: int) -> tuple[Expense, Room, bool]:
        expense = await self._expenses.get(expense_id)
        if expense is None:
            raise NotFound("Запись не найдена — возможно, её уже удалили")
        room, _ = await get_room_and_member(self._rooms, self._participants, actor, expense.room_id)
        can_edit = actor.id in (expense.created_by_user_id, room.owner_user_id)
        return expense, room, can_edit

    async def _ensure_editable(self, actor: User, expense_id: int) -> tuple[Expense, Room]:
        expense, room, can_edit = await self._get_with_room(actor, expense_id)
        if not can_edit:
            raise AccessDenied("Изменять запись может только её автор или владелец комнаты")
        ensure_writable(room)
        return expense, room

    async def get_card(self, actor: User, expense_id: int) -> ExpenseCard:
        expense, room, can_edit = await self._get_with_room(actor, expense_id)
        parts = {
            p.id: p for p in await self._participants.list_by_room(room.id, include_inactive=True)
        }
        author = await self._users.get(expense.created_by_user_id)
        return ExpenseCard(
            expense=expense,
            room=room,
            payer=parts[expense.paid_by_participant_id],
            shares=[(parts[s.participant_id], s.amount) for s in expense.shares],
            author_name=author.first_name if author else "?",
            can_edit=can_edit,
        )

    async def edit_description(self, actor: User, expense_id: int, description: str) -> None:
        await self._ensure_editable(actor, expense_id)
        await self._expenses.update_description(expense_id, _validate_description(description))

    async def edit_amount(self, actor: User, expense_id: int, amount: int) -> None:
        expense, _ = await self._ensure_editable(actor, expense_id)
        _validate_amount(amount)
        if expense.kind is ExpenseKind.REPAYMENT:
            shares = {expense.shares[0].participant_id: amount}
        else:
            shares = split_evenly(amount, [s.participant_id for s in expense.shares])
        await self._expenses.update_amount(expense_id, amount, shares)

    async def edit_payer(self, actor: User, expense_id: int, participant_id: int) -> None:
        expense, room = await self._ensure_editable(actor, expense_id)
        if expense.kind is ExpenseKind.REPAYMENT:
            raise InvalidInput("У возврата долга нельзя сменить плательщика")
        if participant_id not in await self._active_map(room.id):
            raise InvalidInput("Участник не найден — попробуйте заново")
        await self._expenses.update_payer(expense_id, participant_id)

    async def edit_split(self, actor: User, expense_id: int, participant_ids: list[int]) -> None:
        expense, room = await self._ensure_editable(actor, expense_id)
        if expense.kind is ExpenseKind.REPAYMENT:
            raise InvalidInput("У возврата долга нельзя изменить делёжку")
        active = await self._active_map(room.id)
        if not participant_ids or set(participant_ids) - active.keys():
            raise InvalidInput("Список участников делёжки устарел — попробуйте заново")
        shares = split_evenly(expense.amount.amount, participant_ids)
        await self._expenses.update_shares(expense_id, shares)

    async def delete(self, actor: User, expense_id: int) -> int:
        """Удаляет запись, возвращает room_id для возврата в историю."""
        expense, _ = await self._ensure_editable(actor, expense_id)
        await self._expenses.delete(expense_id)
        return expense.room_id

    async def get_history_page(self, actor: User, room_id: int, page: int) -> HistoryPage:
        room, _ = await get_room_and_member(self._rooms, self._participants, actor, room_id)
        total = await self._expenses.count(room.id)
        total_pages = max(1, ceil(total / limits.EXPENSES_PAGE_SIZE))
        page = max(0, min(page, total_pages - 1))
        expenses = await self._expenses.list_page(
            room.id, page * limits.EXPENSES_PAGE_SIZE, limits.EXPENSES_PAGE_SIZE
        )
        items = [
            HistoryItem(
                expense_id=e.id,
                kind=e.kind,
                description=e.description,
                amount=e.amount.amount,
            )
            for e in expenses
        ]
        return HistoryPage(items=items, page=page, total_pages=total_pages, currency=room.currency)
