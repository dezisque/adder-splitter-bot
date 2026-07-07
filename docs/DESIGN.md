# adder-splitter — Telegram-бот для совместного учёта расходов

Дизайн-документ. Статус: черновик, ждёт подтверждения.

---

## 0. Ключевые решения (отличия от исходного ТЗ)

1. **Участник ≠ Пользователь.** Расходы ссылаются на `Participant` (участника комнаты),
   а не на Telegram-пользователя напрямую. Участник может быть привязан к `User`
   (пришёл по инвайт-ссылке) или быть *виртуальным* (добавлен вручную, у человека нет
   Telegram). При появлении человека в Telegram его аккаунт можно привязать к
   виртуальному участнику без потери истории.
2. **Деньги — целые числа в минорных единицах** (копейках), `BIGINT`. Никаких float.
3. **Доли фиксируются при создании расхода** в `expense_shares`. Остаток от деления
   распределяется детерминированно (largest remainder). История стабильна, будущие
   неравные деления не потребуют миграций.
4. **Операция «отметить возврат» (settle up)** включена в MVP — без неё баланс
   невозможно обнулить после реальной расплаты.
5. **Long polling**, не webhook — проще деплой и локальная разработка. Переход на
   webhook позже — замена одной строки в entrypoint.
6. **Redis — да, но только как FSM-storage** aiogram (диалоги переживают рестарт
   бота). Не как кэш и не как брокер. В dev можно MemoryStorage (переключается конфигом).
7. **Удаление комнаты — мягкое** (архивация). Жёсткого удаления данных в MVP нет.

---

## 1. Общая архитектура

Монолит, один процесс. Clean Architecture, 4 слоя, зависимости направлены внутрь:

```
┌────────────────────────────────────────────────────────────┐
│ presentation/  (aiogram: handlers, keyboards, FSM, texts)  │
│   знает про Telegram, НЕ знает про SQL                     │
├────────────────────────────────────────────────────────────┤
│ application/   (сервисы-юзкейсы, DTO, протоколы репо)      │
│   оркестрация: транзакции, права, вызовы domain            │
├────────────────────────────────────────────────────────────┤
│ domain/        (dataclass-сущности, Money, split,          │
│                 settlement — чистые функции, ноль IO)      │
├────────────────────────────────────────────────────────────┤
│ infrastructure/ (SQLAlchemy-модели, репозитории, config)   │
│   реализует протоколы из application                       │
└────────────────────────────────────────────────────────────┘
```

- **DI без фреймворка**: aiogram-middleware на каждый апдейт открывает
  `AsyncSession`, собирает репозитории и сервисы, кладёт их в `data` хендлера,
  коммитит/откатывает по завершении. Если проект вырастет — заменим на `dishka`,
  но сейчас это лишняя зависимость.
- **Транзакция = один апдейт.** Middleware управляет commit/rollback, сервисы
  не вызывают commit сами (только flush при необходимости получить id).
- Расчёт баланса (`split`, `simplify_debts`) — чистые функции в domain,
  покрываются юнит-тестами без БД.

## 2. Структура папок

