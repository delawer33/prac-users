from uuid import UUID

from src.exceptions.base import AppError


class UserNotFoundError(AppError):
    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id
        super().__init__(f"User not found: {user_id}")


class AlreadyExistsError(AppError):
    def __init__(self, field: str, value: str) -> None:
        self.field = field
        self.value = value
        super().__init__(f"{field} already exists: {value}")
