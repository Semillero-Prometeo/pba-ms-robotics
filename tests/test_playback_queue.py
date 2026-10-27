import os
import time
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("NATS_SERVER", "nats://localhost:4222")

import pytest

from src.action.action_service import ActionService
from src.sequence.interfaces.sequence_interface import MotionBlock, SequencePlaybackPayload
from src.sequence.playback_queue import WAIT_SECONDS, PlaybackQueue, QueueStep, step_duration_ms
from src.sequence.sequence_service import SequenceService

ORIGIN = {
    "name": "saludo",
    "description": "Saludo con el brazo derecho",
    "category": "brazo_derecho",
    "arduino_id": 0,
    "blocks": [[0, 0, 0.0, 2, 850, 5, "P0_S0"]],
    "blocks_neutro": [[0, 0, 0.0, 2, 500, 5, "P0_S0"]],
}

ORIGIN_TWO = {
    **ORIGIN,
    "name": "adios",
    "description": "Despedida del gesto",
    "blocks": [[0, 1, 0.0, 2, 200, 5, "P0_S1"]],
    "blocks_neutro": [[0, 1, 0.0, 2, 200, 5, "P0_S1"]],
}


def ready_service(tmp_path: Path, wait: float = 0.05) -> SequenceService:
    service = SequenceService(data_dir=tmp_path)
    service.playback_queue.wait_seconds = wait
    service._ensure_connections = lambda blocks: None  # noqa: ARG005
    service._send_block_command = lambda block: None  # noqa: ARG005
    service.save_sequence({"sequence": ORIGIN, "overwrite": False})
    service.save_sequence({"sequence": ORIGIN_TWO, "overwrite": False})
    return service


