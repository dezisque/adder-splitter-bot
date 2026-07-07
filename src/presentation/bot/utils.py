import re

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from src.domain import limits
from src.domain.exceptions import InvalidInput
from src.domain.value_objects import Money
from src.presentation.bot import texts

_AMOUNT_RE = re.compile(r"^\d{1,8}([.,]\d{1,2})?$")


def parse_amount(text: str) -> int:
    """«2450», «2450.5», «2 450,50» -> копейки. Никаких float."""
    normalized = text.strip().replace(" ", "").replace(" ", "")
    if not _AMOUNT_RE.match(normalized):
        raise InvalidInput("Не понял сумму. Пример: 2450 или 2450,50")
    normalized = normalized.replace(",", ".")
    if "." in normalized:
        major_str, minor_str = normalized.split(".")
        minor = int(minor_str.ljust(2, "0"))
    else:
        major_str, minor = normalized, 0
    amount = int(major_str) * 100 + minor
    if not limits.MIN_AMOUNT <= amount <= limits.MAX_AMOUNT:
        low = Money(limits.MIN_AMOUNT).format()
        high = Money(limits.MAX_AMOUNT).format()
        raise InvalidInput(f"Сумма должна быть от {low} до {high}")
    return amount


async def edit_or_answer(
    callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    """Перерисовывает сообщение под колбэком; повторный клик по тому же экрану — no-op."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer(texts.MESSAGE_TOO_OLD, show_alert=True)
        return
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise
