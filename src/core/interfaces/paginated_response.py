from pydantic import BaseModel


class PaginatedResponse[T](BaseModel):
    total: int
    data: list[T]


class StatusResponse(BaseModel):
    status: str
    response: str | None = None
