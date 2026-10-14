import logging

from src.action.interfaces.command_interface import Command
from src.action.utils.arduino_utils import get_arduino_utils
from src.core.interfaces.paginated_response import ExecuteActionResponse
from src.sequence.ingest import is_complete_pair
from src.sequence.sequence_service import SequenceService

logger = logging.getLogger(__name__)


class ActionService:
    def __init__(self, sequence_service: SequenceService | None = None) -> None:
        self.arduino_utils = get_arduino_utils()
        self.sequence_service = sequence_service or SequenceService()

    def get_actions(self) -> list[Command]:
        commands = self.sequence_service.as_commands()
        if not commands:
            logger.info("Catálogo de movimientos vacío: no hay secuencias con id.")
        return commands

    def execute_action(self, action_id: int, arduino_id: int) -> ExecuteActionResponse:
        sequence = self.sequence_service.find_by_id(action_id)
        if sequence is not None:
            if not is_complete_pair(sequence):
                logger.warning("Secuencia %s incompleta; se omite", action_id)
                return ExecuteActionResponse(status="ok", response=["omitido"])
            status = self.sequence_service.enqueue_turn_pair(sequence)
            return ExecuteActionResponse(
                status=status.status,
                response=[status.message] if status.message else ["secuencia"],
            )

        self.arduino_utils.sync_connections()
        connection = self.arduino_utils.connections.get(arduino_id)

        if connection is None:
            raise ValueError(f"Arduino con id {arduino_id} no encontrado")

        payload = f"{action_id}\n".encode("ascii")
        logger.info(f"Payload: {payload}")

        with connection.lock:
            connection.serial.reset_output_buffer()
            connection.serial.write(payload)
            connection.serial.flush()
            response: list[str] = self.arduino_utils.json_reader.read_first_meaningful_line(
                connection.serial, timeout_seconds=2.0
            )
            logger.info(f"Response: {response}")

            self.arduino_utils.drain_serial(connection.serial)

        return ExecuteActionResponse(status="ok", response=response)
