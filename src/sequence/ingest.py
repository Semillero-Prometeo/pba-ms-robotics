from typing import Any

from src.sequence.interfaces.sequence_interface import MotionBlock, MotionSequenceFile

CATEGORIES = (
    "cara",
    "cuello",
    "brazo_derecho",
    "brazo_izquierdo",
    "torso",
    "cadera",
)


def next_sequence_id(existing: list[MotionSequenceFile]) -> int:
    ids = [item.id for item in existing if item.id is not None]
    return (max(ids) if ids else 0) + 1


def blocks_from_raw(blocks_raw: object, file_arduino: int) -> list[MotionBlock]:
    if not isinstance(blocks_raw, list) or not blocks_raw:
        raise ValueError("Formato de secuencia inválido")
    blocks: list[MotionBlock] = []
    for item in blocks_raw:
        if isinstance(item, list) and len(item) == 7:
            pca, servo, inicio, dur, pos, vel, nombre = item
            blocks.append(
                MotionBlock(
                    arduino_id=int(file_arduino),
                    pca=int(pca),
                    servo=int(servo),
                    inicio=float(inicio),
                    dur=float(dur),
                    pos=int(pos),
                    vel=int(vel),
                    nombre=str(nombre),
                )
            )
            continue
        if isinstance(item, dict):
            block = dict(item)
            block.setdefault("arduino_id", file_arduino)
            blocks.append(MotionBlock.model_validate(block))
            continue
        raise ValueError("Formato de secuencia inválido")
    return blocks


def is_complete_pair(sequence: MotionSequenceFile) -> bool:
    return (
        sequence.category in CATEGORIES
        and bool(sequence.blocks)
        and bool(sequence.blocks_neutro)
        and len((sequence.description or "").strip()) >= 10
    )


def ingest_save(
    payload: dict[str, Any],
    existing: MotionSequenceFile | None,
    next_id: int,
) -> MotionSequenceFile:
    raw = payload.get("sequence")
    if not isinstance(raw, dict):
        raise ValueError("Formato de secuencia inválido")
    name = str(raw.get("name") or "").strip()
    if not name:
        raise ValueError("Nombre de secuencia inválido")
    description = raw.get("description", "")
    if description is None:
        description = ""
    if not isinstance(description, str):
        raise ValueError("Descripción inválida")
    description = description.replace("\n", " ").strip()[:280]
    if len(description) < 10:
        raise ValueError("Descripción inválida")
    category = raw.get("category")
    if category not in CATEGORIES:
        raise ValueError("Categoría inválida")
    file_arduino = raw.get("arduino_id", 0)
    if file_arduino is None:
        file_arduino = 0
    blocks = blocks_from_raw(raw.get("blocks"), int(file_arduino))
    try:
        blocks_neutro = blocks_from_raw(raw.get("blocks_neutro"), int(file_arduino))
    except ValueError as exc:
        raise ValueError("Falta la pista neutra") from exc
    assigned_id = existing.id if existing is not None and existing.id is not None else next_id
    return MotionSequenceFile(
        version=int(raw.get("version") or 1),
        id=assigned_id,
        name=name,
        description=description,
        category=category,
        blocks=blocks,
        blocks_neutro=blocks_neutro,
    )
