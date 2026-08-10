#!/usr/bin/env python
"""Corrige p_s{face}_l1_n/l2_n persistidos sem contato geometrico real com a laje.

Achado real (2026-07-16, P35/13_PAV, via PilEvidenceAuditor): o pipeline de
pre-ficha so escrevia p_s{face}_l1_n quando o motor geometrico
(pillar_face_beams) confirmava laje na face (content_type in laje/both). Faces
100% ocupadas por viga (content_type='viga', sem laje geometrica) ficavam sem
protecao e caiam na busca textual cega por raio do PillarAnalyzer
(_analyze_field, radius=800), que podia gravar o nome de uma laje distante
sem nenhum contato fisico real (P35 face D -> "L325" a 556cm). Esse gap ja
foi fechado no pipeline (main.py + src/core/pillar_analyzer.py); este script
corrige os registros ja persistidos no DB que carregam o valor antigo.

Regra: para cada p_s{face}_l1_n/l2_n com nome de laje real (nao
SEM LAJE/Vazio (X)/vazio), calcula a distancia Shapely real entre o poligono
do pilar e o poligono da laje nomeada. Se a laje nao existir no projeto ou a
distancia exceder --tol (default 15cm), substitui por "SEM LAJE" com
evidencia marcada como fix geometrico. Campos ja validados por humano
(validated_fields_json) sao preservados.

Uso:
  py -3.12 scripts/arete/fix_pil_l1n_no_slab_contact.py \\
    --project-id dd238e47-1dc6-4f63-a760-4e7ce19a7386 \\
    --db D:/Agente-cad-PYSIDE/project_data.vision \\
    --apply
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shapely.geometry import Polygon  # noqa: E402

EMPTY_TXT = {"", "SEM LAJE", "VAZIO (X)", "N/A", "N.A.", "NULO", "NONE", "—"}


def _extract_text(val) -> str:
    if isinstance(val, dict):
        lab = val.get("label") or []
        if isinstance(lab, list) and lab and isinstance(lab[0], dict):
            return str(lab[0].get("text") or "").strip()
        return ""
    if isinstance(val, str):
        return val.strip()
    return ""


def _blocked_field(face: str, field: str, validated: set) -> bool:
    flat = f"p_s{face}_{field}"
    return field in validated or flat in validated


def _load_slabs(conn: sqlite3.Connection, project_id: str) -> dict:
    slabs = {}
    for name, pj in conn.execute(
        "SELECT name, points_json FROM slabs WHERE project_id=?", (project_id,)
    ):
        try:
            pts = json.loads(pj or "[]")
            if len(pts) < 3:
                continue
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            slabs[name] = poly
        except Exception:
            continue
    return slabs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--db", default=str(ROOT.parent / "project_data.vision"))
    ap.add_argument("--tol", type=float, default=15.0, help="Tolerancia de contato em cm")
    ap.add_argument("--apply", action="store_true", help="Grava no DB (sem flag = dry-run)")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.is_file():
        print(f"DB nao encontrado: {db}", flush=True)
        return 2

    conn = sqlite3.connect(str(db))
    try:
        slabs = _load_slabs(conn, args.project_id)
        print(f"[fix_l1n] lajes carregadas: {len(slabs)}", flush=True)

        rows = conn.execute(
            "SELECT id, name, points_json, sides_data_json, links_json, "
            "validated_fields_json FROM pillars WHERE project_id=?",
            (args.project_id,),
        ).fetchall()
        print(f"[fix_l1n] pilares={len(rows)} apply={args.apply} tol={args.tol}cm", flush=True)

        n_fixed = 0
        report = []
        for pid, name, pj, sj, lj, vj in rows:
            try:
                pts = json.loads(pj or "[]")
                if len(pts) < 3:
                    continue
                poly = Polygon(pts)
                if not poly.is_valid:
                    poly = poly.buffer(0)
            except Exception:
                continue

            sides = json.loads(sj or "{}")
            links = json.loads(lj or "{}")
            validated = set(json.loads(vj or "[]") or [])

            changed = False
            for face in "ABCD":
                for slot in ("l1_n", "l2_n"):
                    key = f"p_s{face}_{slot}"
                    txt = _extract_text(links.get(key))
                    if not txt:
                        face_sd = sides.get(face) or {}
                        txt = str(face_sd.get(slot) or "").strip()
                    if not txt or txt.upper() in EMPTY_TXT:
                        continue
                    if _blocked_field(face, slot, validated) or key in validated:
                        continue

                    slab_poly = slabs.get(txt)
                    if slab_poly is None:
                        reason = f"laje '{txt}' nao encontrada no projeto"
                        dist = None
                    else:
                        try:
                            dist = poly.distance(slab_poly)
                        except Exception:
                            continue
                        if dist <= args.tol:
                            continue
                        reason = f"dist={dist:.1f}cm > tol={args.tol}cm"

                    report.append((name, face, slot, txt, reason))
                    links[key] = {
                        "label": [{
                            "type": "text",
                            "text": "SEM LAJE",
                            "role": "Sem contato geometrico real com laje (corrigido)",
                            "source": "qa_geometric_fix_2026-07-16",
                            "previous_value": txt,
                            "previous_reason": reason,
                        }]
                    }
                    face_sd = sides.setdefault(face, {})
                    if isinstance(face_sd, dict):
                        face_sd[slot] = "SEM LAJE"
                        h_key, v_key = f"{slot[:2]}_h", f"{slot[:2]}_v"
                        if not _blocked_field(face, h_key, validated):
                            face_sd.pop(h_key, None)
                        if not _blocked_field(face, v_key, validated):
                            face_sd.pop(v_key, None)
                    changed = True

            if changed:
                n_fixed += 1
                if args.apply:
                    conn.execute(
                        "UPDATE pillars SET sides_data_json=?, links_json=? WHERE id=?",
                        (
                            json.dumps(sides, ensure_ascii=False),
                            json.dumps(links, ensure_ascii=False),
                            pid,
                        ),
                    )

        for name, face, slot, txt, reason in report:
            print(f"  {name} face {face} {slot}: '{txt}' -> SEM LAJE ({reason})", flush=True)

        if args.apply:
            conn.commit()
            print(f"[fix_l1n] COMMIT: {n_fixed} pilar(es) corrigido(s)", flush=True)
        else:
            print(f"[fix_l1n] DRY-RUN: {n_fixed} pilar(es) seriam corrigidos", flush=True)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
