class PermanentEventError(Exception):
    """Поднимается, если сообщение не удается обработать по перманентной причине (например невалидный json)"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
