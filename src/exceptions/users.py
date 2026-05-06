from uuid import UUID

from src.exceptions.common import NotFoundError


class UserNotFoundError(NotFoundError):
    public_message = "User not found"

    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id
        super().__init__(f"User not found: {user_id}")
