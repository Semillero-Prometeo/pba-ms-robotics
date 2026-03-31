from datetime import datetime
from typing import Any

from src.core.interfaces.health import Health
from src.core.settings.env import ROBOTICS_MS


class AppController:
    async def health(self, _: dict[str, Any]) -> Health:
        return Health(
            status="UP", timestamp=datetime.now().isoformat(), msName=ROBOTICS_MS
        )
