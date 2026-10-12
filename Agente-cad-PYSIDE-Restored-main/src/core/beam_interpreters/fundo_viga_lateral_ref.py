"""Laterais (LV) como REFERENCIA nao rigida do Fundo de Viga (FV).

Decisao do dono (2026-09-29, D-76): "assim como fundos serve de ajuda e nao
informacao rigida para as laterais, as laterais vao servir como ajuda para os
fundos, mas nao rigido". Esta passada usa a CENA medida das laterais
(``src/core/lv_beam_scene.py`` — faixa pelo rotulo, pilar pelo poligono real,
vigas que tocam cada face) so' como pista, e so' age com prova local do DXF.

Duas correcoes, nada alem disso:

1. **Painel de outra viga** — painel FV que cai quase todo na faixa de OUTRA
   viga (>= 70 %) e quase nada na faixa da propria (< 30 %) foi atribuido ao
   rotulo errado (13_PAV: VF202, rotulo diagonal, levava o fundo da V306). Sai
   da viga; a dona da faixa o recupera no passo 2. Viga sem cena propria nao
   perde nada (sem pista, sem acao).
2. **Trecho sem fundo** — onde as DUAS faces da viga tem parede (celulas Para
   das laterais, que ja' param em pilar e em viga de mesma altura ou mais
   funda) e nenhum fundo cobre, nasce painel FV — desde que as duas paredes
   existam como LINHA REAL do DXF no proprio trecho (>= 50 %, fora de cota).
   Trecho encostado num painel existente o prolonga; isolado vira painel novo.
   Nao existe comprimento minimo semantico: 1 cm comprovado tambem e' fundo.

Fica de fora (sem pista confiavel): viga com fundo validado por humano, trecho
diagonal, trecho cuja orientacao da cena difere da do fundo.
"""

from __future__ import annotations

import re
import copy
from typing import Any, Iterable, Optional

from shapely.geometry import Polygon, Point
from shapely.ops import unary_union, snap
from shapely.validation import make_valid

SOURCE = "fundo_viga_lateral_reference"
OWN_BAND_MAX = 0.30        # painel com menos que isto na propria faixa...
OTHER_BAND_MIN = 0.70      # ...e mais que isto na faixa de outra viga e' dela
GEOMETRIC_EPS = 1e-3       # apenas evita intervalo vazio por ruido numerico
WALL_COVERAGE_MIN = 0.50   # mesma invariante das laterais (linha real)
DIMENSION_OVERLAP_MAX = 0.05
TOUCH_TOL = 1.0
OVERLAP_AREA_TOL = 0.01   # ignora apenas residuo submilimetrico de ponto flutuante

_SLOT_RE = re.compile(r"^viga_fundo_seg_(\d+)_area_segs$")
_SEG_KEY_RE = re.compile(r"^viga_fundo_seg_(\d+)_(.+)$")


def _merge(intervals: Iterable[tuple[float, float]], gap: float = 0.05) -> list[list[float]]:
    out: list[list[float]] = []
    for a, b in sorted((min(a, b), max(a, b)) for a, b in intervals):
        if out and a <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def _intersect(first: list[list[float]], second: list[list[float]]) -> list[list[float]]:
    out = []
    for a0, a1 in first:
        for b0, b1 in second:
            lo, hi = max(a0, b0), min(a1, b1)
            if hi - lo > 0.05:
                out.append([lo, hi])
    return _merge(out)


def _subtract(base: list[list[float]], cut: list[list[float]]) -> list[list[float]]:
    out = []
    cut = _merge(cut)
    for a, b in base:
        cur = a
        for c0, c1 in cut:
            if c1 <= cur or c0 >= b:
                continue
            if c0 > cur:
                out.append([cur, c0])
            cur = max(cur, c1)
        if cur < b:
            out.append([cur, b])
    return out


def _polygon(points: Any) -> Optional[Any]:
    try:
        pts = [(float(p[0]), float(p[1])) for p in points or []]
    except (TypeError, ValueError, IndexError):
        return None
    if len(pts) < 3:
        return None
    geom = make_valid(Polygon(pts))
    return geom if geom.area > 1e-6 else None


def _panels(beam: dict) -> list[tuple[int, dict, Any]]:
    """Slots de fundo ``(indice, link do contorno, poligono)`` em ordem de indice."""
    out = []
    for key, slots in (beam.get("links") or {}).items():
        match = _SLOT_RE.match(str(key))
        if not match or not isinstance(slots, dict):
            continue
        contour = (slots.get("contour") or [None])[0]
        if not isinstance(contour, dict):
            continue
        out.append((int(match.group(1)), contour, _polygon(contour.get("points"))))
    return sorted(out, key=lambda item: item[0])


def _has_validated(panels: list[tuple[int, dict, Any]]) -> bool:
    return any(bool(link.get("validated")) for _, link, _ in panels)


def _frac(poly: Any, region: Any) -> float:
    if poly is None or region is None or region.is_empty:
        return 0.0
    return poly.intersection(region).area / poly.area


def _axis_span(poly: Any, is_h: bool) -> tuple[float, float]:
    minx, miny, maxx, maxy = poly.bounds
    return (minx, maxx) if is_h else (miny, maxy)


def _wall_spans(run: Any) -> list[list[float]]:
    """Trechos em que as DUAS faces tem parede segundo as celulas Para."""
    from src.core.beam_interpreters.lateral_viga_cells import segment_cell

    topology = []
    for side in ("A", "B"):
        topology.append(_merge(
            (min(s.start, s.end), max(s.start, s.end))
            for s in segment_cell(run, side, "para", minimum_segment=GEOMETRIC_EPS)
        ))
    allowed = _intersect(topology[0], topology[1])
    # A celula pode ser longa e ter pequenas ilhas de linha real. Intersectar
    # com a cobertura observada impede que a media da celula esconda um fundo
    # curto legitimo (inclusive um painel isolado de 1 cm).
    real_a = _merge(tuple(span) for span in run.face_coverage.get("A", []))
    real_b = _merge(tuple(span) for span in run.face_coverage.get("B", []))
    return _intersect(allowed, _intersect(real_a, real_b))


def _walls_are_real(run: Any, a0: float, a1: float) -> bool:
    return all(
        run.line_coverage(side, a0, a1) >= WALL_COVERAGE_MIN
        and run.dimension_overlap(side, a0, a1) <= DIMENSION_OVERLAP_MAX
        for side in ("A", "B")
    )


def _bridge_cut_annotation_wall_gaps(runs, lines, texts):
    """Recover a wall obscured by a source glyph, not arbitrary empty space.

    Require collinear walls on both sides, continuous opposite wall, a source
    section polygon covering the entire missing strip and no real divider or
    section change. Derived coverage only; DXF entities remain untouched.
    """
    from src.core.cad_object_recognition import section_piece_keys
    from src.core.lv_beam_scene import _line_segments
    from shapely.geometry import LineString
    _, records = section_piece_keys(lines or [], texts or [])
    glyphs = [_polygon(r.get('points')) for r in records if r.get('section_kind') == 'beam']
    glyphs = [p for p in glyphs if p is not None]
    if not glyphs:
        return
    edges = [LineString([(x,y),(a,b)]) for x,y,a,b in _line_segments(lines)]
    for scenes in runs.values():
        for run in scenes:
            if run.angle:
                continue
            original = {s: _merge(run.face_coverage.get(s, [])) for s in ('A','B')}
            for side, other in (('A','B'), ('B','A')):
                additions = []
                for left, right in zip(original[side], original[side][1:]):
                    lo, hi = left[1], right[0]
                    if hi <= lo or not any(a <= lo+.05 and b >= hi-.05 for a,b in original[other]):
                        continue
                    strip = run.rect(lo, hi, run.t_lo, run.t_hi)
                    if not any(p.buffer(.05).covers(strip) for p in glyphs):
                        continue
                    dims = {z.get('dim') for z in run.sections if z['end'] > lo and z['start'] < hi}
                    if len(dims) != 1 or None in dims:
                        continue
                    # An independent transverse divider inside the strip is
                    # physical evidence, even when a cut glyph is drawn over it.
                    interior = run.rect(lo+.05, hi-.05, run.t_lo+.05, run.t_hi-.05)
                    if any(e.intersection(interior).length >= run.width-.2
                           and abs((e.coords[-1][0]-e.coords[0][0]) if run.is_horizontal
                                   else (e.coords[-1][1]-e.coords[0][1])) < .1
                           for e in edges):
                        continue
                    additions.append([lo,hi])
                if additions:
                    run.face_coverage[side] = _merge(original[side]+additions)
                    run.provenance.setdefault('paredes_ocultas_por_visao_corte', {})[side] = additions


def _bottom_scene(run: Any, runs_by_name: dict, pillar_report: Any) -> Any:
    """FV uses final incident extents, not stale LV context before end trimming.

    A NASCE symbol cannot disprove a different pillar's solid section, even
    when its classification is uncertain and the beam walls are continuous.
    Keep support exclusions; actual hatch is independently excluded by caller.
    """
    measured = copy.deepcopy(run)
    for side in ("A", "B"):
        measured.incidents[side] = [
            incident for incident in run.incidents[side]
            if incident.get("name") not in runs_by_name or any(
                other.world_band().intersection(run.world_band()).area > GEOMETRIC_EPS
                for other in runs_by_name[incident["name"]]
            )
        ]
    return measured


def _hatched_spans(run: Any, segs: list[tuple[float, float, float, float]]) -> list[list[float]]:
    """Trechos da faixa com HACHURA (>= 3 tracos obliquos paralelos dentro dela).

    Hachura na faixa e' secao de pilar cortado — prova do proprio desenho,
    independente do relatorio de pilares (13_PAV: P12/P13/P14 com bbox no
    simbolo e nao na hachura). Um "X" (2 tracos) nao conta.
    """
    import math

    minx, miny, maxx, maxy = run.world_band().buffer(1.0, join_style=2).bounds
    groups: dict[int, list[tuple[float, float]]] = {}
    for x0, y0, x1, y1 in segs:
        if not (minx <= min(x0, x1) and max(x0, x1) <= maxx and miny <= min(y0, y1) and max(y0, y1) <= maxy):
            continue
        ang = math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180.0
        if min(ang % 90.0, 90.0 - ang % 90.0) < 20.0:
            continue
        a0, a1 = (x0, x1) if run.is_horizontal else (y0, y1)
        groups.setdefault(int(round(ang / 5.0)), []).append((min(a0, a1), max(a0, a1)))
    out = []
    for pieces in groups.values():
        for lo, hi in _merge(pieces, gap=12.0):
            if sum(1 for a, b in pieces if a >= lo - 0.1 and b <= hi + 0.1) >= 3:
                out.append([lo, hi])
    return _merge(out)


def _rect_link(run: Any, a0: float, a1: float, width: float) -> dict:
    lo, hi = min(a0, a1), max(a0, a1)
    if run.is_horizontal:
        pts = [[lo, run.t_lo], [hi, run.t_lo], [hi, run.t_hi], [lo, run.t_hi], [lo, run.t_lo]]
    else:
        pts = [[run.t_lo, lo], [run.t_hi, lo], [run.t_hi, hi], [run.t_lo, hi], [run.t_lo, lo]]
    length = hi - lo
    result = {
        "type": "poly",
        "points": pts,
        "len": length,
        "closed": True,
        "geometry_role": "area_fundo",
        "geometry_source": SOURCE,
        "fv_lateral_reference": True,
        "fv_axis_is_horizontal": bool(run.is_horizontal),
        "ficha": {
            "comprimento_total_fundo": f"{length:.2f}".rstrip("0").rstrip("."),
            "largura_total_fundo": f"{width:.2f}".rstrip("0").rstrip("."),
        },
    }
    section = run.section_at((lo + hi) / 2) or {}
    if section.get('dim') and abs(float(section.get('width', 0))-run.width) <= .15:
        result['fv_measured_section_dim'] = section['dim']
    return result


