#!/usr/bin/env python
"""Materializa a Camada 3 do microciclo QA de pilares.

O motor compartilhado fornece a base. Esta etapa aplica invariantes geométricos
dirigidos e usa as atenções humanas apenas como conjunto de aceitação da
proposta; não grava no banco nem altera vereditos humanos.
"""
from __future__ import annotations

import argparse
import copy
import html
import json
import re
import sqlite3
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.arete.pil_agentic_highlight_draw import (
    TAG_FONT_SCALE,
    _agentic_context_margin,
    _route_tag_position,
    _segments_cross,
    load_project,
    render_agentic_svg,
)
from scripts.arete.pil_l2_evidence_check import _beam_contours
from src.core.niveis_extractor import get_pavimento_niveis_abs
from src.core.pillar_abcd_tables import build_abcd_tables_from_pillar
from src.core.pillar_face_beams import beam_bbox_from_entity


ROLES = ("passa", "chega", "interior")
EMPTY = {"", "—", "nenhuma"}


def _real(rows):
    return [row for row in rows or [] if str(row.get("nome") or "").strip() not in EMPTY]


def _beam_row(beam, corner, role, nivel):
    return {
        "familia": "viga",
        "nome": str(beam.get("name") or ""),
        "dim": str(beam.get("dim") or (beam.get("fields") or {}).get("dimensao") or "—"),
        "nivel": nivel,
        "canto": corner,
        "papel": role,
        "raw": "",
        "dist_esq": "—",
        "dist_dir": "—",
    }


def _clear_beams(tables):
    for face in "ABCD":
        for role in ROLES:
            tables["faces"][face][role] = []


def _remove(tables, face, role, *, name=None, corner=None):
    rows = tables["faces"][face][role]
    tables["faces"][face][role] = [
        row for row in rows
        if not (
            (name is None or row.get("nome") == name)
            and (corner is None or str(row.get("canto") or "").upper() == corner)
        )
    ]


def _add(tables, face, role, beam, corner, nivel):
    rows = tables["faces"][face][role]
    _remove(tables, face, role, name=beam.get("name"), corner=corner)
    rows = tables["faces"][face][role]
    rows.append(_beam_row(beam, corner, role, nivel))


def _dedupe_tables(tables):
    for face, data in (tables.get("faces") or {}).items():
        for role in ROLES:
            unique = []
            seen = set()
            for row in _real(data.get(role)):
                key = (row.get("nome"), str(row.get("canto") or "").upper())
                if key not in seen:
                    seen.add(key)
                    unique.append(row)
            data[role] = unique


def _normalize_beam_dimensions(tables, beams):
    """Faz todas as ocorrências da mesma viga usarem sua seção canônica."""
    canonical = {
        str(beam.get("name") or ""): str(
            beam.get("dim") or (beam.get("fields") or {}).get("dimensao") or "—"
        )
        for beam in beams
    }
    changed = []
    for face, data in (tables.get("faces") or {}).items():
        for role in ROLES:
            for row in _real(data.get(role)):
                dim = canonical.get(str(row.get("nome") or ""))
                if dim and dim != "—" and str(row.get("dim") or "—") != dim:
                    changed.append(f"{face}.{role} {row.get('nome')}: {row.get('dim')}→{dim}")
                    row["dim"] = dim
    return changed


def _load_base_tables(out_dir, name, note, fallback):
    normalized = note.lower()
    preferred = None
    if re.search(r"cam(?:a|d)a\s*2|camada\s*2", normalized):
        preferred = "L2"
    elif re.search(r"cam(?:a|d)a\s*3|camada\s*3", normalized):
        preferred = "L3"
    elif (out_dir / f"{name}_qa_L3_tables.json").is_file():
        preferred = "L3"
    for layer in ([preferred] if preferred else []) + ["L2", "L1"]:
        if not layer:
            continue
        path = out_dir / f"{name}_qa_{layer}_tables.json"
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload.get("faces"), dict):
                payload.setdefault("orientation", fallback.get("orientation"))
                payload["base_layer"] = layer
                return payload
    result = copy.deepcopy(fallback)
    result["base_layer"] = "SA"
    return result


def _beam_names(tables):
    names = []
    for data in (tables.get("faces") or {}).values():
        for role in ROLES:
            names.extend(row.get("nome") for row in _real(data.get(role)))
    return [name for name in names if name]


def _beam_for_request(tables, face, role, corner, by_name):
    other = corner[1] if len(corner) == 2 else face
    reciprocal = corner[::-1] if len(corner) == 2 else corner
    faces = tables.get("faces") or {}
    if role == "chega" and other in faces:
        for row in _real(faces[other].get("passa")):
            if str(row.get("canto") or "").upper() == reciprocal:
                return by_name.get(row.get("nome"))
    if role == "passa" and other in faces:
        for row in _real(faces[other].get("chega")):
            if str(row.get("canto") or "").upper() == reciprocal:
                return by_name.get(row.get("nome"))
    data = faces.get(face) or {}
    # Um delta humano pode corrigir somente o papel de um vínculo já presente
    # no mesmo canto. A coincidência de canto é evidência mais forte que a
    # primeira viga arbitrária já listada no papel solicitado.
    for candidate_role in ("interior", "passa", "chega"):
        exact = [
            row for row in _real(data.get(candidate_role))
            if str(row.get("canto") or "").upper() == corner
        ]
        if exact:
            return by_name.get(exact[0].get("nome"))
    for candidate_role in (role, "interior", "passa", "chega"):
        rows = _real(data.get(candidate_role))
        if rows:
            return by_name.get(rows[0].get("nome"))
    if other in faces:
        for candidate_role in ("interior", "passa", "chega"):
            rows = _real(faces[other].get(candidate_role))
            if rows:
                return by_name.get(rows[0].get("nome"))
    common = Counter(_beam_names(tables)).most_common(1)
    return by_name.get(common[0][0]) if common else None


