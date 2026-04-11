"""Normaliza texto con markdown y saltos de línea para síntesis de voz (párrafo continuo)."""

from __future__ import annotations

import re


def _strip_inline_markdown(fragment: str) -> str:
    """Quita markdown inline de un fragmento ya sin prefijos de lista."""
    s = fragment
    s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"__([^_]+)__", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"_([^_]+)_", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s


def format_text_for_speech(text: str) -> str:
    """
    Convierte respuestas tipo Markdown en texto plano fluido: quita negritas, listas,
    enlaces y colapsa saltos de línea en espacios para que el TTS suene como un párrafo.
    """
    if not text or not text.strip():
        return ""

    s = text.strip()

    # Bloques de código multilínea
    s = re.sub(r"```[\s\S]*?```", " ", s)

    parts: list[str] = []
    for raw_line in s.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Cabecera al inicio de línea
        line = re.sub(r"^#{1,6}\s*", "", line)
        # Viñetas
        line = re.sub(r"^[-*]\s+", "", line)
        # "1. texto" o "12. texto"
        line = re.sub(r"^\d+\.\s+", "", line)
        line = _strip_inline_markdown(line)
        parts.append(line)

    s = " ".join(parts)

    # Asteriscos o guiones bajos residuales (markdown mal balanceado)
    s = s.replace("*", "").replace("_", "")

    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([.,;:!?])", r"\1", s)
    return s.strip()
