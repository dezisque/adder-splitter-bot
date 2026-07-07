"""Рендер текстов сообщений. Всё пользовательское содержимое экранируется."""

from html import escape

from src.application.dto import BalanceView, ExpenseCard, HistoryPage, MemberView, RoomOverview
from src.domain import limits
from src.domain.entities import Participant, Room
from src.domain.enums import ExpenseKind
from src.domain.value_objects import Money

VIRTUAL_MARK = "👻"
OWNER_MARK = "👑"


def money(amount: int, currency: str) -> str:
    return Money(amount, currency).format()


def signed_money(amount: int, currency: str) -> str:
    prefix = "+" if amount > 0 else ""
    return prefix + Money(amount, currency).format()


def name(p: Participant) -> str:
    suffix = f" {VIRTUAL_MARK}" if p.is_virtual else ""
    return escape(p.display_name) + suffix


def button_name(p: Participant, max_len: int = 28) -> str:
    suffix = f" {VIRTUAL_MARK}" if p.is_virtual else ""
    return p.display_name[:max_len] + suffix


def room_card(o: RoomOverview) -> str:
    archived = "\n📦 <i>В архиве — только просмотр</i>" if o.room.is_archived else ""
    currency = o.room.currency
    if o.my_net > 0:
        my = f"🟢 Ваш баланс: <b>{signed_money(o.my_net, currency)}</b> — вам должны"
    elif o.my_net < 0:
        my = f"🔴 Ваш баланс: <b>{money(o.my_net, currency)}</b> — вы должны"
    else:
        my = f"⚪️ Ваш баланс: <b>{money(0, currency)}</b> — всё закрыто"
    hint = (
        ""
        if o.room.is_archived
        else "\n\n💡 Отправьте сообщение вида «Мясо 2450» — добавлю расход в эту комнату."
    )
    return (
        f"<b>{escape(o.room.title)}</b>{archived}\n\n"
        f"{my}\n\n"
        f"👥 Участников: {o.members_count}\n"
        f"🧾 Расходов: {o.expenses_count} на {money(o.expenses_sum, currency)}"
        f"{hint}"
    )


def split_prompt(selected: int, total: int) -> str:
    return f"Между кем делим?\n\n🔴 — участвует, ⚪️ — нет. Выбрано: <b>{selected} из {total}</b>"


def members_list(room: Room, members: list[MemberView]) -> str:
    lines = [f"<b>Участники «{escape(room.title)}»</b>\n"]
    has_virtual = False
    for v in members:
        p = v.participant
        if p.is_virtual:
            has_virtual = True
            label = name(p)
        elif v.username:
            label = f"@{escape(v.username)} ({escape(p.display_name)})"
        else:
            label = escape(p.display_name)
        owner_mark = f" {OWNER_MARK}" if p.user_id == room.owner_user_id else ""
        lines.append(f"• {label}{owner_mark}")
    if has_virtual:
        lines.append(f"\n{VIRTUAL_MARK} — без Telegram, добавлен вручную")
    return "\n".join(lines)


def inactive_room_notice(room: Room) -> str:
    return (
        f"😴 В комнате «{escape(room.title)}» нет активности уже "
        f"{limits.ROOM_INACTIVITY_DAYS} дн.\n\n"
        f"Если ничего не сделать, через {limits.ROOM_DELETION_GRACE_DAYS} дн. "
        "я удалю её вместе со всей историей. Что делаем?"
    )


def room_auto_deleted(room: Room) -> str:
    return f"🗑 Комната «{escape(room.title)}» удалена — в ней долго не было активности."


def invite_text(room: Room, link: str) -> str:
    return (
        f"Ссылка-приглашение в «{escape(room.title)}»:\n\n"
        f"{link}\n\n"
        "Перешлите её друзьям — по клику они попадут в комнату."
    )


def expense_preview(
    description: str,
    amount: int,
    currency: str,
    payer: Participant,
    split_between: list[Participant],
    room_title: str | None = None,
) -> str:
    names = ", ".join(name(p) for p in split_between)
    room_line = f"Комната: <b>{escape(room_title)}</b>\n" if room_title else ""
    return (
        "<b>Проверьте:</b>\n\n"
        f"{room_line}"
        f"🧾 {escape(description)} — <b>{money(amount, currency)}</b>\n"
        f"Оплатил: {name(payer)}\n"
        f"Делится между ({len(split_between)}): {names}"
    )


def expense_card(card: ExpenseCard) -> str:
    e = card.expense
    currency = card.room.currency
    created = e.created_at.strftime("%d.%m.%Y")
    if e.kind is ExpenseKind.REPAYMENT:
        recipient = name(card.shares[0][0]) if card.shares else "?"
        body = (
            f"↩️ <b>{escape(e.description)}</b>\n\n"
            f"Сумма: <b>{money(e.amount.amount, currency)}</b>\n"
            f"Вернул: {name(card.payer)}\n"
            f"Получил: {recipient}"
        )
    else:
        share_lines = "\n".join(
            f"  • {name(p)} — {money(share, currency)}" for p, share in card.shares
        )
        body = (
            f"🧾 <b>{escape(e.description)}</b>\n\n"
            f"Сумма: <b>{money(e.amount.amount, currency)}</b>\n"
            f"Оплатил: {name(card.payer)}\n"
            f"Делится между ({len(card.shares)}):\n{share_lines}"
        )
    return f"{body}\n\nДобавил: {escape(card.author_name)}, {created}"


def history_page_text(page: HistoryPage) -> str:
    pages = f" — стр. {page.page + 1}/{page.total_pages}" if page.total_pages > 1 else ""
    header = f"<b>🕓 История{pages}</b>"
    if not page.items:
        return f"{header}\n\nПока нет ни одной записи."
    lines = [header, ""]
    for i, item in enumerate(page.items, start=1):
        icon = "↩️" if item.kind is ExpenseKind.REPAYMENT else "🧾"
        lines.append(
            f"{i}. {icon} <b>{escape(item.description)}</b> — {money(item.amount, page.currency)}"
            f" · {escape(item.payer_name)}, {item.created_at.strftime('%d.%m')}"
        )
    lines.append("\nОткрыть запись — кнопкой с её номером.")
    return "\n".join(lines)


def balance(view: BalanceView) -> str:
    currency = view.room.currency
    if not view.lines:
        return "<b>📊 Баланс</b>\n\nПока нет ни одного расхода."
    parts = ["<b>📊 Баланс</b>\n"]
    for e in view.lines:
        icon = "🟢" if e.net > 0 else ("🔴" if e.net < 0 else "⚪️")
        parts.append(
            f"{icon} <b>{name(e.participant)}</b> — потратил {money(e.paid, currency)}, "
            f"доля {money(e.owed, currency)} → <b>{signed_money(e.net, currency)}</b>"
        )
    if view.transfers:
        parts.append("\n<b>Кто кому должен:</b>")
        parts.extend(
            f"▪️ {name(t.from_participant)} → {name(t.to_participant)}: "
            f"<b>{money(t.amount, currency)}</b>"
            for t in view.transfers
        )
    else:
        parts.append("\n✨ Все расчёты закрыты!")
    return "\n".join(parts)
