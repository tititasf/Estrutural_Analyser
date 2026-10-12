"""Interpretação geométrica de pilares ortogonais especiais (A–F).

O módulo é aditivo ao contrato ABCD legado. Ele não conhece obra, pavimento
ou nome de item: detecta seis arestas físicas pelo contorno e projeta os fatos
N1 já existentes nas faces E/F.
"""
from __future__ import annotations

import copy
import hashlib
import html
import json
import math
from typing import Any


def physical_ring(points: Any, *, collinear_tol_cm: float = 0.05) -> list[tuple[float, float]]:
    """Reduz o contorno bruto às arestas físicas realmente distintas.

    O DXF pode trazer o ponto de fechamento repetido, vértices duplicados e
    vértices colineares que não criam aresta nova. Contá-los levaria a
    tipificar um retângulo como polígono de N faces.
    """
    try:
        pts = [(float(point[0]), float(point[1])) for point in (points or [])]
    except (TypeError, ValueError, IndexError):
        return []
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) <= 1e-6:
        pts.pop()
    deduped: list[tuple[float, float]] = []
    for point in pts:
        if not deduped or math.dist(deduped[-1], point) > 1e-6:
            deduped.append(point)
    if len(deduped) > 1 and math.dist(deduped[0], deduped[-1]) <= 1e-6:
        deduped.pop()
    if len(deduped) < 3:
        return deduped
    ring = list(deduped)
    changed = True
    while changed and len(ring) > 3:
        changed = False
        for index in range(len(ring)):
            prev_point = ring[index - 1]
            point = ring[index]
            next_point = ring[(index + 1) % len(ring)]
            ax, ay = point[0] - prev_point[0], point[1] - prev_point[1]
            bx, by = next_point[0] - point[0], next_point[1] - point[1]
            base = math.hypot(next_point[0] - prev_point[0], next_point[1] - prev_point[1])
            if base <= 1e-9:
                continue
            if abs(ax * by - ay * bx) / base <= collinear_tol_cm:
                ring.pop(index)
                changed = True
                break
    return ring


def supports_rectangular_tag_renderer(points: Any, *, tol_cm: float = 0.05) -> bool:
    """O renderer ABCD por bbox só representa quatro paredes ortogonais reais.

    Reconhecer um L no motor não significa que o exportador rectangular já
    desenhe suas seis faces. Contornos especiais permanecem pendentes nesse
    consumidor até sua interpretação e seu renderer físicos serem integrados.
    """
    ring = physical_ring(points)
    if len(ring) != 4:
        return False
    xs, ys = zip(*ring)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if min(x1 - x0, y1 - y0) <= tol_cm:
        return False
    corners = set()
    for x, y in ring:
        if min(abs(x - x0), abs(x - x1)) > tol_cm:
            return False
        if min(abs(y - y0), abs(y - y1)) > tol_cm:
            return False
        corners.add((abs(x - x1) < abs(x - x0), abs(y - y1) < abs(y - y0)))
    return len(corners) == 4


def supports_physical_tag_renderer(points: Any, tables: dict | None = None) -> bool:
    """Capabilities of the integrated rectangle / six-face L renderer."""
    return supports_rectangular_tag_renderer(points) or bool(special_physical_face_segments(points, tables))


def physical_tag_geometry_key(points: Any) -> str:
    """Identifies the actual contour, independent of ring start and direction."""
    ring = [tuple(round(value, 6) for value in point) for point in physical_ring(points)]
    if not ring:
        return ''
    variants = [seq[index:] + seq[:index] for seq in (ring, list(reversed(ring)))
                for index in range(len(ring))]
    canonical = min(variants)
    return hashlib.sha256(json.dumps(canonical, separators=(',', ':')).encode()).hexdigest()


def physical_tag_artifact_matches(svg: Any, points: Any, tables: dict | None = None) -> bool:
    """Legacy rectangle tags remain valid; L tags must prove physical rendering."""
    if supports_rectangular_tag_renderer(points):
        return True
    segments = special_physical_face_segments(points, tables)
    if not segments or not isinstance(svg, str):
        return False
    import re
    root = re.search(r'<svg\b[^>]*>', svg)
    if root is None:
        return False
    if len(segments) == 8 and f'data-pil-faces="{physical_face_contract_key(segments)}"' not in root.group(0):
        return False
    return ('data-pil-physical-version="1"' in root.group(0)
            and f'data-pil-geometry="{physical_tag_geometry_key(points)}"' in root.group(0))


