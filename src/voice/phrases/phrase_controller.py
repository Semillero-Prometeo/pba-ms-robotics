from __future__ import annotations

from typing import Any

from src.voice.phrases.models import PhraseCreate, PhraseSetActive, PhraseUpdate
from src.voice.phrases.store import PhraseStore


class PhraseController:
    def __init__(self, store: PhraseStore | None = None) -> None:
        self._store = store or PhraseStore()

    async def list_phrases(self, _: dict[str, Any]) -> dict[str, Any]:
        return {"items": [item.model_dump() for item in self._store.list_phrases()]}

    async def create_phrase(self, data: dict[str, Any]) -> dict[str, Any]:
        payload = PhraseCreate.model_validate(data)
        return self._store.create(payload.title, payload.text, payload.icon or "").model_dump()

    async def update_phrase(self, data: dict[str, Any]) -> dict[str, Any]:
        payload = PhraseUpdate.model_validate(data)
        patch: dict[str, str | None] = {}
        if "title" in payload.model_fields_set:
            patch["title"] = payload.title
        if "text" in payload.model_fields_set:
            patch["text"] = payload.text
        if "icon" in payload.model_fields_set:
            patch["icon"] = payload.icon
        return self._store.update(payload.id, patch).model_dump()

    async def set_active(self, data: dict[str, Any]) -> dict[str, Any]:
        payload = PhraseSetActive.model_validate(data)
        return self._store.set_active(payload.id, payload.active).model_dump()