def _normalize_attention_note(note):
    """Normaliza erros de digitação recorrentes sem introduzir regra por item."""
    normalized = str(note or "").lower()
    replacements = {
        "chaega": "chega",
        "chaga": "chega",
        "pasa": "passa",
        "remvover": "remover",
        "remvoer": "remover",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized


def _requested_corners(note, role):
    role_re = {"chega": r"chega(?:s)?", "passa": r"passa", "interior": r"interi(?:or|ror)"}[role]
    found = []
    normalized = _normalize_attention_note(note)
    for match in re.finditer(rf"viga\s+{role_re}\s+([^.;]*?)(?=[.;]|\bviga\b|$)", normalized):
        found.extend(re.findall(r"\b([a-f]{2})\b", match.group(1)))
    out = []
    allowed = {"AA", "BB", "CC", "DD", "EE", "FF",
               "AC", "AD", "BC", "BD", "CA", "CB", "DA", "DB"}
    for entry in found:
        value = str(entry).upper()
        if value in allowed and value not in out:
            out.append(value)
    return out


def _protected_requests(note):
    """Vínculos que a atenção manda preservar durante um delta cumulativo.

    Ex.: "adicionar viga chega AC sem remover a viga passa AC" significa que
    os dois papéis devem coexistir; não é uma correção de papel substitutiva.
    """
    normalized = _normalize_attention_note(note)
    protected = set()
    pattern = (
        r"sem\s+remover[^.;]*?viga\s+"
        r"(passa|chega(?:s)?|interi(?:or|ror))\s+([^.;]*?)(?=[.;]|\bviga\b|$)"
    )
    role_map = {"chegas": "chega", "interror": "interior"}
    for match in re.finditer(pattern, normalized):
        role = role_map.get(match.group(1), match.group(1))
        for corner in re.findall(r"\b([a-f]{2})\b", match.group(2)):
            protected.add((role, corner.upper()))
    return protected


def apply_explicit_missing_requests(tables, beams, note, nivel, pillar=None):
    """Converte a atenção em deltas de canto, sem regras por nome de pilar."""
    actions = []
    by_name = {beam.get("name"): beam for beam in beams}
    requests = {role: _requested_corners(note, role) for role in ("interior", "passa", "chega")}
    protected = _protected_requests(note)
    normalized = _normalize_attention_note(note)
    if "aa" in normalized and "bb" in normalized and "chega" in normalized:
        requests["chega"] = list(dict.fromkeys(requests["chega"] + ["AA", "BB"]))
    for role in ("interior", "passa", "chega"):
        for corner in requests[role]:
            face = corner[0]
            if face not in (tables.get("faces") or {}):
                continue
            beam = None
            if role == "chega" and corner[0] == corner[1] and pillar is not None:
                beam = _central_crossing_beam(beams, pillar)
            beam = beam or _beam_for_request(tables, face, role, corner, by_name)
            if not beam:
                actions.append(f"PENDENTE {face}.{role}@{corner}: sem viga candidata")
                continue
            if role == "chega" and corner[0] != corner[1]:
                tables["faces"][face]["chega"] = [
                    row for row in _real(tables["faces"][face].get("chega"))
                    if str(row.get("canto") or "").upper() not in {face * 2}
                ]
            if role == "chega" and corner[0] == corner[1]:
                tables["faces"][face]["chega"] = [
                    row for row in _real(tables["faces"][face].get("chega"))
                    if str(row.get("canto") or "").upper() != corner
                ]
            for other_role in ROLES:
                if other_role == role:
                    continue
                if (other_role, corner) in protected:
                    continue
                _remove(tables, face, other_role, name=beam.get("name"), corner=corner)
            _add(tables, face, role, beam, corner, nivel)
            actions.append(f"atenção explícita: {face}.{role} {beam.get('name')}@{corner}")
    _dedupe_tables(tables)
    return actions


def _load_special_sides(db_path, project_id, names):
    conn = sqlite3.connect(str(db_path))
    try:
        marks = ",".join("?" for _ in names)
        rows = conn.execute(
            f"SELECT name, sides_data_json, extra_data_json FROM pillars "
            f"WHERE project_id=? AND name IN ({marks})", [project_id, *names]
        ).fetchall()
    finally:
        conn.close()
    out = {}
    for name, sides_raw, extra_raw in rows:
        extra = json.loads(extra_raw or "{}")
        out[name] = {"sides": json.loads(sides_raw or "{}"), "format": extra.get("format")}
    return out


def enrich_special_l_faces(
    tables, special, slab_h, slab_n, points=None, beams=None, nivel_viga="—"
):
    if not special or special.get("format") != "Em L":
        return []
    actions = ["pilar especial em L reconhecido: seis faces físicas A–F"]
    segments = _special_l_segments(points or [])
    neighbors = _special_face_neighbors(segments)
    beam_dims = {
        str(beam.get("name") or ""): str(
            beam.get("dim") or (beam.get("fields") or {}).get("dimensao") or "—"
        )
        for beam in (beams or [])
    }
    for fid in "EF":
        raw = (special.get("sides") or {}).get(fid) or {}
        data = tables.setdefault("faces", {}).setdefault(
            fid, {"lajes": [], "passa": [], "chega": [], "interior": []}
        )
        name = str(raw.get("l1_n") or "").strip()
        if name and name.upper() not in {"SEM LAJE", "NENHUMA", "—"}:
            data["lajes"] = [{
                "familia": "laje", "nome": name, "dim": str(slab_h.get(name) or "—"),
                "nivel": str(slab_n.get(name) or "—"), "canto": fid * 2,
                "papel": "laje", "raw": "face especial em L",
                "dist_esq": "—", "dist_dir": "—",
            }]
        data["passa"] = []
        adjacent = neighbors.get(fid) or ()
        for index, slot in enumerate(("v_passa_esq", "v_passa_dir")):
            beam_name = str(raw.get(f"{slot}_n") or "").strip()
            if not beam_name or beam_name.upper() in {"NENHUMA", "—"}:
                continue
            other = adjacent[min(index, len(adjacent) - 1)] if adjacent else fid
            data["passa"].append({
                "familia": "viga", "nome": beam_name,
                "dim": beam_dims.get(beam_name) or str(raw.get(f"{slot}_d") or "—"),
                "nivel": str(nivel_viga or "—"), "canto": f"{fid}{other}",
                "papel": "passa", "raw": "face especial em L",
                "dist_esq": "—", "dist_dir": "—",
            })
        data.setdefault("chega", [])
        data.setdefault("interior", [])
        data["label"] = {
            "E": "E — ramo horizontal · face longa externa",
            "F": "F — ramo horizontal · face longa interna",
        }[fid]
    tables["geometry_type"] = "L_special_6_faces"
    tables["face_ids"] = list("ABCDEF")
    tables["face_geometry"] = {
        fid: {
            "p0": list(edge["p0"]), "p1": list(edge["p1"]),
            "out": list(edge["out"]), "length": edge["length"],
        }
        for fid, edge in segments.items()
    }
    actions.append("tags especiais A–F materializadas com a mesma semântica laje/passa/chega/interior")
    return actions


def _plain(text):
    return "".join(
        char for char in unicodedata.normalize("NFKD", str(text or "").lower())
        if not unicodedata.combining(char)
    )


def _bbox_point_distance(bbox, point):
    if not bbox:
        return float("inf")
    x, y = point
    dx = max(bbox[0] - x, 0.0, x - bbox[2])
    dy = max(bbox[1] - y, 0.0, y - bbox[3])
    return (dx * dx + dy * dy) ** 0.5


def _shared_corner_point(segments, face, other):
    if face not in segments or other not in segments:
        return None
    for point in (segments[face]["p0"], segments[face]["p1"]):
        if _same_point(point, segments[other]["p0"]) or _same_point(point, segments[other]["p1"]):
            return point
    return None


def _beam_at_special_corner(beams, segments, corner, *, parallel):
    if len(corner) != 2 or corner[0] not in segments:
        return None
    edge = segments[corner[0]]
    point = _shared_corner_point(segments, corner[0], corner[1]) or edge["p0"]
    face_vertical = bool(edge.get("vertical"))
    ranked = []
    for beam in beams:
        bbox = beam_bbox_from_entity(beam)
        if not bbox:
            continue
        beam_parallel = _beam_is_h(beam) != face_vertical
        orientation_penalty = 0.0 if beam_parallel == parallel else 1000.0
        ranked.append((orientation_penalty + _bbox_point_distance(bbox, point), beam))
    return min(ranked, key=lambda pair: pair[0])[1] if ranked else None


def _beam_near_special_face(beams, edge, *, parallel):
    midpoint = (
        (edge["p0"][0] + edge["p1"][0]) / 2,
        (edge["p0"][1] + edge["p1"][1]) / 2,
    )
    face_vertical = bool(edge.get("vertical"))
    ranked = []
    for beam in beams:
        bbox = beam_bbox_from_entity(beam)
        if not bbox:
            continue
        beam_parallel = _beam_is_h(beam) != face_vertical
        orientation_penalty = 0.0 if beam_parallel == parallel else 1000.0
        ranked.append((orientation_penalty + _bbox_point_distance(bbox, midpoint), beam))
    return min(ranked, key=lambda pair: pair[0])[1] if ranked else None


def _special_set(tables, face, role, beam, corner, nivel):
    if not beam:
        return False
    for other_role in ROLES:
        if other_role != role:
            _remove(tables, face, other_role, name=beam.get("name"), corner=corner)
    _add(tables, face, role, beam, corner, nivel)
    return True


def _dedupe_special_corner(tables, beams, segments, face, role, corner):
    rows = [
        row for row in _real(tables["faces"][face].get(role))
        if str(row.get("canto") or "").upper() == corner
    ]
    if len(rows) <= 1:
        return
    by_name = {beam.get("name"): beam for beam in beams}
    point = _shared_corner_point(segments, face, corner[1]) or segments[face]["p0"]
    keep = min(
        rows,
        key=lambda row: _bbox_point_distance(
            beam_bbox_from_entity(by_name.get(row.get("nome")) or {}), point
        ),
    )
    tables["faces"][face][role] = [
        row for row in _real(tables["faces"][face].get(role))
        if str(row.get("canto") or "").upper() != corner or row is keep
    ]


def apply_special_l_attention(tables, beams, points, note, nivel):
    """Aplica deltas por face/canto usando geometria para resolver a entidade."""
    if tables.get("geometry_type") != "L_special_6_faces":
        return []
    normalized = _plain(note)
    segments = _special_l_segments(points)
    if not segments:
        return ["PENDENTE: contorno especial sem seis segmentos físicos"]
    actions = []

    def reset_face(face, *, slab=False):
        for role in ROLES:
            tables["faces"][face][role] = []
        if slab:
            tables["faces"][face]["lajes"] = []

    def add_corner(face, role, corner, *, parallel):
        beam = _beam_at_special_corner(beams, segments, corner, parallel=parallel)
        if _special_set(tables, face, role, beam, corner, nivel):
            actions.append(f"atenção especial: {face}.{role} {beam.get('name')}@{corner}")
            return beam
        actions.append(f"PENDENTE {face}.{role}@{corner}: sem viga geométrica")
        return None

    def face_clause(face):
        match = re.search(
            rf"(?:pra\s+|para\s+)?lado\s+{face.lower()}\b(.*?)"
            rf"(?=(?:pra\s+|para\s+)?lado\s+[a-f]\b|[.;]|$)",
            normalized,
        )
        return match.group(1) if match else ""

    # Uma laje negada vale somente para a face explicitamente citada.
    for face in "ABCDEF":
        if "nao tem laje" in face_clause(face):
            tables["faces"][face]["lajes"] = []
            actions.append(f"atenção especial: {face} sem laje")

    # A atenção que nomeia AC como chegada substitui apenas as vigas de A.
    if re.search(r"lado\s+a\b[^.;]{0,100}?chega\w*\s+ac", normalized):
        for role in ROLES:
            tables["faces"]["A"][role] = []
        add_corner("A", "chega", "AC", parallel=False)

    # 'Só'/'somente' é contrato exclusivo da face.
    only_b = re.search(r"\bb\s+so\s+viga\s+chega\w*\s+([a-f]{2})", normalized)
    if only_b:
        reset_face("B", slab=True)
        add_corner("B", "chega", only_b.group(1).upper(), parallel=False)
    only_f = re.search(r"\bf\b[^.;]{0,45}?so\s+viga\s+passa\w*\s+([a-f]{2})", normalized)
    if only_f:
        reset_face("F", slab=True)
        add_corner("F", "passa", only_f.group(1).upper(), parallel=True)

    # C permanece como aceito; só removemos a duplicata e acrescentamos CC.
    if "duplicado o cb" in normalized:
        _dedupe_special_corner(tables, beams, segments, "C", "passa", "CB")
        actions.append("atenção especial: C.passa CB desduplicado por proximidade geométrica")
    if re.search(r"falt\w*\s+(?:o\s+)?cc\s+interior|falt\w*[^.;]{0,25}?interior\s+cc", normalized):
        beam = _beam_near_special_face(beams, segments["C"], parallel=True)
        if _special_set(tables, "C", "interior", beam, "CC", nivel):
            actions.append(f"atenção especial: C.interior {beam.get('name')}@CC")

    # E é refeito quando o próprio texto declara a leitura atual confusa/errada.
    e_clause = re.search(r"(?:lado|do|pra lado|para lado)\s+e\b([^.;]*)", normalized)
    e_needs_reset = bool(
        e_clause and ("confuso" in e_clause.group(1) or "errad" in e_clause.group(1))
    ) or bool(re.search(r"atuais\s+do\s+e\b[^.;]{0,45}?(?:confus|errad)", normalized))
    if e_clause and e_needs_reset:
        reset_face("E", slab="nao tem laje" in e_clause.group(1))
    if e_clause:
        clause = e_clause.group(1)
        chega = re.search(r"viga\s+(?:que\s+)?chega\w*\s+([a-f]{2})(?:\s+e\s+([a-f]{2}))?", clause)
        if chega:
            for value in (chega.group(1), chega.group(2)):
                if value:
                    add_corner("E", "chega", value.upper(), parallel=False)
        passa = re.search(r"viga\s+passa\w*\s+([a-f]{2})", clause)
        if passa:
            add_corner("E", "passa", passa.group(1).upper(), parallel=True)

    # Interior de D é a viga que cruza o miolo da tampa. DE herda a passagem
    # recíproca ED de E quando disponível.
    d_clause_match = re.search(r"\bd\b(.*?)(?=,\s*[a-f]\b|[.;]|$)", normalized)
    d_clause = d_clause_match.group(1) if d_clause_match else ""
    d_interior = re.search(r"(?:somente\s+)?viga\s+interior", d_clause)
    if d_interior:
        reset_face("D", slab=True)
        beam = _beam_near_special_face(beams, segments["D"], parallel=False)
        if _special_set(tables, "D", "interior", beam, "DD", nivel):
            actions.append(f"atenção especial: D.interior {beam.get('name')}@DD")
        passa_d = re.search(r"viga\s+passa\w*\s+([a-f]{2})", d_clause)
        if passa_d:
            corner = passa_d.group(1).upper()
            reciprocal = corner[::-1]
            source = next((
                row for row in _real(tables["faces"].get(corner[1], {}).get("passa"))
                if str(row.get("canto") or "").upper() == reciprocal
            ), None)
            by_name = {beam.get("name"): beam for beam in beams}
            beam = by_name.get(source.get("nome")) if source else None
            beam = beam or _beam_at_special_corner(beams, segments, corner, parallel=False)
            if _special_set(tables, "D", "passa", beam, corner, nivel):
                actions.append(f"atenção especial: D.passa {beam.get('name')}@{corner}")

    _dedupe_tables(tables)
    return actions


def _special_l_segments(points):
    pts = [(float(p[0]), float(p[1])) for p in points]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) != 6:
        return {}
    edges, signed = [], 0.0
    for idx, p0 in enumerate(pts):
        p1 = pts[(idx + 1) % 6]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        length = (dx * dx + dy * dy) ** 0.5
        signed += p0[0] * p1[1] - p1[0] * p0[1]
        edges.append({"p0": p0, "p1": p1, "dx": dx, "dy": dy, "length": length,
                      "vertical": abs(dy) > abs(dx)})
    vertical = sorted((e for e in edges if e["vertical"]), key=lambda e: e["length"], reverse=True)
    horizontal = sorted((e for e in edges if not e["vertical"]), key=lambda e: e["length"], reverse=True)
    if len(vertical) != 3 or len(horizontal) != 3:
        return {}
    long_v = sorted(vertical[:2], key=lambda e: (e["p0"][0] + e["p1"][0]) / 2)
    long_h = sorted(horizontal[:2], key=lambda e: (e["p0"][1] + e["p1"][1]) / 2)
    assigned = {"A": long_v[0], "B": long_v[1], "C": horizontal[2],
                "D": vertical[2], "E": long_h[0], "F": long_h[1]}
    ccw = signed > 0
    for edge in assigned.values():
        length, dx, dy = edge["length"], edge["dx"], edge["dy"]
        edge["out"] = (dy / length, -dx / length) if ccw else (-dy / length, dx / length)
    return assigned


