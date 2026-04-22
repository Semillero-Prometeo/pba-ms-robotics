"""OpenAI Speech API (TTS) → WAV vía ``response_format=wav`` (sin ffmpeg)."""

from __future__ import annotations

import logging
import os
from typing import Final

from openai import APIError, OpenAI

logger = logging.getLogger(__name__)

_DEFAULT_MODEL: Final[str] = "gpt-4o-mini-tts"
_DEFAULT_VOICE: Final[str] = "ash"
_DEFAULT_TIMEOUT: Final[float] = 60.0
_MAX_INPUT_CHARS: Final[int] = 4096


def _env_str(name: str, default: str) -> str:
    v = (os.getenv(name) or "").strip()
    return v if v else default


def _clip_for_openai(text: str) -> str:
    if len(text) <= _MAX_INPUT_CHARS:
        return text
    logger.warning("TTS input truncado a %s caracteres (límite OpenAI)", _MAX_INPUT_CHARS)
    return text[: _MAX_INPUT_CHARS - 3] + "..."


def synthesize_openai_to_wav(text: str, out_path: str) -> None:
    """
    Genera WAV con ``client.audio.speech.create(..., response_format=\"wav\")`` y escribe en disco.

    Variables: ``OPENAI_API_KEY`` (obligatoria), ``OPENAI_TTS_MODEL``, ``OPENAI_TTS_VOICE``,
    ``OPENAI_TTS_SPEED``, ``OPENAI_TTS_TIMEOUT``.
    """
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")

    clipped = _clip_for_openai(text)
    model = _env_str("OPENAI_TTS_MODEL", _DEFAULT_MODEL)
    voice = _env_str("OPENAI_TTS_VOICE", _DEFAULT_VOICE)
    speed_s = (os.getenv("OPENAI_TTS_SPEED") or "").strip()
    timeout = float(
        (os.getenv("OPENAI_TTS_TIMEOUT") or str(_DEFAULT_TIMEOUT)).strip() or _DEFAULT_TIMEOUT
    )

    client = OpenAI(api_key=api_key, timeout=timeout)

    kwargs: dict = {
        "model": model,
        "voice": voice,
        "input": clipped,
        "response_format": "wav",
    }
    if speed_s:
        try:
            kwargs["speed"] = float(speed_s)
        except ValueError:
            logger.warning("OPENAI_TTS_SPEED inválido (%s), ignorado", speed_s)

    try:
        response = client.audio.speech.create(**kwargs)
    except APIError as exc:
        logger.warning("OpenAI TTS API error: %s", exc)
        raise

    response.write_to_file(out_path)
