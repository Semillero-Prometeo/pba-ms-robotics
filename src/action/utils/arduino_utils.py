import threading
import time

from serial import Serial
from serial.tools import list_ports

from src.action.constants.action_constant import (
    ARDUINO_BAUDRATE,
    DISCOVERY_BOOT_WAIT_SECONDS,
    LIST_ACTIONS_COMMAND,
    SERIAL_TIMEOUT_SECONDS,
)
from src.action.interfaces.arduino_connection import ArduinoCommandsEnvelope, ArduinoConnection
from src.action.interfaces.command_interface import Command
from src.action.utils.json_reader import JsonReaderUtil


class ArduinoUtils:
    def __init__(self) -> None:
        self.connections: dict[int, ArduinoConnection] = {}
        self.port_index: dict[str, int] = {}
        self.state_lock = threading.Lock()
        self.json_reader = JsonReaderUtil()

    def sync_connections(self) -> None:
        candidate_ports = self.list_candidate_ports()

        with self.state_lock:
            existing_ports = set(self.port_index.keys())
            incoming_ports = set(candidate_ports)

            for removed_port in existing_ports - incoming_ports:
                removed_id = self.port_index.pop(removed_port)
                removed_connection = self.connections.pop(removed_id, None)
                if removed_connection is not None:
                    removed_connection.serial.close()

            for port in candidate_ports:
                if port in self.port_index:
                    continue

                arduino_id = self.next_arduino_id()

                serial_conn = Serial(
                    port=port,
                    baudrate=ARDUINO_BAUDRATE,
                    timeout=SERIAL_TIMEOUT_SECONDS,
                    write_timeout=SERIAL_TIMEOUT_SECONDS,
                )

                time.sleep(DISCOVERY_BOOT_WAIT_SECONDS)
                self.drain_serial(serial_conn)

                self.port_index[port] = arduino_id
                self.connections[arduino_id] = ArduinoConnection(
                    arduino_id=arduino_id,
                    port=port,
                    serial=serial_conn,
                    lock=threading.Lock(),
                )

    def get_actions_from_arduino(self, connection: ArduinoConnection) -> list[Command]:
        with connection.lock:
            connection.serial.write(f"{LIST_ACTIONS_COMMAND}\n".encode("ascii"))
            connection.serial.flush()
            payload = self.json_reader.read_json_payload(connection.serial, timeout_seconds=2.5)

        parsed = ArduinoCommandsEnvelope.model_validate_json(payload)
        return [
            Command(id=cmd.id, name=cmd.name, arduino_id=connection.arduino_id)
            for cmd in parsed.commands
        ]

    def list_candidate_ports(self) -> list[str]:
        ports = sorted(port.device for port in list_ports.comports())
        return [
            port
            for port in ports
            if port.startswith("/dev/ttyACM") or port.startswith("/dev/ttyUSB")
        ]

    def next_arduino_id(self) -> int:
        if not self.connections:
            return 0
        return max(self.connections.keys()) + 1

    def drain_serial(self, serial_conn: Serial) -> None:
        serial_conn.reset_input_buffer()
        serial_conn.reset_output_buffer()