def _rewrite_slots(beam: dict, ordered: list[tuple[Optional[int], dict]], is_h: bool) -> None:
    """Regrava os slots de fundo na ordem do eixo, levando junto os campos por segmento.

    ``ordered``: ``(indice antigo ou None, link)``. Campos ``viga_fundo_seg_N_*``
    do indice antigo acompanham o painel no indice novo; painel novo nasce sem eles.
    """
    links = beam.setdefault("links", {})
    fields = beam.setdefault("fields", {})
    old_fields: dict[int, dict[str, Any]] = {}
    old_beam: dict[int, dict[str, Any]] = {}
    for store, bucket in ((fields, old_fields), (beam, old_beam)):
        for key in [k for k in list(store) if _SEG_KEY_RE.match(str(k))]:
            match = _SEG_KEY_RE.match(str(key))
            bucket.setdefault(int(match.group(1)), {})[match.group(2)] = store.pop(key)
    for key in [k for k in list(links) if _SLOT_RE.match(str(k))]:
        links.pop(key)
    coords = []
    for new_idx, (old_idx, link) in enumerate(ordered, start=1):
        links[f"viga_fundo_seg_{new_idx}_area_segs"] = {"contour": [link]}
        for suffix, value in (old_fields.get(old_idx) or {}).items():
            if suffix != "area_segs":
                fields[f"viga_fundo_seg_{new_idx}_{suffix}"] = value
        for suffix, value in (old_beam.get(old_idx) or {}).items():
            beam[f"viga_fundo_seg_{new_idx}_{suffix}"] = value
        beam[f"viga_fundo_seg_{new_idx}_exists"] = True
        poly = _polygon(link.get("points"))
        if poly is not None:
            coords.append(list(_axis_span(poly, is_h)))
    classified = beam.setdefault("geometry", {}).setdefault("classified", {})
    classified["merged_bottom_groups_coords"] = coords
    classified["merged_bottom_lengths"] = [round(b - a, 6) for a, b in coords]
    links.setdefault("viga_segs", {})["seg_bottom"] = [dict(link) for _, link in ordered]


def _merge_coplanar_slots(beam: dict) -> int:
    """Remove costura artificial, nunca uma abertura ou mudanca de secao.

    Apenas retangulos na mesma faixa. .05 cm e' tolerancia de coordenadas,
    nao comprimento minimo: qualquer abertura maior permanece aberta.
    Campos conflitantes e contornos humanos impedem a uniao.
    """
    panels = _panels(beam)
    if _has_validated(panels):
        return 0
    is_h = bool(beam.get("fv_is_h", beam.get("is_h", True)))
    fields = beam.get("fields") or {}

    def compatible(i, j):
        for store in (fields, beam):
            a = {m.group(2): v for k, v in store.items()
                 if (m := _SEG_KEY_RE.match(str(k))) and int(m.group(1)) == i}
            b = {m.group(2): v for k, v in store.items()
                 if (m := _SEG_KEY_RE.match(str(k))) and int(m.group(1)) == j}
            if any(a[k] != b[k] for k in a.keys() & b.keys() if k != "exists"):
                return False
        dim = lambda i: fields.get(f"viga_fundo_seg_{i}_dim", fields.get("dimensao", beam.get("dim")))
        return dim(i) == dim(j)

    ordered = sorted(panels, key=lambda p: _axis_span(p[2], is_h)[0] if p[2] is not None else 0)
    result = []
    merged = 0
    for index, link, poly in ordered:
        if result and poly is not None and not link.get("special_geometry"):
            prev_index, prev_link = result[-1]
            prev = _polygon(prev_link.get("points"))
            if prev is not None and not prev_link.get("special_geometry") and compatible(prev_index, index):
                a, b = prev.bounds, poly.bounds
                transverse = (1, 3) if is_h else (0, 2)
                gap = _axis_span(poly, is_h)[0] - _axis_span(prev, is_h)[1]
                rectangles = all(
                    not p.interiors and
                    all(p.envelope.boundary.distance(Point(x,y)) <= .05
                        for x,y in p.exterior.coords) and
                    p.envelope.difference(p).area <= .05 * p.envelope.length
                    for p in (prev, poly))
                if rectangles and abs(gap) <= .05 and all(abs(a[k]-b[k]) <= .05 for k in transverse):
                    x0, y0, x1, y1 = min(a[0],b[0]), min(a[1],b[1]), max(a[2],b[2]), max(a[3],b[3])
                    combined = dict(prev_link)
                    combined["points"] = [[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]]
                    combined["len"] = (x1-x0) if is_h else (y1-y0)
                    combined["ficha"] = dict(prev_link.get("ficha") or {})
                    combined["ficha"]["comprimento_total_fundo"] = f"{combined['len']:.2f}".rstrip("0").rstrip(".")
                    combined["fv_coplanar_merged"] = True
                    combined.pop("provenance", None)
                    # A new small cap has no segment fields. Preserve the
                    # original panel's metadata when it joins that cap.
                    for store in (fields, beam):
                        for key, value in list(store.items()):
                            match = _SEG_KEY_RE.match(str(key))
                            if match and int(match.group(1)) == index:
                                store.setdefault(f"viga_fundo_seg_{prev_index}_{match.group(2)}", value)
                    result[-1] = (prev_index, combined)
                    merged += 1
                    continue
        result.append((index, link))
    if merged:
        _rewrite_slots(beam, result, is_h)
    return merged


def _panel_overlap_priority(
    beam: dict,
    index: int,
    link: dict,
    panels: list[tuple[int, dict, Any]],
    *, run: Any = None, source_runs: Any = None,
) -> tuple[int, float, float, float, float, str, int]:
    """Prioridade estrutural estavel para uma area que nao pode ter dois donos.

    Contorno humano vence. Entre automaticos: maior profundidade, maior largura
    e, no empate, a maior fracao continua, antes do desenvolvimento total.
    Somar varios vaos separados nao torna uma viga mais continua. Quando o
    encontro fornece runs medidos, componentes de outra orientacao comprovada
    nao participam. Vaos paralelos conservam a rubrica anterior; ausencia de
    pareamento nao autoriza excluir um painel.
    O nome serve somente como desempate deterministico final.
    """
    validated = int(_has_validated(panels))
    fields = beam.get("fields") or {}
    dimensions = None
    for value in (
        fields.get(f"viga_fundo_seg_{index}_dim"),
        fields.get("dimensao"),
        beam.get("dim"),
    ):
        match = re.search(
            r"(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)",
            str(value or ""),
        )
        if match:
            values = [float(v.replace(",", ".")) for v in match.groups()]
            dimensions = (min(values), max(values))
            break
    width, depth = dimensions or (0.0, 0.0)
    local = [poly for _, _, poly in panels if poly is not None]
    if run is not None:
        measured = list(source_runs or [run])
        retained = []
        for poly in local:
            witnesses = [scene for scene in measured if _frac(poly, scene.world_band()) >= .5]
            parallel = any(min(abs(scene.axis_angle-run.axis_angle) % 180,
                               180-abs(scene.axis_angle-run.axis_angle) % 180) < 15
                           for scene in witnesses)
            if not witnesses or parallel:
                retained.append(poly)
        local = retained
    lengths = [max(poly.bounds[2] - poly.bounds[0], poly.bounds[3] - poly.bounds[1])
               for poly in local]
    development = sum(lengths)
    continuity = max(lengths, default=0.0) / development if development else 0.0
    name = str(beam.get("parent_name") or beam.get("name") or "").upper()
    return validated, depth, width, continuity, development, name, int(index)


def _polygon_parts(geometry: Any) -> list[Any]:
    if geometry is None or geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry] if not geometry.interiors else []
    if geometry.geom_type in {"MultiPolygon", "GeometryCollection"}:
        out = []
        for part in geometry.geoms:
            out.extend(_polygon_parts(part))
        return out
    return []


