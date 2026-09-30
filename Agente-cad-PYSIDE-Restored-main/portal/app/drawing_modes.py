"""Contrato compartilhado dos estilos visuais expostos pelo portal."""

from __future__ import annotations


VISUAL_MODE_NOVA = "NOVA"
VISUAL_MODE_INI = "INI"
VISUAL_MODES = (VISUAL_MODE_NOVA, VISUAL_MODE_INI)


def normalize_visual_mode(value: object) -> str:
    mode = str(value or VISUAL_MODE_NOVA).strip().upper()
    if mode not in VISUAL_MODES:
        raise ValueError(f"modo de desenho invalido: {value!r}")
    return mode


def visual_mode_label(value: object) -> str:
    return "Ini" if normalize_visual_mode(value) == VISUAL_MODE_INI else "Nova"
