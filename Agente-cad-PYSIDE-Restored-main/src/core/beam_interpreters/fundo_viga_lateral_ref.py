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
    return {
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
) -> tuple[int, float, float, float, float, str, int]:
    """Prioridade estrutural estavel para uma area que nao pode ter dois donos.

    Contorno humano vence. Entre automaticos: maior profundidade, maior largura
    e, no empate, a maior fracao continua, antes do desenvolvimento total.
    Somar varios vaos separados nao torna uma viga mais continua.
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
    lengths = [
        max(poly.bounds[2] - poly.bounds[0], poly.bounds[3] - poly.bounds[1])
        for _, _, poly in panels if poly is not None
    ]
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
    *, prefer_continuity: bool = True,
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
            priority = _panel_overlap_priority(beam, index, link, panels)
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
    runs_by_name = build_scene_runs(
        beam_list, texts, lines, pillar_report, slabs, allow_width_hint_fallback=True,
    )
    bands = {
        name: unary_union([run.world_band() for run in runs])
        for name, runs in runs_by_name.items() if runs
    }
    from src.core.lv_beam_scene import _line_segments
    all_segs = _line_segments(lines)
    report: dict[str, Any] = {}

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
        if own is None or not panels or _has_validated(panels):
            continue
        others = unary_union([band for other, band in bands.items() if other != name])
        keep, dropped = [], []
        for idx, link, poly in panels:
            if poly is not None and _frac(poly, own) < OWN_BAND_MAX and _frac(poly, others) >= OTHER_BAND_MIN:
                dropped.append(idx)
            else:
                keep.append((idx, link, poly))
        if dropped:
            is_h = bool(beam.get("fv_is_h", beam.get("is_h", True)))
            keep.sort(key=lambda item: _axis_span(item[2], is_h)[0] if item[2] is not None else 0.0)
            _rewrite_slots(beam, [(idx, link) for idx, link, _ in keep], is_h)
            entry(beam)["removidos"].extend(dropped)

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
        width = float(pair[0]) if pair else additions[0][2].width
        items: list[tuple[float, float, Optional[int], dict]] = []
        for idx, link, poly in panels:
            if poly is None:
                continue
            lo, hi = _axis_span(poly, fv_is_h)
            items.append((lo, hi, idx, link))
        created = []
        for a0, a1, run in additions:
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
        if _has_validated(current) or any(
            poly is not None and _frac(poly, own) >= 0.5 for _, _, poly in current
        ):
            continue
        ordered = []
        for run in runs:
            if not run.angle:
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
            entry(beam)["criados"].append([round(min(ext_a[0], ext_b[0]), 1), round(max(ext_a[1], ext_b[1]), 1)])
        if ordered:
            entry(beam)["removidos"].extend(idx for idx, _, _ in current)
            _rewrite_slots(beam, ordered, bool(beam.get("fv_is_h", beam.get("is_h", True))))
    # D-82: encontro a 90 graus conserva dois paineis independentes, mesmo
    # quando a perna incidente mede apenas 1 cm. Nao consumir a cauda no corpo.
    # Before D-60, slots may still be rejected/repositioned. Continuity is
    # meaningful only after that audit; do not let a provisional run steal
    # area that would disappear when its invalid slot is annulled.
    return resolve_automatic_overlaps_all(beam_list, report, prefer_continuity=False)


def complete_measured_junctions_all(beams, texts, lines, pillar_report, slabs=None):
    """Fill only locally witnessed junction cells after every re-anchoring step.

    Two arriving bottom panels and two measured non-parallel bands witness the
    junction. No free-space extrapolation: extension is at most the opposite
    band's width, and solid supports/hatch veto the cell.
    """
    from src.core.lv_beam_scene import build_scene_runs, _line_segments, _pillar_polygons
    runs = build_scene_runs(
        beams, texts, lines, pillar_report, slabs, allow_width_hint_fallback=True,
    )
    owners = {str(b.get("name")): b for b in beams}
    segs = _line_segments(lines)
    solids = [p for _, _, p in _pillar_polygons(pillar_report)]
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
                _panel_overlap_priority(bc[0],i,l,_panels(bc[0]))[:5] for i,l,p in bc[1]))
            i,link,poly = max(candidates,key=lambda v:v[2].area)
            # Snapping can create a self-intersection; repair before union,
            # since GEOS cannot union invalid inputs (repairing afterwards
            # never runs when union itself raises a TopologyException).
            merged = make_valid(poly.union(make_valid(snap(missing, poly, .05))))
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
    return report


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
