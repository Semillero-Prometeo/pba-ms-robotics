import logging

from src.action.interfaces.command_interface import Command
from src.action.utils.arduino_utils import ArduinoUtils
from src.core.interfaces.paginated_response import ExecuteActionResponse, StatusResponse

logger = logging.getLogger(__name__)


class ActionService:
    def __init__(self) -> None:
        self.arduino_utils = ArduinoUtils()

    def get_actions(self) -> list[Command]:
        return [
            Command(id=1, name="Action 1", arduino_id=1),
            Command(id=2, name="Action 2", arduino_id=1),
            Command(id=3, name="Action 3", arduino_id=1),
            Command(id=4, name="Action 4", arduino_id=1),
            Command(id=5, name="Action 5", arduino_id=1),
            Command(id=6, name="Action 6", arduino_id=1),
            Command(id=7, name="Action 7", arduino_id=1),
            Command(id=8, name="Action 8", arduino_id=1),
            Command(id=9, name="Action 9", arduino_id=1),
            Command(id=10, name="Action 10", arduino_id=1),
            Command(id=11, name="Action 11", arduino_id=1),
            Command(id=12, name="Action 12", arduino_id=1),
            Command(id=13, name="Action 13", arduino_id=1),
            Command(id=14, name="Action 14", arduino_id=1),
            Command(id=15, name="Action 15", arduino_id=1),
            Command(id=16, name="Action 16", arduino_id=1),
        ]
        self.arduino_utils.sync_connections()
        commands: list[Command] = []

        for connection in self.arduino_utils.connections.values():
            commands.extend(self.arduino_utils.get_actions_from_arduino(connection))
            logger.info(f"Commands: {commands}")

        return commands

    def execute_action(self, action_id: int, arduino_id: int) -> ExecuteActionResponse:
        return ExecuteActionResponse(status="ok", response=["Linea 1", "Linea 2"])

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
