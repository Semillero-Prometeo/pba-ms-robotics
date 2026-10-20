from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.voice.phrases.errors import PhraseError
from src.voice.phrases.seed import SEED_ROWS
from src.voice.phrases.store import PhraseStore


def store_at(tmp_path: Path) -> PhraseStore:
    return PhraseStore(tmp_path / "phrases.json")


def test_missing_file_seeds_current_phrases(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    items = store.list_phrases()
    assert len(items) == len(SEED_ROWS)
    assert all(item.active for item in items)
    assert [item.title for item in items] == [row[0] for row in SEED_ROWS]
    assert items[0].id == 1
    assert items[-1].id == len(SEED_ROWS)
    assert items[0].icon == ""
    assert items[1].icon == "menu_book"


def test_empty_items_seeds(tmp_path: Path) -> None:
    path = tmp_path / "phrases.json"
    path.write_text('{"items": []}\n', encoding="utf-8")
    items = PhraseStore(path).list_phrases()
    assert len(items) == len(SEED_ROWS)


def test_second_list_does_not_duplicate(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    first = store.list_phrases()
    second = store.list_phrases()
    assert [item.id for item in first] == [item.id for item in second]
    assert len(second) == len(SEED_ROWS)


def test_create_update_and_set_active_persist(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    store.list_phrases()
    created = store.create("Nueva", "Texto hablado", "star")
    assert created.id == len(SEED_ROWS) + 1
    assert created.active is True
    assert store.list_phrases()[0].id == created.id
    updated = store.update(created.id, {"title": "Editada", "icon": ""})
    assert updated.title == "Editada"
    assert updated.text == "Texto hablado"
    assert updated.icon == ""
    inactive = store.set_active(created.id, False)
    assert inactive.active is False
    again = PhraseStore(tmp_path / "phrases.json").list_phrases()
    found = next(item for item in again if item.id == created.id)
    assert found.title == "Editada"
    assert found.active is False


def test_invalid_title_and_missing_id(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    store.list_phrases()
    with pytest.raises(PhraseError) as empty:
        store.create("  ", "hola")
    assert empty.value.status_code == 400
    with pytest.raises(PhraseError) as missing:
        store.set_active(9999, False)
    assert missing.value.status_code == 404


def test_corrupt_json_does_not_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "phrases.json"
    path.write_text("{nope", encoding="utf-8")
    with pytest.raises(PhraseError) as exc:
        PhraseStore(path).list_phrases()
    assert exc.value.status_code == 500
    assert path.read_text(encoding="utf-8") == "{nope"
