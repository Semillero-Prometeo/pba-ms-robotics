import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from src.action.interfaces.arduino_connection import ArduinoConnection
from src.action.interfaces.command_interface import Command
from src.action.utils.arduino_utils import get_arduino_utils
from src.core.settings.env import SEQUENCES_DATA_DIR
from src.sequence.ingest import CATEGORIES, blocks_from_raw, ingest_save, is_complete_pair, next_sequence_id
from src.sequence.interfaces.sequence_interface import (
    MotionBlock,
    MotionSequenceFile,
    PcaScanResponse,
    SequenceArduino,
    SequenceChainItem,
    SequenceChainStatusResponse,
    SequenceFileInfo,
    SequenceListResponse,
    SequenceStatusResponse,
)

logger = logging.getLogger(__name__)


class SequenceService:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.arduino_utils = get_arduino_utils()
        self.data_dir = Path(data_dir) if data_dir is not None else Path(SEQUENCES_DATA_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._playback_stop_event: threading.Event | None = None
        self._playback_thread: threading.Thread | None = None
        self._playback_state_lock = threading.Lock()
        self._chain_stop_event: threading.Event | None = None
        self._chain_thread: threading.Thread | None = None
        self._chain_state_lock = threading.Lock()
        self._chain_current_sequence: str | None = None
        self._chain_completed_items = 0
        self._chain_total_items = 0

    def list_arduinos(self) -> list[SequenceArduino]:
        self.arduino_utils.sync_connections()
        result: list[SequenceArduino] = []

        for connection in self.arduino_utils.connections.values():
            metadata = self.arduino_utils.get_port_metadata(connection.port)
            fingerprint = metadata.serial_number or metadata.hwid
            result.append(
                SequenceArduino(
                    arduino_id=connection.arduino_id,
                    port=connection.port,
                    hardware_fingerprint=fingerprint,
                )
            )

        return sorted(result, key=lambda item: item.arduino_id)

    def scan_pcas(self, arduino_id: int) -> PcaScanResponse:
        self.arduino_utils.sync_connections()
        connection = self.arduino_utils.connections.get(arduino_id)
        if connection is None:
            raise ValueError(f"Arduino con id {arduino_id} no encontrado")

        with connection.lock:
            connection.serial.reset_input_buffer()
            connection.serial.write(b"SCAN\n")
            connection.serial.flush()
            pcas = self._read_pcas_line(connection)
            self.arduino_utils.drain_serial(connection.serial)

        return PcaScanResponse(arduino_id=arduino_id, pcas=pcas)

    def list_sequences(self) -> SequenceListResponse:
        sequences: list[SequenceFileInfo] = []
        for file_path in sorted(self.data_dir.rglob("*.json")):
            relative_path = file_path.relative_to(self.data_dir)
            sequence_name = relative_path.with_suffix("").as_posix()
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            parsed = self._parse_sequence_payload(name=sequence_name, payload=payload)
            sequences.append(
                SequenceFileInfo(
                    name=sequence_name,
                    file_name=relative_path.as_posix(),
                    id=parsed.id,
                    description=parsed.description,
                    category=parsed.category,
                )
            )
        return SequenceListResponse(total=len(sequences), data=sequences)

    def get_sequence(self, name: str) -> MotionSequenceFile:
        file_path = self._resolve_sequence_path(name)
        if not file_path.exists():
            raise ValueError(f"Secuencia '{name}' no encontrada")

        payload = json.loads(file_path.read_text(encoding="utf-8"))
        return self._parse_sequence_payload(name=name, payload=payload)

    def save_sequence(
        self,
        payload: dict[str, Any] | MotionSequenceFile,
        overwrite: bool | None = None,
    ) -> SequenceStatusResponse:
        if isinstance(payload, MotionSequenceFile):
            envelope: dict[str, Any] = {
                "sequence": payload.model_dump(),
                "overwrite": overwrite or False,
            }
        else:
            envelope = dict(payload)
            if overwrite is not None:
                envelope["overwrite"] = overwrite

        raw = envelope.get("sequence")
        if not isinstance(raw, dict):
            raise ValueError("Formato de secuencia inválido")
        name = str(raw.get("name") or "").strip()
        overwrite_flag = bool(envelope.get("overwrite", False))
        file_path = self._resolve_sequence_path(name)
        existing: MotionSequenceFile | None = None
        if file_path.exists():
            if not overwrite_flag:
                raise ValueError(
                    f"La secuencia '{name}' ya existe. Use overwrite=true para reemplazar."
                )
            existing = self.get_sequence(name)

        all_files: list[MotionSequenceFile] = []
        for info in self.list_sequences().data:
            if overwrite_flag and info.name == name:
                continue
            all_files.append(self.get_sequence(info.name))

        canonical = ingest_save(envelope, existing, next_sequence_id(all_files))
        file_path = self._resolve_sequence_path(canonical.name)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(canonical.model_dump_json(indent=2), encoding="utf-8")
        return SequenceStatusResponse(status="ok", message="Secuencia guardada")

    def as_commands(self) -> list[Command]:
        commands: list[Command] = []
        for info in self.list_sequences().data:
            sequence = self.get_sequence(info.name)
            if sequence.id is None or not is_complete_pair(sequence):
                continue
            commands.append(
                Command(
                    id=sequence.id,
                    name=sequence.name,
                    arduino_id=sequence.blocks[0].arduino_id,
                    description=sequence.description,
                )
            )
        return commands

    def find_by_id(self, action_id: int) -> MotionSequenceFile | None:
        for info in self.list_sequences().data:
            sequence = self.get_sequence(info.name)
            if sequence.id == action_id:
                return sequence
        return None

    def delete_sequence(self, name: str) -> SequenceStatusResponse:
        file_path = self._resolve_sequence_path(name)
        if not file_path.exists():
            raise ValueError(f"Secuencia '{name}' no encontrada")

        file_path.unlink()
        return SequenceStatusResponse(status="ok", message="Secuencia eliminada")

    def start_playback(self, blocks: list[MotionBlock]) -> SequenceStatusResponse:
        with self._playback_state_lock:
            if self._playback_thread is not None and self._playback_thread.is_alive():
                raise ValueError("Ya existe una secuencia en ejecución")

            self.arduino_utils.sync_connections()
            self._ensure_connections(blocks)

            stop_event = threading.Event()
            playback_thread = threading.Thread(
                target=self._run_playback,
                args=(blocks, stop_event),
                name="sequence-playback",
                daemon=True,
            )

            self._playback_stop_event = stop_event
            self._playback_thread = playback_thread
            playback_thread.start()

        return SequenceStatusResponse(status="ok", message="Secuencia iniciada")

    def stop_playback(self) -> SequenceStatusResponse:
        with self._playback_state_lock:
            stop_event = self._playback_stop_event
            thread = self._playback_thread
            self._playback_stop_event = None
            self._playback_thread = None

        if stop_event is None or thread is None:
            return SequenceStatusResponse(status="ok", message="No había secuencia en ejecución")

        stop_event.set()
        thread.join(timeout=2.0)
        return SequenceStatusResponse(status="ok", message="Secuencia detenida")

    def start_chain(self, items: list[SequenceChainItem]) -> SequenceStatusResponse:
        if not items:
            raise ValueError("La cadena de secuencias no puede estar vacía")

        with self._chain_state_lock:
            if self._chain_thread is not None and self._chain_thread.is_alive():
                raise ValueError("Ya existe una cadena en ejecución")

            stop_event = threading.Event()
            chain_thread = threading.Thread(
                target=self._run_chain,
                args=(items, stop_event),
                name="sequence-chain-playback",
                daemon=True,
            )
            self._chain_stop_event = stop_event
            self._chain_thread = chain_thread
            self._chain_current_sequence = None
            self._chain_completed_items = 0
            self._chain_total_items = sum(item.repeat for item in items)
            chain_thread.start()

        return SequenceStatusResponse(status="ok", message="Cadena iniciada")

    def stop_chain(self) -> SequenceStatusResponse:
        with self._chain_state_lock:
            stop_event = self._chain_stop_event
            thread = self._chain_thread
            self._chain_stop_event = None
            self._chain_thread = None
            self._chain_current_sequence = None

        if stop_event is None or thread is None:
            return SequenceStatusResponse(status="ok", message="No había cadena en ejecución")

        stop_event.set()
        self.stop_playback()
        thread.join(timeout=2.0)
        return SequenceStatusResponse(status="ok", message="Cadena detenida")

    def chain_status(self) -> SequenceChainStatusResponse:
        with self._chain_state_lock:
            running = self._chain_thread is not None and self._chain_thread.is_alive()
            return SequenceChainStatusResponse(
                status="ok",
                running=running,
                current_sequence=self._chain_current_sequence,
                completed_items=self._chain_completed_items,
                total_items=self._chain_total_items,
            )

    def _read_pcas_line(self, connection: ArduinoConnection) -> list[int]:
        deadline = time.monotonic() + 2.0
        buffer = ""

        while time.monotonic() < deadline:
            available = connection.serial.in_waiting
            if available <= 0:
                time.sleep(0.01)
                continue

            buffer += connection.serial.read(available).decode("utf-8", errors="ignore")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if line.startswith("PCAS:"):
                    csv_values = line[5:]
                    if not csv_values:
                        return []
                    return [int(item) for item in csv_values.split(",") if item.strip().isdigit()]

        raise ValueError("No se recibió respuesta de PCAS desde el Arduino")

    def _parse_sequence_payload(self, name: str, payload: object) -> MotionSequenceFile:
        if isinstance(payload, list):
            return MotionSequenceFile(name=name, blocks=blocks_from_raw(payload, 0), id=None)
        if isinstance(payload, dict):
            blocks = payload.get("blocks")
            if isinstance(blocks, list) and blocks and isinstance(blocks[0], list):
                return self._parse_origin_dict(name, payload)
            enriched = dict(payload)
            enriched.setdefault("name", name)
            return MotionSequenceFile.model_validate(enriched)
        raise ValueError("Formato de secuencia inválido")

    def _parse_origin_dict(self, name: str, payload: dict[str, Any]) -> MotionSequenceFile:
        enriched = dict(payload)
        enriched.setdefault("name", name)
        file_arduino = enriched.get("arduino_id", 0)
        if file_arduino is None:
            file_arduino = 0
        category = enriched.get("category")
        if category not in CATEGORIES:
            category = None
        blocks = blocks_from_raw(enriched.get("blocks"), int(file_arduino))
        blocks_neutro: list[MotionBlock] = []
        neutro_raw = enriched.get("blocks_neutro")
        if isinstance(neutro_raw, list) and neutro_raw:
            try:
                blocks_neutro = blocks_from_raw(neutro_raw, int(file_arduino))
            except ValueError:
                blocks_neutro = []
        assigned_id = enriched.get("id")
        if assigned_id is not None:
            assigned_id = int(assigned_id)
        description = enriched.get("description", "")
        if not isinstance(description, str):
            description = ""
        return MotionSequenceFile(
            version=int(enriched.get("version") or 1),
            id=assigned_id,
            name=str(enriched.get("name") or name).strip() or name,
            description=description.replace("\n", " ")[:280],
            category=category,
            blocks=blocks,
            blocks_neutro=blocks_neutro,
        )

    def _resolve_sequence_path(self, name: str) -> Path:
        safe_relative_path = self._safe_relative_sequence_name(name)
        return self.data_dir / safe_relative_path

    def _safe_relative_sequence_name(self, name: str) -> Path:
        normalized = name.replace("\\", "/").strip("/")
        if not normalized:
            raise ValueError("Nombre de secuencia inválido")

        safe_parts: list[str] = []
        for part in normalized.split("/"):
            stripped = part.strip()
            if not stripped or stripped in {".", ".."}:
                raise ValueError("Nombre de secuencia inválido")
            safe_part = "".join(
                ch if ch.isalnum() or ch in {"_", "-"} else "-" for ch in stripped
            ).strip("-")
            if not safe_part:
                raise ValueError("Nombre de secuencia inválido")
            safe_parts.append(safe_part)

        relative_path = Path(*safe_parts)
        return relative_path.with_suffix(".json")

    def _ensure_connections(self, blocks: list[MotionBlock]) -> None:
        available_ids = set(self.arduino_utils.connections.keys())
        required_ids = {block.arduino_id for block in blocks}
        missing = sorted(required_ids - available_ids)
        if missing:
            raise ValueError(f"Arduinos no conectados para la secuencia: {missing}")

    def _run_playback(self, blocks: list[MotionBlock], stop_event: threading.Event) -> None:
        start_time = time.monotonic()
        pending = sorted(blocks, key=lambda item: item.inicio)
        fired_indexes: set[int] = set()

        try:
            while not stop_event.is_set() and len(fired_indexes) < len(pending):
                elapsed = time.monotonic() - start_time
                for index, block in enumerate(pending):
                    if index in fired_indexes or elapsed < block.inicio:
                        continue
                    self._send_block_command(block)
                    fired_indexes.add(index)
                time.sleep(0.01)
        finally:
            with self._playback_state_lock:
                if self._playback_thread is threading.current_thread():
                    self._playback_thread = None
                    self._playback_stop_event = None

    def _run_chain(self, items: list[SequenceChainItem], stop_event: threading.Event) -> None:
        try:
            for item in items:
                for _ in range(item.repeat):
                    if stop_event.is_set():
                        return

                    sequence = self.get_sequence(item.name)
                    with self._chain_state_lock:
                        self._chain_current_sequence = item.name

                    self.start_playback(sequence.blocks)
                    self._wait_for_playback(stop_event)
                    if stop_event.is_set():
                        return

                    with self._chain_state_lock:
                        self._chain_completed_items += 1

                    if item.delay_ms > 0:
                        self._sleep_with_stop(item.delay_ms / 1000, stop_event)
                        if stop_event.is_set():
                            return
        finally:
            with self._chain_state_lock:
                if self._chain_thread is threading.current_thread():
                    self._chain_thread = None
                    self._chain_stop_event = None
                    self._chain_current_sequence = None

    def _wait_for_playback(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            with self._playback_state_lock:
                running = self._playback_thread is not None and self._playback_thread.is_alive()
            if not running:
                return
            time.sleep(0.05)

    def _sleep_with_stop(self, seconds: float, stop_event: threading.Event) -> None:
        deadline = time.monotonic() + seconds
        while not stop_event.is_set() and time.monotonic() < deadline:
            time.sleep(0.05)

    def _send_block_command(self, block: MotionBlock) -> None:
        connection = self.arduino_utils.connections.get(block.arduino_id)
        if connection is None:
            logger.warning("Arduino %s desconectado durante playback", block.arduino_id)
            return

        payload = f"PCA,{block.pca},{block.servo},{block.pos},{block.vel}\n"
        print(payload)
        with connection.lock:
            connection.serial.write(payload.encode("ascii"))
            connection.serial.flush()
