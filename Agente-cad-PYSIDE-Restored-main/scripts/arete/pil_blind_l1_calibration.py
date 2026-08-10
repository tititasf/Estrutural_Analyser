#!/usr/bin/env python
"""Calibração cega do agente QA (Camada 1): roda checagens 100% derivadas de
``docs/INTERPRETACAO-PILARES-ABCD.md`` + evidência geométrica dura sobre a
tabela SA atual — SEM ler nenhuma nota humana antes de formar o veredito —
e só DEPOIS compara com o que o humano concluiu no ciclo de revisão.

v2 (2026-08-07) — checagens ampliadas após 1ª calibração (16/31 = 52%):
  1. ``analyze_verdict`` (heurística já existente no motor: dualidade AC/CA,
     BC/CB; banda de topo; C multi-seg; etc.)
  2. papel duplicado: mesmo (viga, canto) em DUAS famílias na mesma face.
  3. evidência geométrica de canto: contorno encosta numa face inteira sem
     canto correspondente registrado.
  4. NOVO — vínculo com gap grande: viga ligada como "passa" numa face mas o
     contorno real está a mais de ``GAP_TOL`` cm da parede — vínculo suspeito.
  5. NOVO — candidato melhor: existe outra viga cujo contorno encosta bem
     mais perto da mesma face do que a que está linkada.
  6. NOVO — face vazia com rótulo órfão: face sem nenhuma família preenchida,
     mas há texto de dimensão (padrão ``NN/NNN``) no DXF perto dela — viga
     não extraída/vinculada.
  7. NOVO — pilar não retangular: polígono tem mais de 4 cantos reais (após
     remover pontos colineares) → candidato a pilar em L (6+ faces).

Uso:
  py -3.12 scripts/arete/pil_blind_l1_calibration.py --items P13 P14 ... --reveal
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.arete.pil_agentic_highlight_draw import load_project, analyze_verdict  # noqa: E402
from scripts.arete.pil_l2_evidence_check import (  # noqa: E402
    _beam_contours, _full_span_faces, _existing_corners, _is_horizontal,
)
from src.core.pillar_abcd_tables import build_abcd_tables_from_pillar  # noqa: E402
from src.core.niveis_extractor import get_pavimento_niveis_abs  # noqa: E402

GAP_TOL = 10.0  # cm — acima disso, vínculo "passa" é suspeito
BETTER_MARGIN = 5.0  # cm — outra viga precisa ser pelo menos isso mais perto p/ contar
DIM_RE = re.compile(r"\b\d{1,2}\s*/\s*\d{2,3}\b")


def check_duplicate_role(tables: dict) -> list[str]:
    issues = []
    faces = (tables or {}).get("faces") or {}
    for fid, face in faces.items():
        seen = {}
        for kind in ("lajes", "passa", "chega", "interior"):
            for r in face.get(kind) or []:
                nome = (r.get("nome") or "").strip()
                if nome in ("", "—", "nenhuma"):
                    continue
                canto = (r.get("canto") or "").strip()
                key = (nome, canto)
                if key in seen and seen[key] != kind:
                    issues.append(
                        f"{fid}: {nome}@{canto} aparece como '{seen[key]}' E '{kind}' "
                        "na mesma face (papel duplicado/conflitante)"
                    )
                else:
                    seen[key] = kind
    return issues


def check_geometry(beams_by_name, px0, py0, px1, py1, face_beams) -> list[str]:
    issues = []
    horizontal = _is_horizontal(px0, py0, px1, py1)
    existing_corners = _existing_corners(face_beams)
    beam_names = _all_named_beams(face_beams)
    for bname in beam_names:
        bdata = beams_by_name.get(bname)
        if not bdata:
            continue
        for seg in _beam_contours(bdata):
            spans = _full_span_faces(seg, px0, py0, px1, py1, horizontal=horizontal)
            for face, corners in spans.items():
                missing = [c for c in corners if c not in existing_corners and c[::-1] not in existing_corners]
                if missing:
                    issues.append(f"{bname} encosta full-span em {face} → faltam cantos {missing}")
    return issues


def _all_named_beams(face_beams: dict) -> set[str]:
    beam_names = set()
    for fb in (face_beams or {}).values():
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
    return beam_names


def _face_wall(fid, px0, py0, px1, py1, horizontal):
    if not horizontal:
        table = {"A": ("x", px0, py0, py1), "B": ("x", px1, py0, py1),
                 "C": ("y", py1, px0, px1), "D": ("y", py0, px0, px1)}
    else:
        table = {"A": ("y", py0, px0, px1), "B": ("y", py1, px0, px1),
                 "C": ("x", px0, py0, py1), "D": ("x", px1, py0, py1)}
    return table[fid]


def _gap_to_face(seg, fid, px0, py0, px1, py1, horizontal) -> float | None:
    axis, coord, s0, s1 = _face_wall(fid, px0, py0, px1, py1, horizontal)
    if axis == "x":
        if seg["y1"] < s0 - 1 or seg["y0"] > s1 + 1:
            return None
        return min(abs(seg["x0"] - coord), abs(seg["x1"] - coord))
    if seg["x1"] < s0 - 1 or seg["x0"] > s1 + 1:
        return None
    return min(abs(seg["y0"] - coord), abs(seg["y1"] - coord))


def _min_gap(bdata: dict, fid: str, px0, py0, px1, py1, horizontal) -> float | None:
    best = None
    for seg in _beam_contours(bdata):
        g = _gap_to_face(seg, fid, px0, py0, px1, py1, horizontal)
        if g is not None and (best is None or g < best):
            best = g
    return best


def check_link_gaps(beams_by_name, px0, py0, px1, py1, face_beams) -> tuple[list[str], list[str]]:
    """Retorna (gap_suspeito, candidato_melhor)."""
    horizontal = _is_horizontal(px0, py0, px1, py1)
    gap_issues = []
    better_issues = []
    for fid, fb in (face_beams or {}).items():
        for slot in ("passa_esq", "passa_dir"):
            e = fb.get(slot)
            if not e or not e.get("name"):
                continue
            bdata = beams_by_name.get(e["name"])
            if not bdata:
                continue
            g = _min_gap(bdata, fid, px0, py0, px1, py1, horizontal)
            if g is not None and g > GAP_TOL:
                gap_issues.append(f"{fid}.{slot}: {e['name']} linkado como passa mas gap real ~{g:.0f}cm (>{GAP_TOL:.0f})")
            # candidato melhor
            best_alt = None
            for oname, odata in beams_by_name.items():
                if oname == e["name"]:
                    continue
                og = _min_gap(odata, fid, px0, py0, px1, py1, horizontal)
                if og is not None and (best_alt is None or og < best_alt[1]):
                    best_alt = (oname, og)
            if best_alt and g is not None and best_alt[1] + BETTER_MARGIN < g:
                better_issues.append(
                    f"{fid}.{slot}: {best_alt[0]} encaixa melhor (gap ~{best_alt[1]:.0f}cm) que "
                    f"{e['name']} atual (gap ~{g:.0f}cm)"
                )
    return gap_issues, better_issues


def check_orphan_label(msp, name_face_beams, px0, py0, px1, py1, window=70.0) -> list[str]:
    issues = []
    horizontal = _is_horizontal(px0, py0, px1, py1)
    faces = {"A", "B", "C", "D"}
    filled = set()
    for fid, fb in (name_face_beams or {}).items():
        has_any = any(fb.get(s) for s in ("passa_esq", "passa_dir")) or fb.get("para") or fb.get("interior")
        if has_any:
            filled.add(fid)
    empty_faces = faces - filled
    if not empty_faces:
        return issues
    for fid in empty_faces:
        axis, coord, s0, s1 = _face_wall(fid, px0, py0, px1, py1, horizontal)
        if axis == "x":
            x0, x1 = (coord - window, coord) if coord <= px0 + 1 else (coord, coord + window)
            y0, y1 = s0 - 20, s1 + 20
        else:
            y0, y1 = (coord - window, coord) if coord <= py0 + 1 else (coord, coord + window)
            x0, x1 = s0 - 20, s1 + 20
        hits = []
        for e in msp:
            t = e.dxftype()
            if t not in ("TEXT", "MTEXT"):
                continue
            try:
                p = e.dxf.insert
                txt = e.dxf.text if t == "TEXT" else e.text
            except Exception:
                continue
            if not (x0 <= p.x <= x1 and y0 <= p.y <= y1):
                continue
            if DIM_RE.search(txt or ""):
                hits.append(txt.strip())
        if hits:
            issues.append(f"{fid}: face vazia mas há rótulo(s) de dimensão próximo(s): {hits[:3]}")
    return issues


def check_pillar_shape(points: list) -> list[str]:
    if len(points) < 3:
        return []
    pts = points[:-1] if points[0] == points[-1] else points[:]
    simplified = []
    n = len(pts)
    for i in range(n):
        a = pts[i - 1]
        b = pts[i]
        c = pts[(i + 1) % n]
        v1 = (b[0] - a[0], b[1] - a[1])
        v2 = (c[0] - b[0], c[1] - b[1])
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        if abs(cross) > 1e-3:
            simplified.append(b)
    if len(simplified) > 4:
        return [f"pilar com {len(simplified)} cantos reais (não-retangular) — candidato a formato L (6+ faces)"]
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", default="dd238e47-1dc6-4f63-a760-4e7ce19a7386")
    ap.add_argument("--db", default=str(ROOT.parent / "project_data.vision"))
    ap.add_argument("--obra", default="Obra_TREINO_1")
    ap.add_argument("--pav", default="13_PAV")
    ap.add_argument("--port", type=int, default=18765)
    ap.add_argument("--items", nargs="+", required=True)
    ap.add_argument("--reveal", action="store_true", help="mostra comparação com nota humana")
    ap.add_argument("--no-dxf-scan", action="store_true", help="pula check 6 (mais lento, abre DXF)")
    args = ap.parse_args()

    dxf_path, slab_h, slab_n, slab_pts, beams, pillars = load_project(
        Path(args.db), args.project_id, args.obra, args.pav
    )
    pillars_by_name = {p["name"]: p for p in pillars}
    beams_by_name = {b.get("name"): b for b in beams}
    niveis = get_pavimento_niveis_abs(args.obra, args.pav) or {"chegada_abs": 852.19}
    nivel_v = f"{niveis.get('chegada_abs')}cm"

    msp = None
    if not args.no_dxf_scan:
        import ezdxf
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

    predictions = {}
    for name in args.items:
        p = pillars_by_name.get(name)
        if not p:
            print(f"{name:5s} [ERR] não encontrado")
            continue
        tables = build_abcd_tables_from_pillar(
            p, slab_height_map=slab_h, slab_nivel_map=slab_n, slab_points_map=slab_pts,
            beams=beams, nivel_viga_default=nivel_v,
        )
        v1, txt1 = analyze_verdict(name, tables, p)
        xs = [pt[0] for pt in p["points"]]
        ys = [pt[1] for pt in p["points"]]
        px0, py0, px1, py1 = min(xs), min(ys), max(xs), max(ys)
        face_beams = p.get("face_beams") or {}

        dup_issues = check_duplicate_role(tables)
        geo_issues = check_geometry(beams_by_name, px0, py0, px1, py1, face_beams)
        gap_issues, better_issues = check_link_gaps(beams_by_name, px0, py0, px1, py1, face_beams)
        shape_issues = check_pillar_shape(p["points"])
        orphan_issues = check_orphan_label(msp, face_beams, px0, py0, px1, py1) if msp is not None else []

        all_issues = (
            ([] if v1 == "validou" else [l.strip("- ") for l in txt1.split("\n") if l.startswith("- ")])
            + dup_issues + geo_issues + gap_issues + better_issues + shape_issues + orphan_issues
        )
        pred_verdict = "invalidou" if all_issues else "validou"
        predictions[name] = {"verdict": pred_verdict, "issues": all_issues}
        print(f"{name:5s} PREDITO={pred_verdict}")
        for it in all_issues:
            print(f"      - {it}")

    if args.reveal:
        print("\n" + "=" * 70)
        print("COMPARAÇÃO COM O HUMANO (revelado agora)")
        print("=" * 70)
        n_match = 0
        n_total = 0
        for name, pred in predictions.items():
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/api/notes/{name}", timeout=10) as resp:
                    doc = json.loads(resp.read().decode("utf-8"))
            except Exception as exc:
                print(f"{name:5s} [ERR api] {exc}")
                continue
            notes = doc.get("notes") or {}
            sa_human = next((v for k, v in notes.items() if k.startswith("aten_pil_hl_sa_human_")), None)
            human_txt = next((v for k, v in notes.items() if k.startswith("aten_pil_ctx_human_")), "") or ""
            n_total += 1
            match = (sa_human == pred["verdict"]) if sa_human else None
            if match:
                n_match += 1
            tag = "MATCH" if match else ("SEM_VEREDITO_HUMANO" if sa_human is None else "DIVERGIU")
            print(f"\n{name:5s} [{tag}] predito={pred['verdict']} humano_SA={sa_human}")
            if human_txt.strip():
                print(f"      humano disse: {human_txt.strip()[:200]}")
        print(f"\n[OK] {n_match}/{n_total} bateram exatamente no veredito SA (validou/invalidou)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
