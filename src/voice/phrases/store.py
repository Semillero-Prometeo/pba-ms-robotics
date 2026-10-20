from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from src.voice.phrases.errors import PhraseError
from src.voice.phrases.models import Phrase
from src.voice.phrases.seed import SEED_ROWS

_ICON_RE = re.compile(r"^[a-z0-9_]+$")
_TITLE_MAX = 80
_TEXT_MAX = 2000


class PhraseStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(os.getenv("PHRASES_PATH", "/usr/src/app/data/phrases.json"))

    def list_phrases(self) -> list[Phrase]:
        return self._load()

    def create(self, title: str, text: str, icon: str = "") -> Phrase:
        items = self._load()
        next_id = max((item.id for item in items), default=0) + 1
        phrase = Phrase(
            id=next_id,
            title=self._clean_title(title),
            text=self._clean_text(text),
            icon=self._clean_icon(icon),
            active=True,
        )
        items.append(phrase)
        self._write(items)
        return phrase

    def update(self, phrase_id: int, patch: dict[str, str | None]) -> Phrase:
        items = self._load()
        phrase = self._find(items, phrase_id)
        if "title" in patch and patch["title"] is not None:
            phrase.title = self._clean_title(patch["title"])
        if "text" in patch and patch["text"] is not None:
            phrase.text = self._clean_text(patch["text"])
        if "icon" in patch:
            phrase.icon = self._clean_icon(patch["icon"] or "")
        self._write(items)
        return phrase

    def set_active(self, phrase_id: int, active: bool) -> Phrase:
        items = self._load()
        phrase = self._find(items, phrase_id)
        phrase.active = active
        self._write(items)
        return phrase

    def _load(self) -> list[Phrase]:
        if not self.path.exists():
            return self._seed()
        raw = self.path.read_text(encoding="utf-8")
        try:
            parsed: Any = json.loads(raw)
            items_raw = parsed["items"]
            items = [Phrase.model_validate(item) for item in items_raw]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise PhraseError("Catálogo de frases corrupto", status_code=500) from exc
        if not items:
            return self._seed()
        return items

    def _seed(self) -> list[Phrase]:
        items = [
            Phrase(id=index, title=title, text=text, icon=icon, active=True)
            for index, (title, text, icon) in enumerate(SEED_ROWS, start=1)
        ]
        self._write(items)
        return items

    def _write(self, items: list[Phrase]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"items": [item.model_dump() for item in items]}, ensure_ascii=False, indent=2)
        fd, tmp_name = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.write("\n")
            os.replace(tmp_name, self.path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def _find(self, items: list[Phrase], phrase_id: int) -> Phrase:
        for item in items:
            if item.id == phrase_id:
                return item
        raise PhraseError(f"Frase {phrase_id} no encontrada", status_code=404)

    def _clean_title(self, value: str) -> str:
        title = value.strip()
        if not title or len(title) > _TITLE_MAX:
            raise PhraseError("Título inválido", status_code=400)
        return title

    def _clean_text(self, value: str) -> str:
        text = value.strip()
        if not text or len(text) > _TEXT_MAX:
            raise PhraseError("Texto inválido", status_code=400)
        return text

    def _clean_icon(self, value: str) -> str:
        icon = value.strip()
        if icon and _ICON_RE.fullmatch(icon) is None:
            raise PhraseError("Ícono inválido", status_code=400)
        return icon
