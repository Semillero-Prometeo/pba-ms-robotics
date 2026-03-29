from typing import Any

from pydantic import BaseModel

from src.action.action_service import ActionService
from src.action.interfaces.command_interface import Command
from src.core.interfaces.paginated_response import PaginatedResponse


class ExecuteActionPayload(BaseModel):
    action_id: int
    arduino_id: int


class ActionController:
    def __init__(self) -> None:
        self.action_service = ActionService()

    async def get_actions(self, _: dict[str, Any]) -> PaginatedResponse[Command]:
        commands: list[Command] = self.action_service.get_actions()

        return PaginatedResponse[Command](total=len(commands), data=commands)

    async def execute_action(self, data: ExecuteActionPayload) -> dict[str, str]:
        payload: ExecuteActionPayload = ExecuteActionPayload.model_validate(data)

        response: str = self.action_service.execute_action(
            action_id=payload.action_id,
            arduino_id=payload.arduino_id,
        )

        return {"status": "ok", "response": response or ""}
