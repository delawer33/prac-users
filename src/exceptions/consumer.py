class TransientRetriesExhausted(Exception):
    """Транзиентная ошибка внешнего сервиса после всех ратраев"""

    def __init__(self, *, message_ref: str, attempts: int, detail: str) -> None:
        super().__init__(
            f"transient retries exhausted after {attempts} attempts "
            f"for {message_ref}: {detail}"
        )
        self.message_ref = message_ref
        self.attempts = attempts
        self.detail = detail
