import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

SAFE_FILE_RE = re.compile(r"[^a-zA-Z0-9_-]+")


class SequenceArduino(BaseModel):
    arduino_id: int
    port: str
    hardware_fingerprint: str | None = None


class MotionBlock(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    arduino_id: int
    pca: int = Field(ge=0, le=10)
    servo: int = Field(ge=0, le=15)
    inicio: float = Field(ge=0)
    dur: float = Field(gt=0)
    pos: int = Field(ge=0, le=1000)
    vel: int = Field(ge=1, le=10)
    nombre: str = Field(min_length=1, max_length=80)

    @model_validator(mode="before")
    @classmethod
    def legacy_block_compat(cls, value: Any) -> Any:
        if isinstance(value, list) and len(value) == 7:
            pca, servo, inicio, dur, pos, vel, nombre = value
            return {
                "arduino_id": 0,
                "pca": pca,
                "servo": servo,
                "inicio": inicio,
                "dur": dur,
                "pos": pos,
                "vel": vel,
                "nombre": nombre,
            }
        return value


class MotionSequenceFile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: int = Field(default=1, ge=1)
    name: str = Field(min_length=1, max_length=80)
    blocks: list[MotionBlock]

    @model_validator(mode="after")
    def validate_name(self) -> "MotionSequenceFile":
        safe_name = SAFE_FILE_RE.sub("-", self.name).strip("-")
        if not safe_name:
            raise ValueError("Nombre de secuencia inválido")
        return self


class SaveSequencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    sequence: MotionSequenceFile
    overwrite: bool = False


class SequenceByNamePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str


class SequencePlaybackPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: list[MotionBlock]


class SequenceFileInfo(BaseModel):
    name: str
    file_name: str


class SequenceListResponse(BaseModel):
    total: int
    data: list[SequenceFileInfo]


class PcaScanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    arduino_id: int


class PcaScanResponse(BaseModel):
    arduino_id: int
    pcas: list[int]


class SequenceStatusResponse(BaseModel):
    status: str
    message: str | None = None


class SequenceChainItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str
    repeat: int = Field(default=1, ge=1, le=20)
    delay_ms: int = Field(default=0, ge=0, le=30000)


class SequenceChainStartPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[SequenceChainItem]


class SequenceChainStatusResponse(BaseModel):
    status: str
    running: bool
    current_sequence: str | None = None
    completed_items: int = 0
    total_items: int = 0