```
adder-splitter/
├── pyproject.toml              # uv, ruff, mypy
├── uv.lock
├── Dockerfile
├── docker-compose.yml          # bot + postgres + redis
├── .env.example
├── alembic.ini
├── migrations/
│   └── versions/
├── src/
│   ├── main.py                 # сборка: Bot, Dispatcher, middlewares, routers
│   ├── config.py               # pydantic-settings
│   ├── domain/
│   │   ├── entities.py         # User, Room, Participant, Expense, ExpenseShare
│   │   ├── value_objects.py    # Money
│   │   ├── enums.py            # ExpenseKind, SplitType
│   │   ├── exceptions.py       # DomainError и наследники
│   │   ├── limits.py           # все константы-ограничения
│   │   └── services/
│   │       ├── split.py        # split_evenly(amount, n) -> list[int]
│   │       └── settlement.py   # simplify_debts(nets) -> list[Transfer]
│   ├── application/
│   │   ├── dto.py
│   │   ├── interfaces.py       # Protocol'ы репозиториев
│   │   └── services/
│   │       ├── user_service.py
│   │       ├── room_service.py
│   │       ├── member_service.py
│   │       ├── expense_service.py
│   │       └── balance_service.py
│   ├── infrastructure/
│   │   └── db/
│   │       ├── base.py         # DeclarativeBase, naming convention
│   │       ├── models.py       # ORM-модели
│   │       ├── session.py      # engine, session factory
│   │       └── repositories/
│   │           ├── user_repo.py
│   │           ├── room_repo.py
│   │           ├── participant_repo.py
│   │           └── expense_repo.py
│   └── presentation/
│       └── bot/
│           ├── handlers/
│           │   ├── start.py    # /start, deep-link join, главное меню
│           │   ├── rooms.py
│           │   ├── members.py
│           │   ├── expenses.py
│           │   ├── balance.py
│           │   └── common.py   # /cancel, /help, устаревшие кнопки
│           ├── keyboards/      # билдеры инлайн-клавиатур
│           ├── callbacks.py    # CallbackData-фабрики (typed)
│           ├── states.py       # FSM StatesGroup'ы
│           ├── middlewares/    # di.py, user_upsert.py
│           ├── formatters.py   # рендер сумм, балансов, списков
│           └── texts.py        # все строки в одном месте
└── tests/
    ├── domain/                 # split, settlement — чистые юнит-тесты
    └── application/            # сервисы с фейковыми репозиториями
```

## 3. База данных (PostgreSQL)

Суммы — `BIGINT` в копейках. `telegram_id` — `BIGINT` (id уже не влезают в int32).

```sql
users
  id            BIGINT PK (identity)
  telegram_id   BIGINT UNIQUE NOT NULL
  username      VARCHAR(32)          -- nullable, может отсутствовать/меняться
  first_name    VARCHAR(128) NOT NULL
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()

rooms
  id            BIGINT PK
  title         VARCHAR(64) NOT NULL
  owner_user_id BIGINT NOT NULL REFERENCES users(id)
  invite_token  VARCHAR(32) UNIQUE NOT NULL   -- secrets.token_urlsafe, можно перегенерить
  currency      CHAR(3) NOT NULL DEFAULT 'RUB' -- задел на мультивалютность
  is_archived   BOOLEAN NOT NULL DEFAULT false
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()

participants                       -- участник комнаты; user_id NULL = виртуальный
  id            BIGINT PK
  room_id       BIGINT NOT NULL REFERENCES rooms(id)
  user_id       BIGINT NULL REFERENCES users(id)
  display_name  VARCHAR(64) NOT NULL  -- снапшот имени; для виртуальных — введённое
  is_active     BOOLEAN NOT NULL DEFAULT true  -- вышел из комнаты = false, строка живёт
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
  UNIQUE (room_id, user_id)          -- partial: WHERE user_id IS NOT NULL

expenses
  id                     BIGINT PK
  room_id                BIGINT NOT NULL REFERENCES rooms(id)
  kind                   VARCHAR(16) NOT NULL DEFAULT 'expense'  -- 'expense' | 'repayment'
  paid_by_participant_id BIGINT NOT NULL REFERENCES participants(id)
  amount                 BIGINT NOT NULL CHECK (amount > 0)  -- копейки
  description            VARCHAR(128) NOT NULL
  split_type             VARCHAR(16) NOT NULL DEFAULT 'equal' -- задел: 'exact', 'shares'
  created_by_user_id     BIGINT NOT NULL REFERENCES users(id) -- кто внёс запись
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()

expense_shares                     -- зафиксированные доли, сумма долей = amount
  expense_id     BIGINT NOT NULL REFERENCES expenses(id) ON DELETE CASCADE
  participant_id BIGINT NOT NULL REFERENCES participants(id)
  amount         BIGINT NOT NULL CHECK (amount >= 0)
  PRIMARY KEY (expense_id, participant_id)
```

Индексы: `participants(room_id)`, `expenses(room_id, created_at DESC)`,
`expense_shares(participant_id)`.

«Возврат долга» (settle up) — это `expenses.kind='repayment'`: платит должник,
единственная доля у кредитора. Баланс считается той же формулой, отдельной
таблицы не нужно.

## 4. Сущности (domain, dataclasses)

