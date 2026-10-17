import os
from pathlib import Path

os.environ.setdefault("NATS_SERVER", "nats://localhost:4222")

import pytest
from pydantic import ValidationError

from src.sequence.ingest import ingest_save, is_complete_pair, next_sequence_id
from src.sequence.interfaces.sequence_interface import MotionSequenceFile
from src.sequence.sequence_service import SequenceService


ORIGIN = {
    "name": "saludo",
    "description": "Saludo con el brazo derecho",
    "category": "brazo_derecho",
    "arduino_id": 2,
    "blocks": [[0, 0, 0.0, 2, 850, 5, "P0_S0"]],
    "blocks_neutro": [[0, 0, 0.0, 2, 500, 5, "P0_S0"]],
}


def test_origin_pair_becomes_canonical():
    result = ingest_save({"sequence": ORIGIN, "overwrite": False}, existing=None, next_id=1)
    assert result.id == 1
    assert result.version == 1
    assert result.name == "saludo"
    assert result.description == "Saludo con el brazo derecho"
    assert result.category == "brazo_derecho"
    assert result.blocks[0].arduino_id == 2
    assert result.blocks[0].pca == 0
    assert result.blocks[0].pos == 850
    assert result.blocks[0].nombre == "P0_S0"
    assert result.blocks_neutro[0].pos == 500
    assert result.blocks_neutro[0].arduino_id == 2


def test_ingest_rejects_short_description():
    raw = dict(ORIGIN)
    raw["description"] = "123456789"
    with pytest.raises(ValueError, match="Descripción inválida"):
        ingest_save({"sequence": raw, "overwrite": False}, existing=None, next_id=3)


def test_ingest_accepts_ten_char_description():
    raw = dict(ORIGIN)
    raw["description"] = "1234567890"
    result = ingest_save({"sequence": raw, "overwrite": False}, existing=None, next_id=3)
    assert result.description == "1234567890"


def test_ingest_rejects_missing_category():
    raw = dict(ORIGIN)
    raw.pop("category")
    with pytest.raises(ValueError, match="Categoría inválida"):
        ingest_save({"sequence": raw, "overwrite": False}, None, 1)


def test_ingest_rejects_empty_neutro():
    raw = dict(ORIGIN)
    raw["blocks_neutro"] = []
    with pytest.raises(ValueError, match="Falta la pista neutra"):
        ingest_save({"sequence": raw, "overwrite": False}, None, 1)


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
    assert result.category == "brazo_derecho"


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
    assert listed.data[0].category == "brazo_derecho"
    loaded = service.get_sequence("saludo")
    assert loaded.id == 1
    assert loaded.category == "brazo_derecho"
    assert loaded.blocks[0].arduino_id == 2
    assert loaded.blocks_neutro[0].pos == 500


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


def test_legacy_file_lists_but_not_in_catalog(tmp_path: Path):
    path = tmp_path / "legado.json"
    path.write_text(
        '{"version": 1, "id": 7, "name": "legado", "blocks": ['
        '{"arduino_id": 0, "pca": 0, "servo": 0, "inicio": 0, "dur": 2, "pos": 0, "vel": 1, "nombre": "P0_S0"}'
        "]}",
        encoding="utf-8",
    )
    service = SequenceService(data_dir=tmp_path)
    listed = service.list_sequences()
    assert listed.data[0].id == 7
    assert listed.data[0].category is None
    assert '"category"' not in path.read_text(encoding="utf-8")
    from src.action.action_service import ActionService

    assert ActionService(sequence_service=service).get_actions() == []


def test_short_description_lists_but_not_in_catalog(tmp_path: Path):
    path = tmp_path / "corto.json"
    path.write_text(
        '{"version": 1, "id": 8, "name": "corto", "description": "corta",'
        '"category": "cara", "blocks": ['
        '{"arduino_id": 0, "pca": 0, "servo": 0, "inicio": 0, "dur": 2, "pos": 0, "vel": 1, "nombre": "P0_S0"}'
        '], "blocks_neutro": ['
        '{"arduino_id": 0, "pca": 0, "servo": 0, "inicio": 0, "dur": 2, "pos": 0, "vel": 1, "nombre": "N0"}'
        "]}",
        encoding="utf-8",
    )
    service = SequenceService(data_dir=tmp_path)
    listed = service.list_sequences()
    assert listed.data[0].name == "corto"
    from src.action.action_service import ActionService

    assert ActionService(sequence_service=service).get_actions() == []


def test_duplicate_without_overwrite_raises(tmp_path: Path):
    service = SequenceService(data_dir=tmp_path)
    service.save_sequence({"sequence": ORIGIN, "overwrite": False})
    with pytest.raises(ValueError, match="ya existe"):
        service.save_sequence({"sequence": ORIGIN, "overwrite": False})


def test_ingest_accepts_empty_description():
    raw = dict(ORIGIN)
    raw["description"] = ""
    result = ingest_save({"sequence": raw, "overwrite": False}, existing=None, next_id=11)
    assert result.id == 11
    assert result.description == ""
    assert is_complete_pair(result) is False


def test_ingest_five_char_description_rejected():
    raw = dict(ORIGIN)
    raw["description"] = "corta"
    with pytest.raises(ValueError, match="Descripción inválida"):
        ingest_save({"sequence": raw, "overwrite": False}, existing=None, next_id=12)
