import os
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("NATS_SERVER", "nats://localhost:4222")

from src.action.action_service import ActionService
from src.action.interfaces.command_interface import Command
from src.sequence.interfaces.sequence_interface import SequenceStatusResponse
from src.sequence.sequence_service import SequenceService


ORIGIN = {
    "name": "saludo",
    "description": "Saludo con el brazo derecho",
    "arduino_id": 2,
    "blocks": [[0, 0, 0.0, 2, 0, 1, "P0_S0"]],
}


def test_get_actions_from_sequences_not_firmware(tmp_path: Path):
    sequences = SequenceService(data_dir=tmp_path)
    sequences.save_sequence({"sequence": ORIGIN, "overwrite": False})
    (tmp_path / "legado.json").write_text(
        '{"version": 1, "name": "legado", "blocks": ['
        '{"arduino_id": 0, "pca": 0, "servo": 0, "inicio": 0, "dur": 2, "pos": 0, "vel": 1, "nombre": "P0_S0"}'
        "]}",
        encoding="utf-8",
    )
    service = ActionService(sequence_service=sequences)
    commands = service.get_actions()
    assert commands == [
        Command(id=1, name="saludo", arduino_id=2, description="Saludo con el brazo derecho")
    ]


def test_empty_store_get_actions_empty(tmp_path: Path):
    service = ActionService(sequence_service=SequenceService(data_dir=tmp_path))
    assert service.get_actions() == []


def test_execute_action_plays_sequence(tmp_path: Path):
    sequences = SequenceService(data_dir=tmp_path)
    sequences.save_sequence({"sequence": ORIGIN, "overwrite": False})
    sequences.start_playback = MagicMock(
        return_value=SequenceStatusResponse(status="ok", message="Secuencia en ejecución")
    )
    service = ActionService(sequence_service=sequences)
    result = service.execute_action(action_id=1, arduino_id=9)
    sequences.start_playback.assert_called_once()
    blocks = sequences.start_playback.call_args.args[0]
    assert blocks[0].arduino_id == 2
    assert result.status == "ok"


def test_execute_action_unknown_id_writes_serial(tmp_path: Path):
    sequences = SequenceService(data_dir=tmp_path)
    service = ActionService(sequence_service=sequences)
    service.arduino_utils = MagicMock()
    connection = MagicMock()
    service.arduino_utils.connections = {0: connection}
    service.arduino_utils.json_reader.read_first_meaningful_line.return_value = ["ok"]
    result = service.execute_action(action_id=99, arduino_id=0)
    connection.serial.write.assert_called_once_with(b"99\n")
    assert result.status == "ok"
