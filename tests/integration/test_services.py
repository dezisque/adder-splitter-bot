import os

import pytest

from src.domain.exceptions import AccessDenied, NotFound
from tests.integration.conftest import Services, make_user

pytestmark = pytest.mark.skipif(
    os.environ.get("TEST_DATABASE_URL") is None, reason="TEST_DATABASE_URL не задан"
)


async def test_full_flow(services: Services) -> None:
    """Сценарий из ТЗ: комната, участники (включая виртуального), расходы,
    баланс, возврат долга."""
    igor = await make_user(services, 1001, "Игорь")
    masha = await make_user(services, 1002, "Маша")

    room = await services.rooms.create(igor, "🏕 Шашлыки")
    joined_room, joined = await services.members.join_by_token(masha, room.invite_token)
    assert joined and joined_room.id == room.id
    await services.members.add_virtual(igor, room.id, "Данил")

    members = await services.members.list_members(igor, room.id)
    assert len(members) == 3
    by_name = {p.display_name: p for p in members}
    assert by_name["Данил"].is_virtual

    all_ids = [p.id for p in members]
    # Игорь платит 4500, Маша 1200, Данил (виртуальный) 800 — всё на всех
    await services.expenses.add(
        igor,
        room_id=room.id,
        payer_participant_id=by_name["Игорь"].id,
        amount=450_000,
        description="Мясо",
        participant_ids=all_ids,
    )
    await services.expenses.add(
        masha,
        room_id=room.id,
        payer_participant_id=by_name["Маша"].id,
        amount=120_000,
        description="Напитки",
        participant_ids=all_ids,
    )
    # Машa вносит расход, который оплатил виртуальный Данил
    await services.expenses.add(
        masha,
        room_id=room.id,
        payer_participant_id=by_name["Данил"].id,
        amount=80_000,
        description="Уголь",
        participant_ids=all_ids,
    )

    view = await services.balance.get(igor, room.id)
    paid = {e.participant.display_name: e.paid for e in view.lines}
    assert paid == {"Игорь": 450_000, "Маша": 120_000, "Данил": 80_000}

    # личный баланс в карточке комнаты совпадает с расчётом
    overview = await services.rooms.get_overview(igor, room.id)
    assert overview.my_net == 233_333
    assert sum(e.net for e in view.lines) == 0
    assert sum(e.owed for e in view.lines) == 650_000
    # Игорь — единственный кредитор, ему должны и Маша, и Данил
    assert len(view.transfers) == 2
    assert all(t.to_participant.display_name == "Игорь" for t in view.transfers)

    # Маша полностью возвращает долг
    masha_debt = next(t.amount for t in view.transfers if t.from_participant.display_name == "Маша")
    await services.expenses.add_repayment(
        masha,
        room_id=room.id,
        from_participant_id=by_name["Маша"].id,
        to_participant_id=by_name["Игорь"].id,
        amount=masha_debt,
    )
    view = await services.balance.get(igor, room.id)
    masha_net = next(e.net for e in view.lines if e.participant.display_name == "Маша")
    assert masha_net == 0
    assert len(view.transfers) == 1  # остался только долг Данила


async def test_history_and_edits(services: Services) -> None:
    igor = await make_user(services, 2001, "Игорь")
    masha = await make_user(services, 2002, "Маша")
    room = await services.rooms.create(igor, "Тест")
    await services.members.join_by_token(masha, room.invite_token)
    members = await services.members.list_members(igor, room.id)
    ids = [p.id for p in members]

    expense = await services.expenses.add(
        masha,
        room_id=room.id,
        payer_participant_id=ids[1],
        amount=1000,
        description="Кофе",
        participant_ids=ids,
    )

    # Игорь (не автор, но владелец) может редактировать; сумма пересплитится
    await services.expenses.edit_amount(igor, expense.id, 333)
    card = await services.expenses.get_card(igor, expense.id)
    assert card.expense.amount.amount == 333
    assert sum(amount for _, amount in card.shares) == 333

    # делёжка: только на Игоря
    await services.expenses.edit_split(masha, expense.id, [ids[0]])
    card = await services.expenses.get_card(masha, expense.id)
    assert [p.id for p, _ in card.shares] == [ids[0]]

    page = await services.expenses.get_history_page(igor, room.id, 0)
    assert page.total_pages == 1 and len(page.items) == 1

    room_id = await services.expenses.delete(igor, expense.id)
    assert room_id == room.id
    page = await services.expenses.get_history_page(igor, room.id, 0)
    assert page.items == []


async def test_edit_denied_for_outsider_author(services: Services) -> None:
    igor = await make_user(services, 3001, "Игорь")
    masha = await make_user(services, 3002, "Маша")
    danil = await make_user(services, 3003, "Данил")
    room = await services.rooms.create(igor, "Права")
    await services.members.join_by_token(masha, room.invite_token)
    await services.members.join_by_token(danil, room.invite_token)
    members = await services.members.list_members(igor, room.id)
    ids = [p.id for p in members]

    expense = await services.expenses.add(
        igor,
        room_id=room.id,
        payer_participant_id=ids[0],
        amount=500,
        description="Такси",
        participant_ids=ids,
    )
    # Маша — не автор и не владелец
    with pytest.raises(AccessDenied):
        await services.expenses.edit_amount(masha, expense.id, 600)


