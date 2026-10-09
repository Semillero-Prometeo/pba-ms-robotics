from pydantic import BaseModel, Field


class Command(BaseModel):
    id: int
    name: str
    arduino_id: int
    description: str = Field(default="")