def physical_face_contract_key(segments: dict) -> str:
    walls = {fid: sorted([tuple(round(v,6) for v in edge['p0']),
                         tuple(round(v,6) for v in edge['p1'])])
             for fid,edge in segments.items()}
    return hashlib.sha256(json.dumps(walls,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def rectangular_pieces(
    points: Any, *, tol: float = 1e-6,
) -> list[tuple[float, float, float, float]]:
    """Decompõe o contorno físico nos retângulos que ele realmente ocupa.

    A caixa envolvente de um pilar em L cobre o vazio da dobra, e quem lê a
    caixa acha que a viga atravessa um apoio de 165 cm onde na verdade há uma
    perna de 19 — a largura dela. `P27` é esse caso: `V329` morre no topo da
    perna, mas a caixa faz o apoio parecer largo demais para interromper.

    Retangular devolve o próprio retângulo, então o critério é único.
    """
    ring = physical_ring(points)
    if len(ring) < 4:
        return []
    xs = sorted({point[0] for point in ring})
    pieces: list[tuple[float, float, float, float]] = []
    for x0, x1 in zip(xs, xs[1:]):
        if x1 - x0 <= tol:
            continue
        meio = (x0 + x1) / 2.0
        cortes: list[float] = []
        for index, p0 in enumerate(ring):
            p1 = ring[(index + 1) % len(ring)]
            if abs(p0[1] - p1[1]) > tol:
                continue  # aresta vertical não corta a varredura
            lo, hi = sorted((p0[0], p1[0]))
            if lo - tol <= meio <= hi + tol:
                cortes.append(p0[1])
        cortes.sort()
        for y0, y1 in zip(cortes[0::2], cortes[1::2]):
            if y1 - y0 > tol:
                pieces.append((x0, y0, x1, y1))
    return pieces


def secao_l_from_points(points: Any) -> dict[str, float] | None:
    """Medidas canônicas da seção em L (cm), só do contorno físico.

    ``externa_x/y`` = caixa; ``interna_x`` = espessura do ramo vertical;
    ``interna_y`` = altura do recorte (externa_y − espessura do ramo horizontal).
    Convenção do stub CIMA L / ficha N2 ``pilar_especial.secao_l``.
    """
    ring = physical_ring(points)
    if len(ring) != 6:
        return None
    pieces = rectangular_pieces(points)
    if len(pieces) != 2:
        return None
    xs = [point[0] for point in ring]
    ys = [point[1] for point in ring]
    externa_x = max(xs) - min(xs)
    externa_y = max(ys) - min(ys)
    thicknesses = [min(piece[2] - piece[0], piece[3] - piece[1]) for piece in pieces]
    thick = min(thicknesses)
    if thick <= 0.05 or externa_x <= thick or externa_y <= thick:
        return None
    return {
        "externa_x": round(externa_x, 4),
        "interna_x": round(thick, 4),
        "externa_y": round(externa_y, 4),
        "interna_y": round(externa_y - thick, 4),
    }


def classify_pillar_geometry(points: Any) -> str:
    """Tipifica o pilar pelo contorno físico, sem depender de nome ou layer.

    A tipificação é derivada do número de arestas reais; nenhum valor é
    assumido por omissão, para que um contorno inesperado apareça como tal em
    vez de se disfarçar de retangular.
    """
    ring = physical_ring(points)
    if len(ring) < 3:
        return ""
    if len(ring) == 4:
        return "rectangular"
    if len(ring) == 6 and special_l_face_segments(points):
        return "L_special_6_faces"
    return f"poly_{len(ring)}_faces"


def special_l_face_segments(points: Any) -> dict[str, dict[str, Any]]:
    pts = physical_ring(points)
    if len(pts) != 6:
        return {}
    edges: list[dict[str, Any]] = []
    signed = 0.0
    for index, p0 in enumerate(pts):
        p1 = pts[(index + 1) % 6]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            return {}
        signed += p0[0] * p1[1] - p1[0] * p0[1]
        edges.append({
            "p0": p0, "p1": p1, "dx": dx, "dy": dy,
            "length": length, "vertical": abs(dy) > abs(dx),
        })
    vertical = sorted(
        (edge for edge in edges if edge["vertical"]),
        key=lambda edge: edge["length"], reverse=True,
    )
    horizontal = sorted(
        (edge for edge in edges if not edge["vertical"]),
        key=lambda edge: edge["length"], reverse=True,
    )
    if len(vertical) != 3 or len(horizontal) != 3:
        return {}
    long_v = sorted(vertical[:2], key=lambda edge: (edge["p0"][0] + edge["p1"][0]) / 2.0)
    long_h = sorted(horizontal[:2], key=lambda edge: (edge["p0"][1] + edge["p1"][1]) / 2.0)
    assigned = {
        "A": long_v[0], "B": long_v[1], "C": horizontal[2],
        "D": vertical[2], "E": long_h[0], "F": long_h[1],
    }
    ccw = signed > 0.0
    for edge in assigned.values():
        dx, dy, length = edge["dx"], edge["dy"], edge["length"]
        edge["out"] = (dy / length, -dx / length) if ccw else (-dy / length, dx / length)
    return assigned


def special_face_neighbors(segments: dict[str, dict[str, Any]]) -> dict[str, tuple[str, str]]:
    def same(a: Any, b: Any) -> bool:
        return math.dist((float(a[0]), float(a[1])), (float(b[0]), float(b[1]))) <= 0.01

    result: dict[str, tuple[str, str]] = {}
    for fid, edge in segments.items():
        found: list[str] = []
        for endpoint in (edge["p0"], edge["p1"]):
            found.append(next((
                other for other, candidate in segments.items()
                if other != fid and (
                    same(endpoint, candidate["p0"]) or same(endpoint, candidate["p1"])
                )
            ), fid))
        result[fid] = (found[0], found[1])
    return result


def eight_face_segments(points: Any, face_geometry: Any) -> dict[str, dict[str, Any]]:
    """Resolve eight named faces only from an explicit physical face contract.

    Eight vertices alone do not determine the A–H convention (U and T have
    different assignments). Validate a complete bijection with actual walls,
    then derive normals from the source contour, never from supplied metadata.
    """
    ring = physical_ring(points)
    if len(ring) != 8 or not isinstance(face_geometry, dict):
        return {}
    if set(face_geometry) != set('ABCDEFGH'):
        return {}
    edges = []
    signed = sum(p[0]*ring[(i+1)%8][1]-ring[(i+1)%8][0]*p[1]
                 for i,p in enumerate(ring))
    if abs(signed) <= 1e-6:
        return {}
    for i,p0 in enumerate(ring):
        p1 = ring[(i+1)%8]
        dx,dy = p1[0]-p0[0],p1[1]-p0[1]
        length = math.hypot(dx,dy)
        if length <= 0.05 or min(abs(dx),abs(dy)) > 0.05:
            return {}
        edges.append(dict(p0=p0,p1=p1,dx=dx,dy=dy,length=length,
                          vertical=abs(dy)>abs(dx),
                          out=(dy/length,-dx/length) if signed>0 else (-dy/length,dx/length)))
    # Reject self-intersections before assigning names.
    from shapely.geometry import Polygon
    if not Polygon(ring).is_valid:
        return {}
    assigned = {}
    used = set()
    for fid in 'ABCDEFGH':
        try:
            a,b = face_geometry[fid]['p0'],face_geometry[fid]['p1']
            matches = [i for i,e in enumerate(edges) if
                       (math.dist(a,e['p0']) <= .05 and math.dist(b,e['p1']) <= .05) or
                       (math.dist(b,e['p0']) <= .05 and math.dist(a,e['p1']) <= .05)]
        except (KeyError,TypeError,ValueError):
            return {}
        if len(matches) != 1 or matches[0] in used:
            return {}
        used.add(matches[0])
        assigned[fid] = edges[matches[0]]
    return assigned


def special_physical_face_segments(points: Any, tables: dict | None = None) -> dict:
    """L uses its established convention; eight faces require named walls."""
    return (special_l_face_segments(points) or
            eight_face_segments(points, (tables or {}).get('face_geometry')) or
            special_u_face_segments(points))


def special_u_face_segments(points: Any) -> dict:
    """Owner convention: A/B back, E/F left leg, G/H right leg, C/D tips.

    Left/right are viewed from the back towards the U opening. Outer walls
    are A/E/G; inner walls B/F/H. This is topology, independent of DXF order.
    """
    ring = physical_ring(points)
    if len(ring) != 8:
        return {}
    signed = sum(p[0]*ring[(i+1)%8][1]-ring[(i+1)%8][0]*p[1]
                 for i,p in enumerate(ring))
    reflex = []
    for i,p in enumerate(ring):
        a,b = ring[i-1],ring[(i+1)%8]
        cross = (p[0]-a[0])*(b[1]-p[1])-(p[1]-a[1])*(b[0]-p[0])
        if cross*signed < 0:
            reflex.append(i)
    # Only U: its two reentrant vertices bound the inner back directly.
    if len(reflex) != 2 or (reflex[1]-reflex[0]) % 8 not in (1,7):
        return {}
    edges = [{'p0':p,'p1':ring[(i+1)%8]} for i,p in enumerate(ring)]
    bid = next(i for i in range(8) if {i,(i+1)%8} == set(reflex))
    b = edges[bid]
    dx,dy = b['p1'][0]-b['p0'][0],b['p1'][1]-b['p0'][1]
    length = math.hypot(dx,dy)
    if length <= .05:
        return {}
    outward = (dy/length,-dx/length) if signed>0 else (-dy/length,dx/length)
    left = (-outward[1],outward[0])
    projection = lambda edge,axis: sum((p[0]*axis[0]+p[1]*axis[1])/2 for p in (edge['p0'],edge['p1']))
    parallel = [i for i,e in enumerate(edges)
                if abs((e['p1'][0]-e['p0'][0])*outward[0]+(e['p1'][1]-e['p0'][1])*outward[1]) <= .05]
    if len(parallel) != 4:
        return {}
    aid = min(parallel,key=lambda i:projection(edges[i],outward))
    if aid == bid:
        return {}
    tips = sorted(set(parallel)-{aid,bid},key=lambda i:projection(edges[i],left),reverse=True)
    legs = sorted(set(range(8))-set(parallel),key=lambda i:projection(edges[i],left),reverse=True)
    ids = dict(A=aid,B=bid,C=tips[0],D=tips[1],E=legs[0],F=legs[1],H=legs[2],G=legs[3])
    return eight_face_segments(points,{fid:edges[i] for fid,i in ids.items()})


def _row(
    family: str, name: str, dim: Any, level: Any, corner: str, role: str,
    *, source: str,
) -> dict[str, Any]:
    return {
        "familia": family, "nome": str(name), "dim": str(dim or "—"),
        "nivel": str(level or "—"), "canto": corner, "papel": role,
        "raw": source, "dist_esq": "—", "dist_dir": "—",
    }


def _parse_sides(pillar: dict) -> dict:
    sides = pillar.get("sides_data") or pillar.get("sides_data_json") or {}
    if isinstance(sides, str):
        try:
            sides = json.loads(sides)
        except Exception:
            sides = {}
    return sides if isinstance(sides, dict) else {}


def _beam_bbox(beam: dict) -> tuple[float, float, float, float] | None:
    try:
        from src.core.pillar_face_beams import beam_bbox_from_entity
        return beam_bbox_from_entity(beam)
    except Exception:
        return None


#: Tolerância (cm) para uma parede de viga coincidir com a aresta da face.
EDGE_TOL_CM = 2.0


def beams_running_along_edge(
    edge: dict, beams: list, *, tol: float = EDGE_TOL_CM,
) -> list[dict]:
    """Vigas que correm **ao longo** da aresta física, com parede sobre ela.

    As faces E e F do pilar em L não existem em ``sides_data`` — o SA só
    preenche A–D. Derivá-las da geometria é o que permite ver a viga que
    corre no braço (V305 no braço de P26/P27, cuja banda é exatamente E–F).
    """
    from src.core.pillar_face_beams import (
        _run_thickness_matches_section, beam_bbox_from_entity, beam_runs_from_entity,
        beam_section_dim,
    )

    (ex0, ey0), (ex1, ey1) = edge["p0"], edge["p1"]
    horizontal = abs(ey1 - ey0) <= tol
    fixed = (ey0 + ey1) / 2.0 if horizontal else (ex0 + ex1) / 2.0
    lo, hi = (
        (min(ex0, ex1), max(ex0, ex1)) if horizontal
        else (min(ey0, ey1), max(ey0, ey1))
    )
    found: list[dict] = []
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        name = str(beam.get("name") or "").strip()
        if not name or any(row["name"] == name for row in found):
            continue
        bbox = beam_bbox_from_entity(beam)
        if not bbox:
            continue
        section = beam_section_dim(beam)
        for run in beam_runs_from_entity(beam) or [bbox]:
            walls = (run[1], run[3]) if horizontal else (run[0], run[2])
            span = (run[0], run[2]) if horizontal else (run[1], run[3])
            # Corredor mais grosso que a seção não é trecho físico: é bbox de
            # trechos disjuntos, e encosta em aresta que a viga não toca
            # (V323 na face E de P26).
            if not _run_thickness_matches_section(
                min(abs(run[2] - run[0]), abs(run[3] - run[1])), section,
            ):
                continue
            # Correr **ao longo** da aresta exige eixo paralelo a ela. Uma
            # viga perpendicular que morre encostada tem parede na linha da
            # aresta, mas não corre nela: `V323` (vertical) chega no pé do
            # `P26` e virava passante da face horizontal E.
            run_h = abs(run[2] - run[0]) >= abs(run[3] - run[1])
            if run_h != horizontal:
                continue
            if all(abs(wall - fixed) > tol for wall in walls):
                continue
            if min(hi, max(span)) - max(lo, min(span)) <= tol:
                continue
            found.append({"name": name, "beam": beam})
            break
    return found


def _beam_crosses_edge(
    edge: dict | None, beam: dict | None, *, tol: float = EDGE_TOL_CM,
) -> bool:
    """A viga chega **perpendicular** à aresta, cruzando a linha dela."""
    if not edge or not beam:
        return False
    from src.core.pillar_face_beams import beam_runs_from_entity, beam_bbox_from_entity

    (ex0, ey0), (ex1, ey1) = edge["p0"], edge["p1"]
    horizontal = abs(ey1 - ey0) <= tol
    fixed = (ey0 + ey1) / 2.0 if horizontal else (ex0 + ex1) / 2.0
    lo, hi = (
        (min(ex0, ex1), max(ex0, ex1)) if horizontal
        else (min(ey0, ey1), max(ey0, ey1))
    )
    for run in beam_runs_from_entity(beam) or [beam_bbox_from_entity(beam)]:
        if not run:
            continue
        rx0, ry0, rx1, ry1 = run
        run_h = abs(rx1 - rx0) >= abs(ry1 - ry0)
        if run_h == horizontal:
            continue  # paralela: não é chegada perpendicular
        along = (
            (min(rx0, rx1), max(rx0, rx1)) if horizontal
            else (min(ry0, ry1), max(ry0, ry1))
        )
        across = (
            (min(ry0, ry1), max(ry0, ry1)) if horizontal
            else (min(rx0, rx1), max(rx0, rx1))
        )
        if min(hi, along[1]) - max(lo, along[0]) <= tol:
            continue
        if across[0] - tol <= fixed <= across[1] + tol:
            return True
    return False


def _beam_contains_edge(
    edge: dict | None, beam: dict | None, *, tol: float = EDGE_TOL_CM,
) -> bool:
    """A aresta inteira cabe dentro do corredor da viga."""
    if not edge or not beam:
        return False
    from src.core.pillar_face_beams import beam_runs_from_entity, beam_bbox_from_entity

    (ex0, ey0), (ex1, ey1) = edge["p0"], edge["p1"]
    horizontal = abs(ey1 - ey0) <= tol
    fixed = (ey0 + ey1) / 2.0 if horizontal else (ex0 + ex1) / 2.0
    lo, hi = (
        (min(ex0, ex1), max(ex0, ex1)) if horizontal
        else (min(ey0, ey1), max(ey0, ey1))
    )
    for run in beam_runs_from_entity(beam) or [beam_bbox_from_entity(beam)]:
        if not run:
            continue
        rx0, ry0, rx1, ry1 = run
        along = (
            (min(rx0, rx1), max(rx0, rx1)) if horizontal
            else (min(ry0, ry1), max(ry0, ry1))
        )
        across = (
            (min(ry0, ry1), max(ry0, ry1)) if horizontal
            else (min(rx0, rx1), max(rx0, rx1))
        )
        if (
            along[0] <= lo + tol and along[1] >= hi - tol
            and across[0] - tol <= fixed <= across[1] + tol
        ):
            return True
    return False


def _beam_touches_edge(
    edge: dict | None, beam: dict | None, *, tol: float = EDGE_TOL_CM,
) -> bool:
    """O corredor da viga encosta na aresta física, com contato ao longo dela."""
    if not edge or not beam:
        return False
    from src.core.pillar_face_beams import beam_runs_from_entity, beam_bbox_from_entity

    (ex0, ey0), (ex1, ey1) = edge["p0"], edge["p1"]
    horizontal = abs(ey1 - ey0) <= tol
    fixed = (ey0 + ey1) / 2.0 if horizontal else (ex0 + ex1) / 2.0
    lo, hi = (
        (min(ex0, ex1), max(ex0, ex1)) if horizontal
        else (min(ey0, ey1), max(ey0, ey1))
    )
    for run in beam_runs_from_entity(beam) or [beam_bbox_from_entity(beam)]:
        if not run:
            continue
        rx0, ry0, rx1, ry1 = run
        across = (min(ry0, ry1), max(ry0, ry1)) if horizontal else (min(rx0, rx1), max(rx0, rx1))
        along = (min(rx0, rx1), max(rx0, rx1)) if horizontal else (min(ry0, ry1), max(ry0, ry1))
        if max(across[0] - fixed, fixed - across[1], 0.0) > tol:
            continue
        if min(hi, along[1]) - max(lo, along[0]) > tol:
            return True
    return False


def slabs_touching_edge(
    edge: dict, slab_points_map: dict | None, *, tol: float = EDGE_TOL_CM,
) -> list[str]:
    """Lajes cujo contorno encosta na aresta física, com contato ao longo dela.

    Mesma razão de `beams_running_along_edge`: `sides_data` só traz A–D, e as
    faces E e F do pilar em L saíam sempre sem laje. O contato é medido no
    polígono da laje, não em campo de ficha.
    """
    (ex0, ey0), (ex1, ey1) = edge["p0"], edge["p1"]
    horizontal = abs(ey1 - ey0) <= tol
    fixed = (ey0 + ey1) / 2.0 if horizontal else (ex0 + ex1) / 2.0
    lo, hi = (
        (min(ex0, ex1), max(ex0, ex1)) if horizontal
        else (min(ey0, ey1), max(ey0, ey1))
    )
    found: list[tuple[float, str]] = []
    for name, points in (slab_points_map or {}).items():
        bbox = _bbox_of(points)
        if not bbox:
            continue
        sx0, sy0, sx1, sy1 = bbox
        across = (sy0, sy1) if horizontal else (sx0, sx1)
        along = (sx0, sx1) if horizontal else (sy0, sy1)
        if min(abs(across[0] - fixed), abs(across[1] - fixed)) > tol:
            continue
        contato = min(hi, along[1]) - max(lo, along[0])
        if contato <= tol:
            continue
        found.append((contato, str(name)))
    return [name for _contato, name in sorted(found, reverse=True)]


def _bbox_of(points: Any) -> tuple[float, float, float, float] | None:
    try:
        pts = [(float(p[0]), float(p[1])) for p in (points or [])]
    except (TypeError, ValueError, IndexError):
        return None
    if len(pts) < 2:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def slab_physical_contact_intervals(edge: dict, points: Any, *, tol: float = 0.05) -> list:
    """Measure shared polygon edges, including disjoint contacts on one face.

    A slab bounding box cannot prove contact with a concave pillar. Only
    collinear boundary segments with slab material outside the face qualify.
    """
    from shapely.geometry import Point, Polygon

    ring = physical_ring(points)
    if len(ring) < 3:
        return []
    polygon = Polygon(ring)
    if not polygon.is_valid:
        return []
    start, end = sorted((tuple(edge['p0']), tuple(edge['p1'])))
    axis = 0 if abs(end[1]-start[1]) <= tol else 1
    lo, hi = start[axis], end[axis]
    fixed = start[1-axis]
    intervals = []
    for p, q in zip(ring, ring[1:]+ring[:1]):
        if max(abs(p[1-axis]-fixed), abs(q[1-axis]-fixed)) > tol:
            continue
        a, b = max(lo,min(p[axis],q[axis])), min(hi,max(p[axis],q[axis]))
        if b-a <= tol:
            continue
        midpoint = list(start)
        midpoint[axis] = (a+b)/2
        outside = Point(midpoint[0]+edge['out'][0]*tol*2,
                        midpoint[1]+edge['out'][1]*tol*2)
        if polygon.covers(outside):
            intervals.append(_oriented_face_interval(edge, a, b, axis))
    merged = []
    for a,b in sorted(intervals):
        if merged and a <= merged[-1][1]+tol:
            merged[-1][1] = max(merged[-1][1],b)
        else:
            merged.append([a,b])
    return merged


def _oriented_face_interval(edge, low, high, axis):
    """Parameterize a physical contact from the contract's p0 to p1."""
    start, end = edge['p0'][axis], edge['p1'][axis]
    return (low-start, high-start) if end > start else (start-high, start-low)


def reconcile_physical_slab_contacts(tables, segments, slab_points_map,
                                     slab_height_map, slab_nivel_map):
    """Replace box-based slab assignments only with available source polygons."""
    rejected = copy.deepcopy(tables.get('physical_slab_contact_rejections') or [])
    for fid,edge in segments.items():
        bucket = tables.setdefault('faces',{}).setdefault(fid,{})
        measured = []
        for name,points in slab_points_map.items():
            for interval in slab_physical_contact_intervals(edge,points):
                row = _row('laje',name,slab_height_map.get(name),slab_nivel_map.get(name),
                           fid*2,'laje',source='SA/N1 measured slab polygon boundary')
                row['_physical_contact_interval_cm'] = interval
                row['_physical_contact_origin'] = 'p0'
                row['dist_esq'] = str(interval[0])+'cm'
                row['dist_dir'] = str(max(0,edge['length']-interval[1]))+'cm'
                measured.append(row)
        retained = []
        for row in bucket.get('lajes',[]):
            name = row.get('nome')
            if name in slab_points_map:
                if not any(r['nome']==name for r in measured):
                    rejected.append({'face':fid,'row':copy.deepcopy(row),
                                     'reason':'slab_polygon_does_not_touch_physical_face'})
            elif name not in ('nenhuma','—','',None):
                retained.append(row)
        bucket['lajes'] = retained+measured
    tables['physical_slab_contact_rejections'] = list({
        json.dumps(entry,sort_keys=True,ensure_ascii=False):entry for entry in rejected
    }.values())


def _arrival_corner_on_edge(
    edge: dict, neighbors: tuple[str, str], beam: dict | None, face: str,
) -> str:
    bbox = _beam_bbox(beam or {})
    if not bbox:
        return f"{face}{neighbors[0]}"
    center = ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)
    distances = [math.dist(center, edge["p0"]), math.dist(center, edge["p1"])]
    return f"{face}{neighbors[0 if distances[0] <= distances[1] else 1]}"


def enrich_special_pillar_tables(
    tables: dict,
    pillar: dict,
    *,
    slab_height_map: dict | None = None,
    slab_nivel_map: dict | None = None,
    slab_points_map: dict | None = None,
    beams: list | None = None,
    nivel_viga_default: str = "—",
) -> dict:
    """Adiciona A–F e geometria física a um payload de tabelas já calculado."""
    raw_points = pillar.get("points") or pillar.get("points_json") or []
    eight = (eight_face_segments(raw_points, pillar.get('face_geometry') or tables.get('face_geometry'))
             or special_u_face_segments(raw_points))
    if eight:
        return enrich_eight_face_tables(tables, eight, slab_height_map=slab_height_map,
                                       slab_nivel_map=slab_nivel_map,
                                       slab_points_map=slab_points_map, beams=beams)
    segments = special_l_face_segments(raw_points)
    if not segments:
        tables.setdefault("face_ids", list("ABCD"))
        # A tipificação vem do contorno, não de um default do escritor de
        # sidecar: sem ela o payload canônico sai sem identidade geométrica.
        geometry_type = classify_pillar_geometry(raw_points)
        if geometry_type:
            tables["geometry_type"] = geometry_type
        return tables

    if (beams is None and slab_points_map is None
            and tables.get('geometry_type') == 'L_special_6_faces'
            and set(tables.get('faces') or {}) == set('ABCDEF')):
        # A reader without source geometry cannot recompute (or erase) E/F.
        # The canonical physical interpretation remains the source of truth.
        return tables

    slab_height_map = slab_height_map or {}
    slab_nivel_map = slab_nivel_map or {}
    beams = beams or []
    by_name = {str(beam.get("name") or ""): beam for beam in beams if isinstance(beam, dict)}
    beam_dims = {
        name: str(
            beam.get("dim")
            or (beam.get("fields") or {}).get("dimensao")
            or "—"
        )
        for name, beam in by_name.items()
    }
    sides = _parse_sides(pillar)
    neighbors = special_face_neighbors(segments)
    faces = tables.setdefault("faces", {})
    for fid in "EF":
        faces[fid] = {
            "label": {
                "E": "E — ramo horizontal · face longa externa",
                "F": "F — ramo horizontal · face longa interna",
            }[fid],
            "lajes": [], "passa": [], "chega": [], "interior": [],
        }

    # E é a face exterior do braço; F é a reentrância. Laje indicada no
    # braço pertence à exterior e não deve ser duplicada na concavidade.
    raw_e = sides.get("E") or {}
    slab_name = str(raw_e.get("l1_n") or "").strip()
    if not slab_name or slab_name.upper() in {"SEM LAJE", "NENHUMA", "—"}:
        # `sides_data` só é preenchido em A–D; a laje de E vem da geometria,
        # pelo contato do polígono com a aresta física do braço.
        tocando = slabs_touching_edge(segments["E"], slab_points_map)
        slab_name = tocando[0] if tocando else ""
    if slab_name and slab_name.upper() not in {"SEM LAJE", "NENHUMA", "—"}:
        faces["E"]["lajes"].append(_row(
            "laje", slab_name, slab_height_map.get(slab_name),
            slab_nivel_map.get(slab_name), "EE", "laje",
            source="SA/N1 special six-face geometry",
        ))

    # A viga longitudinal do braço passa nos dois extremos de E. Na face
    # interna F somente o extremo compartilhado com a tampa curta D é físico.
    #
    # A fonte é a geometria, não ``sides_data``: o SA só preenche A–D, e ler
    # dali deixava E e F sempre vazias. A aresta física do braço diz qual viga
    # corre nela.
    pass_names: list[str] = [
        row["name"] for row in beams_running_along_edge(segments["E"], beams)
    ]
    for key in ("v_passa_esq_n", "v_passa_dir_n"):
        name = str(raw_e.get(key) or "").strip()
        if name and name.upper() not in {"NENHUMA", "—"} and name not in pass_names:
            pass_names.append(name)
    for name in pass_names:
        for other in neighbors["E"]:
            faces["E"]["passa"].append(_row(
                "viga", name, beam_dims.get(name), nivel_viga_default,
                f"E{other}", "passa", source="SA/N1 special six-face geometry",
            ))
        other_f = "D" if "D" in neighbors["F"] else neighbors["F"][0]
        faces["F"]["passa"].append(_row(
            "viga", name, beam_dims.get(name), nivel_viga_default,
            f"F{other_f}", "passa", source="SA/N1 special six-face geometry",
        ))

    # As chegadas gravadas na antiga tampa D são vigas perpendiculares à
    # face exterior E. Reposicioná-las pelo endpoint físico elimina o uso da
    # caixa envolvente retangular nos pilares em L.
    raw_d = sides.get("D") or {}
    for index in range(1, 5):
        name = str(raw_d.get(f"v_ch{index}_n") or "").strip()
        if not name or name.upper() in {"NENHUMA", "—"}:
            continue
        corner = _arrival_corner_on_edge(segments["E"], neighbors["E"], by_name.get(name), "E")
        faces["E"]["chega"].append(_row(
            "viga", name, beam_dims.get(name) or raw_d.get(f"v_ch{index}_d"),
            nivel_viga_default, corner, "chega",
            source="SA/N1 special six-face geometry",
        ))
    # A tabela ABCD da caixa grava as mesmas chegadas na tampa D (com
    # ``sides_data`` vazio, só ali).  A D da caixa é a face sul inteira; a D
    # física é a tampa curta, cujo canto com A não existe (`V327` "DA" e
    # `V328` "DB" no `P27`, 151+14 e 146+19 = 165 cm = E).  Canto impossível e
    # viga sem contato com a tampa: a chegada é de E.
    e_names = {str(row.get("nome") or "") for row in faces["E"]["chega"]}
    bucket_d = faces.get("D") or {}
    kept_d = []
    for row in bucket_d.get("chega") or []:
        name = str(row.get("nome") or "")
        corner = str(row.get("canto") or "").upper().strip()
        valid_corner = len(corner) == 2 and corner[0] == "D" and corner[1] in (*neighbors["D"], "D")
        if valid_corner or _beam_touches_edge(segments["D"], by_name.get(name)):
            kept_d.append(row)
            continue
        if name not in e_names:
            moved = dict(row)
            moved["canto"] = _arrival_corner_on_edge(segments["E"], neighbors["E"], by_name.get(name), "E")
            faces["E"]["chega"].append(moved)
            e_names.add(name)
    if bucket_d:
        bucket_d["chega"] = kept_d

    # Viga que corre no braço pertence a E/F. A tabela ABCD, montada sobre a
    # caixa envolvente, também a colocava numa face longa — o mesmo trecho
    # aparecia duas vezes, com o papel errado na segunda (V305 em A/B de
    # P26/P27). O contorno real manda.
    arm_names = {
        row["name"] for edge in ("E", "F")
        for row in beams_running_along_edge(segments[edge], beams)
    }
    # A tampa curta D fica de fora: ali a viga do braço é interior, não uma
    # duplicata da caixa envolvente.
    for fid in "ABC":
        bucket = faces.get(fid) or {}
        for role in ("passa", "chega", "interior"):
            bucket[role] = [
                row for row in bucket.get(role) or []
                if str(row.get("nome") or "") not in arm_names
            ]

    # A chegada que a caixa envolvente registrou em A–D pode pertencer a uma
    # aresta física que virou E ou F. `V323` morre no pé do `P26`, aresta E, e
    # a tabela da caixa a punha também na "tampa sul" D. Onde a viga já está
    # registrada em E/F, a duplicata na caixa cai.
    faces_ef = {
        str(row.get("nome") or "")
        for fid in ("E", "F")
        for role in ("passa", "chega", "interior")
        for row in (faces.get(fid) or {}).get(role) or []
    }
    # `interior` fica de fora: na tampa curta a viga do braço é interior de
    # verdade, não duplicata (`V305` em D do `P26`).
    #
    # E a duplicata só cai quando a viga **não toca a aresta física** daquela
    # face: `V305` atravessa mesmo a face D do `P27` (a tampa curta em
    # x 4387,4), enquanto `V323` no `P26` nem chega perto da D de lá.
    for fid in "ABCD":
        bucket = faces.get(fid) or {}
        aresta = segments.get(fid)
        for role in ("passa", "chega"):
            bucket[role] = [
                row for row in bucket.get(role) or []
                if str(row.get("nome") or "") not in faces_ef
                or _beam_touches_edge(aresta, by_name.get(str(row.get("nome") or "")))
            ]

    # Quando outra viga **chega** perpendicular à tampa curta, é ela que fica
    # com o par de passagem da esquina; a viga que corre ao longo da tampa —
    # a que **contém** a aresta — passa a ser o interior dali. Sem chegada
    # nenhuma, quem corre ao longo mantém o par (`P26`: só a `V304`).
    for fid in ("C", "D"):
        aresta = segments.get(fid)
        bucket = faces.get(fid) or {}
        if not aresta:
            continue
        chegando = [
            row for row in bucket.get("chega") or []
            if str(row.get("nome") or "") not in ("", "—", "nenhuma")
            and _beam_crosses_edge(aresta, by_name.get(str(row.get("nome") or "")))
        ]
        if not chegando:
            continue
        contendo = [
            row for row in bucket.get("passa") or []
            if _beam_contains_edge(aresta, by_name.get(str(row.get("nome") or "")))
        ]
        if not contendo:
            continue
        nomes = {str(row.get("nome") or "") for row in contendo}
        bucket["passa"] = [
            row for row in bucket.get("passa") or []
            if str(row.get("nome") or "") not in nomes
        ]
        for row in contendo:
            if any(
                str(x.get("nome") or "") == str(row.get("nome") or "")
                for x in bucket.get("interior") or []
            ):
                continue
            bucket.setdefault("interior", []).append(_row(
                "viga", str(row.get("nome") or ""), row.get("dim"),
                row.get("nivel"), f"{fid}{fid}", "interior",
                source="SA/N1 special six-face geometry",
            ))

    # Medido e revertido (2026-08-22): materializar `passa` na tampa curta
    # para toda viga que atravessa a aresta física. Acerta o `D.passa V305`
    # do `P27` e cria um igual no `P26`, que o corpus não tem — os dois L são
    # espelhados e a `V305` atravessa a tampa curta dos dois do mesmo jeito.
    # A diferença está na atribuição do corpus (E/F no `P26`, D no `P27`),
    # não na geometria. Pergunta aberta ao dono.

    reconcile_verified_special_contacts(tables, segments, beams)
    if slab_points_map is not None:
        reconcile_physical_slab_contacts(tables, segments, slab_points_map,
                                         slab_height_map, slab_nivel_map)
    for fid,edge in segments.items():
        direction = ('leste' if edge['out'][0]>0 else 'oeste') if edge['out'][0] else (
            'norte' if edge['out'][1]>0 else 'sul')
        faces[fid]['label'] = f'{fid} — face física · exterior {direction}'
    tables["geometry_type"] = "L_special_6_faces"
    tables["face_ids"] = list("ABCDEF")
    tables["face_geometry"] = {
        fid: {
            "p0": list(edge["p0"]), "p1": list(edge["p1"]),
            "out": list(edge["out"]), "length": edge["length"],
        }
        for fid, edge in segments.items()
    }
    tables["face_neighbors"] = {
        fid: list(pair) for fid, pair in neighbors.items()
    }
    tables["special_geometry_source"] = "SA/N1 physical six-edge contour"
    return tables


def enrich_eight_face_tables(tables: dict, segments: dict, *, slab_height_map=None,
                            slab_nivel_map=None, slab_points_map=None, beams=None) -> dict:
    """Eight-wall contact interpretation, independent of legacy bounding boxes."""
    if beams is None and slab_points_map is None and tables.get('geometry_type') == 'physical_8_faces':
        return tables
    old = copy.deepcopy(tables.get('faces') or {})
    tables['faces'] = {fid: dict(label=f'{fid} — face física', lajes=[], passa=[],
                               chega=[], interior=[]) for fid in segments}
    if old and tables.get('geometry_type') != 'physical_8_faces':
        tables['legacy_bbox_faces'] = old
    # Verified wall intersections and slab intervals are independent evidence.
    # A legacy ABCD box label is never promoted into a named physical contact.
    reconcile_verified_special_contacts(tables, segments, beams or [])
    if slab_points_map is not None:
        reconcile_physical_slab_contacts(tables, segments, slab_points_map,
                                        slab_height_map or {}, slab_nivel_map or {})
    tables['face_ids'] = list('ABCDEFGH')
    tables['geometry_type'] = 'physical_8_faces'
    tables['face_geometry'] = {fid: {key: list(edge[key]) if key != 'length' else edge[key]
                                   for key in ('p0','p1','out','length')}
                               for fid,edge in segments.items()}
    tables['face_neighbors'] = {fid: list(pair) for fid,pair in special_face_neighbors(segments).items()}
    tables['special_geometry_source'] = 'SA/N1 validated eight-edge face contract'
    tables['physical_contact_status'] = ('verified_sources' if beams is not None and slab_points_map is not None
                                         else 'pending_source_geometry')
    return tables


def reconcile_verified_special_contacts(tables: dict, segments: dict, beams: list) -> None:
    """Reconcile legacy box links only against explicitly verified wall runs.

    Missing verification leaves the original evidence intact. Rejected links
    are retained in an audit, never converted into guessed adjacent corners.
    """
    from src.core.pillar_face_beams import beam_runs_from_entity

    verified = {str(b.get('name') or ''): b for b in beams
                if b.get('_verified_wall_runs')}
    # Section evidence is emitted only after both original DXF walls were
    # checked over the entire run. It can therefore confirm a recovered run
    # even when there is no FV candidate contour to fill _verified_wall_runs.
    for beam in beams:
        name = str(beam.get('name') or '')
        if name in verified:
            continue
        sections = beam.get('_verified_section_texts') or []
        if sections:
            source = copy.deepcopy(beam)
            source['_verified_wall_runs'] = [(run, dim) for run, dim, _pos in sections]
            verified[name] = source
    if not verified:
        return
    rejected = copy.deepcopy(tables.get('physical_contact_rejections') or [])
    faces = tables.setdefault('faces', {})
    for fid, edge in segments.items():
        bucket = faces.setdefault(fid, {})
        for role in ('passa', 'chega', 'interior'):
            retained = []
            for row in bucket.get(role, []):
                beam = verified.get(str(row.get('nome') or ''))
                if beam and not _beam_touches_edge(edge, beam):
                    rejected.append({'face': fid, 'role': role, 'row': copy.deepcopy(row),
                                     'reason': 'verified_wall_runs_do_not_touch_physical_face'})
                elif beam and role in ('chega','passa') and _beam_crosses_edge(edge, beam):
                    # Rebuild below from the actual intersection interval.
                    continue
                else:
                    retained.append(row)
            bucket[role] = retained
        start, end = sorted((edge['p0'], edge['p1']))
        horizontal = abs(start[1] - end[1]) <= EDGE_TOL_CM
        axis = 0 if horizontal else 1
        lo, hi = start[axis], end[axis]
        for name, beam in verified.items():
            if not _beam_crosses_edge(edge, beam):
                continue
            intervals = set()
            for run in beam_runs_from_entity(beam):
                run_h = abs(run[2]-run[0]) >= abs(run[3]-run[1])
                if run_h == horizontal:
                    continue
                fixed = start[1-axis]
                if not run[1-axis]-EDGE_TOL_CM <= fixed <= run[3-axis]+EDGE_TOL_CM:
                    continue
                a, b = max(lo, run[axis]), min(hi, run[axis+2])
                if b-a > EDGE_TOL_CM:
                    intervals.add((a,b))
            for a,b in sorted(intervals):
                contact_start, contact_end = _oriented_face_interval(edge, a, b, axis)
                row = _row('viga', name, beam.get('dim'), None, fid*2, 'chega',
                           source='SA/N1 verified wall intersection with physical face')
                row['dist_esq'] = str(max(0.0,contact_start))+'cm'
                row['dist_dir'] = str(max(0.0,edge['length']-contact_end))+'cm'
                row['_physical_contact_interval_cm'] = [contact_start,contact_end]
                row['_physical_contact_origin'] = 'p0'
                bucket.setdefault('chega', []).append(row)
    tables['physical_contact_rejections'] = list({
        json.dumps(entry, sort_keys=True, ensure_ascii=False): entry
        for entry in rejected
    }.values())


def physical_face_contact(segments: dict, fid: str, kind: str, row: dict) -> tuple:
    """Contact span and tip on an actual edge; never on its enclosing box.

    New measured intervals follow p0 to p1. Legacy rows without an explicit
    origin retain their lower-coordinate convention.
    Invalid corner assignments stay explicit instead of inventing a contact.
    """
    import re

    edge = segments[fid]
    start, end = tuple(edge['p0']), tuple(edge['p1'])
    if row.get('_physical_contact_origin') != 'p0':
        start, end = sorted((start, end))
    length = math.dist(start, end)
    if length <= 1e-6:
        raise ValueError(f'{fid}: face física sem comprimento')
    unit = ((end[0] - start[0]) / length, (end[1] - start[1]) / length)

    def at(distance):
        return start[0] + unit[0] * distance, start[1] + unit[1] * distance

    def number(value):
        match = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*(?:cm)?\s*', str(value))
        return float(match[1].replace(',', '.')) if match else None

    measured = row.get('_physical_contact_interval_cm')
    if measured is not None:
        a,b = map(float, measured)
        if not 0 <= a < b <= length + .01:
            raise ValueError(f'{fid}: intervalo físico inválido')
        return at(a), at(min(b,length)), at((a+min(b,length))/2)

    corner = str(row.get('canto') or '').upper().strip()
    contact = None
    if kind in {'passa', 'chega'} and corner != fid * 2:
        if len(corner) != 2 or corner[0] != fid or corner[1] not in segments:
            raise ValueError(f'{fid}: canto físico inválido {corner!r}')
        other = segments[corner[1]]
        contact = next((point for point in (start, end)
                        if any(math.dist(point, p) <= .01 for p in (other['p0'], other['p1']))), None)
        if contact is None:
            raise ValueError(f'{fid}: faces não adjacentes em {corner}')
    if kind == 'passa':
        if contact is None:
            raise ValueError(f'{fid}: passagem sem vértice físico')
        return start, end, contact
    if kind == 'chega':
        match = re.match(r'\s*(\d+(?:[.,]\d+)?)', str(row.get('dim') or ''))
        width = float(match[1].replace(',', '.')) if match else None
        if width is None or not 0 < width <= length + .01:
            raise ValueError(f'{fid}: largura da chegada ausente ou maior que a face')
        width = min(width, length)
        offset = (length - width) / 2 if contact is None else (0 if contact == start else length - width)
        return at(offset), at(offset + width), at(offset + width / 2)
    de, dd = number(row.get('dist_esq')), number(row.get('dist_dir'))
    if de is not None or dd is not None:
        if de is None or dd is None or de + dd > length + .01:
            raise ValueError(f'{fid}: intervalo de contato físico inconsistente')
        return at(de), at(length - dd), at((de + length - dd) / 2)
    return start, end, at(length / 2)


def format_tables_portal_dynamic(formatter, tables: dict) -> str:
    """Compatibilidade: força o formatter legado a receber uma cópia A–F.

    O formatter compartilhado será simplificado quando o arquivo legado puder
    ser migrado; até lá, consumidores podem usar os metadados A–F diretamente.
    """
    base = formatter(copy.deepcopy(tables))
    if not set(tables.get("face_ids") or []) & set('EFGH'):
        return base
    cards: list[str] = []
    colors = {"E": "#c2410c", "F": "#0f766e", "G": "#6d28d9", "H": "#b45309"}
    family_labels = {
        "lajes": "Lajes", "passa": "Passam",
        "chega": "Chegam", "interior": "Interior",
    }
    for fid in [fid for fid in 'EFGH' if fid in (tables.get('faces') or {})]:
        data = (tables.get("faces") or {}).get(fid) or {}
        rows: list[str] = []
        for family, label in family_labels.items():
            real = [
                row for row in (data.get(family) or [])
                if str(row.get("nome") or "") not in {"", "—", "nenhuma"}
            ]
            if not real:
                real = [{"nome": "nenhuma", "dim": "—", "nivel": "—", "canto": "—"}]
            for row in real:
                cells = [label, row.get("nome"), row.get("dim"), row.get("nivel"),
                         row.get("canto"), row.get("dist_esq"), row.get("dist_dir")]
                index = next((i for i, source in enumerate(data.get(family) or []) if source is row), -1)
                rendered = []
                for column, value in enumerate(cells):
                    field = {1: "nome", 2: "dim", 3: "nivel", 4: "canto", 5: "dist_esq", 6: "dist_dir"}.get(column)
                    attrs = (f' class="abcd-editable" data-field="{field}"'
                             f' data-value="{html.escape(str(value or ""), quote=True)}"'
                             if index >= 0 and field in {"nome", "dim", "nivel", "canto"} else "")
                    warning = ""
                    status_key = "dist" if field in {"dist_esq", "dist_dir"} else field
                    if status_key and row.get(f"{status_key}_status") in {"inferred", "fallback", "ambiguous", "conflict", "missing"}:
                        reason = html.escape(str(row.get(f"{status_key}_motivo") or "Requer revisão"), quote=True)
                        warning = f' <span class="abcd-level-attention" role="img" aria-label="Atenção: {reason}" title="{reason}">⚠</span>'
                    rendered.append(f"<td{attrs}>{html.escape(str(value or '—'))}{warning}</td>")
                row_attrs = f' data-face="{fid}" data-role="{family}" data-index="{index}"' if index >= 0 else ""
                rows.append(f"<tr{row_attrs}>" + "".join(rendered) + "</tr>")
        cards.append(
            f'<div class="abcd-p-card" style="border-left:4px solid {colors[fid]}">'
            f'<div class="abcd-p-title" style="color:{colors[fid]}">'
            f'{html.escape(str(data.get("label") or fid))}</div>'
            '<table class="abcd-p-tbl"><tr><th>Família</th><th>Nome</th><th>Dim</th>'
            '<th>Nível</th><th>Canto</th><th>d.esq</th><th>d.dir</th></tr>'
            + "".join(rows) + "</table></div>"
        )
    marker = '<div class="abcd-p-grid">'
    insertion = "".join(cards)
    if marker in base:
        start = base.index(marker) + len(marker)
        return base[:start] + insertion + base[start:]
    return base + insertion
