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

Fica de fora (sem pista confiavel): viga com fundo validado por humano, trecho
diagonal, trecho cuja orientacao da cena difere da do fundo.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

SOURCE = "fundo_viga_lateral_reference"
OWN_BAND_MAX = 0.30        # painel com menos que isto na propria faixa...
OTHER_BAND_MIN = 0.70      # ...e mais que isto na faixa de outra viga e' dela
MIN_GAP = 15.0             # trecho menor e' folga, nao vao
MIN_ISOLATED = 25.0        # toco solto (sem painel vizinho) do tamanho de uma
                           # largura de viga e' encontro, nao vao (V313: P29 x V306)
WALL_COVERAGE_MIN = 0.50   # mesma invariante das laterais (linha real)
DIMENSION_OVERLAP_MAX = 0.05
TOUCH_TOL = 1.0

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

    faces = []
    for side in ("A", "B"):
        faces.append(_merge((min(s.start, s.end), max(s.start, s.end)) for s in segment_cell(run, side, "para")))
    return _intersect(faces[0], faces[1])


def _walls_are_real(run: Any, a0: float, a1: float) -> bool:
    return all(
        run.line_coverage(side, a0, a1) >= WALL_COVERAGE_MIN
        and run.dimension_overlap(side, a0, a1) <= DIMENSION_OVERLAP_MAX
        for side in ("A", "B")
    )


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


def apply_lateral_reference_all(
    beams: list[dict],
    texts: list[dict],
    lines: list[dict],
    pillar_report: Any,
    slabs: Any = None,
) -> dict[str, Any]:
    """Passada global. Retorna ``{viga: {"removidos": [...], "criados": [...]}}``."""
    from src.core.lv_beam_scene import _norm_name, _pillar_polygons, build_scene_runs
    from src.core.beam_interpreters.fundo_viga import FundoVigaInterpreter

    beam_list = [b for b in beams or [] if isinstance(b, dict)]
    runs_by_name = build_scene_runs(beam_list, texts, lines, pillar_report, slabs)
    bands = {
        name: unary_union([run.world_band() for run in runs])
        for name, runs in runs_by_name.items() if runs
    }
    # Pilar SOLIDO (NASCE e ignorados ja' ficam de fora, mesma regra das
    # laterais): secao de pilar nao e' fundo da viga.
    solid_pillars = [poly for _, _, poly in _pillar_polygons(pillar_report)]
    from src.core.lv_beam_scene import _line_segments
    all_segs = _line_segments(lines)
    report: dict[str, Any] = {}

    def entry(beam: dict) -> dict:
        return report.setdefault(str(beam.get("name")), {"removidos": [], "criados": []})

    owners: dict[str, dict] = {}
    for beam in beam_list:
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
            for pillar in solid_pillars:
                inter = pillar.intersection(band)
                if inter.is_empty or inter.area <= 0:
                    continue
                minx, miny, maxx, maxy = inter.bounds
                depth = (maxy - miny) if run.is_horizontal else (maxx - minx)
                if depth >= 0.5 * run.width:
                    covered.append(_axis_span(inter, run.is_horizontal))
            covered.extend(_hatched_spans(run, all_segs))
            for a0, a1 in _subtract(_wall_spans(run), [list(c) for c in covered]):
                if a1 - a0 >= MIN_GAP and _walls_are_real(run, a0, a1):
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
            touches = any(abs(lo - a1) <= TOUCH_TOL or abs(hi - a0) <= TOUCH_TOL for lo, hi, _, _ in items)
            if not touches and a1 - a0 < MIN_ISOLATED:
                continue
            touching = [
                i for i, (lo, hi, idx, link) in enumerate(items)
                if idx is not None and (abs(lo - a1) <= TOUCH_TOL or abs(hi - a0) <= TOUCH_TOL)
                and not link.get("special_geometry")
            ]
            if touching:
                i = touching[0]
                lo, hi, idx, _link = items[i]
                lo, hi = min(lo, a0), max(hi, a1)
                link = _rect_link(run, lo, hi, width)
                link["fv_lateral_reference_extends"] = idx
                items[i] = (lo, hi, idx, link)
            else:
                items.append((a0, a1, None, _rect_link(run, a0, a1, width)))
            created.append([round(a0, 1), round(a1, 1)])
        if not created:
            continue
        items.sort(key=lambda item: item[0])
        _rewrite_slots(beam, [(idx, link) for _, _, idx, link in items], fv_is_h)
        FundoVigaInterpreter.assign_segment_dimensions_from_texts(beam)
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
    return report


def needs_area_repair(beam: dict) -> bool:
    """Painel diagonal desta passada ja' sai das paredes medidas; o reparador
    retangular o transformaria em bbox (e o gate D-60 o anularia)."""
    return not any(
        str(link.get("geometry_source") or "") == SOURCE + "_special_diagonal"
        for _, link, _ in _panels(beam)
    )


def report_summary(report: dict[str, Any]) -> str:
    removed = sum(len(v["removidos"]) for v in report.values())
    created = sum(len(v["criados"]) for v in report.values())
    return f"{created} trecho(s) recuperado(s), {removed} painel(is) devolvido(s) a' dona da faixa em {len(report)} viga(s)"
