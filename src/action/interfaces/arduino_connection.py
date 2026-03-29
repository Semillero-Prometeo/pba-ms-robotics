import threading

from pydantic import BaseModel
from serial import Serial


class ArduinoConnection(BaseModel):
    arduino_id: int
    port: str
    serial: Serial
    lock: threading.Lock


class ArduinoCommand(BaseModel):
    id: int
    name: str


class ArduinoCommandsEnvelope(BaseModel):
    commands: list[ArduinoCommand]
