"""Contrato compartilhado dos estilos visuais expostos pelo portal."""

from __future__ import annotations


VISUAL_MODE_NOVA = "NOVA"
VISUAL_MODE_INI = "INI"
VISUAL_MODES = (VISUAL_MODE_NOVA, VISUAL_MODE_INI, 'MOLDE_1', 'MOLDE_2', 'MOLDE_3')


def normalize_visual_mode(value: object) -> str:
    mode = str(value or VISUAL_MODE_NOVA).strip().upper()
    if mode not in VISUAL_MODES:
        raise ValueError(f"modo de desenho invalido: {value!r}")
    return mode


def visual_mode_label(value: object) -> str:
    from scripts.drawing_mode_config import MODE_LABELS
    return MODE_LABELS[normalize_visual_mode(value)]
