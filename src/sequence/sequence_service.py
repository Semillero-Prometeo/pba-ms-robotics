import json
import logging
import threading
import time
from pathlib import Path

from src.action.interfaces.arduino_connection import ArduinoConnection
from src.action.utils.arduino_utils import get_arduino_utils
from src.core.settings.env import SEQUENCES_DATA_DIR
from src.sequence.interfaces.sequence_interface import (
    MotionBlock,
    MotionSequenceFile,
    PcaScanResponse,
    SequenceArduino,
    SequenceFileInfo,
    SequenceListResponse,
    SequenceStatusResponse,
)

logger = logging.getLogger(__name__)


class SequenceService:
    def __init__(self) -> None:
        self.arduino_utils = get_arduino_utils()
        self.data_dir = Path(SEQUENCES_DATA_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._playback_stop_event: threading.Event | None = None
        self._playback_thread: threading.Thread | None = None
        self._playback_state_lock = threading.Lock()

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
        for file_path in sorted(self.data_dir.glob("*.json")):
            sequences.append(
                SequenceFileInfo(name=file_path.stem, file_name=file_path.name)
            )
        return SequenceListResponse(total=len(sequences), data=sequences)

    def get_sequence(self, name: str) -> MotionSequenceFile:
        file_path = self._resolve_sequence_path(name)
        if not file_path.exists():
            raise ValueError(f"Secuencia '{name}' no encontrada")

        payload = json.loads(file_path.read_text(encoding="utf-8"))
        return self._parse_sequence_payload(name=name, payload=payload)

    def save_sequence(self, sequence: MotionSequenceFile, overwrite: bool) -> SequenceStatusResponse:
        file_path = self._resolve_sequence_path(sequence.name)
        if file_path.exists() and not overwrite:
            raise ValueError(
                f"La secuencia '{sequence.name}' ya existe. Use overwrite=true para reemplazar."
            )

        file_path.write_text(sequence.model_dump_json(indent=2), encoding="utf-8")
        return SequenceStatusResponse(status="ok", message="Secuencia guardada")

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
            return MotionSequenceFile(name=name, blocks=payload)
        if isinstance(payload, dict):
            enriched = dict(payload)
            enriched.setdefault("name", name)
            return MotionSequenceFile.model_validate(enriched)
        raise ValueError("Formato de secuencia inválido")

    def _resolve_sequence_path(self, name: str) -> Path:
        safe_name = self._safe_name(name)
        return self.data_dir / f"{safe_name}.json"

    def _safe_name(self, name: str) -> str:
        return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "-" for ch in name).strip("-")

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

    def _send_block_command(self, block: MotionBlock) -> None:
        connection = self.arduino_utils.connections.get(block.arduino_id)
        if connection is None:
            logger.warning("Arduino %s desconectado durante playback", block.arduino_id)
            return

        payload = f"PCA,{block.pca},{block.servo},{block.pos},{block.vel}\n".encode("ascii")
        with connection.lock:
            connection.serial.write(payload)
            connection.serial.flush()
