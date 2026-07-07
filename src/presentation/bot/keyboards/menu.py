from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.presentation.bot.callbacks import MenuCB, MenuTarget


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📂 Мои комнаты", callback_data=MenuCB(to=MenuTarget.ROOMS))
    builder.button(text="➕ Создать комнату", callback_data=MenuCB(to=MenuTarget.NEW_ROOM))
    builder.adjust(1)
    return builder.as_markup()
