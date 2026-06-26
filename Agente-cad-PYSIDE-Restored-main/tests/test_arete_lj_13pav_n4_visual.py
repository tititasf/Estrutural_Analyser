# -*- coding: utf-8 -*-
"""ARETE LAJ 13_PAV: valida N2 humano x N4 oficial.

Este teste verifica os DXFs N4 publicados em:
DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/n4

Tambem gera PNGs lado a lado para inspeção visual manual em:
D:/Agente-cad-PYSIDE/test_output/arete_lj/pytest_13_PAV
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from arete_lj_batch_13pav import (  # noqa: E402
    DADOS,
    OBRA_NAME,
    abs_outline_bbox,
    close_bbox,
    db_items,
    make_contact_sheet,
    preferred_recorte,
    text_summary,
)
from arete_lj_canonico import canonical, diff, render_side_by_side  # noqa: E402
from motor_reverso_laj import extrair_ficha_laje  # noqa: E402


OUT_DIR = Path("D:/Agente-cad-PYSIDE/test_output/arete_lj/pytest_13_PAV")


def test_arete_lj_13pav_n2_vs_n4_official_visual():
    obra_dir = DADOS / OBRA_NAME
    n4_dir = obra_dir / "Fase-6_Execucao_CAD" / "n4"
    png_dir = OUT_DIR / "png"
    png_dir.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    pngs: list[Path] = []

    for row in db_items():
        eid = row["id"]
        recorte = preferred_recorte(eid, row.get("db_recorte"))
        n4 = n4_dir / f"LJ_preview_{eid}.dxf"

        if not recorte or not recorte.exists():
            failures.append(f"{eid}: recorte N2 ausente")
            continue
        if not n4.exists():
            failures.append(f"{eid}: N4 oficial ausente em {n4}")
            continue

        ref_fc = canonical(recorte)
        n4_fc = canonical(n4)
        d = diff(ref_fc, n4_fc)

        ref_ficha = extrair_ficha_laje(str(recorte), eid, OBRA_NAME)
        n4_ficha = extrair_ficha_laje(str(n4), eid, OBRA_NAME)
        ref_bbox = abs_outline_bbox(ref_ficha)
        n4_bbox = abs_outline_bbox(n4_ficha)
        marco_ok = close_bbox(ref_bbox, n4_bbox)

        summary = text_summary(n4)
        png = png_dir / f"ARETE_LJ_{eid}.png"
        render_side_by_side(recorte, n4, png)
        if png.exists():
            pngs.append(png)

        if not d["pass"]:
            failures.append(f"{eid}: conteudo FAIL {d['diffs']}")
        if not marco_ok:
            failures.append(f"{eid}: marco FAIL ref={ref_bbox} n4={n4_bbox}")
        if summary["has_aux00"] or summary["has_c_equals"]:
            failures.append(f"{eid}: cruft no N4 texts={summary['texts']}")

    make_contact_sheet(pngs, OUT_DIR / "ARETE_LJ_13PAV_pytest_contact_sheet.png")
    assert not failures, "\n".join(failures)
