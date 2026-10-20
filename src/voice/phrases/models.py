from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Phrase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    text: str
    icon: str = ""
    active: bool = True


class PhraseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    text: str
    icon: str | None = None


class PhraseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str | None = None
    text: str | None = None
    icon: str | None = None


class PhraseSetActive(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    active: bool