def resolve_automatic_overlaps_all(
    beams: list[dict],
    report: Optional[dict[str, Any]] = None,
    *, prefer_continuity: bool = True, texts=None, lines=None, pillar_report=None, slabs=None,
) -> dict[str, Any]:
    """Elimina dupla propriedade FV sem retangularizar chanfros/diagonais.

    Processa vigas da maior para a menor prioridade e subtrai do contorno
    automatico apenas a area ja' pertencente a uma viga prioritaria. A
    diferenca usa o poligono real (inclusive diagonal). Se a operacao gerasse
    furo interno nao representavel pelo contrato atual, o conflito fica
    registrado como nao resolvido em vez de inventar geometria.
    """
    report = report if report is not None else {}
    beam_list = [beam for beam in beams or [] if isinstance(beam, dict)]
    source_runs = {}
    if prefer_continuity and texts is not None and lines is not None:
        from src.core.lv_beam_scene import build_scene_runs
        source_runs = build_scene_runs(beam_list, texts, lines, pillar_report or {}, slabs,
                                       allow_width_hint_fallback=True)
    for beam in beam_list:
        _merge_coplanar_slots(beam)
    # A relocated legacy slot can become wholly contained in another slot of
    # the SAME beam. It is duplicate area, not an isolated physical panel.
    for beam in beam_list:
        panels = _panels(beam)
        if _has_validated(panels):
            continue
        duplicates = []
        for index, link, poly in panels:
            if poly is None:
                continue
            for other_index, _, other in panels:
                if other is None or other_index == index:
                    continue
                if other.area < poly.area or (other.area == poly.area and other_index > index):
                    continue
                if poly.difference(other.buffer(.05, join_style=2)).area <= 1e-6:
                    duplicates.append(index)
                    break
        if duplicates:
            _rewrite_slots(beam, [(i, link) for i, link, _ in panels if i not in duplicates],
                           bool(beam.get("fv_is_h", beam.get("is_h", True))))
            row = report.setdefault(str(beam.get("name")), {"removidos": [], "criados": []})
            row.setdefault("duplicados_contidos", []).extend(duplicates)
    panel_items = []
    opaque_by_beam: dict[int, list[tuple[Optional[int], dict]]] = {}
    for beam in beam_list:
        panels = _panels(beam)
        for index, link, poly in panels:
            if poly is None:
                # Preserve legacy/non-polygonal slots if another panel from the
                # same beam needs to be rewritten during overlap arbitration.
                opaque_by_beam.setdefault(id(beam), []).append((index, link))
                continue
            measured = source_runs.get(str(beam.get('name')), [])
            witnesses = [(scene, _frac(poly, scene.world_band())) for scene in measured]
            witnesses = [(scene, fraction) for scene, fraction in witnesses if fraction >= .5]
            own_run = max(witnesses, key=lambda item:item[1])[0] if witnesses else None
            priority = _panel_overlap_priority(beam, index, link, panels,
                                               run=own_run, source_runs=measured)
            if not prefer_continuity:
                priority = (*priority[:3], 0.0, *priority[4:])
            panel_items.append((priority, beam, index, link, poly))
    panel_items.sort(key=lambda item: (
        -item[0][0], -item[0][1], -item[0][2], -item[0][3],
        -item[0][4], item[0][5], item[0][6],
    ))

    occupied_owners: list[tuple[str, Any]] = []
    rebuilt_by_beam: dict[int, list[tuple[Optional[int], dict]]] = {
        id(beam): list(opaque_by_beam.get(id(beam), [])) for beam in beam_list
    }
    cuts_by_beam: dict[int, list[dict[str, Any]]] = {}
    unresolved_by_beam: dict[int, list[dict[str, Any]]] = {}

    for _priority, beam, old_idx, link, poly in panel_items:
        name = str(beam.get("parent_name") or beam.get("name") or "")
        # Partial overlaps can also occur between legacy slots of the same
        # beam (not just wholly contained duplicates). Keep their union, but
        # assign each physical patch only once, using the same stable order.
        previous = [owner_poly for _, owner_poly in occupied_owners]
        occupied = unary_union(previous) if previous else None
        if occupied is None:
            rebuilt_by_beam[id(beam)].append((old_idx, link))
            occupied_owners.append((name, poly))
            continue
        intersection = poly.intersection(occupied)
        if intersection.area <= OVERLAP_AREA_TOL:
            rebuilt_by_beam[id(beam)].append((old_idx, link))
            occupied_owners.append((name, poly))
            continue
        owners = sorted({
            owner for owner, owner_poly in occupied_owners
            if poly.intersection(owner_poly).area > OVERLAP_AREA_TOL
        })
        protected = bool(_priority[0])
        if protected:
            # Vigas validadas sao ordenadas antes das automaticas. Este caso
            # so' resta quando dois contornos humanos conflitam.
            rebuilt_by_beam[id(beam)].append((old_idx, link))
            unresolved_by_beam.setdefault(id(beam), []).append({
                "segmento": old_idx,
                "com": owners,
                "area_cm2": round(intersection.area, 3),
                "motivo": "ambos_validados",
            })
            occupied_owners.append((name, poly))
            continue
        difference = make_valid(poly.difference(occupied))
        parts = [part for part in _polygon_parts(difference) if part.area > OVERLAP_AREA_TOL]
        if difference.area > OVERLAP_AREA_TOL and not parts:
            rebuilt_by_beam[id(beam)].append((old_idx, link))
            unresolved_by_beam.setdefault(id(beam), []).append({
                "segmento": old_idx,
                "com": owners,
                "area_cm2": round(intersection.area, 3),
                "motivo": "diferenca_com_furo",
            })
            occupied_owners.append((name, poly))
            continue
        for part in parts:
            # Only a clipping by-product, never a measured isolated panel:
            # sub-coordinate-tolerance residues are not physical segments.
            dx = part.bounds[2] - part.bounds[0]
            dy = part.bounds[3] - part.bounds[1]
            if part.area < .1 and min(dx, dy) <= .05:
                report.setdefault(name, {}).setdefault("residuos_numericos_cm2", []).append(part.area)
                continue
            new_link = dict(link)
            points = [[float(x), float(y)] for x, y in part.exterior.coords]
            new_link["points"] = points
            new_link["closed"] = True
            minx, miny, maxx, maxy = part.bounds
            axis_hint = link.get("fv_axis_is_horizontal")
            if isinstance(axis_hint, bool):
                length = maxx - minx if axis_hint else maxy - miny
            else:
                length = max(maxx - minx, maxy - miny)
            new_link["len"] = length
            ficha = dict(new_link.get("ficha") or {})
            ficha["comprimento_total_fundo"] = f"{length:.2f}".rstrip("0").rstrip(".")
            new_link["ficha"] = ficha
            new_link["fv_overlap_trimmed"] = True
            new_link["fv_overlap_trimmed_by"] = owners
            rebuilt_by_beam[id(beam)].append((old_idx, new_link))
            occupied_owners.append((name, part))
        cuts_by_beam.setdefault(id(beam), []).append({
            "segmento": old_idx,
            "com": owners,
            "area_cm2": round(intersection.area, 3),
        })

    for beam in beam_list:
        name = str(beam.get("parent_name") or beam.get("name") or "")
        cuts = cuts_by_beam.get(id(beam), [])
        unresolved = unresolved_by_beam.get(id(beam), [])
        if cuts or unresolved:
            rebuilt = rebuilt_by_beam[id(beam)]
            is_h = bool(beam.get("fv_is_h", beam.get("is_h", True)))
            rebuilt.sort(key=lambda item: (
                _axis_span(_polygon(item[1].get("points")), is_h)[0]
                if _polygon(item[1].get("points")) is not None else 0.0
            ))
            _rewrite_slots(beam, rebuilt, is_h)
            row = report.setdefault(name, {"removidos": [], "criados": []})
            if cuts:
                row.setdefault("conflitos_recortados", []).extend(cuts)
            if unresolved:
                row.setdefault("conflitos_nao_resolvidos", []).extend(unresolved)
    for beam in beam_list:
        count = _merge_coplanar_slots(beam)
        if count:
            report.setdefault(str(beam.get("name")), {}).setdefault("costuras_unidas", 0)
            report[str(beam.get("name"))]["costuras_unidas"] += count
    return report


def clip_automatic_bottoms_to_solid_pillars(beams, pillar_report):
    """Enforce solid-support exclusion even on inherited/rebuilt FV contours.

    Human geometry is never changed silently. NASCE/ignored supports follow
    the shared physical-solid contract. No minimum panel length is imposed.
    """
    from src.core.lv_beam_scene import _pillar_polygons
    return _clip_automatic_bottoms_to_obstacles(beams, _pillar_polygons(pillar_report), 'pilares')


def _confirmed_cut_obstacles(slabs, lines):
    """Source-witnessed annotation polygons for diagnostics, never FV solids."""
    from src.core.lv_cut_inventory import collect_explicit_cuts
    from src.core.lv_beam_scene import _line_segments
    from shapely.geometry import LineString
    from shapely.strtree import STRtree
    edges = [LineString([(x,y),(a,b)]) for x,y,a,b in _line_segments(lines)]
    if not edges:
        return []
    tree = STRtree(edges)
    result = []
    for cut in collect_explicit_cuts([], slabs or []):
        poly = _polygon(cut.get('pts'))
        if poly is None or poly.boundary.length <= 0:
            continue
        candidates = tree.query(poly.boundary.buffer(.15))
        witness = unary_union([edges[int(i)] for i in candidates]).buffer(.15)
        if poly.boundary.difference(witness).length > .01 * poly.boundary.length:
            continue
        result.append((cut['uid'], 'corte_dxf', poly))
    return result


def _clip_automatic_bottoms_to_obstacles(beams, solids, kind):
    # Compatibility callers must also respect annotation semantics: source
    # confirmation proves the glyph exists, not that it is a physical hole.
    if kind == 'cortes':
        return {}
    from shapely.geometry import LineString
    from shapely.ops import split
    report = {}

    def source_mask(poly, solid):
        if kind != 'cortes' or poly is None or solid.geom_type != 'Polygon':
            return solid
        # Expand source edges only by the generated band's half-quantum.
        # Keeping the original mask in the union prevents shrinking a cut.
        band = poly.bounds
        def align(ring, side):
            result=[]
            for point in ring.coords:
                values=list(point)
                for k in ((0,1) if side==0 else (2,3)):
                    bound=band[k]
                    if abs(values[k%2]-bound)<=.05:
                        values[k%2]=bound
                result.append(values)
            return result
        adjusted=[make_valid(Polygon(align(solid.exterior, side),
                  [align(r, side) for r in solid.interiors])) for side in (0,1)]
        return unary_union([solid,*adjusted])

    def parts_without_holes(geom, is_h):
        if geom.is_empty:
            return []
        if geom.geom_type != "Polygon":
            return [p for g in getattr(geom, "geoms", []) for p in parts_without_holes(g, is_h)]
        if not geom.interiors:
            return [geom]
        # FV contours cannot encode holes. Divide through an internal support,
        # retaining exactly the difference, instead of filling/dropping a hole.
        center = Polygon(geom.interiors[0]).representative_point()
        x0, y0, x1, y1 = geom.bounds
        line = (LineString([(center.x, y0-1), (center.x, y1+1)]) if is_h
                else LineString([(x0-1, center.y), (x1+1, center.y)]))
        return [p for g in split(geom, line).geoms for p in parts_without_holes(g, is_h)]

    for beam in beams or []:
        panels = _panels(beam)
        is_h = bool(beam.get("fv_is_h", beam.get("is_h", True)))
        protected = _has_validated(panels) or any(
            link.get("manual") or str(link.get("geometry_source", "")).startswith("manual")
            for _, link, _ in panels)
        ordered, cuts = [], []
        for index, link, poly in panels:
            masks = [(name, source_mask(poly, solid)) for name, _, solid in solids]
            hits = [(name, solid) for name, solid in masks
                    if poly is not None and poly.intersection(solid).area > OVERLAP_AREA_TOL]
            if not hits:
                ordered.append((index, link))
                continue
            event = {"segmento": index, kind: [name for name, _ in hits]}
            if protected:
                report.setdefault(str(beam.get("name")), []).append(dict(event, motivo="geometria_humana_preservada"))
                ordered.append((index, link))
                continue
            obstacles = unary_union([p for _, p in hits])
            difference = make_valid(poly.difference(obstacles))
            event["area_cm2"] = round(poly.area-difference.area, 6)
            cuts.append(event)
            for part in parts_without_holes(difference, is_h):
                if part.area <= 1e-6:
                    continue  # numerical zero, never a semantic length limit
                lo, hi = _axis_span(part, is_h)
                new_link = copy.deepcopy(link)
                new_link.update(points=[list(p) for p in part.exterior.coords], closed=True, len=hi-lo)
                prefix = 'fv_solid_pillar' if kind == 'pilares' else 'fv_source_cut'
                new_link[prefix+'_trimmed'] = True
                new_link[prefix+'_trimmed_by'] = event[kind]
                new_link["ficha"] = dict(link.get("ficha") or {},
                    comprimento_total_fundo=f"{hi-lo:.2f}".rstrip("0").rstrip("."))
                new_link.pop("fv_provenance", None)
                ordered.append((index, new_link))
        if cuts:
            ordered.sort(key=lambda item: _axis_span(_polygon(item[1]["points"]), is_h)[0])
            _rewrite_slots(beam, ordered, is_h)
            report.setdefault(str(beam.get("name")), []).extend(cuts)
    return report