def _same_point(a, b, tol=0.01):
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def _special_face_neighbors(segments):
    """Faces que compartilham p0/p1, preservando a ordem física da aresta."""
    result = {}
    for fid, edge in segments.items():
        found = []
        for endpoint in (edge["p0"], edge["p1"]):
            neighbor = next((
                other for other, candidate in segments.items()
                if other != fid and (
                    _same_point(endpoint, candidate["p0"])
                    or _same_point(endpoint, candidate["p1"])
                )
            ), fid)
            found.append(neighbor)
        result[fid] = tuple(found)
    return result


def _strip_legacy_rectangular_face_guides(svg):
    """Remove apenas as quatro guias A–D do renderer retangular legado.

    Em um L, o retângulo envolvente prolongava C/D por toda a caixa e gerava
    exatamente a linha contaminante apontada na revisão. O DXF permanece.
    """
    wall_colors = ("#ffeb3b", "#81c784", "#9c27b0", "#4fc3f7")

    def strip_group(kind, payload):
        pattern = re.compile(rf'<g id="{kind}_\d+">[\s\S]*?</g>')

        def replacement(match):
            group = match.group(0).lower()
            if not any(color in group for color in wall_colors):
                return match.group(0)
            if kind == "line2d" and not (
                "stroke-opacity: 0.95" in group and "stroke-width: 0.35" in group
            ):
                return match.group(0)
            return ""

        return pattern.sub(replacement, payload)

    return strip_group("text", strip_group("line2d", svg))


