class DomainError(Exception):
    """Базовая ожидаемая бизнес-ошибка; message показывается пользователю."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(DomainError):
    pass


class AccessDenied(DomainError):
    pass


class LimitExceeded(DomainError):
    pass


class InvalidInput(DomainError):
    pass
