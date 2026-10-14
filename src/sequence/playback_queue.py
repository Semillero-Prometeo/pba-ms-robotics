from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from src.sequence.interfaces.sequence_interface import (
    MotionBlock,
    QueueStepPublic,
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
            self._thread = None
            self._stop = threading.Event()

    def snapshot(self) -> RuntimeSnapshot:
        with self._lock:
            current_step = self._current
            pending = list(self._queue)
            if current_step is None and pending:
                current_step = pending[0]
                pending = pending[1:]
            current = self._public(current_step)
            queue = [item for item in (self._public(step) for step in pending) if item is not None]
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

    def _public(self, step: QueueStep | None) -> QueueStepPublic | None:
        if step is None:
            return None
        return QueueStepPublic(
            id=step.id,
            name=step.name,
            mode=step.mode,  # type: ignore[arg-type]
            source=step.source,  # type: ignore[arg-type]
        )

    def _pop(self) -> QueueStep | None:
        with self._lock:
            if not self._queue:
                self._current = None
                return None
            step = self._queue.pop(0)
            self._current = step
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

    def _sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while not self._stop.is_set() and time.monotonic() < deadline:
            time.sleep(0.02)
