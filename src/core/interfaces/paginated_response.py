from pydantic import BaseModel


class PaginatedResponse[T](BaseModel):
    total: int
    data: list[T]
