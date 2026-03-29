import logging
import time

from serial import Serial

from src.action.constants.action_constant import JSON_BEGIN_MARKER, JSON_END_MARKER

logger = logging.getLogger(__name__)


class JsonReaderUtil:
    def __init__(self) -> None:
        self.json_data: str = ""

    def read_json_payload(self, serial_conn: Serial, timeout_seconds: float) -> str:
        start = time.monotonic()
        inside_json = False
        lines: list[str] = []

        while time.monotonic() - start < timeout_seconds:
            raw_line = serial_conn.readline()
            if not raw_line:
                continue

            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            if line == JSON_BEGIN_MARKER:
                inside_json = True
                lines.clear()
                continue

            if line == JSON_END_MARKER and inside_json:
                return "".join(lines)

            if inside_json:
                lines.append(line)

        raise TimeoutError("No se recibió JSON de acciones desde el Arduino")

    def read_first_meaningful_line(self, serial_conn: Serial, timeout_seconds: float) -> str:
        start = time.monotonic()
        while time.monotonic() - start < timeout_seconds:
            raw_line = serial_conn.readline()
            if not raw_line:
                continue
            text = raw_line.decode("utf-8", errors="ignore").strip()
            if text:
                return text

        logger.warning("No hubo respuesta del Arduino tras ejecutar acción")
        return ""
