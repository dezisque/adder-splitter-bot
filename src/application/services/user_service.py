from src.application.interfaces import UserRepo
from src.domain.entities import User


class UserService:
    def __init__(self, users: UserRepo) -> None:
        self._users = users

    async def upsert_from_telegram(
        self, telegram_id: int, username: str | None, first_name: str
    ) -> User:
        """Регистрирует пользователя или обновляет его профиль при изменении."""
        user = await self._users.get_by_telegram_id(telegram_id)
        if user is None:
            return await self._users.create(telegram_id, username, first_name)
        if user.username != username or user.first_name != first_name:
            await self._users.update_profile(user.id, username, first_name)
            user.username = username
            user.first_name = first_name
        return user
