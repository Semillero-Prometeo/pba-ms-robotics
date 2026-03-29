from pydantic import BaseModel


class Command(BaseModel):
    id: int
    name: str
    arduino_id: int