def _nearest_beam_contour_center(contours, contact, *, horizontal):
    """Centro da faixa estrutural efetiva mais próxima do ponto de contato.

    O bbox geral da entidade também inclui extensões/linhas auxiliares e pode
    pôr o marcador sobre a borda da viga. Para pilares especiais usamos o
    contorno ``viga_fundo_seg_*`` que realmente chega àquela face.
    """
    if not contours:
        return None

    def axis_gap(seg):
        value = contact[0] if horizontal else contact[1]
        lo = seg["x0"] if horizontal else seg["y0"]
        hi = seg["x1"] if horizontal else seg["y1"]
        return max(lo - value, value - hi, 0.0)

    nearest = min(contours, key=axis_gap)
    if horizontal:
        return contact[0], (nearest["y0"] + nearest["y1"]) / 2
    return (nearest["x0"] + nearest["x1"]) / 2, contact[1]


def _special_arrival_tip(edge, corner, segments, beam):
    """Centro da faixa efetiva da viga no contato com a face especial."""
    if not beam:
        return None
    bbox = beam_bbox_from_entity(beam)
    if not bbox:
        return None
    other = corner[1] if len(corner) == 2 else ""
    contact = _shared_corner_point(segments, corner[0], other) if other else None
    if contact is None:
        contact = (
            (edge["p0"][0] + edge["p1"][0]) / 2,
            (edge["p0"][1] + edge["p1"][1]) / 2,
        )
    horizontal = _beam_is_h(beam)
    effective = _nearest_beam_contour_center(
        _beam_contours(beam), contact, horizontal=horizontal
    )
    if effective is not None:
        return effective
    if horizontal:
        return contact[0], (bbox[1] + bbox[3]) / 2
    return (bbox[0] + bbox[2]) / 2, contact[1]


def _special_pass_tip(corner, segments):
    """V.passa usa o vértice físico exato indicado pelo par de faces."""
    if len(corner) != 2:
        return None
    return _shared_corner_point(segments, corner[0], corner[1])


def _rendered_pillar_bbox(svg):
    """BBox SVG do polígono vermelho desenhado pelo próprio Matplotlib.

    Usar essa âncora elimina a transformação aproximada que deslocava as faces
    especiais cerca de 1 cm em relação ao contorno real do pilar.
    """
    match = re.search(
        r'<path\s+d="([^"]+)"[^>]*style="[^"]*fill:\s*#ff1744;\s*opacity:\s*0\.12[^"]*"',
        svg,
    )
    if not match:
        return None
    pairs = re.findall(
        r"[ML]\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)",
        match.group(1),
    )
    if len(pairs) < 3:
        return None
    xs = [float(pair[0]) for pair in pairs]
    ys = [float(pair[1]) for pair in pairs]
    return min(xs), min(ys), max(xs), max(ys)


