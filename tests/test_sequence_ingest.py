import os
from pathlib import Path

os.environ.setdefault("NATS_SERVER", "nats://localhost:4222")

import pytest
from pydantic import ValidationError

from src.sequence.ingest import ingest_save, next_sequence_id
from src.sequence.interfaces.sequence_interface import MotionSequenceFile
from src.sequence.sequence_service import SequenceService


ORIGIN = {
    "name": "saludo",
    "description": "Saludo con el brazo derecho",
    "arduino_id": 2,
    "blocks": [[0, 0, 0.0, 2, 0, 1, "P0_S0"]],
}


def test_origin_becomes_canonical_with_id():
    result = ingest_save({"sequence": ORIGIN, "overwrite": False}, existing=None, next_id=1)
    assert result.id == 1
    assert result.version == 1
    assert result.name == "saludo"
    assert result.description == "Saludo con el brazo derecho"
    assert result.blocks[0].arduino_id == 2
    assert result.blocks[0].pca == 0
    assert result.blocks[0].nombre == "P0_S0"


def test_raw_seven_tuple_list_description_empty():
    result = ingest_save(
        {"sequence": {"name": "viejo", "blocks": [[0, 0, 0.0, 2, 0, 1, "P0_S0"]]}, "overwrite": False},
        existing=None,
        next_id=3,
    )
    assert result.id == 3
    assert result.description == ""


def test_overwrite_keeps_id_updates_description():
    existing = ingest_save({"sequence": ORIGIN, "overwrite": False}, existing=None, next_id=4)
    updated = dict(ORIGIN)
    updated["description"] = "Otra frase"
    result = ingest_save(
        {"sequence": updated, "overwrite": True},
        existing=existing,
        next_id=99,
    )
    assert result.id == 4
    assert result.description == "Otra frase"


def test_invalid_payload_rejected():
    with pytest.raises((ValueError, ValidationError)):
        ingest_save({"sequence": {"name": "x", "blocks": "no"}, "overwrite": False}, None, 1)


def test_next_id_skips_deleted_and_starts_at_one():
    assert next_sequence_id([]) == 1
    kept = MotionSequenceFile(
        version=1,
        id=4,
        name="saludo",
        description="",
        blocks=[{"arduino_id": 0, "pca": 0, "servo": 0, "inicio": 0, "dur": 2, "pos": 0, "vel": 1, "nombre": "P0_S0"}],
    )
    assert next_sequence_id([kept]) == 5


def test_save_and_list_roundtrip(tmp_path: Path):
    service = SequenceService(data_dir=tmp_path)
    service.save_sequence({"sequence": ORIGIN, "overwrite": False})
    listed = service.list_sequences()
    assert listed.total == 1
    assert listed.data[0].name == "saludo"
    assert listed.data[0].id == 1
    assert listed.data[0].description == "Saludo con el brazo derecho"
    loaded = service.get_sequence("saludo")
    assert loaded.id == 1
    assert loaded.blocks[0].arduino_id == 2


def test_canonical_without_id_lists_but_file_untouched(tmp_path: Path):
    path = tmp_path / "legado.json"
    path.write_text(
        '{"version": 1, "name": "legado", "blocks": ['
        '{"arduino_id": 0, "pca": 0, "servo": 0, "inicio": 0, "dur": 2, "pos": 0, "vel": 1, "nombre": "P0_S0"}'
        "]}",
        encoding="utf-8",
    )
    service = SequenceService(data_dir=tmp_path)
    listed = service.list_sequences()
    assert listed.data[0].name == "legado"
    assert listed.data[0].id is None
    assert listed.data[0].description == ""
    assert '"id"' not in path.read_text(encoding="utf-8")


def test_duplicate_without_overwrite_raises(tmp_path: Path):
    service = SequenceService(data_dir=tmp_path)
    service.save_sequence({"sequence": ORIGIN, "overwrite": False})
    with pytest.raises(ValueError, match="ya existe"):
        service.save_sequence({"sequence": ORIGIN, "overwrite": False})