```python
@dataclass(frozen=True, slots=True)
class Money:                    # value object
    amount: int                 # минорные единицы
    currency: str = "RUB"
    # __add__, __sub__, format() -> "2 450 ₽"

@dataclass(slots=True)
class User:
    id: int; telegram_id: int; username: str | None
    first_name: str; created_at: datetime

@dataclass(slots=True)
class Room:
    id: int; title: str; owner_user_id: int
    invite_token: str; currency: str; is_archived: bool; created_at: datetime

@dataclass(slots=True)
class Participant:
    id: int; room_id: int; user_id: int | None
    display_name: str; is_active: bool
    @property
    def is_virtual(self) -> bool: return self.user_id is None

@dataclass(slots=True)
class Expense:
    id: int; room_id: int; kind: ExpenseKind
    paid_by_participant_id: int; amount: Money; description: str
    split_type: SplitType; created_by_user_id: int
    created_at: datetime; shares: list[ExpenseShare]

@dataclass(frozen=True, slots=True)
class ExpenseShare:
    participant_id: int; amount: int

# Расчётные (не хранятся):
@dataclass(frozen=True, slots=True)
class Transfer:
    from_participant_id: int; to_participant_id: int; amount: int

@dataclass(frozen=True, slots=True)
class BalanceSheet:
    lines: list[BalanceLine]    # participant, paid, owed, net
    transfers: list[Transfer]   # "кто кому сколько"
```

## 5. ER-диаграмма

```
┌──────────┐ 1      n ┌──────────────┐ n      1 ┌──────────┐
│  users   │──────────│ participants │──────────│  rooms   │
└──────────┘ (user_id └──────────────┘          └──────────┘
     │        NULLABLE →   │      │ 1                │ 1
     │        виртуальный) │      │                  │
     │ 1                   │ 1    │ paid_by          │ n
     │ owner               │      └────────────┐     │
     │                     │ n                 │ n   │
     │              ┌────────────────┐   ┌──────────────┐
     └──────────────│ expense_shares │n─1│   expenses   │
       (created_by) └────────────────┘   └──────────────┘
```

- `users 1—n rooms` (владелец), `users 1—n participants` (nullable — виртуальные),
- `rooms 1—n participants`, `rooms 1—n expenses`,
- `participants 1—n expenses` (плательщик), `participants n—m expenses` через `expense_shares`.

## 6. Слой сервисов (application)

Каждый метод — один юзкейс. Все проверки прав — здесь, не в хендлерах.

```python
class UserService:
    async def upsert_from_telegram(tg_id, username, first_name) -> User

class RoomService:
    async def create(owner: User, title: str) -> Room          # + participant владельца
    async def list_for_user(user: User) -> list[Room]
    async def get_for_member(user: User, room_id: int) -> Room  # проверка членства
    async def archive(user: User, room_id: int) -> None         # только владелец
    async def regenerate_invite(user: User, room_id: int) -> str

class MemberService:
    async def join_by_token(user: User, token: str) -> Room     # идемпотентно
    async def add_virtual(actor: User, room_id: int, name: str) -> Participant
    async def leave(user: User, room_id: int) -> None           # is_active=False; владелец не может
    async def list_members(room_id: int) -> list[Participant]
    async def claim_virtual(user, room_id, participant_id)      # V1.1: привязка аккаунта

class ExpenseService:
    async def add(actor, room_id, payer_id, amount, description,
                  participant_ids) -> Expense                   # доли через split_evenly
    async def add_repayment(actor, room_id, from_id, to_id, amount) -> Expense
    async def edit_amount / edit_description / edit_payer / edit_split(...)
    async def delete(actor, expense_id) -> None                 # автор или владелец
    async def list_page(room_id, page, per_page) -> Page[Expense]

class BalanceService:
    async def get(room_id: int) -> BalanceSheet
```

Domain-функции (чистые, юнит-тестируемые):

```python
def split_evenly(amount: int, participant_ids: Sequence[int]) -> dict[int, int]
    # largest remainder: 245000 / 3 -> 81667, 81667, 81666 (детерминированно по id)

def simplify_debts(nets: Mapping[int, int]) -> list[Transfer]
    # net = paid - owed; greedy: max должник -> max кредитор; ≤ n-1 переводов
```

## 7. FSM-состояния (aiogram StatesGroup)

Только текстовый ввод живёт в FSM; выбор кнопками — обычные callback'и
(контекст — в `state.data`: room_id и черновик расхода).

