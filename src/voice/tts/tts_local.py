"""Offline TTS: Piper (if model configured) else espeak-ng/espeak (Spanish)."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from src.voice.utils.errors import VoicePlaybackError

logger = logging.getLogger(__name__)

_ESPEAK_VOICE_ENV = "ESPEAK_VOICE"
_DEFAULT_ESPEAK_VOICE = "es"


def _models_voice_dir() -> Path:
    """``src/core/models/voice`` relativo a este paquete (``src/voice/tts`` → ``src``)."""
    return Path(__file__).resolve().parent.parent.parent / "core" / "models" / "voice"


def _first_onnx_in_models_voice() -> str | None:
    directory = _models_voice_dir()
    if not directory.is_dir():
        return None
    models = sorted(directory.glob("*.onnx"))
    if not models:
        return None
    return str(models[0])


def _resolve_piper_model_path() -> str | None:
    """
    Orden: ``PIPER_MODEL_PATH`` si el fichero existe; si no, primer ``*.onnx`` en
    ``src/core/models/voice`` (layout del repo).
    """
    env_path = (os.getenv("PIPER_MODEL_PATH") or "").strip()
    if env_path and os.path.isfile(env_path):
        return env_path
    fallback = _first_onnx_in_models_voice()
    if fallback and os.path.isfile(fallback):
        if env_path:
            logger.warning(
                "PIPER_MODEL_PATH no apunta a un fichero válido (%s); usando %s",
                env_path,
                fallback,
            )
        else:
            logger.info("PIPER_MODEL_PATH no definido; usando modelo en repo: %s", fallback)
        return fallback
    if env_path:
        logger.warning(
            "PIPER_MODEL_PATH inválido y no hay .onnx en src/core/models/voice: %s", env_path
        )
    return None


def synthesize_speech_to_wav(text: str, out_path: str) -> None:
    """
    Write spoken `text` to a WAV file.

    - If `piper` is on PATH and hay un modelo `.onnx` (env o ``src/core/models/voice``), use Piper.
    - Otherwise use `espeak-ng` or `espeak` with Spanish voice (override with ESPEAK_VOICE).
    """
    model_path = _resolve_piper_model_path()
    piper_bin = shutil.which("piper")
    if piper_bin and model_path:
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
        logger.warning(
            "Piper failed (%s), falling back to espeak: %s", proc.returncode, proc.stderr
        )

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
