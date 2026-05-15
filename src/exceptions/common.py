from src.exceptions.base import AppError


class NotFoundError(AppError):
    http_status_code = 404
    log_level = "warning"
    public_message = "Not found"


class ConflictError(AppError):
    http_status_code = 409
    log_level = "warning"


class AlreadyExistsError(ConflictError):
    public_message = "Already exists"

    def __init__(self, field: str, value: str) -> None:
        self.field = field
        self.value = value
        self.public_message = f"{field.capitalize()} already exists"
        super().__init__(f"{field} already exists: {value}")

