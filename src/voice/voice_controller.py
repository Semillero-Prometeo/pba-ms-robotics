"""HTTP helpers to exercise voice without NATS (debug / integration tests)."""

from __future__ import annotations

import subprocess

from fastapi import APIRouter, HTTPException

from src.core.nats.nats_client import nats_handler
from src.voice.voice_service import SpeakPayload, SpeakResult, VoiceService

router = APIRouter(prefix="/voice", tags=["voice"])


def _service() -> VoiceService:
    return VoiceService(nats_handler.req_nc)


async def speak_http(body: SpeakPayload) -> SpeakResult:
    try:
        return await _service().speak_only(body.message)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