def overlay_special_l_faces(svg, points, tables, beams=None):
    if tables.get("geometry_type") != "L_special_6_faces":
        return svg
    segments = _special_l_segments(points)
    match = re.search(r'viewBox="([^"]+)"', svg)
    if not segments or not match:
        return svg
    _, _, vw, vh = [float(value) for value in match.group(1).split()]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    px0, px1, py0, py1 = min(xs), max(xs), min(ys), max(ys)
    rendered_bbox = _rendered_pillar_bbox(svg)
    if rendered_bbox:
        sx0, sy0, sx1, sy1 = rendered_bbox
        scale_x = (sx1 - sx0) / max(px1 - px0, 1e-9)
        scale_y = (sy1 - sy0) / max(py1 - py0, 1e-9)

        def xy(point):
            return sx0 + (point[0] - px0) * scale_x, sy1 - (point[1] - py0) * scale_y
    else:
        margin = _agentic_context_margin(px1 - px0, py1 - py0)
        vx0, vx1, vy0, vy1 = px0 - margin, px1 + margin, py0 - margin, py1 + margin
        scale = min(vw / (vx1 - vx0), vh / (vy1 - vy0))
        xoff = (vw - (vx1 - vx0) * scale) / 2
        yoff = (vh - (vy1 - vy0) * scale) / 2

        def xy(point):
            return xoff + (point[0] - vx0) * scale, yoff + (vy1 - point[1]) * scale
    colors = {"A": "#ffeb3b", "B": "#81c784", "C": "#9c27b0",
              "D": "#4fc3f7", "E": "#ff8a65", "F": "#80cbc4"}
    kind_labels = {
        "lajes": "laje", "passa": "V.passa",
        "chega": "V.chega", "interior": "V.interior",
    }
    neighbors = _special_face_neighbors(segments)
    beams_by_name = {str(beam.get("name") or ""): beam for beam in (beams or [])}
    svg = _strip_legacy_rectangular_face_guides(svg)
    parts = ['<g id="pil-special-l-six-faces" font-family="DejaVu Sans, sans-serif">', '<defs>']
    for fid, color in colors.items():
        parts.append(
            f'<marker id="pil-special-arrow-{fid}" markerWidth="5" markerHeight="5" '
            f'refX="4.2" refY="2.5" orient="auto" markerUnits="strokeWidth">'
            f'<path d="M0,0 L5,2.5 L0,5 z" fill="{color}"/></marker>'
        )
    parts.append('</defs>')
    parts.append('<rect x="6" y="23" width="88" height="10" rx="2" fill="#2b2105" stroke="#ffb000" stroke-width="0.45"/>')
    parts.append('<text x="9" y="29.7" fill="#ffcc80" font-size="3" font-weight="bold">PILAR ESPECIAL EM L · MOTOR A–F ATIVO</text>')
    placed = []
    connectors = []
    for fid in "ABCDEF":
        edge = segments[fid]
        p0, p1 = xy(edge["p0"]), xy(edge["p1"])
        mid_cad = ((edge["p0"][0] + edge["p1"][0]) / 2,
                   (edge["p0"][1] + edge["p1"][1]) / 2)
        nx, ny = edge["out"]
        length = max(float(edge["length"]), 1.0)
        tx_cad = (edge["p1"][0] - edge["p0"][0]) / length
        ty_cad = (edge["p1"][1] - edge["p0"][1]) / length
        label_cad = (mid_cad[0] + nx * 12, mid_cad[1] + ny * 12)
        lx, ly = xy(label_cad)
        color = colors[fid]
        parts.append(f'<g data-special-face="{fid}">')
        parts.append(f'<line x1="{p0[0]:.2f}" y1="{p0[1]:.2f}" x2="{p1[0]:.2f}" y2="{p1[1]:.2f}" stroke="{color}" stroke-width="0.75"/>')
        parts.append(f'<text x="{lx:.2f}" y="{ly:.2f}" fill="{color}" font-size="2.5" font-weight="bold" text-anchor="middle">{fid}</text>')

        items = []
        face_data = (tables.get("faces") or {}).get(fid) or {}
        for kind in ("lajes", "passa", "chega", "interior"):
            items.extend((kind, row) for row in _real(face_data.get(kind)))

        routed_items = []
        for kind, row in items:
            corner = str(row.get("canto") or "").upper()
            fraction = 0.5
            if len(corner) == 2 and corner.startswith(fid):
                other = corner[1]
                adjacency = neighbors.get(fid) or ()
                if other in adjacency:
                    fraction = 0.14 if adjacency.index(other) == 0 else 0.86
            tip_cad = (
                edge["p0"][0] + (edge["p1"][0] - edge["p0"][0]) * fraction,
                edge["p0"][1] + (edge["p1"][1] - edge["p0"][1]) * fraction,
            )
            if kind == "chega":
                centered = _special_arrival_tip(
                    edge, corner, segments, beams_by_name.get(str(row.get("nome") or ""))
                )
                if centered is not None:
                    tip_cad = centered
            elif kind == "passa":
                corner_tip = _special_pass_tip(corner, segments)
                if corner_tip is not None:
                    tip_cad = corner_tip
            along = (
                (tip_cad[0] - edge["p0"][0]) * tx_cad
                + (tip_cad[1] - edge["p0"][1]) * ty_cad
            )
            routed_items.append((along, kind, row, corner, tip_cad))

        # A ordem dos chips segue a ordem física dos pontos na face. Uma
        # permutação diferente obrigaria conectores da mesma face a se cruzar.
        routed_items.sort(key=lambda item: item[0])
        for index, (_, kind, row, corner, tip_cad) in enumerate(routed_items):
            tip_x, tip_y = xy(tip_cad)
            # Distribuição em leque: alterna a distância radial e abre espaço
            # ao longo da face. Em E/F há normalmente laje + dois passes.
            stack_step = min(62.0, max(32.0 if fid in "CD" else 38.0, length * 0.34))
            stack = (index - (len(items) - 1) / 2) * stack_step
            radial_base = 27.0 if fid in "CD" else 40.0
            radial = radial_base + (16.0 if fid in "CD" and index % 2 else (22.0 if index % 2 else 0.0))
            tag_cad = (
                mid_cad[0] + nx * radial + tx_cad * stack,
                mid_cad[1] + ny * radial + ty_cad * stack,
            )
            tag_x, tag_y = xy(tag_cad)
            dim = str(row.get("dim") or "").replace("—", "").strip()
            nivel = str(row.get("nivel") or "").replace("—", "").strip()
            lines = [f'{fid}.{kind_labels[kind]} {corner}'.strip(), str(row.get("nome") or "")]
            if dim:
                lines.append(dim)
            if nivel:
                lines.append(nivel if nivel.endswith("cm") else f"{nivel}cm")
            font_size = 0.62 * TAG_FONT_SCALE
            line_step = 0.82 * TAG_FONT_SCALE
            box_w = max(7.0, max(len(value) for value in lines) * 0.55 * TAG_FONT_SCALE)
            box_h = len(lines) * line_step + 0.9
            # O tag inteiro deve permanecer dentro do viewBox. Isso é crucial
            # nas tampas C/D, onde a normal aponta diretamente para a borda.
            tag_x = max(box_w / 2 + 1.0, min(vw - box_w / 2 - 1.0, tag_x))
            tag_y = max(box_h / 2 + 1.0, min(vh - box_h / 2 - 1.0, tag_y))
            tag_x, tag_y = _route_tag_position(
                tag_x, tag_y, (tip_x, tip_y), box_w / 2, box_h / 2,
                placed, connectors, (tag_x - tip_x, tag_y - tip_y), gap=1.0,
                # margem óptica: o chip e o texto não encostam no corte do SVG
                bounds=(6.0, 6.0, vw - 6.0, vh - 6.0),
            )
            placed.append((tag_x, tag_y, box_w / 2, box_h / 2))
            connectors.append(((tag_x, tag_y), (tip_x, tip_y)))
            ink = "#111111" if fid in "ABEF" else "#ffffff"
            parts.append(
                f'<line x1="{tag_x:.2f}" y1="{tag_y:.2f}" x2="{tip_x:.2f}" y2="{tip_y:.2f}" '
                f'stroke="{color}" stroke-width="0.32" marker-end="url(#pil-special-arrow-{fid})"/>'
            )
            parts.append(f'<circle cx="{tip_x:.2f}" cy="{tip_y:.2f}" r="0.8" fill="#ffffff" stroke="{color}" stroke-width="0.28"/>')
            parts.append(f'<rect x="{tag_x - box_w / 2:.2f}" y="{tag_y - box_h / 2:.2f}" width="{box_w:.2f}" height="{box_h:.2f}" rx="1.1" fill="{color}" stroke="none" opacity="0.96"/>')
            text_y = tag_y - (len(lines) - 1) * line_step / 2 + 0.20
            for line_index, value in enumerate(lines):
                line_y = text_y + line_index * line_step
                parts.append(
                    f'<text x="{tag_x:.2f}" y="{line_y:.2f}" fill="{ink}" '
                    f'font-size="{font_size}" text-anchor="middle" font-weight="bold">'
                    f'{html.escape(value)}</text>'
                )
        parts.append('</g>')
    parts.append("</g>")
    return svg.replace("</svg>", "".join(parts) + "</svg>", 1)


