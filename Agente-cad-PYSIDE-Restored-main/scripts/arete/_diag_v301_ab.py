# -*- coding: utf-8 -*-
"""Diagnóstico rápido V301 A/B — face_units, N4 bands, cotas inventadas."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import ezdxf

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

from arete.geometry_lv_units import split_n4_view  # noqa: E402
from arete.gerar_lv_n4_fichas import _entry_from_live_recorte  # noqa: E402
from gerar_lv_dxf_stog import select_canonical_face_units  # noqa: E402

DB = Path(r"D:\Agente-cad-PYSIDE\project_data.vision")
N4_DIR = Path(
    r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1"
    r"\Fase-6_Execucao_CAD\n4"
)


def main() -> None:
    conn = sqlite3.connect(str(DB))
    row = conn.execute(
        "SELECT recorte_path FROM reverse_eng_recortes "
        "WHERE UPPER(elemento_id)=? AND UPPER(classe)='LV' "
        "ORDER BY id DESC LIMIT 1",
        ("V301",),
    ).fetchone()
    conn.close()
    n2 = Path(row[0])
    print("N2", n2)
    entry = _entry_from_live_recorte("V301")
    if not entry:
        print("ENTRY FAIL")
        return
    fus = entry.get("face_units") or []
    print("face_units raw", len(fus))
    for i, u in enumerate(fus):
        segs = u.get("segments") or u.get("panels") or []
        ws = [float(s.get("largura_cm", s.get("width", 0)) or 0) for s in segs]
        bb = u.get("bbox") or {}
        print(
            f"  [{i}] side={u.get('side')} label={u.get('label')!r} "
            f"h={u.get('h_body') or u.get('h')} w={ws[:14]} "
            f"bbox={bb} marco={u.get('marco_laje_sup')} laje_sup={u.get('laje_sup')}"
        )

    canon = select_canonical_face_units(fus, viga_nome="V301")
    print("CANON", len(canon))
    for u in canon:
        segs = u.get("segments") or u.get("panels") or []
        ws = [float(s.get("largura_cm", s.get("width", 0)) or 0) for s in segs]
        bb = u.get("bbox") or {}
        print(
            f"  side={u.get('side')} label={u.get('label')!r} "
            f"h={u.get('h_body') or u.get('h')} w={ws} "
            f"bbox={bb} marco={u.get('marco_laje_sup')} laje={u.get('laje_sup')} "
            f"deg={u.get('has_degrau')}"
        )

    for side in ("A", "B"):
        n4 = N4_DIR / f"LV_preview_V301_VIEW_{side}.dxf"
        if not n4.exists():
            print("MISSING", n4)
            continue
        units = split_n4_view(n4, side)
        print(f"N4 {side} bands", len(units))
        for u in units:
            print(
                f"  lab={u['label']!r} origin={u['origin']} "
                f"h={u['h_body']:.1f} body_end={u.get('body_end_x')} "
                f"w={u.get('widths')}"
            )
        # cotas MTEXT/DIMENSION values near origin of first matching V301 label
        doc = ezdxf.readfile(str(n4))
        msp = doc.modelspace()
        dims = []
        for e in msp:
            if e.dxftype() == "DIMENSION":
                try:
                    txt = (e.dxf.get("text") or "").strip()
                    m = float(e.dxf.actual_measurement)
                    ins = e.dxf.defpoint
                    dims.append((round(m, 2), txt, round(ins.x, 1), round(ins.y, 1)))
                except Exception:
                    pass
            elif e.dxftype() in ("TEXT", "MTEXT"):
                t = (e.dxf.text if e.dxftype() == "TEXT" else e.text).strip()
                # numeric-ish
                t2 = t.replace(",", ".").replace(" ", "")
                try:
                    v = float(t2)
                except Exception:
                    continue
                ins = e.dxf.insert
                dims.append((round(v, 2), t, round(ins.x, 1), round(ins.y, 1)))
        dims.sort(key=lambda x: (x[2], x[0]))
        # highlight invented suspects
        suspects = {117.5, 174.0, 116.0, 124.0, 20.5, 307.0, 58.5, 98.5, 142.0}
        print(f"N4 {side} dim-like count", len(dims))
        inv = [d for d in dims if d[0] in suspects or abs(d[0] - 117.5) < 0.2]
        print("  suspects", inv[:40])
        # unique measurement values
        vals = sorted({d[0] for d in dims})
        print("  unique vals", vals[:60])


if __name__ == "__main__":
    main()
