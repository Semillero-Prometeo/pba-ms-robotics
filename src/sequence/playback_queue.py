from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from src.sequence.interfaces.sequence_interface import (
    MotionBlock,
    QueueStepPublic,
    RuntimeBlockPublic,
    RuntimeSnapshot,
)

logger = logging.getLogger(__name__)

WAIT_SECONDS = 1.0


@dataclass
class QueueStep:
    id: int | None
    name: str
    mode: str
    source: str
    blocks: list[MotionBlock] | None = None


def step_duration_ms(step: QueueStep, wait_seconds: float = WAIT_SECONDS) -> int:
    if step.mode == "espera":
        return int(round(wait_seconds * 1000))
    blocks = step.blocks or []
    if not blocks:
        return 0
    return int(round(max(block.inicio for block in blocks) * 1000))


class PlaybackQueue:
    def __init__(
        self,
        fire_blocks: Callable[[list[MotionBlock], threading.Event], None],
        wait_seconds: float = WAIT_SECONDS,
    ) -> None:
        self._fire_blocks = fire_blocks
        self.wait_seconds = wait_seconds
        self._lock = threading.Lock()
        self._queue: list[QueueStep] = []
        self._current: QueueStep | None = None
        self._step_started: float | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def enqueue(self, steps: list[QueueStep], *, reject_if_busy: bool) -> None:
        with self._lock:
            if reject_if_busy and self._busy_unlocked():
                raise ValueError("Ya existe una secuencia en ejecución")
            self._queue.extend(steps)
            if self._thread is None or not self._thread.is_alive():
                self._stop.clear()
                self._thread = threading.Thread(target=self._run, name="sequence-queue", daemon=True)
                self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._queue.clear()
            thread = self._thread
            self._stop.set()
        if thread is not None:
            thread.join(timeout=2.0)
        with self._lock:
            self._current = None
            self._step_started = None
            self._thread = None
            self._stop = threading.Event()

    def snapshot(self) -> RuntimeSnapshot:
        with self._lock:
            current_step = self._current
            pending = list(self._queue)
            started = self._step_started
            peeked = False
            if current_step is None and pending:
                current_step = pending[0]
                pending = pending[1:]
                peeked = True
            elapsed = 0.0 if peeked or started is None or current_step is None else time.monotonic() - started
            current = self._public(current_step, for_current=True, elapsed_s=elapsed)
            queue = [
                item
                for item in (self._public(step, for_current=False, elapsed_s=0.0) for step in pending)
                if item is not None
            ]
            source = None
            if current is not None:
                source = current.source
            elif queue:
                source = queue[0].source
            return RuntimeSnapshot(
                busy=self._busy_unlocked(),
                source=source,
                current=current,
                queue=queue,
            )

    def _busy_unlocked(self) -> bool:
        thread_live = self._thread is not None and self._thread.is_alive()
        return thread_live or self._current is not None or bool(self._queue)

    def _public(
        self,
        step: QueueStep | None,
        *,
        for_current: bool,
        elapsed_s: float,
    ) -> QueueStepPublic | None:
        if step is None:
            return None
        duration = step_duration_ms(step, self.wait_seconds)
        remaining: int | None = None
        blocks = None
        if for_current:
            remaining = max(0, min(duration, duration - int(round(elapsed_s * 1000))))
            if step.mode == "espera" or not step.blocks:
                blocks = []
            else:
                blocks = [
                    RuntimeBlockPublic(
                        nombre=block.nombre,
                        pca=block.pca,
                        servo=block.servo,
                        inicio=block.inicio,
                        dur=block.dur,
                        pos=block.pos,
                        vel=block.vel,
                        fired=elapsed_s >= block.inicio,
                    )
                    for block in step.blocks
                ]
        return QueueStepPublic(
            id=step.id,
            name=step.name,
            mode=step.mode,  # type: ignore[arg-type]
            source=step.source,  # type: ignore[arg-type]
            duration_ms=duration,
            remaining_ms=remaining,
            blocks=blocks,
        )

    def _pop(self) -> QueueStep | None:
        with self._lock:
            if not self._queue:
                self._current = None
                self._step_started = None
                return None
            step = self._queue.pop(0)
            self._current = step
            self._step_started = time.monotonic()
            return step

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                step = self._pop()
                if step is None:
                    return
                if step.mode == "espera":
                    self._sleep(self.wait_seconds)
                    continue
                if step.blocks is None:
                    logger.warning("Paso %s sin bloques; se descarta", step.name)
                    continue
                try:
                    self._fire_blocks(step.blocks, self._stop)
                except ValueError:
                    logger.warning(
                        "Paso descartado por hardware ausente: %s %s", step.name, step.mode
                    )
                    continue
        finally:
            with self._lock:
                if self._thread is threading.current_thread():
                    self._thread = None
                    self._current = None
                    self._step_started = None

    def _sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while not self._stop.is_set() and time.monotonic() < deadline:
            time.sleep(0.02)