def apply_lateral_reference_all(
    beams: list[dict],
    texts: list[dict],
    lines: list[dict],
    pillar_report: Any,
    slabs: Any = None,
) -> dict[str, Any]:
    """Passada global. Retorna ``{viga: {"removidos": [...], "criados": [...]}}``."""
    from src.core.lv_beam_scene import _norm_name, build_scene_runs
    from src.core.beam_interpreters.fundo_viga import FundoVigaInterpreter

    beam_list = [b for b in beams or [] if isinstance(b, dict)]
    from src.core.pillar_geometry_recovery import reconcile_pillar_source_geometry
    reconcile_pillar_source_geometry(pillar_report, lines, texts)
    solid_cuts = {}  # anchor to measured walls before subtracting support polygons
    runs_by_name = build_scene_runs(
        beam_list, texts, lines, pillar_report, slabs, allow_width_hint_fallback=True,
    )
    _bridge_cut_annotation_wall_gaps(runs_by_name, lines, texts)
    bands = {
        name: unary_union([run.world_band() for run in runs])
        for name, runs in runs_by_name.items() if runs
    }
    from src.core.lv_beam_scene import _line_segments
    all_segs = _line_segments(lines)
    report: dict[str, Any] = {
        name: {"removidos": [], "criados": [], "pilares_solidos": cuts}
        for name, cuts in solid_cuts.items()
    }

    def entry(beam: dict) -> dict:
        return report.setdefault(str(beam.get("name")), {"removidos": [], "criados": []})

    owners: dict[str, dict] = {}
    normalize_dimension = getattr(
        FundoVigaInterpreter,
        "normalize_dimension_from_own_geometry",
        None,
    )
    for beam in beam_list:
        # A normalizacao da cota e uma melhoria independente, ainda nao
        # presente em todos os runtimes do portal. A referencia pelas laterais
        # nao pode deixar de criar fundos (inclusive os minimos) por causa dela.
        if callable(normalize_dimension):
            normalize_dimension(beam)
        owners.setdefault(_norm_name(beam.get("parent_name") or beam.get("name")), beam)

    # 1) Painel na faixa de outra viga sai da viga errada.
    for beam in beam_list:
        name = _norm_name(beam.get("parent_name") or beam.get("name"))
        own = bands.get(name)
        panels = _panels(beam)
        if own is None or not panels or _has_validated(panels) or any(l.get("manual") or str(l.get("geometry_source", "")).startswith("manual") for _,l,_ in panels):
            continue
        others = unary_union([band for other, band in bands.items() if other != name])
        keep, dropped = [], []
        for idx, link, poly in panels:
            measured_rectangle = False
            if poly is not None and not link.get('special_geometry') and abs(poly.area-poly.envelope.area)<.01:
                for r in runs_by_name.get(name, []):
                    if r.angle or not r.sections or not r.face_coverage:
                        continue
                    lo,hi=_axis_span(poly,r.is_horizontal)
                    span=max(hi-lo,GEOMETRIC_EPS)
                    if min(r.end,hi)-max(r.start,lo) >= .95*span and not r.world_band().buffer(.15,join_style=2).covers(poly):
                        measured_rectangle=True
                        break
            if poly is not None and (_frac(poly, own) < OWN_BAND_MAX or measured_rectangle):
                dropped.append(idx)
            else:
                keep.append((idx, link, poly))
        if dropped:
            is_h = bool(beam.get("fv_is_h", beam.get("is_h", True)))
            keep.sort(key=lambda item: _axis_span(item[2], is_h)[0] if item[2] is not None else 0.0)
            _rewrite_slots(beam, [(idx, link) for idx, link, _ in keep], is_h)
            entry(beam)["removidos"].extend(dropped)

    for name,cuts in clip_automatic_bottoms_to_solid_pillars(beam_list,pillar_report).items():
        report.setdefault(name, {'removidos':[], 'criados':[]})['pilares_solidos']=cuts

    # Fundo ja' reconhecido, por viga dona, para nao duplicar painel.
    claimed = [
        (poly, _norm_name(b.get("parent_name") or b.get("name")))
        for b in beam_list for _, _, poly in _panels(b) if poly is not None
    ]

    # 2) Trecho com as duas paredes e sem fundo ganha painel.
    for name, runs in runs_by_name.items():
        beam = owners.get(name)
        if beam is None:
            continue
        panels = _panels(beam)
        if _has_validated(panels):
            continue
        fv_is_h = bool(beam.get("fv_is_h", beam.get("is_h", True)))
        pair = FundoVigaInterpreter._parse_height_pair(
            (beam.get("fields") or {}).get("dimensao") or beam.get("dim")
        )
        additions: list[tuple[float, float, Any]] = []
        for run in runs:
            if run.angle or run.is_horizontal != fv_is_h:
                continue
            band = run.world_band()
            covered = []
            for poly, owner in claimed:
                if owner == name:
                    # Painel proprio conta pelo eixo mesmo deslocado na
                    # transversal (VF301: fundo 5 cm fora da faixa) — o gate
                    # D-60 o reancora; duplicar seria pior.
                    covered.append(_axis_span(poly, run.is_horizontal))
                    continue
                inter = poly.intersection(band)
                if inter.is_empty or inter.area <= 0:
                    continue
                minx, miny, maxx, maxy = inter.bounds
                depth = (maxy - miny) if run.is_horizontal else (maxx - minx)
                if depth >= 0.5 * run.width:
                    covered.append(_axis_span(inter, run.is_horizontal))
            # Nao recortar novamente pela caixa bruta do relatorio de pilares.
            # ``_wall_spans`` ja nasce da mesma cena que aplica as regras das
            # faces A/B (SOLIDO, NASCE, face curta/passante). Um segundo corte
            # aqui ignoraria a semantica da cena. Exclusoes de pilares da
            # propria cena permanecem; a hachura real e' tratada abaixo e
            # protege os casos em que a caixa declarada do pilar esta errada.
            covered.extend(_hatched_spans(run, all_segs))
            measured = _bottom_scene(run, runs_by_name, pillar_report)
            for a0, a1 in _subtract(_wall_spans(measured), [list(c) for c in covered]):
                if a1 - a0 > GEOMETRIC_EPS and _walls_are_real(run, a0, a1):
                    additions.append((a0, a1, run))
        if not additions:
            continue
        items: list[tuple[float, float, Optional[int], dict]] = []
        for idx, link, poly in panels:
            if poly is None:
                continue
            lo, hi = _axis_span(poly, fv_is_h)
            items.append((lo, hi, idx, link))
        created = []
        for a0, a1, run in additions:
            width = run.width  # two measured walls, never a neighbouring section
            touching = [
                i for i, (lo, hi, idx, link) in enumerate(items)
                if idx is not None and (abs(lo - a1) <= TOUCH_TOL or abs(hi - a0) <= TOUCH_TOL)
                and not link.get("special_geometry")
            ]
            if touching:
                i = touching[0]
                lo, hi, idx, _link = items[i]
                lo, hi = min(lo, a0), max(hi, a1)
                # A proven bridge joins BOTH neighbours; extending only the
                # first left an artificial seam through a NASCE symbol.
                joined = [i]
                for j in touching[1:]:
                    other_lo, other_hi, _, other_link = items[j]
                    other_poly = _polygon(other_link.get("points"))
                    if other_poly is not None and _frac(other_poly, run.world_band()) >= .99:
                        lo, hi = min(lo, other_lo), max(hi, other_hi)
                        joined.append(j)
                link = _rect_link(run, lo, hi, width)
                link["fv_lateral_reference_extends"] = idx
                items[i] = (lo, hi, idx, link)
                for j in sorted(joined[1:], reverse=True):
                    items.pop(j)
            else:
                items.append((a0, a1, None, _rect_link(run, a0, a1, width)))
            created.append([round(a0, 1), round(a1, 1)])
        if not created:
            continue
        items.sort(key=lambda item: item[0])
        _rewrite_slots(beam, [(idx, link) for _, _, idx, link in items], fv_is_h)
        # Cota por segmento (d94ce7be7) pode faltar numa instalacao atrasada:
        # sem ela os slots novos ficam com a dimensao da viga.
        assign_dims = getattr(FundoVigaInterpreter, "assign_segment_dimensions_from_texts", None)
        if assign_dims is not None:
            assign_dims(beam)
        for idx, link, _ in _panels(beam):
            dim = link.get('fv_measured_section_dim')
            key = f'viga_fundo_seg_{idx}_dim'
            if dim and key not in (beam.get('validated_fields') or []):
                beam.setdefault('fields', {})[key] = dim
                beam[key] = dim
        entry(beam)["criados"].extend(created)
        claimed.extend(
            (_polygon(link.get("points")), name) for _, _, _, link in items
            if link.get("fv_lateral_reference")
        )
    # 3) Viga DIAGONAL que ficou sem nenhum fundo (13_PAV: VF202, que so' tinha
    # os paineis da V306) ganha um painel na faixa diagonal medida pelas
    # laterais — as duas paredes tem de existir como linha real.
    for name, runs in runs_by_name.items():
        beam = owners.get(name)
        own = bands.get(name)
        if beam is None or own is None or not any(run.angle for run in runs):
            continue
        current = _panels(beam)
        # Painel fora da propria faixa nao e' fundo desta viga: o gate D-60 o
        # anularia de qualquer forma; aqui ele da' lugar ao da faixa medida.
        if _has_validated(current):
            continue
        # Um master pode juntar ocorrencias desconectadas do mesmo nome.
        # Recuperacao nova exige identidade local antes de unir orientacoes;
        # labels da cena horizontal sao cotas, por isso consultar textos fonte.
        from src.core.lv_beam_scene import BEAM_NAME_RE, LABEL_BAND_DIST
        run_bands = [run.world_band() for run in runs]
        components = list(range(len(runs)))

        def component(index):
            while components[index] != index:
                index = components[index]
            return index

        for i, first in enumerate(run_bands):
            for j in range(i):
                # Apenas contato fisico/submilimetrico; nao unir gap de cena.
                if first.distance(run_bands[j]) <= 0.1:
                    components[component(i)] = component(j)
        named_runs = []
        for text in texts or []:
            label = _norm_name(str(text.get("text") or ""))
            pos = text.get("pos")
            if label != name or not BEAM_NAME_RE.fullmatch(label) or not pos or len(pos) < 2:
                continue
            try:
                rotation = float(text.get("rotation") or 0.0) % 180.0
                point = Point(float(pos[0]), float(pos[1]))
            except (TypeError, ValueError):
                continue
            candidates = []
            for index, run in enumerate(runs):
                heading = (run.angle if run.angle else (0.0 if run.is_horizontal else 90.0)) % 180.0
                delta = abs(rotation - heading)
                if min(delta, 180.0 - delta) > 15.0:
                    continue
                x, y = run.to_local(point.x, point.y)
                axial = x if run.angle or run.is_horizontal else y
                extents = [run.face_extent.get(side) or (run.start, run.end) for side in ("A", "B")]
                lo = min(value for extent in extents for value in extent)
                hi = max(value for extent in extents for value in extent)
                distance = point.distance(run_bands[index])
                if lo - 0.1 <= axial <= hi + 0.1 and distance <= LABEL_BAND_DIST:
                    candidates.append((distance, index, heading))
            if candidates:
                _, index, heading = min(candidates)
                named_runs.append((component(index), heading, text.get("handle"), index))
        named_components = {item[0] for item in named_runs}
        mixed_component_orientations = any(
            min(abs(first.axis_angle - second.axis_angle) % 180.0,
                180.0 - abs(first.axis_angle - second.axis_angle) % 180.0) > 15.0
            for i, first in enumerate(runs) for j, second in enumerate(runs)
            if component(i) != component(j)
        )
        require_local_identity = bool(named_runs) and mixed_component_orientations
        # Um retorno ortogonal pertence a propria viga, mas nao cobre seu
        # corpo diagonal. Conservar seus contornos e decidir por faixa local,
        # sem trocar contorno rico/chanfrado que ja pertence ao run angular.
        retained = [(idx, link, poly) for idx, link, poly in current
                    if poly is not None and _frac(poly, own) >= 0.5]
        ordered = [(idx, link) for idx, link, _ in retained]
        created_diagonal = False
        for run_index, run in enumerate(runs):
            if not run.angle:
                continue
            band = run.world_band()
            if any(_frac(poly, band) >= 0.5 or _frac(band, poly) >= 0.5
                   for _, _, poly in retained):
                continue
            # Homonimos remotos nao vetam uma faixa local comprovada e nao
            # emprestam seu rotulo a outra faixa. A associacao acima mede
            # orientacao, projecao axial e distancia no CAD fonte, por run.
            local_labels = [item[2] for item in named_runs if item[3] == run_index]
            if require_local_identity and not local_labels:
                pending = entry(beam).setdefault("angular_identity_pending", {
                    "motivo": "run_angular_sem_rotulo_local_em_nome_desconectado",
                    "named_components": len(named_components),
                    "label_handles": [item[2] for item in named_runs],
                    "run_indices": [],
                })
                pending["run_indices"].append(run_index)
                continue
            ext_a = run.face_extent.get("A") or (run.start, run.end)
            ext_b = run.face_extent.get("B") or (run.start, run.end)
            if not all(
                run.line_coverage(side, *ext) >= WALL_COVERAGE_MIN
                for side, ext in (("A", ext_a), ("B", ext_b))
            ):
                continue
            pts = [run.point(ext_a[0], "A"), run.point(ext_a[1], "A"),
                   run.point(ext_b[1], "B"), run.point(ext_b[0], "B")]
            poly = _polygon(pts)
            if poly is None:
                continue
            length = max(abs(ext_a[1] - ext_a[0]), abs(ext_b[1] - ext_b[0]))
            link = {
                "type": "poly",
                "points": [list(p) for p in pts] + [list(pts[0])],
                "len": length,
                "closed": True,
                "geometry_role": "area_fundo",
                "geometry_source": SOURCE + "_special_diagonal",
                "fv_lateral_reference": True,
                "ficha": {
                    "comprimento_total_fundo": f"{length:.2f}".rstrip("0").rstrip("."),
                    "largura_total_fundo": f"{run.width:.2f}".rstrip("0").rstrip("."),
                },
            }
            ordered.append((None, link))
            created_diagonal = True
            if require_local_identity:
                entry(beam).setdefault("angular_local_identity", []).append({
                    "run_index": run_index,
                    "component_index": component(run_index),
                    "label_handles": local_labels,
                    "orientation": run.axis_angle,
                })
            entry(beam)["criados"].append([round(min(ext_a[0], ext_b[0]), 1), round(max(ext_a[1], ext_b[1]), 1)])
        if created_diagonal:
            retained_indices = {idx for idx, _, _ in retained}
            entry(beam)["removidos"].extend(
                idx for idx, _, _ in current if idx not in retained_indices
            )
            _rewrite_slots(beam, ordered, bool(beam.get("fv_is_h", beam.get("is_h", True))))
    # D-82: encontro a 90 graus conserva dois paineis independentes, mesmo
    # quando a perna incidente mede apenas 1 cm. Nao consumir a cauda no corpo.
    # Before D-60, slots may still be rejected/repositioned. Continuity is
    # meaningful only after that audit; do not let a provisional run steal
    # area that would disappear when its invalid slot is annulled.
    result = resolve_automatic_overlaps_all(beam_list, report, prefer_continuity=False)
    for name, cuts in clip_automatic_bottoms_to_solid_pillars(beam_list, pillar_report).items():
        result.setdefault(name, {}).setdefault("pilares_solidos", []).extend(cuts)
    return result


