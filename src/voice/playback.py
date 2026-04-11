"""Play WAV files via PulseAudio / PipeWire / ALSA."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

from src.voice.errors import VoicePlaybackError

logger = logging.getLogger(__name__)


def _skip_playback() -> bool:
    return os.getenv("VOICE_SKIP_PLAYBACK", "").strip().lower() in ("1", "true", "yes")


def play_wav_file(path: str, sink_name: str | None) -> None:
    """
    Play a WAV file. Uses paplay with -d sink when sink_name is set; falls back to pw-play, aplay.

    Set ``VOICE_SKIP_PLAYBACK=1`` to only generate TTS files (useful in Docker without /dev/snd).

    In Docker without a sound device or PulseAudio, paplay/aplay usually fail: mount ``/dev/snd`` or
    use the host Pulse socket (see README).
    """
    if _skip_playback():
        logger.warning(
            "VOICE_SKIP_PLAYBACK is set: skipping playback (WAV was written at %s). "
            "Unset for real audio or configure Docker audio.",
            path,
        )
        return

    env = os.environ.copy()

    if sink_name:
        env["PULSE_SINK"] = sink_name

    paplay_cmd: list[str] = ["paplay", path]
    if sink_name:
        paplay_cmd = ["paplay", "-d", sink_name, path]

    failures: list[str] = []

    for cmd in (paplay_cmd, ["pw-play", path]):
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                env=env,
                check=False,
            )
        except FileNotFoundError:
            continue
        if proc.returncode == 0:
            return
        detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        failures.append(f"{' '.join(cmd)}: {detail}")
        logger.warning("Playback command failed (%s)", failures[-1])

    aplay_found = shutil.which("aplay")
    if aplay_found:
        proc = subprocess.run(
            [aplay_found, path],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode == 0:
            return
        detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        failures.append(f"aplay: {detail}")
    else:
        failures.append("aplay: not installed")

    hint = (
        "No se pudo reproducir audio. En Docker suele faltar /dev/snd o un servidor PulseAudio. "
        "Opciones: (1) montar dispositivos de audio (ver README y docker-compose comentado), "
        "(2) ejecutar el MS en el host Linux con altavoz/BT, "
        "(3) poner VOICE_SKIP_PLAYBACK=1 para omitir reproducción y solo validar TTS."
    )
    raise VoicePlaybackError(f"{hint} Detalle: {' | '.join(failures)}")
