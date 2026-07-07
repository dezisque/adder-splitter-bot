from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import Expense, ExpenseShare
from src.domain.enums import ExpenseKind, SplitType
from src.domain.value_objects import Money
from src.infrastructure.db.models import ExpenseModel, ExpenseShareModel, RoomModel


def _to_domain(model: ExpenseModel, currency: str) -> Expense:
    return Expense(
        id=model.id,
        room_id=model.room_id,
        kind=ExpenseKind(model.kind),
        paid_by_participant_id=model.paid_by_participant_id,
        amount=Money(model.amount, currency),
        description=model.description,
        split_type=SplitType(model.split_type),
        created_by_user_id=model.created_by_user_id,
        created_at=model.created_at,
        shares=[ExpenseShare(s.participant_id, s.amount) for s in model.shares],
    )


def _apply_shares(model: ExpenseModel, shares: dict[int, int]) -> None:
    """Правит коллекцию долей на месте — без пересоздания строк с тем же PK."""
    existing = {s.participant_id: s for s in model.shares}
    for pid, share in list(existing.items()):
        if pid not in shares:
            model.shares.remove(share)
    for pid, amount in shares.items():
        if pid in existing:
            existing[pid].amount = amount
        else:
            model.shares.append(ExpenseShareModel(participant_id=pid, amount=amount))


class SqlExpenseRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _model(self, expense_id: int) -> ExpenseModel | None:
        return await self._session.get(ExpenseModel, expense_id)

    async def add(
        self,
        *,
        room_id: int,
        kind: ExpenseKind,
        paid_by_participant_id: int,
        amount: int,
        description: str,
        split_type: SplitType,
        created_by_user_id: int,
        shares: dict[int, int],
        currency: str,
    ) -> Expense:
        model = ExpenseModel(
            room_id=room_id,
            kind=kind.value,
            paid_by_participant_id=paid_by_participant_id,
            amount=amount,
            description=description,
            split_type=split_type.value,
            created_by_user_id=created_by_user_id,
            shares=[
                ExpenseShareModel(participant_id=pid, amount=share) for pid, share in shares.items()
            ],
        )
        self._session.add(model)
        await self._session.flush()
        return _to_domain(model, currency)

    async def get(self, expense_id: int) -> Expense | None:
        row = (
            await self._session.execute(
                select(ExpenseModel, RoomModel.currency)
                .join(RoomModel, ExpenseModel.room_id == RoomModel.id)
                .where(ExpenseModel.id == expense_id)
            )
        ).first()
        if row is None:
            return None
        return _to_domain(row[0], row[1])

    async def update_description(self, expense_id: int, description: str) -> None:
        model = await self._model(expense_id)
        if model is not None:
            model.description = description
            await self._session.flush()

    async def update_amount(self, expense_id: int, amount: int, shares: dict[int, int]) -> None:
        model = await self._model(expense_id)
        if model is not None:
            model.amount = amount
            _apply_shares(model, shares)
            await self._session.flush()

    async def update_payer(self, expense_id: int, participant_id: int) -> None:
        model = await self._model(expense_id)
        if model is not None:
            model.paid_by_participant_id = participant_id
            await self._session.flush()

    async def update_shares(self, expense_id: int, shares: dict[int, int]) -> None:
        model = await self._model(expense_id)
        if model is not None:
            _apply_shares(model, shares)
            await self._session.flush()

    async def delete(self, expense_id: int) -> None:
        model = await self._model(expense_id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    async def list_page(self, room_id: int, offset: int, limit: int) -> list[Expense]:
        rows = await self._session.execute(
            select(ExpenseModel, RoomModel.currency)
            .join(RoomModel, ExpenseModel.room_id == RoomModel.id)
            .where(ExpenseModel.room_id == room_id)
            .order_by(ExpenseModel.created_at.desc(), ExpenseModel.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return [_to_domain(row[0], row[1]) for row in rows]

    async def count(self, room_id: int) -> int:
        count = await self._session.scalar(
            select(func.count()).select_from(ExpenseModel).where(ExpenseModel.room_id == room_id)
        )
        return count or 0

    async def expense_stats(self, room_id: int) -> tuple[int, int]:
        """(количество, сумма) только по тратам — возвраты не в счёт."""
        row = (
            await self._session.execute(
                select(func.count(), func.coalesce(func.sum(ExpenseModel.amount), 0)).where(
                    ExpenseModel.room_id == room_id,
                    ExpenseModel.kind == ExpenseKind.EXPENSE.value,
                )
            )
        ).one()
        return int(row[0]), int(row[1])

    async def paid_totals(self, room_id: int) -> dict[int, int]:
        rows = await self._session.execute(
            select(ExpenseModel.paid_by_participant_id, func.sum(ExpenseModel.amount))
            .where(ExpenseModel.room_id == room_id)
            .group_by(ExpenseModel.paid_by_participant_id)
        )
        return {int(pid): int(total) for pid, total in rows}

    async def owed_totals(self, room_id: int) -> dict[int, int]:
        rows = await self._session.execute(
            select(ExpenseShareModel.participant_id, func.sum(ExpenseShareModel.amount))
            .join(ExpenseModel, ExpenseShareModel.expense_id == ExpenseModel.id)
            .where(ExpenseModel.room_id == room_id)
            .group_by(ExpenseShareModel.participant_id)
        )
        return {int(pid): int(total) for pid, total in rows}
