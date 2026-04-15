from typing import Any

from pydantic import BaseModel, ConfigDict

from src.sequence.interfaces.sequence_interface import (
    PcaScanPayload,
    SaveSequencePayload,
    SequenceByNamePayload,
    SequencePlaybackPayload,
    SequenceStatusResponse,
)
from src.sequence.sequence_service import SequenceService


class StopSequencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SequenceController:
    def __init__(self) -> None:
        self.sequence_service = SequenceService()

    async def list_arduinos(self, _: dict[str, Any]) -> list[dict[str, Any]]:
        arduino_list = self.sequence_service.list_arduinos()
        return [item.model_dump() for item in arduino_list]

    async def scan_pcas(self, data: PcaScanPayload) -> dict[str, Any]:
        payload = PcaScanPayload.model_validate(data)
        return self.sequence_service.scan_pcas(payload.arduino_id).model_dump()

    async def list_sequences(self, _: dict[str, Any]) -> dict[str, Any]:
        return self.sequence_service.list_sequences().model_dump()

    async def get_sequence(self, data: SequenceByNamePayload) -> dict[str, Any]:
        payload = SequenceByNamePayload.model_validate(data)
        return self.sequence_service.get_sequence(payload.name).model_dump()

    async def save_sequence(self, data: SaveSequencePayload) -> SequenceStatusResponse:
        payload = SaveSequencePayload.model_validate(data)
        return self.sequence_service.save_sequence(payload.sequence, payload.overwrite)

    async def delete_sequence(self, data: SequenceByNamePayload) -> SequenceStatusResponse:
        payload = SequenceByNamePayload.model_validate(data)
        return self.sequence_service.delete_sequence(payload.name)

    async def start_playback(self, data: SequencePlaybackPayload) -> SequenceStatusResponse:
        payload = SequencePlaybackPayload.model_validate(data)
        return self.sequence_service.start_playback(payload.blocks)

    async def stop_playback(self, data: StopSequencePayload) -> SequenceStatusResponse:
        _ = StopSequencePayload.model_validate(data)
        return self.sequence_service.stop_playback()