def complete_measured_junctions_all(beams, texts, lines, pillar_report, slabs=None):
    """Fill only locally witnessed junction cells after every re-anchoring step.

    Two arriving bottom panels and two measured non-parallel bands witness the
    junction. No free-space extrapolation: extension is at most the opposite
    band's width, and solid supports/hatch veto the cell.
    """
    from src.core.lv_beam_scene import build_scene_runs, _line_segments, _pillar_polygons
    from src.core.pillar_geometry_recovery import reconcile_pillar_source_geometry
    reconcile_pillar_source_geometry(pillar_report, lines, texts)
    runs = build_scene_runs(
        beams, texts, lines, pillar_report, slabs, allow_width_hint_fallback=True,
    )
    _bridge_cut_annotation_wall_gaps(runs, lines, texts)
    owners = {str(b.get("name")): b for b in beams}
    segs = _line_segments(lines)
    solids = [p for _, _, p in _pillar_polygons(pillar_report)]
    # A cut-view contour is a drawing annotation, never a physical support.
    # Its profile can inform levels/sections, but must not remove bottom area
    # or veto a junction. Actual pillar polygons remain solid obstacles.
    report = {}
    scenes = [r for rr in runs.values() for r in rr
              if r.provenance.get('band_source') != 'trecho_de_canto_em_L']
    for n, first in enumerate(scenes):
        for second in scenes[n + 1:]:
            delta = abs(first.axis_angle-second.axis_angle) % 180.
            if first.beam_name == second.beam_name or min(delta,180.-delta)<15.:
                continue
            b1, b2 = owners.get(first.beam_name), owners.get(second.beam_name)
            if b1 is None or b2 is None or _has_validated(_panels(b1)) or _has_validated(_panels(b2)):
                continue
            cell = first.world_band(second.width).intersection(second.world_band(first.width))
            if cell.area <= OVERLAP_AREA_TOL:
                continue
            # End supports remain outside FV. Incorrect uncertain boxes can
            # not be erased by a nearby NASCE symbol or by this fill.
            if any(cell.intersection(p).area > OVERLAP_AREA_TOL for p in solids):
                continue
            if any(_intersect([list(r.axis_bounds(r.to_local_geom(cell)))], _hatched_spans(r, segs))
                   for r in (first, second)):
                continue
            near = []
            for beam in (b1,b2):
                candidates = [(i,l,p) for i,l,p in _panels(beam)
                              if p is not None and p.distance(cell) <= .1]
                if not candidates:
                    break
                near.append((beam,candidates))
            if len(near) != 2:
                continue
            occupied = unary_union([p for b in beams for _,_,p in _panels(b) if p is not None])
            missing = cell.difference(occupied)
            if missing.area <= OVERLAP_AREA_TOL:
                continue
            beam,candidates = max(near,key=lambda bc:max(
                _panel_overlap_priority(bc[0],i,l,_panels(bc[0]),
                                        run=first if bc[0] is b1 else second,
                                        source_runs=runs.get(str(bc[0].get('name')), []))[:5]
                for i,l,p in bc[1]))
            i,link,poly = max(candidates,key=lambda v:v[2].area)
            # Snapping can create a self-intersection; repair before union,
            # since GEOS cannot union invalid inputs (repairing afterwards
            # never runs when union itself raises a TopologyException).
            merged = make_valid(poly.union(make_valid(snap(missing, poly, .05))))
            parts = _polygon_parts(merged)
            if len(parts) != 1:
                # A witnessed junction fill can miss its owner's rounded
                # vertex by microns. Snap in both directions, adding only
                # material inside the measured cell, without moving the arm.
                contact = make_valid(snap(poly, missing, .05)).intersection(cell)
                merged = make_valid(unary_union([poly, merged, contact]))
                parts = _polygon_parts(merged)
            if len(parts) != 1:
                # Snap only matches vertices, not rounded vertex-on-edge
                # contacts. Close sub-.05cm contacts inside this proven cell;
                # union with the original so no material can be eroded.
                contact = merged.buffer(.025, join_style=2).buffer(-.025, join_style=2)
                merged = make_valid(merged.union(contact.intersection(cell)))
                parts = _polygon_parts(merged)
            if len(parts) != 1:
                continue
            new_link = dict(link,points=[list(p) for p in parts[0].exterior.coords],
                            fv_junction_reference=True, fv_lateral_reference=True)
            own_run=first if beam is b1 else second
            lo,hi=own_run.axis_bounds(own_run.to_local_geom(parts[0]))
            new_link['len']=hi-lo
            new_link['ficha']=dict(link.get('ficha') or {},comprimento_total_fundo=f'{hi-lo:.2f}'.rstrip('0').rstrip('.'))
            new_link.pop('fv_provenance',None)
            _rewrite_slots(beam,[(idx,new_link if idx==i else l) for idx,l,_ in _panels(beam)],
                           bool(beam.get("fv_is_h",beam.get("is_h",True))))
            report.setdefault(beam['name'],[]).append({'com':second.beam_name if beam is b1 else first.beam_name,
                                                       'area_cm2':round(missing.area,3)})
    # A measured corner stub is part of the diagonal owner's L, not the beam
    # ending on the opposite face of the solid support.
    for name,rr in runs.items():
        beam=owners.get(name)
        if beam is None or _has_validated(_panels(beam)):
            continue
        for stub in rr:
            if stub.provenance.get('band_source') != 'trecho_de_canto_em_L':
                continue
            for i,link,poly in _panels(beam):
                if poly is None or not any(r.angle for r in rr) or poly.distance(stub.world_band()) > 1.:
                    continue
                # The gate can retain a separate rectangle of this measured
                # stub. It is not the diagonal body receiving the corner;
                # do not let it consume the closure merely by slot order.
                if stub.world_band().buffer(.15).covers(poly):
                    continue
                coords=list(poly.exterior.coords)
                caps=[]
                for t in (stub.t_lo,stub.t_hi):
                    matching=[(y if not stub.is_horizontal else x) for x,y in coords
                              if abs((x if not stub.is_horizontal else y)-t)<.1
                              and min(abs((y if not stub.is_horizontal else x)-stub.start),
                                      abs((y if not stub.is_horizontal else x)-stub.end))<=stub.width]
                    if not matching:break
                    caps.append(min(matching,key=lambda a:min(abs(a-stub.start),abs(a-stub.end))))
                if len(caps)!=2:continue
                endpoint=stub.end if abs(sum(caps)/2-stub.start)<abs(sum(caps)/2-stub.end) else stub.start
                points=[stub.to_world(*((a,t) if stub.is_horizontal else (t,a)))
                        for a,t in ((caps[0],stub.t_lo),(caps[1],stub.t_hi),(endpoint,stub.t_hi),(endpoint,stub.t_lo))]
                extension=Polygon(points)
                merged=make_valid(poly.union(extension))
                parts=_polygon_parts(merged)
                if len(parts)!=1:continue
                new_link=dict(link,points=[list(p) for p in parts[0].exterior.coords],
                              fv_lateral_reference=True,special_geometry='diagonal_corner_l')
                new_link.pop('fv_provenance',None)
                _rewrite_slots(beam,[(idx,new_link if idx==i else l) for idx,l,_ in _panels(beam)],
                               bool(beam.get('fv_is_h',beam.get('is_h',True))))
                report.setdefault(name,[]).append({'canto_em_l':True,'area_cm2':round(extension.difference(poly).area,3)})
                break
    _chamfer_arriving_junctions(beams, runs, solids, report)
    for name, cuts in clip_automatic_bottoms_to_solid_pillars(beams, pillar_report).items():
        report.setdefault(name, []).extend({"pilar_solido": cut} for cut in cuts)
    _optimize_unmarked_junctions(beams, runs, lines, solids, report)
    _merge_unsupported_section_seams(beams, runs, lines, report)
    _refresh_measured_panel_sections(beams, runs)
    return report


