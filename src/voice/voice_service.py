"""Orchestration: NATS chat to management MS, then local TTS + playback."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.voice.output.sink import get_preferred_sink_name
from src.voice.utils.playback import play_wav_file
from src.voice.utils.speech_text import format_text_for_speech
from src.voice.tts.tts_local import synthesize_speech_to_wav

if TYPE_CHECKING:
    from nats.aio.client import Client as NATSClient

logger = logging.getLogger(__name__)


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
        spoken, sink = await asyncio.to_thread(_synthesize_and_play_sync, message)
        return SpeakResult(message=message, spoken=spoken, sink=sink)
