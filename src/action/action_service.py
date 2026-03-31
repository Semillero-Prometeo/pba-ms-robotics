import logging

from src.action.interfaces.command_interface import Command
from src.action.utils.arduino_utils import ArduinoUtils

logger = logging.getLogger(__name__)


class ActionService:
    def __init__(self) -> None:
        self.arduino_utils = ArduinoUtils()

    def get_actions(self) -> list[Command]:
        self.arduino_utils.sync_connections()
        commands: list[Command] = []

        for connection in self.arduino_utils.connections.values():
            commands.extend(self.arduino_utils.get_actions_from_arduino(connection))
            logger.info(f"Commands: {commands}")

        return commands

    def execute_action(self, action_id: int, arduino_id: int) -> str:
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
            response = self.arduino_utils.json_reader.read_first_meaningful_line(
                connection.serial, timeout_seconds=2.0
            )
            logger.info(f"Response: {response}")

        return response
