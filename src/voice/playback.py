"""Play WAV files via PulseAudio / PipeWire / ALSA."""

from __future__ import annotations

import logging
import os
import subprocess

logger = logging.getLogger(__name__)


def play_wav_file(path: str, sink_name: str | None) -> None:
    """
    Play a WAV file. Uses paplay with -d sink when sink_name is set; falls back to pw-play, aplay.
    """
    env = os.environ.copy()

    if sink_name:
        env["PULSE_SINK"] = sink_name

    paplay_cmd: list[str] = ["paplay", path]
    if sink_name:
        paplay_cmd = ["paplay", "-d", sink_name, path]

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
        logger.warning("Playback command failed (%s): %s", cmd, proc.stderr)

    try:
        subprocess.run(["aplay", path], check=True, timeout=600)
    except FileNotFoundError as exc:
        raise RuntimeError("No audio player found (paplay, pw-play, or aplay)") from exc
