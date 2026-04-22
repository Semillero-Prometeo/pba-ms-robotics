"""Orchestration: NATS chat to management MS, then local TTS + playback."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.voice.output.sink import get_preferred_sink_name
from src.voice.tts.tts_local import synthesize_speech_to_wav
from src.voice.tts.tts_openai import synthesize_openai_to_wav
from src.voice.utils.playback import play_wav_file
from src.voice.utils.speech_text import format_text_for_speech

if TYPE_CHECKING:
    from nats.aio.client import Client as NATSClient

logger = logging.getLogger(__name__)


def _should_attempt_openai_tts() -> bool:
    """``VOICE_TTS_MODE=local`` nunca usa cloud; ``auto``/``openai`` si hay ``OPENAI_API_KEY``."""
    mode = (os.getenv("VOICE_TTS_MODE") or "auto").strip().lower()
    if mode == "local":
        return False
    return bool((os.getenv("OPENAI_API_KEY") or "").strip())


class SpeakPayload(BaseModel):
    message: str = Field(..., min_length=1)


class SpeakResult(BaseModel):
    message: str
    spoken: bool
    sink: str | None = None


def _synthesize_and_play_sync(text: str) -> tuple[bool, str | None]:
    text = format_text_for_speech(text)
    sink = get_preferred_sink_name()
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        used_cloud = False
        if _should_attempt_openai_tts():
            try:
                synthesize_openai_to_wav(text, path)
                used_cloud = True
            except Exception as exc:
                logger.warning("OpenAI TTS no disponible (%s); usando TTS local.", exc)
        if not used_cloud:
            synthesize_speech_to_wav(text, path)
        play_wav_file(path, sink)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return True, sink


class VoiceService:
    def __init__(self, nc: NATSClient) -> None:
        self._nc = nc

    async def speak_only(self, message: str) -> SpeakResult:
        # return SpeakResult(message=message, spoken=True, sink=get_preferred_sink_name())

        spoken, sink = await asyncio.to_thread(_synthesize_and_play_sync, message)
        return SpeakResult(message=message, spoken=spoken, sink=sink)
