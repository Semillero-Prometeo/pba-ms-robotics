"""Offline TTS: Piper (if model configured) else espeak-ng/espeak (Spanish)."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

from src.voice.errors import VoicePlaybackError

logger = logging.getLogger(__name__)

_ESPEAK_VOICE_ENV = "ESPEAK_VOICE"
_DEFAULT_ESPEAK_VOICE = "es"


def synthesize_speech_to_wav(text: str, out_path: str) -> None:
    """
    Write spoken `text` to a WAV file.

    - If `piper` is on PATH and `PIPER_MODEL_PATH` points to an .onnx model, use Piper.
    - Otherwise use `espeak-ng` or `espeak` with Spanish voice (override with ESPEAK_VOICE).
    """
    model_path = (os.getenv("PIPER_MODEL_PATH") or "").strip()
    piper_bin = shutil.which("piper")
    if piper_bin and model_path and os.path.isfile(model_path):
        logger.info("TTS: using Piper with model %s", model_path)
        proc = subprocess.run(
            [piper_bin, "--model", model_path, "--output_file", out_path],
            input=text,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        if proc.returncode == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
            return
        logger.warning("Piper failed (%s), falling back to espeak: %s", proc.returncode, proc.stderr)

    voice = (os.getenv(_ESPEAK_VOICE_ENV) or _DEFAULT_ESPEAK_VOICE).strip() or _DEFAULT_ESPEAK_VOICE
    espeak = shutil.which("espeak-ng") or shutil.which("espeak")
    if not espeak:
        raise RuntimeError(
            "No TTS available: install Piper (+ set PIPER_MODEL_PATH) or espeak-ng / espeak"
        )

    logger.info("TTS: using %s voice=%s", espeak, voice)
    try:
        subprocess.run(
            [espeak, "-v", voice, "-w", out_path, text],
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or str(exc)
        raise VoicePlaybackError(f"espeak-ng falló: {detail}", status_code=503) from exc