def _merge_unsupported_section_seams(beams, runs, lines, report):
    """Remove automatic seams not located at a source section transition.

    Conflicting callouts remain recorded on the combined contour. A field
    conflict alone cannot invent a short physical panel at an unrelated point.
    Never bridge openings, source dividers, manual geometry or differing levels.
    """
    from src.core.lv_beam_scene import _line_segments
    from shapely.geometry import LineString
    edges = [LineString([(x,y),(a,b)]) for x,y,a,b in _line_segments(lines)]
    for beam in beams:
        panels = _panels(beam)
        if beam.get('is_validated') or beam.get('validated_fields') or _has_validated(panels):
            continue
        is_h = bool(beam.get('fv_is_h', beam.get('is_h', True)))
        result = []
        merged = 0
        for idx, link, poly in sorted(panels, key=lambda p: _axis_span(p[2],is_h)[0] if p[2] is not None else 0):
            protected = lambda l: l.get('manual') or l.get('special_geometry') or str(l.get('geometry_source','')).startswith('manual')
            if not result or poly is None or protected(link):
                result.append((idx,link)); continue
            prev_idx, prev_link = result[-1]
            prev = _polygon(prev_link.get('points'))
            if prev is None or protected(prev_link):
                result.append((idx,link)); continue
            seam = _axis_span(prev,is_h)[1]
            transverse = (1,3) if is_h else (0,2)
            same_band = all(abs(prev.bounds[k]-poly.bounds[k]) <= .05 for k in transverse)
            rectangular = all(p.envelope.difference(p).area <= .05*p.length for p in (prev,poly))
            candidate = next((r for r in runs.get(beam.get('name'),[]) if not r.angle
                              and r.world_band().buffer(.05).covers(prev.union(poly))
                              and any(z['start']+.05 < seam < z['end']-.05 for z in r.sections)),None)
            if (not same_band or not rectangular or abs(_axis_span(poly,is_h)[0]-seam) > .05 or candidate is None):
                result.append((idx,link)); continue
            seam_line = LineString([candidate.point(seam,'A'),candidate.point(seam,'B')])
            if any(e.intersection(seam_line.buffer(.05)).length > .15 for e in edges):
                result.append((idx,link)); continue
            fields = beam.get('fields') or {}
            conflict = False
            for store in (fields,beam):
                a = {m.group(2):v for k,v in store.items() if (m:=_SEG_KEY_RE.match(str(k))) and int(m.group(1))==prev_idx}
                b = {m.group(2):v for k,v in store.items() if (m:=_SEG_KEY_RE.match(str(k))) and int(m.group(1))==idx}
                if any(a[k]!=b[k] for k in a.keys() & b.keys() if k not in ('exists','dim')):
                    conflict = True
            if conflict:
                result.append((idx,link)); continue
            combined = dict(prev_link)
            union = prev.union(poly)
            combined.update(points=[list(p) for p in union.envelope.exterior.coords],
                            len=_axis_span(union,is_h)[1]-_axis_span(union,is_h)[0],
                            fv_unmarked_section_seam_merged=True)
            refs = [dict(z) for z in candidate.sections if z['end']>_axis_span(union,is_h)[0] and z['start']<_axis_span(union,is_h)[1]]
            combined['fv_source_section_references'] = refs
            dims = {z.get('dim') for z in refs}
            if len(dims)>1:
                combined['fv_section_transition_unlocated'] = True
                combined.pop('fv_measured_section_dim',None)
            keep_idx = prev_idx if prev.area >= poly.area else idx
            result[-1] = (keep_idx,combined)
            merged += 1
        if merged:
            _rewrite_slots(beam,result,is_h)
            report.setdefault(beam['name'],[]).append({'costuras_sem_transicao_removidas':merged})


def _refresh_measured_panel_sections(beams, runs):
    """Source-local section facts override unvalidated stale segment dimensions."""
    for beam in beams:
        for idx,link,poly in _panels(beam):
            if (poly is None or link.get('manual') or link.get('validated')
                    or str(link.get('geometry_source','')).startswith('manual')):
                continue
            key=f'viga_fundo_seg_{idx}_dim'
            if key in (beam.get('validated_fields') or []) or beam.get('is_validated'):
                continue
            candidates=[]
            for run in runs.get(beam.get('name'),[]):
                overlap=poly.intersection(run.world_band()).area
                if overlap < .8*poly.area:
                    continue
                local=run.to_local_geom(poly);lo,hi=run.axis_bounds(local)
                sections={z.get('dim') for z in run.sections if z['end']>lo+.05 and z['start']<hi-.05}
                if len(sections)==1 and None not in sections:
                    candidates.append(next(iter(sections)))
            if len(set(candidates))==1:
                dim=candidates[0]
                beam.setdefault('fields',{})[key]=beam[key]=dim
                link['fv_measured_section_dim']=dim


def _optimize_unmarked_junctions(beams, runs, lines, obstacles, report):
    """Reassign an occupied, unmarked equal-depth junction to reduce panels.

    No new material, no erased gap, no L-shaped rectangle approximation.
    A source line on the proposed seam vetoes reassignment. Different depths
    retain structural priority; validated/manual contours remain untouched.
    """
    from src.core.lv_beam_scene import _line_segments
    from shapely.geometry import box, LineString
    owners = {b.get('name'): b for b in beams}
    scenes = [r for rr in runs.values() for r in rr if not r.angle]
    structural = [LineString([(x,y),(a,b)]) for x,y,a,b in _line_segments(lines)]
    for j, first in enumerate(scenes):
        for second in scenes[j+1:]:
            if first.beam_name == second.beam_name or first.is_horizontal == second.is_horizontal:
                continue
            pair = [owners.get(r.beam_name) for r in (first, second)]
            if any(b is None or _has_validated(_panels(b)) or any(l.get('manual') or str(l.get('geometry_source','')).startswith('manual') for _,l,_ in _panels(b)) for b in pair):
                continue
            cell = first.world_band(second.width).intersection(second.world_band(first.width))
            if cell.is_empty or cell.area <= OVERLAP_AREA_TOL:
                continue
            nearby = [[p for p in _panels(b) if p[2] is not None and p[2].distance(cell) <= .05] for b in pair]
            if any(not pp for pp in nearby):
                continue
            coords = [xy for pp in nearby for _,_,p in pp for xy in p.exterior.coords]
            # Align only independent sub-.05 cm coordinate rounding.
            bounds = []
            for k,a in enumerate(cell.bounds):
                near = [p[k%2] for p in coords if abs(p[k%2]-a)<=.05]
                bounds.append((min(near) if k<2 else max(near)) if near else a)
            cell = box(*bounds)
            if any(cell.intersection(p).area > OVERLAP_AREA_TOL for p in obstacles):
                continue
            zones = [r.section_at(r.local_axis(cell.centroid.x,cell.centroid.y)) or {} for r in (first,second)]
            if any(z.get('depth') is None for z in zones) or abs(zones[0]['depth']-zones[1]['depth']) > .01:
                continue
            if any(any(abs(float(z.get('depth',0))-float(zone.get('depth',0))) > .01
                       for z in r.sections
                       if any(min(z['end'],r.local_axis(p.bounds[2],p.bounds[3]))
                              -max(z['start'],r.local_axis(p.bounds[0],p.bounds[1])) > .05
                              for _,_,p in pp))
                   for r,pp,zone in zip((first,second),nearby,zones)):
                continue  # joining different sections would erase their local facts
            original = [unary_union([p for _,_,p in pp]) for pp in nearby]
            existing_seam = original[0].boundary.intersection(original[1].boundary).intersection(cell.buffer(.05))
            if existing_seam.length and any(edge.intersection(existing_seam.buffer(.05)).length > .15 for edge in structural):
                continue  # never erase a divider already witnessed by the DXF
            union = unary_union(original)
            precision_area = cell.difference(union).area
            if precision_area > .05*cell.boundary.length or not union.buffer(.05,join_style=2).covers(cell):
                continue
            third = [p for b in beams if all(b is not own for own in pair) for _,_,p in _panels(b) if p is not None]
            if any(cell.intersection(p).area > OVERLAP_AREA_TOL for p in third):
                continue
            def partition_rank(parts):
                lengths = [max(r.local_axis(x, y) for x, y in p.exterior.coords)
                           - min(r.local_axis(x, y) for x, y in p.exterior.coords)
                           for r, polygons in zip((first, second), parts) for p in polygons]
                short = [length for length in lengths if length < 60. - .05]
                # Equal depths only: panel count wins, then avoid short pieces.
                # This preference never removes a necessary short panel.
                return (sum(map(len, parts)), len(short), sum(60. - length for length in short))

            baseline_parts = [[p for _, _, p in pp] for pp in nearby]
            baseline_rank = partition_rank(baseline_parts)
            baseline = baseline_rank[0]
            choices = []
            for winner in (0,1):
                shapes = [original[k].union(cell) if k==winner else original[k].difference(cell) for k in (0,1)]
                parts = [_polygon_parts(make_valid(p)) for p in shapes]
                if any(p.difference(r.world_band(r.width).buffer(.05,join_style=2)).area > .01
                       for r,pp in zip((first,second),parts) for p in pp):
                    continue  # cannot turn a straight run into an L
                if unary_union(shapes).symmetric_difference(union).area > precision_area+OVERLAP_AREA_TOL:
                    continue
                count = sum(map(len,parts))
                rank = partition_rank(parts)
                if rank >= baseline_rank:
                    continue
                seam = shapes[0].boundary.intersection(shapes[1].boundary)
                if seam.length and any(edge.intersection(seam.buffer(.05)).length > .15 for edge in structural):
                    continue
                choices.append((rank,winner,parts))
            if not choices:
                continue
            _,winner,parts = min(choices,key=lambda c:(c[0],-zones[c[1]].get('width',0)))
            for k,b in enumerate(pair):
                replaced = {idx for idx,_,_ in nearby[k]}
                ordered = [(idx,l) for idx,l,_ in _panels(b) if idx not in replaced]
                for p in parts[k]:
                    idx,old,_ = max(nearby[k],key=lambda v:v[2].intersection(p).area)
                    lo,hi = _axis_span(p, bool(b.get('fv_is_h',b.get('is_h',True))))
                    link = copy.deepcopy(old)
                    link.update(points=[list(xy) for xy in p.exterior.coords],len=hi-lo,fv_unmarked_junction_optimized=True)
                    link['ficha'] = dict(link.get('ficha') or {},comprimento_total_fundo=f'{hi-lo:.2f}'.rstrip('0').rstrip('.'))
                    link.pop('fv_provenance',None)
                    ordered.append((idx,link))
                ordered.sort(key=lambda x:_axis_span(_polygon(x[1]['points']),bool(b.get('fv_is_h',b.get('is_h',True))))[0])
                _rewrite_slots(b,ordered,bool(b.get('fv_is_h',b.get('is_h',True))))
                report.setdefault(b['name'],[]).append({'cruzamento_sem_divisoria':pair[1-k]['name'],'dono':pair[winner]['name'],'paineis_antes':baseline,'paineis_depois':sum(map(len,parts)), 'arredondamento_area_cm2':round(precision_area,6)})