def wait_idle(service: SequenceService, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not service.get_runtime().busy:
            return
        time.sleep(0.02)
    raise AssertionError(service.get_runtime().model_dump())


def test_wait_seconds_is_one():
    assert WAIT_SECONDS == 1.0


def test_execute_action_enqueues_pair_and_returns_before_it_finishes(tmp_path: Path):
    service = ready_service(tmp_path, wait=0.3)

    def slow_fire(blocks, stop_event):
        stop_event.wait(0.4)

    service._fire_blocks = slow_fire
    actions = ActionService(sequence_service=service)
    started = time.monotonic()
    result = actions.execute_action(1, 0)
    elapsed = time.monotonic() - started
    assert result.status == "ok"
    assert elapsed < 0.2
    snap = service.get_runtime()
    assert snap.busy is True
    assert snap.source == "turno"
    assert snap.current is not None
    assert snap.current.mode == "normal"
    assert snap.current.name == "saludo"
    modes = [snap.current.mode, *[item.mode for item in snap.queue]]
    assert modes == ["normal", "espera", "neutro", "espera"]
    service.stop_playback()
    wait_idle(service)


def test_second_execute_appends_second_pair(tmp_path: Path):
    service = ready_service(tmp_path, wait=0.3)

    def slow_fire(blocks, stop_event):
        stop_event.wait(0.4)

    service._fire_blocks = slow_fire
    actions = ActionService(sequence_service=service)
    actions.execute_action(1, 0)
    actions.execute_action(2, 0)
    snap = service.get_runtime()
    names_modes = [(snap.current.name, snap.current.mode)] + [
        (item.name, item.mode) for item in snap.queue
    ]
    assert names_modes == [
        ("saludo", "normal"),
        ("saludo", "espera"),
        ("saludo", "neutro"),
        ("saludo", "espera"),
        ("adios", "normal"),
        ("adios", "espera"),
        ("adios", "neutro"),
        ("adios", "espera"),
    ]
    service.stop_playback()
    wait_idle(service)


def test_user_play_while_busy_leaves_queue(tmp_path: Path):
    service = ready_service(tmp_path, wait=0.3)
    service._fire_blocks = lambda blocks, stop_event: stop_event.wait(0.4)
    ActionService(sequence_service=service).execute_action(1, 0)
    before = service.get_runtime().model_dump()
    with pytest.raises(ValueError, match="Ya existe una secuencia en ejecución"):
        service.start_user_playback(
            SequencePlaybackPayload(mode="neutro", source="panel", name="saludo")
        )
    after = service.get_runtime().model_dump()
    assert after["queue"] == before["queue"]
    assert after["current"] == before["current"]
    service.stop_playback()
    wait_idle(service)


def test_stop_clears_queue_and_wait(tmp_path: Path):
    service = ready_service(tmp_path, wait=2.0)
    service._fire_blocks = lambda blocks, stop_event: stop_event.wait(0.05)
    ActionService(sequence_service=service).execute_action(1, 0)
    time.sleep(0.08)
    status = service.stop_playback()
    assert status.status == "ok"
    wait_idle(service, timeout=1.0)
    snap = service.get_runtime()
    assert snap.busy is False
    assert snap.current is None
    assert snap.queue == []
    assert snap.source is None


def test_missing_arduino_skips_step_and_continues(tmp_path: Path):
    service = ready_service(tmp_path, wait=0.05)
    calls: list[str] = []

    def fire(blocks, stop_event):
        if blocks[0].pos == 850:
            raise ValueError("Arduinos no conectados para la secuencia: [0]")
        calls.append(blocks[0].nombre)
        return None

    service._fire_blocks = fire
    ActionService(sequence_service=service).execute_action(1, 0)
    wait_idle(service)
    assert calls == ["P0_S0"]


def test_incomplete_sequence_omits(tmp_path: Path):
    service = SequenceService(data_dir=tmp_path)
    (tmp_path / "incompleto.json").write_text(
        '{"version": 1, "id": 3, "name": "incompleto", "blocks": ['
        '{"arduino_id": 0, "pca": 0, "servo": 0, "inicio": 0, "dur": 2, "pos": 0, "vel": 1, "nombre": "P0_S0"}'
        "]}",
        encoding="utf-8",
    )
    service.start_user_playback = MagicMock()
    result = ActionService(sequence_service=service).execute_action(3, 0)
    assert result.status == "ok"
    assert result.response == ["omitido"]
    service.start_user_playback.assert_not_called()


def test_unknown_id_writes_serial(tmp_path: Path):
    service = SequenceService(data_dir=tmp_path)
    actions = ActionService(sequence_service=service)
    actions.arduino_utils = MagicMock()
    connection = MagicMock()
    actions.arduino_utils.connections = {0: connection}
    actions.arduino_utils.json_reader.read_first_meaningful_line.return_value = ["ok"]
    result = actions.execute_action(99, 0)
    connection.serial.write.assert_called_once_with(b"99\n")
    assert result.status == "ok"


def test_get_actions_one_row_per_gesture(tmp_path: Path):
    service = ready_service(tmp_path)
    commands = ActionService(sequence_service=service).get_actions()
    names = [item.name for item in commands]
    assert sorted(names) == ["adios", "saludo"]
    assert {item.id for item in commands} == {1, 2}


def _block(inicio: float, nombre: str = "P0_S0") -> MotionBlock:
    return MotionBlock(
        arduino_id=0,
        pca=0,
        servo=0,
        inicio=inicio,
        dur=2.0,
        pos=100,
        vel=5,
        nombre=nombre,
    )


def test_espera_duration_is_wait_seconds_in_ms():
    step = QueueStep(id=1, name="saludo", mode="espera", source="turno")
    assert step_duration_ms(step, 1.0) == 1000
    assert step_duration_ms(step, WAIT_SECONDS) == 1000


def test_gesture_duration_is_max_inicio_ms():
    step = QueueStep(
        id=1,
        name="saludo",
        mode="normal",
        source="turno",
        blocks=[_block(0.0, "a"), _block(1.5, "b")],
    )
    assert step_duration_ms(step) == 1500
    empty = QueueStep(id=1, name="x", mode="neutro", source="turno", blocks=[])
    assert step_duration_ms(empty) == 0


def test_current_has_blocks_and_queue_does_not(tmp_path: Path):
    service = ready_service(tmp_path, wait=0.3)

    def slow_fire(blocks, stop_event):
        stop_event.wait(0.4)

    service._fire_blocks = slow_fire
    ActionService(sequence_service=service).execute_action(1, 0)
    snap = service.get_runtime()
    assert snap.current is not None
    assert snap.current.mode == "normal"
    assert snap.current.duration_ms == 0
    assert snap.current.remaining_ms is not None
    assert snap.current.blocks is not None
    assert [item.nombre for item in snap.current.blocks] == ["P0_S0"]
    espera = snap.queue[0]
    assert espera.mode == "espera"
    assert espera.duration_ms == 300
    assert espera.blocks is None
    assert espera.remaining_ms is None
    service.stop_playback()
    wait_idle(service)


def test_espera_current_has_empty_blocks(tmp_path: Path):
    service = ready_service(tmp_path, wait=0.4)
    service._fire_blocks = lambda blocks, stop_event: None
    ActionService(sequence_service=service).execute_action(1, 0)
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        snap = service.get_runtime()
        if snap.current is not None and snap.current.mode == "espera":
            assert snap.current.blocks == []
            assert snap.current.duration_ms == 400
            service.stop_playback()
            wait_idle(service)
            return
        time.sleep(0.02)
    raise AssertionError(service.get_runtime().model_dump())


def test_remaining_drops_during_slow_step():
    def slow_fire(blocks, stop_event):
        stop_event.wait(0.3)

    queue = PlaybackQueue(slow_fire, wait_seconds=1.0)
    queue.enqueue(
        [
            QueueStep(
                id=1,
                name="saludo",
                mode="normal",
                source="turno",
                blocks=[_block(0.5, "late")],
            )
        ],
        reject_if_busy=False,
    )
    time.sleep(0.12)
    snap = queue.snapshot()
    assert snap.current is not None
    assert snap.current.duration_ms == 500
    assert 0 < snap.current.remaining_ms < 500
    queue.stop()


def test_fired_follows_elapsed_vs_inicio():
    def slow_fire(blocks, stop_event):
        stop_event.wait(0.35)

    queue = PlaybackQueue(slow_fire, wait_seconds=1.0)
    queue.enqueue(
        [
            QueueStep(
                id=1,
                name="saludo",
                mode="normal",
                source="turno",
                blocks=[_block(0.0, "early"), _block(0.2, "late")],
            )
        ],
        reject_if_busy=False,
    )
    time.sleep(0.08)
    first = queue.snapshot()
    names = {item.nombre: item.fired for item in first.current.blocks}
    assert names["early"] is True
    assert names["late"] is False
    time.sleep(0.2)
    second = queue.snapshot()
    later = {item.nombre: item.fired for item in second.current.blocks}
    assert later["early"] is True
    assert later["late"] is True
    queue.stop()
