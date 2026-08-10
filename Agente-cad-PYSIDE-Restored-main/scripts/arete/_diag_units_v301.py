# -*- coding: utf-8 -*-
"""Dump face_units UNIT* panels/h/marco for V301."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent))

from arete.gerar_lv_n4_fichas import _entry_from_live_recorte
from arete.geometry_lv_units import unit_label
from gerar_lv_dxf_stog import (
    _marco_extension_cm,
    _small_panel_start_x,
    select_canonical_face_units,
)


def main():
    entry = _entry_from_live_recorte("V301")
    fus = select_canonical_face_units(entry.get("face_units") or [], "V301")
    for i, u in enumerate(fus):
        lab = unit_label(u, i)
        side = u.get("side")
        panels = u.get("panels") or []
        widths = [round(float(p.get("width", 0) or 0), 1) for p in panels]
        h = float(u.get("h_body") or u.get("h") or 0)
        ls = float(u.get("laje_sup") or 0)
        li = float(u.get("laje_inf") or 0)
        marco = bool(u.get("marco_laje_sup"))
        mh = _marco_extension_cm(marco, ls)
        sx = _small_panel_start_x(0.0, h, panels)
        total = sum(widths)
        print(
            f"[{i}] {lab} side={side} h={h:.1f} laje_sup={ls} laje_inf={li} "
            f"marco={marco} mh={mh:.1f} small_x={sx} full={total:.1f}"
        )
        print(f"     widths={widths}")
        print(
            f"     h+mh={h+mh:.1f} h+ls={h+ls:.1f} h+li+mh={h+li+mh:.1f} "
            f"h+li+ls={h+li+ls:.1f}"
        )


if __name__ == "__main__":
    main()