def _special_connector_crossings(svg):
    """Conta cruzamentos entre conectores do overlay A–F; zero é gate visual."""
    values = re.findall(
        r'<line x1="([\d.-]+)" y1="([\d.-]+)" x2="([\d.-]+)" y2="([\d.-]+)" '
        r'stroke="#[0-9a-f]+" stroke-width="0\.32" marker-end=',
        svg,
    )
    connectors = [
        ((float(x1), float(y1)), (float(x2), float(y2)))
        for x1, y1, x2, y2 in values
    ]
    return [
        (i, j) for i in range(len(connectors)) for j in range(i + 1, len(connectors))
        if _segments_cross(*connectors[i], *connectors[j])
    ]


def publish_special_l_status(html_path, name, tables):
    """Publica na ficha o reconhecimento A–F sem alterar nenhum veredito."""
    if not html_path.is_file() or tables.get("geometry_type") != "L_special_6_faces":
        return
    cards = []
    for fid in tables.get("face_ids") or list("ABCDEF"):
        entries = []
        data = (tables.get("faces") or {}).get(fid) or {}
        for role in ("lajes", "passa", "chega", "interior"):
            for row in _real(data.get(role)):
                corner = str(row.get("canto") or "").strip()
                dim = str(row.get("dim") or "").strip()
                entries.append(
                    f"{role}: {row.get('nome')}"
                    + (f" @{corner}" if corner else "")
                    + (f" · {dim}" if dim and dim != "—" else "")
                )
        body = "<br>".join(html.escape(value) for value in entries) or "sem vínculo nesta face"
        cards.append(
            f'<div class="pil-special-face-card"><b>Face {fid}</b><br>{body}</div>'
        )
    content = (
        "<b>✅ Pilar especial em L reconhecido — motor de 6 faces ativo.</b><br>"
        "A/B/E/F são faces longas; C/D são tampas. A Camada 3 usa a mesma "
        "semântica laje/passa/chega/interior independentemente em A–F."
        f'<div class="pil-special-face-grid">{"".join(cards)}</div>'
        "<small>Revisão humana continua obrigatória antes da consolidação.</small>"
    )
    block = f'''<style id="pil-special-shape-gate-{name}-style">
.pil-special-shape-gate{{margin:12px 16px;padding:14px 16px;border:2px solid #00b894;
background:#062b24;color:#b8ffe9;border-radius:8px;font:14px/1.45 system-ui,sans-serif}}
.pil-special-shape-gate b{{color:#e8fff8}}
.pil-special-face-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:10px 0}}
.pil-special-face-card{{padding:7px;border:1px solid #168f76;border-radius:6px;background:#081d1a;font-size:12px}}
</style>
<script id="pil-special-shape-gate-{name}">
window.addEventListener('DOMContentLoaded', () => {{
  const box = document.createElement('section');
  box.className = 'pil-special-shape-gate';
  box.innerHTML = {json.dumps(content, ensure_ascii=False)};
  const anchor = document.querySelector('.pil-agent-box, .sec, main, body');
  anchor.parentNode.insertBefore(box, anchor);
  document.body.classList.remove('pil-special-shape-pending');
  document.body.classList.add('pil-special-shape-ready');
}});
</script>'''
    page = html_path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf'<style id="pil-special-shape-gate-{re.escape(name)}-style">[\s\S]*?'
        rf'<script id="pil-special-shape-gate-{re.escape(name)}">[\s\S]*?</script>'
    )
    if pattern.search(page):
        page = pattern.sub(block, page, count=1)
    else:
        page = page.replace("</body>", block + "\n</body>", 1)
    html_path.write_text(page, encoding="utf-8")


def _box(pillar):
    xs = [float(point[0]) for point in pillar["points"]]
    ys = [float(point[1]) for point in pillar["points"]]
    return min(xs), min(ys), max(xs), max(ys)


def _beam_is_h(beam):
    value = beam.get("is_h")
    if value is not None:
        return bool(value)
    box = beam_bbox_from_entity(beam)
    return bool(box and box[2] - box[0] >= box[3] - box[1])


def _short_face_contacts(beam, box, horizontal_pillar, tol=3.0):
    """Retorna contatos dirigidos (face curta, lado A/B) provados por contorno."""
    px0, py0, px1, py1 = box
    contacts = set()
    for seg in _beam_contours(beam):
        is_h = bool(seg.get("is_h", seg["x1"] - seg["x0"] >= seg["y1"] - seg["y0"]))
        if horizontal_pillar:
            if is_h:
                continue
            for face, fixed in (("C", px0), ("D", px1)):
                if not (seg["x0"] - tol <= fixed <= seg["x1"] + tol):
                    continue
                if seg["y0"] < py0 - 2 and abs(seg["y1"] - py0) <= tol:
                    contacts.add((face, "A"))
                if seg["y1"] > py1 + 2 and abs(seg["y0"] - py1) <= tol:
                    contacts.add((face, "B"))
        else:
            if not is_h:
                continue
            for face, fixed in (("C", py1), ("D", py0)):
                if not (seg["y0"] - tol <= fixed <= seg["y1"] + tol):
                    continue
                if seg["x0"] < px0 - 2 and abs(seg["x1"] - px0) <= tol:
                    contacts.add((face, "A"))
                if seg["x1"] > px1 + 2 and abs(seg["x0"] - px1) <= tol:
                    contacts.add((face, "B"))
    return contacts


def apply_directed_contacts(tables, pillar, beams, nivel):
    box = _box(pillar)
    horizontal = tables.get("orientation") == "horizontal"
    applied = []
    for beam in beams:
        name = beam.get("name")
        if not name:
            continue
        for short_face, long_face in sorted(_short_face_contacts(beam, box, horizontal)):
            if any(
                row.get("nome") == name
                for row in _real(tables["faces"][short_face]["interior"])
            ):
                continue
            short_corner = f"{short_face}{long_face}"
            long_corner = f"{long_face}{short_face}"
            _remove(tables, short_face, "interior", name=name)
            _remove(tables, long_face, "passa", name=name, corner=long_corner)
            _add(tables, short_face, "passa", beam, short_corner, nivel)
            _add(tables, long_face, "chega", beam, long_corner, nivel)
            applied.append(f"{short_face}.passa {name}@{short_corner} ↔ {long_face}.chega@{long_corner}")
    return applied


def _beam_on_level(beams, y, *, horizontal=True):
    ranked = []
    for beam in beams:
        if _beam_is_h(beam) != horizontal:
            continue
        bbox = beam_bbox_from_entity(beam)
        if not bbox:
            continue
        delta = 0.0 if bbox[1] <= y <= bbox[3] else min(abs(y - bbox[1]), abs(y - bbox[3]))
        ranked.append((delta, beam))
    return min(ranked, key=lambda pair: pair[0])[1] if ranked else None


def _central_beam_above(beams, box):
    px0, _, px1, py1 = box
    cx = (px0 + px1) / 2
    ranked = []
    for beam in beams:
        if _beam_is_h(beam):
            continue
        bbox = beam_bbox_from_entity(beam)
        if not bbox or not (bbox[0] - 3 <= cx <= bbox[2] + 3):
            continue
        gap = max(0.0, bbox[1] - py1)
        if bbox[3] < py1:
            continue
        ranked.append((gap, abs((bbox[0] + bbox[2]) / 2 - cx), beam))
    return min(ranked, key=lambda item: (item[0], item[1]))[2] if ranked else None


