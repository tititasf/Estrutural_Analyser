#!/usr/bin/env python
"""Diagnóstico de evidência dura p/ Camada 2 (looping agêntico PIL ABCD).

Não decide, não redesenha. Cruza ``face_beams`` (o que o motor já classificou)
com os contornos REAIS dos segmentos de cada viga citada (``beams.data_json
.links.viga_fundo_seg_N_area_segs.contour``) e aponta faces/cantos do pilar
onde há toque geométrico (segmento cuja largura bate com a face) sem entrada
correspondente em ``face_beams`` — assimetria de builder, candidato a Ag.L2.

Método completo: docs/LOOPING-AGENTICO-INTERPRETACAO-PILARES-ABCD.md §3.1
Caso de referência: P16 (INSIGHTS-QA-L1.md §8 do pack 13_PAV_20260804_..._pilares_abcd)

Uso:
  py -3.12 scripts/arete/pil_l2_evidence_check.py \\
    --pack scripts/arete/html_fichas/Obra_TREINO_1/13_PAV_..._pilares_abcd \\
    --items P9 P12 P15 P18 ...
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TOL = 3.0  # cm — tolerância p/ considerar "bate com a face"

# Convenção INTERPRETACAO-PILARES-ABCD.md (mesma de pil_agentic_highlight_draw.py):
#   vertical:   A=oeste(x0)  B=leste(x1)  C=norte(y1)  D=sul(y0)
#   horizontal: A=sul(y0)    B=norte(y1)  C=oeste(x0)  D=leste(x1)
# "orientação" aqui = a mesma heurística de pil_agentic_highlight_draw.load_project:
# vertical se altura(y) > largura(x), senão horizontal.


def _beam_contours(data: dict) -> list[dict]:
    out = []
    links = data.get("links") or {}
    for k, v in links.items():
        if not k.endswith("_area_segs") or not isinstance(v, dict):
            continue
        for seg in v.get("contour") or []:
            pts = seg.get("points") or []
            if len(pts) < 4:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            out.append({
                "field": k, "tag": seg.get("tag"),
                "x0": min(xs), "x1": max(xs), "y0": min(ys), "y1": max(ys),
            })
    return out


def _is_horizontal(px0: float, py0: float, px1: float, py1: float) -> bool:
    return (py1 - py0) <= (px1 - px0)


def _full_span_faces(
    seg: dict, px0: float, py0: float, px1: float, py1: float, *, horizontal: bool
) -> dict[str, tuple[str, str]]:
    """Faces onde o contorno da viga ENCOSTA na face inteira (ponta a ponta) e é
    ADJACENTE ao pilar naquela direção (não precisa sobrepor as outras faces —
    um segmento encostado de um lado implica os 2 cantos daquele lado mesmo sem
    cruzar as faces perpendiculares).

    Retorna {face: (corner_esq, corner_dir)} — os 2 cantos que esse encosto implica,
    já na convenção certa (vertical ou horizontal, INTERPRETACAO-PILARES-ABCD.md).
    """
    out: dict[str, tuple[str, str]] = {}
    full_width = seg["x0"] <= px0 + TOL and seg["x1"] >= px1 - TOL   # cobre x0..x1
    full_height = seg["y0"] <= py0 + TOL and seg["y1"] >= py1 - TOL  # cobre y0..y1
    touches_south = abs(seg["y1"] - py0) < TOL or (seg["y0"] < py0 - TOL < seg["y1"])
    touches_north = abs(seg["y0"] - py1) < TOL or (seg["y0"] < py1 - TOL < seg["y1"])
    touches_west = abs(seg["x1"] - px0) < TOL or (seg["x0"] < px0 - TOL < seg["x1"])
    touches_east = abs(seg["x0"] - px1) < TOL or (seg["x0"] < px1 - TOL < seg["x1"])

    if not horizontal:
        # A=oeste B=leste C=norte D=sul
        if full_width and touches_south:
            out["D"] = ("AD", "BD")
        if full_width and touches_north:
            out["C"] = ("AC", "BC")
        if full_height and touches_west:
            out["A"] = ("AC", "AD")
        if full_height and touches_east:
            out["B"] = ("BC", "BD")
    else:
        # A=sul B=norte C=oeste D=leste
        if full_width and touches_south:
            out["A"] = ("AC", "AD")
        if full_width and touches_north:
            out["B"] = ("BC", "BD")
        if full_height and touches_west:
            out["C"] = ("AC", "BC")
        if full_height and touches_east:
            out["D"] = ("AD", "BD")
    return out


def _existing_corners(face_beams: dict) -> set[str]:
    """Cantos com viga REGISTRADA (não os rótulos estruturais corner_esq/corner_dir,
    que existem sempre, com ou sem viga — não são evidência)."""
    out = set()
    for fid, fb in (face_beams or {}).items():
        for slot in ("passa_esq", "passa_dir"):
            e = fb.get(slot)
            if e and e.get("name") and e.get("corner"):
                out.add(e["corner"].upper())
        for e in fb.get("para") or []:
            if e.get("name") and e.get("corner"):
                out.add(e["corner"].upper())
    return out


def check_item(conn: sqlite3.Connection, project_id: str, name: str) -> dict:
    row = conn.execute(
        "SELECT points_json, extra_data_json FROM pillars WHERE project_id=? AND name=?",
        (project_id, name),
    ).fetchone()
    if not row:
        return {"item": name, "error": "pilar não encontrado"}
    pts = json.loads(row[0] or "[]")
    extra = json.loads(row[1] or "{}") if row[1] else {}
    face_beams = extra.get("face_beams") or {}
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    px0, py0, px1, py1 = min(xs), min(ys), max(xs), max(ys)

    beam_names = set()
    for fb in face_beams.values():
        for slot in ("passa_esq", "passa_dir"):
            e = fb.get(slot)
            if e and e.get("name"):
                beam_names.add(e["name"])
        for e in fb.get("para") or []:
            if e.get("name"):
                beam_names.add(e["name"])
        for e in fb.get("interior") or []:
            if e.get("name"):
                beam_names.add(e["name"])

    existing_corners = _existing_corners(face_beams)
    horizontal = _is_horizontal(px0, py0, px1, py1)

    findings = []
    for bname in sorted(beam_names):
        brow = conn.execute(
            "SELECT data_json FROM beams WHERE project_id=? AND name=?",
            (project_id, bname),
        ).fetchone()
        if not brow:
            continue
        bdata = json.loads(brow[0] or "{}")
        for seg in _beam_contours(bdata):
            spans = _full_span_faces(seg, px0, py0, px1, py1, horizontal=horizontal)
            if not spans:
                continue
            for face, corners in spans.items():
                missing = [
                    c for c in corners
                    if c not in existing_corners and c[::-1] not in existing_corners
                ]
                if missing:
                    findings.append({
                        "beam": bname, "field": seg["field"], "full_span_face": face,
                        "implied_corners": list(corners), "missing_corners": missing,
                        "contour_bbox": [seg["x0"], seg["y0"], seg["x1"], seg["y1"]],
                    })

    return {
        "item": name,
        "bbox": [px0, py0, px1, py1],
        "orientation": "horizontal" if horizontal else "vertical",
        "beam_names_in_face_beams": sorted(beam_names),
        "existing_corners_recorded": sorted(existing_corners),
        "findings": findings,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT.parent / "project_data.vision"))
    ap.add_argument("--project-id", default="dd238e47-1dc6-4f63-a760-4e7ce19a7386")
    ap.add_argument("--pack", required=False)
    ap.add_argument("--items", nargs="+", required=True)
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    results = []
    for name in args.items:
        r = check_item(conn, args.project_id, name.upper())
        results.append(r)
        n = len(r.get("findings") or [])
        flag = f"{n} achado(s)" if n else "sem achado geométrico"
        print(f"{name:5s} {flag}")
        for f in r.get("findings") or []:
            print(f"      {f['beam']} encosta full-span em {f['full_span_face']} "
                  f"→ implica {f['implied_corners']}, faltam {f['missing_corners']} "
                  f"(bbox {[round(v,1) for v in f['contour_bbox']]})")

    if args.pack:
        out = Path(args.pack) / "propostas" / "l2_evidence_report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] relatório → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
