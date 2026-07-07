from enum import StrEnum

from aiogram.filters.callback_data import CallbackData


class MenuTarget(StrEnum):
    MAIN = "main"
    ROOMS = "rooms"
    NEW_ROOM = "new"
    ARCHIVED = "arch"


class MenuCB(CallbackData, prefix="m"):
    """Навигация по главному меню."""

    to: MenuTarget


class RoomAction(StrEnum):
    OPEN = "open"
    REFRESH = "rfr"
    INVITE = "inv"
    INVITE_REGEN = "invr"
    MEMBERS = "mem"
    BALANCE = "bal"
    HISTORY = "hist"
    SETTINGS = "set"
    ARCHIVE = "arc"
    ARCHIVE_YES = "arcy"
    DELETE = "del"
    DELETE_YES = "dely"
    LEAVE = "lv"
    LEAVE_YES = "lvy"
    ADD_EXPENSE = "exp"
    REPAY = "rep"


class RoomCB(CallbackData, prefix="r"):
    action: RoomAction
    room_id: int


class MemberAction(StrEnum):
    ADD_VIRTUAL = "add"
    REMOVE = "rm"
    REMOVE_YES = "rmy"


class MemberCB(CallbackData, prefix="mb"):
    action: MemberAction
    room_id: int
    participant_id: int  # 0 для add_virtual


class ExpAction(StrEnum):
    VIEW = "v"
    EDIT_DESC = "ed"
    EDIT_AMOUNT = "ea"
    EDIT_PAYER = "ep"
    EDIT_SPLIT = "es"
    DELETE = "d"
    DELETE_YES = "dy"


class ExpCB(CallbackData, prefix="e"):
    action: ExpAction
    expense_id: int


class ExpListCB(CallbackData, prefix="el"):
    """Страница истории расходов комнаты."""

    room_id: int
    page: int


class PayerCB(CallbackData, prefix="p"):
    """Выбор плательщика в анкете нового расхода."""

    participant_id: int


class EditPayerCB(CallbackData, prefix="pe"):
    """Смена плательщика существующего расхода (stateless)."""

    expense_id: int
    participant_id: int


class SplitAction(StrEnum):
    TOGGLE = "t"
    ALL = "a"
    DONE = "ok"


class SplitCB(CallbackData, prefix="s"):
    action: SplitAction
    participant_id: int  # 0 для all/done


class RepayFromCB(CallbackData, prefix="rf"):
    participant_id: int


class RepayToCB(CallbackData, prefix="rt"):
    participant_id: int


class RepayAmountCB(CallbackData, prefix="ra"):
    """Кнопка «вся сумма» — возврат ровно на сумму долга по расчёту."""

    amount: int


class KeepRoomCB(CallbackData, prefix="keep"):
    """«Оставить» из уведомления об авто-удалении: сбрасывает таймер."""

    room_id: int


class ConfirmCB(CallbackData, prefix="ok"):
    """Подтверждение на последнем шаге анкеты."""


class CancelCB(CallbackData, prefix="x"):
    """Универсальная отмена текущего диалога."""