async def test_archive_blocks_changes(services: Services) -> None:
    igor = await make_user(services, 4001, "Игорь")
    masha = await make_user(services, 4002, "Маша")
    room = await services.rooms.create(igor, "Архив")
    await services.members.join_by_token(masha, room.invite_token)
    members = await services.members.list_members(igor, room.id)

    with pytest.raises(AccessDenied):
        await services.rooms.archive(masha, room.id)  # не владелец

    await services.rooms.archive(igor, room.id)

    with pytest.raises(AccessDenied):
        await services.expenses.add(
            igor,
            room_id=room.id,
            payer_participant_id=members[0].id,
            amount=100,
            description="Поздно",
            participant_ids=[m.id for m in members],
        )
    danil = await make_user(services, 4003, "Данил")
    with pytest.raises(AccessDenied):
        await services.members.join_by_token(danil, room.invite_token)


async def test_delete_room_wipes_everything(services: Services) -> None:
    igor = await make_user(services, 6001, "Игорь")
    masha = await make_user(services, 6002, "Маша")
    room = await services.rooms.create(igor, "Снести")
    await services.members.join_by_token(masha, room.invite_token)
    members = await services.members.list_members(igor, room.id)
    await services.expenses.add(
        igor,
        room_id=room.id,
        payer_participant_id=members[0].id,
        amount=1000,
        description="Кофе",
        participant_ids=[m.id for m in members],
    )

    with pytest.raises(AccessDenied):
        await services.rooms.delete(masha, room.id)  # не владелец

    await services.rooms.delete(igor, room.id)
    assert await services.rooms.list_for_user(igor) == []
    with pytest.raises(NotFound):
        await services.rooms.get_overview(igor, room.id)


async def test_inactivity_lifecycle(services: Services) -> None:
    """Неактивная комната: предупреждение -> грейс -> удаление; активность спасает."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update

    from src.infrastructure.db.models import RoomModel
    from src.infrastructure.db.repositories.room_repo import SqlRoomRepo

    igor = await make_user(services, 7001, "Игорь")
    room = await services.rooms.create(igor, "Тихая")
    repo = SqlRoomRepo(services.session)
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=3)

    # свежая комната под раздачу не попадает
    assert await repo.list_to_notify(cutoff) == []

    await services.session.execute(
        update(RoomModel)
        .where(RoomModel.id == room.id)
        .values(last_activity_at=now - timedelta(days=4))
    )
    assert [r.id for r in await repo.list_to_notify(cutoff)] == [room.id]

    await repo.mark_deletion_notified(room.id)
    assert await repo.list_to_notify(cutoff) == []
    assert await repo.list_to_delete(cutoff) == []  # грейс ещё не истёк

    await services.session.execute(
        update(RoomModel)
        .where(RoomModel.id == room.id)
        .values(deletion_notified_at=now - timedelta(days=4))
    )
    assert [r.id for r in await repo.list_to_delete(cutoff)] == [room.id]

    # «Оставить» (или любая активность) снимает приговор
    await services.rooms.keep_alive(igor, room.id)
    assert await repo.list_to_delete(cutoff) == []
    assert await repo.list_to_notify(cutoff) == []

    # архивная комната не удаляется, даже если совсем старая
    await services.session.execute(
        update(RoomModel)
        .where(RoomModel.id == room.id)
        .values(last_activity_at=now - timedelta(days=30), is_archived=True)
    )
    assert await repo.list_to_notify(cutoff) == []


async def test_members_view_has_usernames(services: Services) -> None:
    igor = await services.users.create(8001, "igor_k", "Игорь")
    room = await services.rooms.create(igor, "Юзернеймы")
    await services.members.add_virtual(igor, room.id, "Серёга")

    views = await services.members.list_members_view(igor, room.id)
    by_name = {v.participant.display_name: v for v in views}
    assert by_name["Игорь"].username == "igor_k"
    assert by_name["Серёга"].username is None
    assert by_name["Серёга"].participant.is_virtual

    targets = await services.members.list_members_with_telegram(igor, room.id)
    by_tg = {p.display_name: tg for p, tg in targets}
    assert by_tg == {"Игорь": 8001, "Серёга": None}


async def test_leave_and_rejoin_keeps_participant(services: Services) -> None:
    igor = await make_user(services, 5001, "Игорь")
    masha = await make_user(services, 5002, "Маша")
    room = await services.rooms.create(igor, "Выход")
    await services.members.join_by_token(masha, room.invite_token)
    before = await services.members.list_members(igor, room.id)
    masha_pid = next(p.id for p in before if p.user_id == masha.id)

    with pytest.raises(AccessDenied):
        await services.members.leave(igor, room.id)  # владелец не выходит

    await services.members.leave(masha, room.id)
    assert len(await services.members.list_members(igor, room.id)) == 1

    _, rejoined = await services.members.join_by_token(masha, room.invite_token)
    assert rejoined
    after = await services.members.list_members(igor, room.id)
    assert next(p.id for p in after if p.user_id == masha.id) == masha_pid
