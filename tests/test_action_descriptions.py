import json
from pathlib import Path

from src.action.descriptions import apply_descriptions, load_descriptions
from src.action.interfaces.command_interface import Command


def test_missing_file_yields_empty_map(tmp_path: Path):
    assert load_descriptions(tmp_path / "missing.json") == {}


def test_invalid_json_yields_empty_map(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")
    assert load_descriptions(path) == {}


def test_apply_descriptions_joins_on_arduino_and_id(tmp_path: Path):
    path = tmp_path / "action-descriptions.json"
    path.write_text(
        json.dumps(
            [
                {"arduino_id": 1, "id": 4, "description": "Saludo con el brazo derecho"},
                {"arduino_id": 2, "id": 4, "description": "Otro arduino"},
            ]
        ),
        encoding="utf-8",
    )
    commands = [
        Command(id=4, name="Saludo", arduino_id=1),
        Command(id=9, name="Reposo", arduino_id=1),
    ]
    described = apply_descriptions(commands, load_descriptions(path))
    assert described[0].description == "Saludo con el brazo derecho"
    assert described[1].description == ""
