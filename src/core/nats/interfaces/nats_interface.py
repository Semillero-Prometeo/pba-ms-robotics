from collections.abc import Callable

from pydantic import BaseModel


class NatsSubscriber(BaseModel):
    controller: Callable
    subject: str