def _chamfer_arriving_junctions(beams, runs, solids, report):
    """D-85/FV: repartition an angled arrival, never extrapolate its outline.

    A cross has material continuing on BOTH sides of its node and is not an
    elbow. Different beam names stay different panels. A genuine same-owner
    bend is not repartitioned here (D-82). Only witnessed, equal-depth end
    junctions with a reflex notch may exchange area along a straight cut.
    """
    import math
    from itertools import combinations
    from shapely.geometry import LineString
    from shapely.ops import split

    _stepped_collinear_junctions(beams, runs, solids, report)

    owners = {str(b.get('name')): b for b in beams}
    scenes = [r for rr in runs.values() for r in rr
              if r.provenance.get('band_source') != 'trecho_de_canto_em_L']

    def notch_score(poly, window):
        if poly.geom_type != 'Polygon' or poly.interiors:
            return (1000, 1000)
        poly = poly.simplify(.05, preserve_topology=True)
        pts = list(poly.exterior.coords)[:-1]
        signed = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(pts, pts[1:]+pts[:1]))
        orientation = 1 if signed > 0 else -1
        reflex = 0
        corners = 0
        for n,p in enumerate(pts):
            if not window.covers(Point(p)):
                continue
            a,b=pts[n-1],pts[(n+1)%len(pts)]
            u,v=(p[0]-a[0],p[1]-a[1]),(b[0]-p[0],b[1]-p[1])
            scale=math.hypot(*u)*math.hypot(*v)
            cross=(u[0]*v[1]-u[1]*v[0])*orientation
            # Submillimetric vertices are rounding, not a physical notch.
            if min(math.hypot(*u),math.hypot(*v)) < .05 or abs(cross) < .01*scale:
                continue
            corners += 1
            if cross < 0:
                reflex += 1
        return reflex, corners

    def parallel_seam(p,q,r1,r2,window):
        seam=p.boundary.intersection(q.boundary).intersection(window)
        parts=list(getattr(seam,'geoms',[seam]))
        for part in parts:
            if part.geom_type!='LineString' or part.length<.1:
                continue
            a,b=part.coords[0],part.coords[-1]
            angle=math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))%180
            if any(min(abs(angle-r.axis_angle),180-abs(angle-r.axis_angle))<1 for r in (r1,r2)):
                return 1
        return 0

    windows=[]
    for first,second in combinations(scenes,2):
        delta=abs(first.axis_angle-second.axis_angle)%180
        delta=min(delta,180-delta)
        if first.beam_name==second.beam_name or delta<15 or abs(delta-90)<1:
            continue
        cell=first.world_band(second.width).intersection(second.world_band(first.width))
        if cell.is_empty or cell.area<=OVERLAP_AREA_TOL:
            continue
        center=cell.centroid
        # Endpoint evidence distinguishes an arrival from a through cross.
        if any(min(abs(r.local_axis(center.x,center.y)-r.start),
                   abs(r.local_axis(center.x,center.y)-r.end))>2*max(first.width,second.width)
               for r in (first,second)):
            continue
        window=cell.buffer(max(first.width,second.width),join_style=2)
        if any(cell.intersection(p).area>OVERLAP_AREA_TOL for p in solids):
            continue
        windows.append(window)

    for window in windows:
        for _ in range(8):
            entries=[]
            for name,rr in runs.items():
                beam=owners.get(name)
                if beam is None or _has_validated(_panels(beam)):
                    continue
                for i,link,poly in _panels(beam):
                    if poly is None or poly.geom_type!='Polygon' or poly.intersection(window).area<=.01:
                        continue
                    own=[r for r in rr if r.provenance.get('band_source')!='trecho_de_canto_em_L'
                         and poly.intersection(r.world_band()).area>.01]
                    if own:
                        entries.append((beam,i,link,poly,max(own,key=lambda r:poly.intersection(r.world_band()).area)))
            best=None
            for first,second in combinations(entries,2):
                b1,i1,l1,p1,r1=first
                b2,i2,l2,p2,r2=second
                if (l1.get('fv_single_cut_triple') or l2.get('fv_single_cut_triple') or
                        (l1.get('fv_stepped_junction') and l2.get('fv_stepped_junction'))):
                    continue
                if b1 is b2 or p1.distance(p2)>.05:
                    continue
                delta=abs(r1.axis_angle-r2.axis_angle)%180
                if abs(min(delta,180-delta)-90)<1:
                    continue
                c=window.centroid
                if any(min(abs(r.local_axis(c.x,c.y)-r.start),
                           abs(r.local_axis(c.x,c.y)-r.end))>2*max(r1.width,r2.width)
                       for r in (r1,r2)):
                    continue
                def depth(beam,index,link,run):
                    c=window.centroid
                    axis=max(run.start,min(run.end,run.local_axis(c.x,c.y)))
                    section=run.section_at(axis)
                    return float((section or {}).get('depth') or
                                 _panel_overlap_priority(beam,index,link,_panels(beam))[1])
                h1=depth(b1,i1,l1,r1)
                h2=depth(b2,i2,l2,r2)
                if h1<=0 or abs(h1-h2)>.01:
                    continue
                shape_before=tuple(sum(s) for s in zip(notch_score(p1,window),notch_score(p2,window)))
                before=(shape_before[0],parallel_seam(p1,p2,r1,r2,window),shape_before[1])
                if before[0]==0 and before[1]==0 and before[2]<=4:
                    continue
                union=make_valid(p1.union(p2))
                if union.geom_type!='Polygon' or union.interiors:
                    continue
                pts=[tuple(p) for p in union.exterior.coords[:-1] if window.covers(Point(p))]
                pts += [tuple(p) for p in union.simplify(.05, preserve_topology=True).exterior.coords[:-1]
                        if window.covers(Point(p))]
                # A third arm may meet halfway along the straight chamfer.
                edge_pts=list(union.exterior.coords)
                pts += [((a[0]+b[0])/2,(a[1]+b[1])/2) for a,b in zip(edge_pts,edge_pts[1:])
                        if window.covers(Point(a)) and window.covers(Point(b))]
                pts=list(dict.fromkeys(pts))
                anchor1=p1.difference(window)
                anchor2=p2.difference(window)
                if anchor1.is_empty or anchor2.is_empty:
                    continue
                seed1,seed2=anchor1.representative_point(),anchor2.representative_point()
                reach=2*math.hypot(union.bounds[2]-union.bounds[0],union.bounds[3]-union.bounds[1])+1
                for a,b in combinations(pts,2):
                    dx,dy=b[0]-a[0],b[1]-a[1]
                    length=math.hypot(dx,dy)
                    if length<.1:
                        continue
                    dx,dy=dx/length,dy/length
                    cutter=LineString([(a[0]-reach*dx,a[1]-reach*dy),(a[0]+reach*dx,a[1]+reach*dy)])
                    parts=_polygon_parts(split(union,cutter))
                    if len(parts)!=2:
                        continue
                    q1=next((p for p in parts if p.covers(seed1)),None)
                    q2=next((p for p in parts if p.covers(seed2)),None)
                    if q1 is None or q2 is None or q1 is q2:
                        continue
                    changed=p1.symmetric_difference(q1)
                    if changed.difference(window).area>.01:
                        continue
                    shape_after=tuple(sum(s) for s in zip(notch_score(q1,window),notch_score(q2,window)))
                    after=(shape_after[0],parallel_seam(q1,q2,r1,r2,window),shape_after[1])
                    if after>=before:
                        continue
                    score=tuple(a-b for a,b in zip(after,before))+(changed.area,)
                    if best is None or score<best[0]:
                        best=(score,first,second,q1,q2)
            if best is None:
                break
            _,first,second,q1,q2=best
            for (beam,i,link,poly,run),new in ((first,q1),(second,q2)):
                lo,hi=run.axis_bounds(run.to_local_geom(new))
                updated=dict(link,points=[list(p) for p in new.exterior.coords],
                             fv_junction_chamfer=True,fv_lateral_reference=True,len=hi-lo)
                updated['ficha']=dict(link.get('ficha') or {},comprimento_total_fundo=f'{hi-lo:.2f}'.rstrip('0').rstrip('.'))
                updated.pop('fv_provenance',None)
                _rewrite_slots(beam,[(idx,updated if idx==i else l) for idx,l,_ in _panels(beam)],
                               bool(beam.get('fv_is_h',beam.get('is_h',True))))
                report.setdefault(beam['name'],[]).append({'chanfro_de_encontro':True,
                                                         'area_redistribuida_cm2':round(poly.symmetric_difference(new).area,3)})
    # Fresh DXF bands may only become a connected witnessed union after the
    # pairwise arrival seams above. Resolve the three-owner width transition
    # again before the generic triple split; already resolved slots are inert.
    _stepped_collinear_junctions(beams, runs, solids, report)
    _single_cut_triple_junctions(beams, runs, solids, report)


def _stepped_collinear_junctions(beams, runs, solids, report):
    """Three end arrivals: narrower continuation stops at the branch wall.

    Use the witnessed union's corners, not an equal split of a guessed nose.
    The wider continuation and branch share a single full-width chord. This
    only repartitions existing material: no external outline or other slot moves.
    """
    import math
    from itertools import combinations, product
    from shapely.geometry import LineString
    from shapely.ops import split

    entries = []
    for beam in beams:
        if _has_validated(_panels(beam)):
            continue
        rr = [r for r in runs.get(str(beam.get('name')), [])
              if r.provenance.get('band_source') != 'trecho_de_canto_em_L']
        for idx, link, poly in _panels(beam):
            if poly is not None and poly.geom_type == 'Polygon' and rr:
                scene = max(rr, key=lambda r: poly.intersection(r.world_band()).area)
                entries.append((beam, idx, link, poly, scene))

    def delta(r, s):
        d = abs(r.axis_angle-s.axis_angle) % 180
        return min(d, 180-d)

    for pair in combinations(entries, 2):
        wide, narrow = sorted(pair, key=lambda e: e[4].width, reverse=True)
        rw, rn = wide[4], narrow[4]
        if wide[0] is narrow[0] or delta(rw, rn) > 1 or rw.width-rn.width < .1:
            continue
        for branch in entries:
            rb = branch[4]
            group = [wide, narrow, branch]
            if len({id(e[0]) for e in group}) != 3 or any(
                    e[2].get('fv_stepped_junction') for e in group):
                continue
            angle = delta(rw, rb)
            if angle < 15 or abs(angle-90) < 1 or abs(rb.width-rw.width) > .1:
                continue
            cell = rw.world_band(rb.width).intersection(rb.world_band(rw.width))
            if cell.is_empty or cell.area <= OVERLAP_AREA_TOL:
                continue
            center = cell.centroid
            radius = 2*max(rw.width, rb.width)
            if any(min(abs(e[4].local_axis(center.x, center.y)-e[4].start),
                       abs(e[4].local_axis(center.x, center.y)-e[4].end)) > radius
                   for e in group):
                continue
            window = cell.buffer(max(rw.width, rb.width), join_style=2)
            if any(window.intersection(s).area > OVERLAP_AREA_TOL for s in solids):
                continue
            anchors = [e[3].difference(window) for e in group]
            if any(a.is_empty for a in anchors):
                continue
            seeds = [a.representative_point() for a in anchors]
            # Collinear arms must arrive from opposite directions, not overlap.
            if (rw.local_axis(seeds[0].x, seeds[0].y)-rw.local_axis(center.x, center.y)) * (
                    rw.local_axis(seeds[1].x, seeds[1].y)-rw.local_axis(center.x, center.y)) >= 0:
                continue
            depths = []
            for owner, idx, link, poly, scene in group:
                section = scene.section_at(scene.local_axis(center.x, center.y)) or {}
                depths.append(float(section.get('depth') or
                                    _panel_overlap_priority(owner, idx, link, _panels(owner))[1]))
            if min(depths) <= 0 or max(depths)-min(depths) > .01:
                continue
            original = unary_union([e[3] for e in group])
            # Independently measured DXF bands may miss by hundredths of a
            # millimetre. Bridge only snapped material inside the witnessed
            # crossing cell; never erode existing material or move outer arms.
            closure_area = 0.
            if original.geom_type == 'MultiPolygon' or (original.geom_type == 'Polygon' and original.interiors):
                additions = [make_valid(snap(e[3], unary_union(
                    [other[3] for other in group if other is not e]), .05)).intersection(cell)
                    for e in group]
                closed = unary_union([original, *additions])
                contact = closed.buffer(.025, join_style=2).buffer(-.025, join_style=2)
                closed = closed.union(contact.intersection(cell))
                closure_area = closed.difference(original).area
                if closed.difference(original.buffer(.05)).area > .01:
                    continue
                original = closed
            if original.geom_type != 'Polygon' or original.interiors:
                continue
            reach = 4*math.hypot(original.bounds[2]-original.bounds[0],
                                original.bounds[3]-original.bounds[1])+1
            # First cut: the branch wall facing the narrower continuation.
            near_t = min((rb.t_lo, rb.t_hi), key=lambda t: abs(
                (rb.to_local(seeds[1].x, seeds[1].y)[1 if rb.is_horizontal else 0])-t))
            wall = LineString([rb.to_world(*((s, near_t) if rb.is_horizontal else (near_t, s)))
                               for s in (-reach, reach)])
            parts = _polygon_parts(split(original, wall))
            small = next((p for p in parts if p.covers(seeds[1])), None)
            rest = next((p for p in parts if p.covers(seeds[0]) and p.covers(seeds[2])), None)
            if len(parts) != 2 or small is None or rest is None or small is rest:
                continue
            pts = list(original.simplify(.05, preserve_topology=True).exterior.coords)[:-1]
            # The correct seam uses both measured continuation walls. Their
            # intersections can lie inside a union edge, not at a union vertex.
            for t in (rw.t_lo, rw.t_hi):
                diagonal = LineString([rw.to_world(*((s,t) if rw.is_horizontal else (t,s)))
                                       for s in (-reach, reach)])
                for branch_t in (rb.t_lo, rb.t_hi):
                    branch_wall = LineString([rb.to_world(*((s,branch_t) if rb.is_horizontal else (branch_t,s)))
                                              for s in (-reach, reach)])
                    hit = diagonal.intersection(branch_wall)
                    if hit.geom_type == 'Point' and window.covers(hit):
                        pts.append((hit.x, hit.y))
            walls = [[p for p in pts if window.covers(Point(p)) and abs(
                rb.to_local(*p)[1 if rb.is_horizontal else 0]-t) < .05]
                     for t in (rb.t_lo, rb.t_hi)]
            candidates = []
            for a, b in product(*walls):
                continuation_t = [rw.to_local(*p)[1 if rw.is_horizontal else 0] for p in (a,b)]
                if not (min(abs(continuation_t[0]-rw.t_lo), abs(continuation_t[0]-rw.t_hi)) < .05
                        and min(abs(continuation_t[1]-rw.t_lo), abs(continuation_t[1]-rw.t_hi)) < .05
                        and abs(continuation_t[0]-continuation_t[1]) > rw.width-.1):
                    continue
                dx, dy = b[0]-a[0], b[1]-a[1]
                length = math.hypot(dx, dy)
                if length <= .05:
                    continue
                cutter = LineString([(a[0]-reach*dx/length, a[1]-reach*dy/length),
                                     (a[0]+reach*dx/length, a[1]+reach*dy/length)])
                halves = _polygon_parts(split(rest, cutter))
                large = next((p for p in halves if p.covers(seeds[0])), None)
                side = next((p for p in halves if p.covers(seeds[2])), None)
                if len(halves) != 2 or large is None or side is None or large is side:
                    continue
                proposed = [large, small, side]
                if any(p.interiors or not p.is_valid for p in proposed):
                    continue
                if any(old[3].symmetric_difference(new).difference(window).area > .01
                       for old, new in zip(group, proposed)):
                    continue
                if unary_union(proposed).symmetric_difference(original).area > 1e-6:
                    continue
                if any(p.intersection(q).area > 1e-6 for k, p in enumerate(proposed)
                       for q in proposed[k+1:]):
                    continue
                # Keep both diagonal arms inside their measured wall strips.
                def infinite_band(scene):
                    return Polygon([scene.to_world(*((s,t) if scene.is_horizontal else (t,s)))
                                    for s,t in ((-reach,scene.t_lo),(reach,scene.t_lo),
                                                (reach,scene.t_hi),(-reach,scene.t_hi))])
                spill = sum(p.intersection(window).difference(infinite_band(r).buffer(.05)).area
                            for p,r in ((large,rw),(small,rn)))
                if spill > .05:
                    continue
                candidates.append((length, proposed))
            if not candidates:
                continue
            proposed = min(candidates, key=lambda c: c[0])[1]
            for entry, new in zip(group, proposed):
                owner, idx, panel, old, scene = entry
                lo, hi = scene.axis_bounds(scene.to_local_geom(new))
                updated = dict(panel, points=[list(p) for p in new.exterior.coords],
                               fv_stepped_junction=True, fv_junction_chamfer=True,
                               fv_lateral_reference=True, len=hi-lo)
                updated['ficha'] = dict(panel.get('ficha') or {},
                                       comprimento_total_fundo=f'{hi-lo:.2f}'.rstrip('0').rstrip('.'))
                updated.pop('fv_provenance', None)
                _rewrite_slots(owner, [(i, updated if i == idx else l) for i,l,_ in _panels(owner)],
                               bool(owner.get('fv_is_h', owner.get('is_h', True))))
                report.setdefault(owner['name'], []).append({'encontro_colinear_secao_muda': True,
                    'area_redistribuida_cm2': round(old.symmetric_difference(new).area, 3),
                    'fechamento_precision_cm2': round(closure_area, 3)})
            return _stepped_collinear_junctions(beams, runs, solids, report)


