# adder-splitter

Telegram-бот для совместного учёта расходов: комната на компанию, расходы с делёжкой,
автоматический расчёт «кто кому сколько должен» и отметка возвратов.

Дизайн и архитектура — в [docs/DESIGN.md](docs/DESIGN.md).

## Стек

Python 3.13 · aiogram 3 · PostgreSQL · SQLAlchemy 2 · Alembic · Docker Compose · uv.
Clean Architecture: `domain` (чистая логика) → `application` (юзкейсы) →
`infrastructure` (БД) / `presentation` (Telegram).

## Запуск

1. Получите токен бота у [@BotFather](https://t.me/BotFather).
2. `cp .env.example .env` и впишите `BOT_TOKEN`.
3. Всё в Docker:

```sh
docker compose up -d --build
```

Либо локально (Postgres из compose, бот — на машине):

```sh
docker compose up -d postgres
uv sync
uv run alembic upgrade head
uv run python -m src.main
```

Postgres наружу смотрит через порт **5433** (5432 часто занят локальным).

## Тесты и проверки

```sh
uv run pytest                # юнит-тесты domain-слоя
uv run ruff check . && uv run mypy

# интеграционные тесты сервисов (нужен живой Postgres):
docker compose exec postgres createdb -U adder adder_splitter_test
TEST_DATABASE_URL=postgresql+asyncpg://adder:adder@localhost:5433/adder_splitter_test \
  uv run pytest tests/integration
```

## Команды бота

`/start` — меню (и вступление по инвайт-ссылке) · `/rooms` · `/newroom` ·
`/cancel` · `/help`. Всё остальное — инлайн-кнопки.
