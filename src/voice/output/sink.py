"""Prefer Bluetooth sink, then USB, then first available PulseAudio sink."""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Final

logger = logging.getLogger(__name__)

_ENV_SINK: Final[str] = "PULSE_SINK"
_ENV_VOICE_SINK: Final[str] = "VOICE_AUDIO_SINK"


def get_preferred_sink_name() -> str | None:
    """
    Return PulseAudio sink name for playback, or None to use server default.

    Override with PULSE_SINK or VOICE_AUDIO_SINK.
    """
    override = (os.getenv(_ENV_SINK) or os.getenv(_ENV_VOICE_SINK) or "").strip()
    if override:
        return override

    try:
        proc = subprocess.run(
            ["pactl", "list", "short", "sinks"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except FileNotFoundError:
        logger.debug("pactl not found; no automatic sink selection")
        return None

    if proc.returncode != 0:
        logger.warning("pactl list short sinks failed: %s", proc.stderr)
        return None

    sinks: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            sinks.append((parts[0], parts[1]))

    if not sinks:
        return None

    for _idx, name in sinks:
        lower = name.lower()
        if "bluez" in lower or "bluetooth" in lower:
            logger.info("Selected Bluetooth sink: %s", name)
            return name

    for _idx, name in sinks:
        if "usb" in name.lower():
            logger.info("Selected USB sink: %s", name)
            return name

    chosen = sinks[0][1]
    logger.info("Selected default (first) sink: %s", chosen)
    return chosen
