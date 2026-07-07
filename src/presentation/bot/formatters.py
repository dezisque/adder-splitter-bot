"""Рендер текстов сообщений. Всё пользовательское содержимое экранируется."""

from html import escape

from src.application.dto import BalanceView, ExpenseCard, RoomOverview
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
    return (
        f"<b>{escape(o.room.title)}</b>{archived}\n\n"
        f"👥 Участников: {o.members_count}\n"
        f"💸 Расходов: {o.expenses_count} на {money(o.expenses_sum, o.room.currency)}"
    )


def members_list(room: Room, participants: list[Participant]) -> str:
    lines = [f"<b>Участники «{escape(room.title)}»</b>\n"]
    has_virtual = False
    for p in participants:
        marks = ""
        if p.user_id == room.owner_user_id:
            marks = f" {OWNER_MARK}"
        if p.is_virtual:
            has_virtual = True
        lines.append(f"• {name(p)}{marks}")
    if has_virtual:
        lines.append(f"\n{VIRTUAL_MARK} — без Telegram, добавлен вручную")
    return "\n".join(lines)


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
) -> str:
    names = ", ".join(name(p) for p in split_between)
    return (
        "<b>Проверьте:</b>\n\n"
        f"💸 {escape(description)} — <b>{money(amount, currency)}</b>\n"
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
            f"💸 <b>{escape(e.description)}</b>\n\n"
            f"Сумма: <b>{money(e.amount.amount, currency)}</b>\n"
            f"Оплатил: {name(card.payer)}\n"
            f"Делится между ({len(card.shares)}):\n{share_lines}"
        )
    return f"{body}\n\nДобавил: {escape(card.author_name)}, {created}"


def history_header(page: int, total_pages: int) -> str:
    pages = f" — стр. {page + 1}/{total_pages}" if total_pages > 1 else ""
    return f"<b>📜 История{pages}</b>\n\nНажмите на запись, чтобы открыть её."


def history_button(kind: ExpenseKind, description: str, amount: int, currency: str) -> str:
    icon = "↩️" if kind is ExpenseKind.REPAYMENT else "💸"
    return f"{icon} {description[:24]} — {money(amount, currency)}"


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
            f"➡️ {name(t.from_participant)} → {name(t.to_participant)}: "
            f"<b>{money(t.amount, currency)}</b>"
            for t in view.transfers
        )
    else:
        parts.append("\n✨ Все расчёты закрыты!")
    return "\n".join(parts)