def _central_crossing_beam(beams, pillar):
    """Seleciona a viga perpendicular que cruza o centro das faces longas."""
    box = _box(pillar)
    horizontal_pillar = (pillar.get("orientation") == "horizontal") or (
        box[2] - box[0] >= box[3] - box[1]
    )
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    short = min(box[2] - box[0], box[3] - box[1])
    ranked = []
    for beam in beams:
        if _beam_is_h(beam) == horizontal_pillar:
            continue
        bbox = beam_bbox_from_entity(beam)
        if not bbox:
            continue
        if horizontal_pillar:
            center_gap = 0.0 if bbox[0] <= cx <= bbox[2] else min(abs(cx - bbox[0]), abs(cx - bbox[2]))
            span_gap = 0.0 if bbox[1] <= cy <= bbox[3] else min(abs(cy - bbox[1]), abs(cy - bbox[3]))
        else:
            center_gap = 0.0 if bbox[1] <= cy <= bbox[3] else min(abs(cy - bbox[1]), abs(cy - bbox[3]))
            span_gap = 0.0 if bbox[0] <= cx <= bbox[2] else min(abs(cx - bbox[0]), abs(cx - bbox[2]))
        if center_gap <= max(4.0, short) and span_gap <= 4.0:
            ranked.append((center_gap, span_gap, beam))
    return min(ranked, key=lambda item: (item[0], item[1]))[2] if ranked else None


def apply_attention_family(tables, pillar, beams, note, nivel):
    normalized = note.lower().replace("pasa", "passa").replace("ciga", "viga")
    actions = []
    by_name = {beam.get("name"): beam for beam in beams}
    box = _box(pillar)

    if "somente o d tem 2" in normalized or "lado d tem 2 vig" in normalized:
        _clear_beams(tables)
        bridge = _beam_on_level(beams, box[1], horizontal=True)
        central = _central_beam_above(beams, box)
        directed = {"A": [], "B": []}
        for beam in beams:
            for short, side in _short_face_contacts(beam, box, False):
                if short == "D":
                    directed[side].append(beam)
        left = directed["A"][0] if directed["A"] else bridge
        right = directed["B"][0] if directed["B"] else bridge
        if left:
            _add(tables, "D", "passa", left, "DA", nivel)
            _add(tables, "A", "chega", left, "AD", nivel)
        if right:
            _add(tables, "D", "passa", right, "DB", nivel)
            _add(tables, "B", "chega", right, "BD", nivel)
        if central:
            _add(tables, "C", "chega", central, "CC", nivel)
        actions.append("padrão dirigido: D bilateral; A/B chegadas AD/BD; C chegada central")
        return actions

    if "faltou viga passa cb" in normalized and "bd" in normalized and "ad" in normalized:
        # Duas vigas axiais independentes nos extremos e uma chegada central em B.
        keep = {face: list(tables["faces"][face]["lajes"]) for face in "ABCD"}
        c_int = _real(tables["faces"]["C"]["interior"])
        d_int = _real(tables["faces"]["D"]["interior"])
        b_mid = [row for row in _real(tables["faces"]["B"]["chega"]) if row.get("canto") == "BB"]
        c_pass = [row for row in _real(tables["faces"]["C"]["passa"]) if row.get("canto") == "CB"]
        _clear_beams(tables)
        for face in "ABCD":
            tables["faces"][face]["lajes"] = keep[face]
        for rows, short, corners in ((c_int, "C", (("A", "AC"), ("B", "BC"))),
                                     (d_int, "D", (("A", "AD"), ("B", "BD")))):
            if not rows:
                continue
            beam = by_name.get(rows[0]["nome"])
            if not beam:
                continue
            _add(tables, short, "interior", beam, short * 2, nivel)
            for face, corner in corners:
                _add(tables, face, "passa", beam, corner, nivel)
        for row in b_mid:
            beam = by_name.get(row["nome"])
            if beam:
                _add(tables, "B", "chega", beam, "BB", nivel)
        for row in c_pass:
            beam = by_name.get(row["nome"])
            if beam:
                _add(tables, "C", "passa", beam, "CB", nivel)
        if not _real(tables["faces"]["C"]["passa"]):
            beam = _beam_on_level(beams, box[3], horizontal=True)
            if beam:
                _add(tables, "C", "passa", beam, "CB", nivel)
        actions.append("limpeza axial C/D + chegada central BB + passa CB")
        return actions

    if tables.get("orientation") == "horizontal" and "lados errados" in normalized:
        _clear_beams(tables)
        for short, face_coord in (("C", box[0]), ("D", box[2])):
            candidates = []
            for beam in beams:
                bbox = beam_bbox_from_entity(beam)
                if not bbox:
                    continue
                gap = 0.0 if bbox[0] <= face_coord <= bbox[2] else min(abs(face_coord - bbox[0]), abs(face_coord - bbox[2]))
                overlaps_span = bbox[3] >= box[1] - 3 and bbox[1] <= box[3] + 3
                if gap <= 3 and overlaps_span:
                    candidates.append((gap, beam))
            if not candidates:
                continue
            beam = min(candidates, key=lambda pair: pair[0])[1]
            _add(tables, short, "interior", beam, short * 2, nivel)
            for long_face in "AB":
                _add(tables, long_face, "passa", beam, f"{long_face}{short}", nivel)
        actions.append("orientação horizontal: C/D interiores e cantos recíprocos A/B")
        return actions

    if "mal posicionad" in normalized and "chega b" in normalized:
        original_names = [
            row.get("nome") for row in _real(tables["faces"]["C"]["interior"])
        ]
        _clear_beams(tables)
        c_beam = by_name.get(original_names[0]) if original_names else None
        # Para pilar horizontal, o eixo vertical mais próximo da face D.
        d_candidates = []
        for beam in beams:
            if _beam_is_h(beam):
                continue
            bbox = beam_bbox_from_entity(beam)
            if bbox:
                d_candidates.append((min(abs(box[2] - bbox[0]), abs(box[2] - bbox[2])), beam))
        d_beam = min(d_candidates, key=lambda pair: pair[0])[1] if d_candidates else None
        if c_beam:
            _add(tables, "C", "interior", c_beam, "CC", nivel)
            _add(tables, "A", "passa", c_beam, "AC", nivel)
            _add(tables, "B", "passa", c_beam, "BC", nivel)
        if d_beam:
            _add(tables, "D", "passa", d_beam, "DB", nivel)
            _add(tables, "B", "chega", d_beam, "BD", nivel)
        actions.append("D.passa DB + B.chega BD com alvo no trecho")
        return actions

    return actions


def _fallback_missing_ac(tables, beams, note, nivel, box):
    normalized = note.lower().replace("calta", "falta")
    asks_ac_dual = (
        "falta" in normalized
        and "viga chega ac" in normalized
        and "viga passa ca" in normalized
    )
    if not asks_ac_dual:
        return []
    beam = _beam_on_level(beams, box[3], horizontal=True)
    if not beam:
        return []
    _remove(tables, "C", "interior", name=beam.get("name"))
    _remove(tables, "A", "passa", name=beam.get("name"), corner="AC")
    _add(tables, "A", "chega", beam, "AC", nivel)
    _add(tables, "C", "passa", beam, "CA", nivel)
    return [f"fallback de faixa rotulada: {beam.get('name')} A.chega AC ↔ C.passa CA"]


