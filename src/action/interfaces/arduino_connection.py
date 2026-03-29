import threading
from dataclasses import dataclass

from pydantic import BaseModel
from serial import Serial


@dataclass(slots=True)
class ArduinoConnection:
    arduino_id: int
    port: str
    serial: Serial
    lock: threading.Lock


class ArduinoCommand(BaseModel):
    id: int
    name: str


class ArduinoCommandsEnvelope(BaseModel):
    commands: list[ArduinoCommand]