def _single_cut_triple_junctions(beams, runs, solids, report):
    """D-85/FV adendo: replace a three-owner nose by one full-width chord.

    The removed tip is shared between its two actual neighbours, not erased.
    Only equal-depth end arrivals qualify; protected panels and through crosses
    are excluded. No beam names, floor coordinates or minimum panel lengths.
    """
    import math
    from shapely.geometry import LineString, Polygon
    from shapely.ops import split, unary_union

    entries = []
    for beam in beams:
        if _has_validated(_panels(beam)):
            continue
        for index, link, poly in _panels(beam):
            rr = [r for r in runs.get(str(beam.get('name')), [])
                  if r.provenance.get('band_source') != 'trecho_de_canto_em_L']
            if poly is not None and poly.geom_type == 'Polygon' and rr:
                run = max(rr, key=lambda r: poly.intersection(r.world_band()).area)
                entries.append((beam, index, link, poly, run))

    for target in entries:
        beam, index, link, poly, run = target
        if link.get('fv_single_cut_triple') or link.get('fv_stepped_junction'):
            continue
        pts = list(poly.simplify(.05, preserve_topology=True).exterior.coords)[:-1]
        for n, c in enumerate(pts):
            a, b = pts[n-1], pts[(n+1) % len(pts)]
            local = [run.to_local(*p) for p in (a, c, b)]
            axes = [p[0 if run.is_horizontal else 1] for p in local]
            transverse = [p[1 if run.is_horizontal else 0] for p in local]
            # Both ends of the chord must be witnessed opposite beam walls.
            if min(abs(transverse[0]-run.t_lo)+abs(transverse[2]-run.t_hi),
                   abs(transverse[0]-run.t_hi)+abs(transverse[2]-run.t_lo)) > .1:
                continue
            if not (axes[1] < min(axes[0], axes[2])-.05 or
                    axes[1] > max(axes[0], axes[2])+.05):
                continue
            tip = Polygon([a, c, b])
            if not tip.is_valid or tip.area <= OVERLAP_AREA_TOL:
                continue
            if tip.difference(poly).area > 1e-6 or any(
                    tip.intersection(s).area > OVERLAP_AREA_TOL for s in solids):
                continue
            neighbors = []
            for edge in (LineString([a, c]), LineString([c, b])):
                candidates = [e for e in entries if e[0] is not beam and
                              edge.intersection(e[3].boundary.buffer(.01)).length > .95*edge.length]
                if len(candidates) != 1:
                    break
                neighbors.append(candidates[0])
            if len(neighbors) != 2 or neighbors[0][0] is neighbors[1][0]:
                continue
            group = [target] + neighbors
            center = tip.centroid
            depths = []
            for owner, idx, panel, shape, scene in group:
                axis = scene.local_axis(center.x, center.y)
                if min(abs(axis-scene.start), abs(axis-scene.end)) > 2*max(run.width, scene.width):
                    break
                section = scene.section_at(axis) or {}
                depths.append(float(section.get('depth') or
                                    _panel_overlap_priority(owner, idx, panel, _panels(owner))[1]))
            if len(depths) != 3 or min(depths) <= 0 or max(depths)-min(depths) > .01:
                continue
            if any(abs(min(abs(run.axis_angle-e[4].axis_angle)%180,
                           180-abs(run.axis_angle-e[4].axis_angle)%180)-90) < 1
                   for e in neighbors):
                continue
            midpoint = ((a[0]+b[0])/2, (a[1]+b[1])/2)
            dx, dy = b[0]-a[0], b[1]-a[1]
            reach = 4*max(poly.bounds[2]-poly.bounds[0], poly.bounds[3]-poly.bounds[1], 1)
            length = math.hypot(dx, dy)
            cutter = LineString([(a[0]-reach*dx/length, a[1]-reach*dy/length),
                                 (a[0]+reach*dx/length, a[1]+reach*dy/length)])
            bodies = [p for p in _polygon_parts(split(poly, cutter))
                      if p.intersection(tip).area < 1e-6]
            if len(bodies) != 1:
                continue
            body = bodies[0]
            cap = poly.difference(body)
            halves = [cap.intersection(Polygon([a, c, midpoint])),
                      cap.intersection(Polygon([c, b, midpoint]))]
            proposed = [body] + [e[3].union(h) for e, h in zip(neighbors, halves)]
            # Heal numerical seam cracks only (1e-8 cm), never a physical gap.
            proposed = [p if p.geom_type == 'Polygon' else p.buffer(1e-8).buffer(-1e-8)
                        for p in proposed]
            if any(p.geom_type != 'Polygon' or not p.is_valid or p.interiors for p in proposed):
                continue
            original = unary_union([e[3] for e in group])
            if unary_union(proposed).symmetric_difference(original).area > 1e-5:
                continue
            if any(p.intersection(q).area > 1e-6 for k, p in enumerate(proposed) for q in proposed[k+1:]):
                continue
            for entry, new in zip(group, proposed):
                owner, idx, panel, old, scene = entry
                lo, hi = scene.axis_bounds(scene.to_local_geom(new))
                updated = dict(panel, points=[list(p) for p in new.exterior.coords],
                               fv_single_cut_triple=True, fv_junction_chamfer=True,
                               fv_lateral_reference=True, len=hi-lo)
                updated['ficha'] = dict(panel.get('ficha') or {},
                                       comprimento_total_fundo=f'{hi-lo:.2f}'.rstrip('0').rstrip('.'))
                updated.pop('fv_provenance', None)
                _rewrite_slots(owner, [(i, updated if i == idx else l) for i, l, _ in _panels(owner)],
                               bool(owner.get('fv_is_h', owner.get('is_h', True))))
                report.setdefault(owner['name'], []).append({'chanfro_unico_no_triplo': True,
                    'area_redistribuida_cm2': round(old.symmetric_difference(new).area, 3)})
            # Entries are a snapshot: restart after each committed redistribution.
            return _single_cut_triple_junctions(beams, runs, solids, report)


def needs_area_repair(beam: dict) -> bool:
    """Contorno D-76 ja' sai das paredes medidas e nao deve ser reconstruido.

    A reparacao geral roda antes da referencia lateral. Repeti-la depois sobre
    qualquer painel D-76 — nao apenas L/diagonal — troca seu vao pelo grupo N1
    antigo e faz o gate anular justamente os complementos curtos medidos.
    """
    return not any(
        bool(link.get("fv_lateral_reference"))
        for _, link, _ in _panels(beam)
    )


def report_summary(report: dict[str, Any]) -> str:
    removed = sum(len(v["removidos"]) for v in report.values())
    created = sum(len(v["criados"]) for v in report.values())
    trimmed = sum(len(v.get("conflitos_recortados") or []) for v in report.values())
    shaped = sum(len(v.get("contornos_l") or []) for v in report.values())
    l_details = [
        f"{name}<-{item.get('incidente')}:{item.get('cauda')}"
        for name, values in report.items()
        for item in (values.get("contornos_l") or [])
    ]
    suffix = f" [L: {', '.join(l_details)}]" if l_details else ""
    return (f"{created} trecho(s) recuperado(s), {removed} painel(is) devolvido(s) "
            f"a' dona da faixa, {shaped} contorno(s) em L, {trimmed} conflito(s) "
            f"FV recortado(s) em {len(report)} viga(s){suffix}")
