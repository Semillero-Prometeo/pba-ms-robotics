"""HTTP-style codes for NATS error payloads consumed by the gateway."""


class PhraseError(Exception):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code
