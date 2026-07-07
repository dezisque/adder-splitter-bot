from src.application.dto import BalanceEntry, BalanceView, TransferView
from src.application.interfaces import ExpenseRepo, ParticipantRepo, RoomRepo
from src.application.services._access import get_room_and_member
from src.domain.entities import User
from src.domain.services.settlement import simplify_debts


class BalanceService:
    def __init__(
        self, rooms: RoomRepo, participants: ParticipantRepo, expenses: ExpenseRepo
    ) -> None:
        self._rooms = rooms
        self._participants = participants
        self._expenses = expenses

    async def get(self, user: User, room_id: int) -> BalanceView:
        room, _ = await get_room_and_member(self._rooms, self._participants, user, room_id)
        paid = await self._expenses.paid_totals(room.id)
        owed = await self._expenses.owed_totals(room.id)
        participants = await self._participants.list_by_room(room.id, include_inactive=True)

        # вышедшие участники остаются в балансе, пока их долг не закрыт
        lines = [
            entry
            for p in participants
            if (entry := BalanceEntry(p, paid.get(p.id, 0), owed.get(p.id, 0)))
            and (p.is_active or entry.net != 0)
        ]
        lines.sort(key=lambda e: -e.net)

        transfers = simplify_debts({e.participant.id: e.net for e in lines})
        by_id = {e.participant.id: e.participant for e in lines}
        return BalanceView(
            room=room,
            lines=lines,
            transfers=[
                TransferView(by_id[t.from_participant_id], by_id[t.to_participant_id], t.amount)
                for t in transfers
            ],
        )