```python
class CreateRoom(StatesGroup):
    title = State()                 # ждём название комнаты

class AddVirtualMember(StatesGroup):
    name = State()                  # ждём имя участника

class AddExpense(StatesGroup):
    description = State()           # ждём описание
    amount = State()                # ждём сумму
    payer = State()                 # выбор кнопками
    split = State()                 # мультивыбор кнопками + "Все"
    confirm = State()               # карточка-превью, "Сохранить"

class EditExpense(StatesGroup):
    description = State()
    amount = State()

class AddRepayment(StatesGroup):
    amount = State()                # от кого/кому выбрано кнопками до входа в state
```

`/cancel` и кнопка «✖️ Отмена» очищают state из любого шага.

## 8. Команды

Минимум команд, вся навигация — кнопками (как и просили):

| Команда | Действие |
|---|---|
| `/start` | Приветствие + главное меню (мои комнаты, создать комнату) |
| `/start join_<token>` | Deep-link: вступление в комнату по инвайту |
| `/rooms` | Список моих комнат |
| `/newroom` | Создать комнату (вход в FSM) |
| `/cancel` | Прервать текущий диалог |
| `/help` | Краткая справка |

## 9. Callback-кнопки (CallbackData-фабрики, typed)

Лимит callback_data — 64 байта, поэтому короткие префиксы + числовые id.

| Фабрика | Данные | Назначение |
|---|---|---|
| `MenuCB` | `to: main\|rooms` | навигация в меню |
| `RoomCB` | `action, room_id` | `open`, `invite`, `members`, `balance`, `history`, `settings`, `archive`, `archive_yes`, `leave`, `leave_yes` |
| `MemberCB` | `action, room_id, participant_id` | `add_virtual`, `remove`, `remove_yes` |
| `ExpCB` | `action, room_id, expense_id` | `add`, `view`, `edit_desc`, `edit_amount`, `edit_payer`, `edit_split`, `del`, `del_yes` |
| `ExpListCB` | `room_id, page` | пагинация истории (по 8 на страницу) |
| `PayerCB` | `participant_id` | выбор «кто оплатил» (в FSM) |
| `SplitCB` | `action, participant_id?` | `toggle`, `all`, `done` — мультивыбор с ☑/⬜ |
| `RepayCB` | `action, room_id, participant_id?` | «я вернул долг»: from → to → сумма |
| `ConfirmCB` | `action: save\|cancel` | подтверждение в конце FSM |

Все опасные действия (удалить расход, архивировать комнату, выйти) — двухшаговые:
кнопка → «Точно? Да/Нет».

## 10. Основные сценарии

**A. Создание комнаты и приглашение**
`/start` → «➕ Создать комнату» → ввод «🏕 Шашлыки» → карточка комнаты + кнопка
«🔗 Пригласить» → бот выдаёт `t.me/<bot>?start=join_abc123` → владелец кидает
ссылку в чат компании.

**B. Вступление по ссылке**
Друг жмёт ссылку → `/start join_abc123` → «Вы вступили в 🏕 Шашлыки» + карточка
комнаты. Повторное нажатие — идемпотентно («вы уже в комнате»).

**C. Ручное добавление участника (без Telegram)**
Карточка комнаты → «👥 Участники» → «➕ Добавить вручную» → ввод «Серёга» →
участник появляется во всех выборах плательщика/делёжки наравне с остальными.

**D. Добавление расхода**
Карточка комнаты → «💸 Добавить расход» → «Мясо» → «2450» → выбор плательщика
(по умолчанию подсвечен сам добавляющий) → выбор участников (по умолчанию ☑ все,
одна кнопка «Готово») → превью-карточка → «Сохранить» → бот показывает
обновлённый баланс.

**E. Баланс**
«📊 Баланс» → по каждому: потратил / доля / итог, затем список переводов:
«Данил → Игорю 980 ₽», «Маша → Игорю 1320 ₽».

**F. Возврат долга (settle up)**
«📊 Баланс» → «✅ Я вернул долг» → выбрать кому → сумма (подставляется из
расчёта, можно изменить) → записывается `repayment` → баланс пересчитан.