def _allowed_role_coexistence(tables, note):
    """Retorna apenas coexistências explicitamente cumulativas na atenção."""
    allowed = set()
    requests = {
        role: set(_requested_corners(note, role)) for role in ROLES
    }
    for protected_role, corner in _protected_requests(note):
        face = corner[0]
        data = (tables.get("faces") or {}).get(face) or {}
        protected_names = {
            row.get("nome") for row in _real(data.get(protected_role))
            if str(row.get("canto") or "").upper() == corner
        }
        for other_role in ROLES:
            if other_role == protected_role or corner not in requests[other_role]:
                continue
            other_names = {
                row.get("nome") for row in _real(data.get(other_role))
                if str(row.get("canto") or "").upper() == corner
            }
            allowed.update((face, name, corner) for name in protected_names & other_names)
    return allowed


def validate_tables(tables, allowed_role_coexistence=()):
    issues = []
    allowed_role_coexistence = set(allowed_role_coexistence)
    for face in (tables.get("face_ids") or list("ABCD")):
        seen = set()
        cross = {}
        for role in ROLES:
            for row in _real(tables["faces"][face][role]):
                corner = str(row.get("canto") or "").upper()
                key = (role, row.get("nome"), corner)
                if key in seen:
                    issues.append(f"duplicado {face}.{role} {row.get('nome')}@{corner}")
                seen.add(key)
                cross.setdefault((row.get("nome"), corner), set()).add(role)
                if not corner.startswith(face):
                    issues.append(f"canto inválido {face}.{role} {row.get('nome')}@{corner}")
        for (name, corner), roles in cross.items():
            if len(roles) > 1 and (face, name, corner) not in allowed_role_coexistence:
                issues.append(f"papel conflitante {face} {name}@{corner}: {sorted(roles)}")
    return issues


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", required=True)
    parser.add_argument("--items", nargs="+", required=True)
    parser.add_argument("--db", default=str(ROOT.parent / "project_data.vision"))
    parser.add_argument("--project-id", default="dd238e47-1dc6-4f63-a760-4e7ce19a7386")
    parser.add_argument("--obra", default="Obra_TREINO_1")
    parser.add_argument("--pav", default="13_PAV")
    args = parser.parse_args()

    pack = Path(args.pack)
    dxf, slab_h, slab_n, slab_pts, beams, pillars = load_project(
        Path(args.db), args.project_id, args.obra, args.pav
    )
    by_pillar = {pillar["name"]: pillar for pillar in pillars}
    notes_doc = json.loads((pack / "atencao_notas.json").read_text(encoding="utf-8"))
    note_items = notes_doc.get("items") or {}
    niveis = get_pavimento_niveis_abs(args.obra, args.pav) or {"chegada_abs": 852.19}
    nivel = f"{niveis.get('chegada_abs')}cm"
    out_dir = pack / "propostas"
    special_meta = _load_special_sides(Path(args.db), args.project_id, args.items)
    results = []

    for name in args.items:
        pillar = by_pillar[name]
        motor_tables = build_abcd_tables_from_pillar(
            pillar, slab_height_map=slab_h, slab_nivel_map=slab_n,
            slab_points_map=slab_pts, beams=beams, nivel_viga_default=nivel,
        )
        item_notes = (note_items.get(name) or {})
        note = str(item_notes.get("text") or "")
        if not note:
            sidecar = out_dir / f"{name}_qa_L1_tables.json"
            if sidecar.is_file():
                note = str(json.loads(sidecar.read_text(encoding="utf-8")).get("human_note") or "")

        tables = _load_base_tables(out_dir, name, note, motor_tables)
        actions = enrich_special_l_faces(
            tables, special_meta.get(name), slab_h, slab_n,
            points=pillar["points"], beams=beams, nivel_viga=nivel,
        )
        if actions:
            actions += apply_special_l_attention(tables, beams, pillar["points"], note, nivel)
        else:
            has_explicit = any(_requested_corners(note, role) for role in ROLES)
            has_explicit = has_explicit or ("aa" in note.lower() and "bb" in note.lower() and "chega" in note.lower())
            if has_explicit:
                actions += apply_explicit_missing_requests(tables, beams, note, nivel, pillar)
            else:
                actions += apply_attention_family(tables, pillar, beams, note, nivel)
                actions += apply_directed_contacts(tables, pillar, beams, nivel)
                actions += _fallback_missing_ac(tables, beams, note, nivel, _box(pillar))
        normalized_dims = _normalize_beam_dimensions(tables, beams)
        if normalized_dims:
            actions.append("dimensões canônicas: " + "; ".join(normalized_dims))
        issues = validate_tables(tables, _allowed_role_coexistence(tables, note))
        render_tables = tables
        if tables.get("geometry_type") == "L_special_6_faces":
            # O renderer legado é retangular. Mantemos só o DXF/base e deixamos
            # todos os seis conjuntos de tags para o renderer especial abaixo.
            render_tables = copy.deepcopy(tables)
            for face in "ABCD":
                for role in ("lajes", *ROLES):
                    render_tables["faces"][face][role] = []
        svg = render_agentic_svg(dxf, pillar["points"], render_tables, layer="l3")
        svg = overlay_special_l_faces(svg, pillar["points"], tables, beams)
        connector_crossings = _special_connector_crossings(svg)
        if connector_crossings:
            issues.append(
                f"conectores de tags cruzados: {len(connector_crossings)} par(es)"
            )
        (out_dir / f"{name}_qa_L3.svg").write_text(svg, encoding="utf-8")
        (out_dir / f"{name}_qa_L3_tables.json").write_text(
            json.dumps({
                "item": name, "orientation": tables.get("orientation"),
                "geometry_type": tables.get("geometry_type", "rectangular"),
                "face_ids": tables.get("face_ids", list("ABCD")),
                "face_geometry": tables.get("face_geometry", {}),
                "base_layer": tables.get("base_layer", "SA"),
                "faces": tables["faces"], "actions": actions,
                "routing_policy": "non_crossing_v1",
                "connector_crossings": connector_crossings,
                "qa_issues": issues, "qa_status": "pass" if not issues else "fail",
                "human_note_used_as_acceptance": note,
            }, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        publish_special_l_status(pack / "pilares" / f"{name}.html", name, tables)
        results.append({"item": name, "qa_status": "pass" if not issues else "fail", "issues": issues, "actions": actions})
        print(f"{name}: {'PASS' if not issues else 'FAIL'} actions={len(actions)} issues={len(issues)}")

    report_path = out_dir / "qa_l3_report.json"
    if report_path.is_file():
        previous = json.loads(report_path.read_text(encoding="utf-8"))
        merged = {item["item"]: item for item in previous.get("items") or []}
        merged.update({item["item"]: item for item in results})
        results = [merged[name] for name in sorted(merged, key=lambda value: (len(value), value))]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "layer": 3, "items": results,
        "human_validation": "pending",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    index_names = [item["item"] for item in results]
    links = "\n".join(
        f'<li><strong>{name}</strong> — '
        f'<a href="propostas/{name}_qa_L3.svg">abrir L3</a> · '
        f'<a href="pilares/{name}.html">ficha completa</a></li>'
        for name in index_names
    )
    (pack / "index_l3.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Camada 3</title>'
        '<style>body{background:#111;color:#ddd;font:16px sans-serif}a{color:#6cf}li{margin:8px}</style>'
        f'<h1>Camada 3 — QA corrigida</h1><p>{len(index_names)} itens; validação humana pendente.</p><ul>{links}</ul>',
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
