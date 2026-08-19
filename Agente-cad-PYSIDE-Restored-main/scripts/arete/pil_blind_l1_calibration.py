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
from src.core.dxf_loader import DXFLoader  # noqa: E402
from src.core.pillar_geometry_recovery import (  # noqa: E402
    repair_truncated_named_pillars_from_dxf,
)

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


def check_corner_occupancy(tables: dict) -> list[str]:
    """Um canto físico não pode ter duas vigas no mesmo papel/face."""
    issues = []
    faces = (tables or {}).get("faces") or {}
    for fid, face in faces.items():
        for kind in ("passa", "chega", "interior"):
            by_corner: dict[str, list[str]] = {}
            for row in face.get(kind) or []:
                nome = str(row.get("nome") or "").strip()
                corner = str(row.get("canto") or "").strip().upper()
                if nome in ("", "—", "nenhuma") or corner in ("", "—"):
                    continue
                by_corner.setdefault(corner, []).append(nome)
            for corner, names in by_corner.items():
                distinct = list(dict.fromkeys(names))
                if len(distinct) > 1:
                    issues.append(
                        f"{fid}.{kind}@{corner}: canto ocupado por múltiplas vigas {distinct}"
                    )
    return issues


def check_orientation_contract(points: list, tables: dict) -> list[str]:
    """Compara a direção física do retângulo com o contrato ABCD publicado."""
    if not points:
        return []
    try:
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
    except (TypeError, ValueError, IndexError):
        return []
    expected = "horizontal" if max(xs) - min(xs) >= max(ys) - min(ys) else "vertical"
    actual = str((tables or {}).get("orientation") or "").strip().lower()
    if actual == expected:
        return []
    return [
        f"orientação ABCD divergente: geometria={expected}, tabela={actual or 'ausente'}"
    ]


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


def expected_short_face_bridge_links(
    beams_by_name: dict, px0: float, py0: float, px1: float, py1: float,
    *, tol: float = 3.0, min_extension: float = 2.0,
) -> set[tuple[str, str, str, str]]:
    """Reconstrui vinculos dirigidos quando uma viga contorna o pilar.

    A evidencia exigida e independente do inventario SA: dois contornos da
    mesma viga, alinhados a uma face curta, terminam exatamente nos dois lados
    do pilar. O conjunto esperado e, por exemplo, D passa DA+DB e A/B recebem
    chegadas AD+BD. Nomes de pilares ou vigas nao participam da regra.
    """
    horizontal_pillar = _is_horizontal(px0, py0, px1, py1)
    expected: set[tuple[str, str, str, str]] = set()
    short_faces = (
        {"C": ("x", px0, py0, py1), "D": ("x", px1, py0, py1)}
        if horizontal_pillar
        else {"C": ("y", py1, px0, px1), "D": ("y", py0, px0, px1)}
    )
    for beam_name, beam in beams_by_name.items():
        if not beam_name or not beam:
            continue
        segments = _beam_contours(beam)
        if not segments:
            continue
        for face, (wall_axis, fixed, span0, span1) in short_faces.items():
            # A viga deve correr paralela a face curta.
            wants_horizontal = wall_axis == "y"
            candidates = [
                seg for seg in segments
                if bool(seg.get("is_h", (seg["x1"] - seg["x0"]) >= (seg["y1"] - seg["y0"])))
                == wants_horizontal
                and (
                    seg["y0"] - tol <= fixed <= seg["y1"] + tol
                    if wall_axis == "y"
                    else seg["x0"] - tol <= fixed <= seg["x1"] + tol
                )
            ]
            if wall_axis == "y":
                low = any(seg["x0"] < span0 - min_extension and abs(seg["x1"] - span0) <= tol for seg in candidates)
                high = any(seg["x1"] > span1 + min_extension and abs(seg["x0"] - span1) <= tol for seg in candidates)
            else:
                low = any(seg["y0"] < span0 - min_extension and abs(seg["y1"] - span0) <= tol for seg in candidates)
                high = any(seg["y1"] > span1 + min_extension and abs(seg["y0"] - span1) <= tol for seg in candidates)
            if not (low and high):
                continue
            expected.update({
                (face, "passa", beam_name, f"{face}A"),
                (face, "passa", beam_name, f"{face}B"),
                ("A", "chega", beam_name, f"A{face}"),
                ("B", "chega", beam_name, f"B{face}"),
            })
    return expected


def actual_directed_links(face_beams: dict) -> set[tuple[str, str, str, str]]:
    actual: set[tuple[str, str, str, str]] = set()
    for face, slots in (face_beams or {}).items():
        for slot in ("passa_esq", "passa_dir"):
            item = slots.get(slot) or {}
            if item.get("name") and item.get("corner"):
                actual.add((face, "passa", item["name"], item["corner"]))
        for item in slots.get("para") or []:
            if item.get("name") and item.get("corner"):
                actual.add((face, "chega", item["name"], item["corner"]))
    return actual


def check_directional_topology(beams_by_name, px0, py0, px1, py1, face_beams) -> list[str]:
    expected = expected_short_face_bridge_links(beams_by_name, px0, py0, px1, py1)
    actual = actual_directed_links(face_beams)
    issues = []
    for face, role, beam, corner in sorted(expected - actual):
        issues.append(
            f"topologia dirigida: falta {face}.{role} {beam}@{corner} "
            "(dois trechos geometricos chegam aos lados opostos da face curta)"
        )
    # Para as vigas reconstruidas, papeis/cantos adicionais tambem sao
    # suspeitos; o QA os informa sem inventar substituicao por proximidade.
    bridge_beams = {item[2] for item in expected}
    expected_by_beam = {item for item in expected if item[2] in bridge_beams}
    for face, role, beam, corner in sorted(
        item for item in actual if item[2] in bridge_beams and item not in expected_by_beam
    ):
        issues.append(f"topologia dirigida: sobra {face}.{role} {beam}@{corner} sem suporte no contorno bilateral")
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
    # O QA deve avaliar a geometria observacional vigente. Isto apenas corrige
    # a copia em memoria; nao persiste nada no banco de producao.
    dxf_data = DXFLoader.load_dxf(str(dxf_path)) if dxf_path else None
    if dxf_data:
        repair_truncated_named_pillars_from_dxf(
            {p["name"]: p for p in pillars},
            polylines=dxf_data.get("polylines", []),
            texts=dxf_data.get("texts", []),
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

        dup_issues = check_duplicate_role(tables) + check_corner_occupancy(tables)
        orientation_issues = check_orientation_contract(p["points"], tables)
        geo_issues = check_geometry(beams_by_name, px0, py0, px1, py1, face_beams)
        topology_issues = check_directional_topology(
            beams_by_name, px0, py0, px1, py1, face_beams
        )
        gap_issues, better_issues = check_link_gaps(beams_by_name, px0, py0, px1, py1, face_beams)
        shape_issues = check_pillar_shape(p["points"])
        orphan_issues = check_orphan_label(msp, face_beams, px0, py0, px1, py1) if msp is not None else []

        all_issues = (
            ([] if v1 == "validou" else [l.strip("- ") for l in txt1.split("\n") if l.startswith("- ")])
            + dup_issues + orientation_issues + geo_issues + topology_issues + gap_issues + better_issues + shape_issues + orphan_issues
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