**G. Редактирование/удаление расхода**
«📜 История» → страница расходов → тап по расходу → карточка с кнопками
«✏️ Описание / 💰 Сумма / 👤 Плательщик / 👥 Делёжка / 🗑 Удалить». Права: автор
записи или владелец комнаты.

**H. Выход и архивация**
Участник: «⚙️ Настройки» → «🚪 Выйти» (с предупреждением, если баланс ≠ 0).
Владелец: «📦 Архивировать комнату» (расходы сохраняются, комната read-only).

## 11. Проблемные места и как они закрыты

1. **Округление.** 2450/3 не делится. Largest remainder в копейках, остаток —
   детерминированно первым по id. Сумма долей всегда равна сумме расхода (инвариант,
   проверяется в domain).
2. **Float.** Запрещён полностью: парсинг «2450», «2450.50», «2 450,5» → int копеек.
3. **Удаление участника с расходами.** Строку `participants` нельзя удалять —
   на неё ссылаются доли. Только `is_active=False`; в балансе остаётся, пока net ≠ 0.
4. **Выход с ненулевым балансом.** Не блокируем (это не платёжная система), но
   предупреждаем и оставляем участника в расчёте баланса.
5. **Устаревшие инлайн-клавиатуры.** Кто-то удалил расход, а у другого висит старая
   кнопка → callback отвечает «Запись устарела, обновляю» и перерисовывает экран.
   Все callback'и обязаны `answer()` (иначе «часики» у пользователя).
6. **Потеря FSM при рестарте.** RedisStorage в проде.
7. **Лимит callback_data 64 байта.** Короткие фабрики, только числовые id, без строк.
8. **Утечка инвайт-ссылки.** Кнопка «перегенерировать ссылку» у владельца; старый
   токен инвалидируется.
9. **username отсутствует/меняется.** Не полагаемся на username вообще:
   идентификация по telegram_id, отображение по display_name (снапшот first_name).
10. **Гонки.** Транзакция на апдейт + БД-констрейнты (unique на членство) —
    двойное вступление/двойной сабмит схлопываются.
11. **Часовые пояса.** Храним TIMESTAMPTZ (UTC), показываем дату без времени —
    для MVP достаточно; TZ комнаты — будущее.
12. **Анти-абьюз.** Константы в `limits.py`: ≤ 50 комнат на пользователя,
    ≤ 50 участников, ≤ 1000 расходов на комнату, сумма ≤ 10 млн ₽, длины строк.

## 12. Предложения по UX (сверх ТЗ)

1. **Settle up** — включено в MVP (см. решение №4). Главная кнопка экрана баланса.
2. **Быстрое добавление одной строкой:** в комнате написать «Мясо 2450» — бот
   распарсит и предложит превью с делёжкой на всех. Резко снижает трение. (V1.1)
3. **Умолчания в анкете расхода:** плательщик = тот, кто добавляет; делёжка = все.
   Типовой расход добавляется за 4 тапа + 2 строки текста.
4. **Редактирование сообщений вместо новых:** меню/списки перерисовываются через
   `edit_message_text` — чат не превращается в простыню.
5. **Привязка виртуального участника:** друг наконец поставил Telegram, зашёл по
   ссылке → бот предлагает «Вы — Серёга?» и сливает аккаунт с виртуальным
   участником. (V1.1, схема это уже поддерживает.)
6. **Групповой режим** (бот добавляется прямо в чат компании) — самый естественный
   UX для сценария, но заметно усложняет MVP (права, привязка чат→комната,
   шум в чате). Осознанно откладываем; текущая архитектура его не блокирует.
7. **Карточка расхода показывает автора записи** — меньше споров «кто это внёс».

---

## План реализации (после подтверждения)

1. **Каркас:** uv, pyproject, ruff+mypy, config, Docker/Compose, engine, alembic,
   первая миграция, `/start` со стабом меню.
2. **Комнаты и участники:** создание, инвайт-ссылки, вступление, виртуальные
   участники, выход, архивация.
3. **Расходы:** добавление (полный FSM), история с пагинацией, карточка,
   редактирование, удаление.
4. **Баланс:** split + simplify_debts (с юнит-тестами), экран баланса, settle up.
5. **Полировка:** тексты, edge-cases, устаревшие клавиатуры, лимиты, README.

Каждый этап — работоспособный бот, который можно потыкать руками.
