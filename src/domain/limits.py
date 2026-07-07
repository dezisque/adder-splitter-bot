"""Все ограничения проекта. Единственное место с «магическими» числами."""

MAX_ROOMS_PER_USER = 50
MAX_MEMBERS_PER_ROOM = 50
MAX_EXPENSES_PER_ROOM = 1000

MIN_AMOUNT = 1  # копейки
MAX_AMOUNT = 10_000_000 * 100  # 10 млн ₽ в копейках

MAX_ROOM_TITLE_LEN = 64
MAX_MEMBER_NAME_LEN = 64
MAX_EXPENSE_DESCRIPTION_LEN = 128

INVITE_TOKEN_BYTES = 16
EXPENSES_PAGE_SIZE = 8

# авто-удаление брошенных комнат (архивные не трогаем)
ROOM_INACTIVITY_DAYS = 3  # без активности -> предупреждение владельцу
ROOM_DELETION_GRACE_DAYS = 3  # после предупреждения -> удаление
CLEANUP_INTERVAL_SECONDS = 3600

DEFAULT_CURRENCY = "RUB"
