import json
from pathlib import Path

from src.action.interfaces.command_interface import Command


def load_descriptions(path: Path) -> dict[tuple[int, int], str]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    if not isinstance(raw, list):
        return {}
    found: dict[tuple[int, int], str] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        try:
            key = (int(row["arduino_id"]), int(row["id"]))
        except (KeyError, TypeError, ValueError):
            continue
        text = row.get("description", "")
        found[key] = text if isinstance(text, str) else ""
    return found


def apply_descriptions(
    commands: list[Command],
    descriptions: dict[tuple[int, int], str],
) -> list[Command]:
    return [
        command.model_copy(
            update={"description": descriptions.get((command.arduino_id, command.id), "")}
        )
        for command in commands
    ]
