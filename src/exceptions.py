from uuid import UUID


class AppError(Exception):
    pass


class UserNotFoundError(AppError):
    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id
        super().__init__(f"User not found: {user_id}")


class UserEmailAlreadyExistsError(AppError):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"Email already registered: {email}")
