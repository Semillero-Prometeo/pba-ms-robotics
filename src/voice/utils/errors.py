"""Exceptions with HTTP-style codes for NATS error payloads consumed by the gateway."""


class VoicePlaybackError(Exception):
    """Playback/TTS failure (typically no audio device in Docker or missing tools)."""

    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code
