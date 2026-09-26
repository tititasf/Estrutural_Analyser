"""Cena medida de uma viga para as Laterais de Viga (LV) — topologia BRUTA.

Este modulo so' mede o desenho; nao decide segmento, Para/Passa nem ajuste.
Quem decide e' ``src/core/beam_interpreters/lateral_viga_cells.py``.

O que a cena carrega (tudo em coordenadas do DXF):

* faixa da viga: orientacao (pela rotacao do PROPRIO rotulo), as duas faces
  longitudinais (``t_lo``/``t_hi``) e a extensao ao longo do eixo, seguida
  pelas linhas de borda do DXF a partir do rotulo;
* face A = ``t_lo`` e face B = ``t_hi`` (guia G0: viga horizontal -> A embaixo,
  B em cima; vertical -> A a' esquerda, B a' direita);
* pilares que ocupam cada face, pelo POLIGONO real (nunca a bbox: o P26 do
  13_PAV e' um "U" de 165 cm cuja unica parede na V304 tem 19 cm);
* vigas que tocam cada face (chegando ou atravessando) com a secao delas;
* zonas de secao ao longo da viga (G1), lidas nos rotulos ``b/h`` da propria
  viga. Fronteiras entre rotulos diferentes usam os divisores do fundo apenas
  como REFERENCIA (regra do dono 2026-09-25: FV e' referencia, nunca lei); sem
  referencia, o ponto medio entre os rotulos, marcado como tal;
* lajes encostadas em cada face.

Nada aqui le N2/N4.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from shapely.geometry import Polygon, box
from shapely.validation import make_valid

SECTION_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)\s*$")
PILLAR_NAME_RE = re.compile(r"^P\d+[A-Z]?$", re.IGNORECASE)
BEAM_NAME_RE = re.compile(r"^(?:V|VF|VB|VT)\d+[A-Z]?$", re.IGNORECASE)

AXIS_TOL = 0.6          # colinearidade de borda (cm)
MAX_EDGE_GAP = 250.0    # maior interrupcao de borda que ainda e' a mesma viga
LABEL_BAND_DIST = 45.0  # rotulo da viga fica encostado na faixa
SECTION_LABEL_DIST = 16.0


def _norm_name(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).upper()


def _num(text: str) -> float:
    return float(str(text).replace(",", "."))


def parse_section(text: str) -> Optional[tuple[float, float]]:
    match = SECTION_RE.match(str(text or ""))
    if not match:
        return None
    return _num(match.group(1)), _num(match.group(2))


def _rotation_axis(rotation: Any) -> Optional[bool]:
    """True = horizontal, False = vertical, None = diagonal/indefinido."""
    try:
        angle = float(rotation or 0.0) % 180.0
    except (TypeError, ValueError):
        return None
    if angle <= 15.0 or angle >= 165.0:
        return True
    if 75.0 <= angle <= 105.0:
        return False
    return None


def _merge(intervals: Iterable[tuple[float, float]], gap: float = 0.0) -> list[list[float]]:
    out: list[list[float]] = []
    for a, b in sorted((min(i), max(i)) for i in intervals):
        if out and a <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


@dataclass
class LvScene:
    beam_name: str
    is_horizontal: bool
    t_lo: float
    t_hi: float
    start: float
    end: float
    labels: list[dict] = field(default_factory=list)
    pillars: dict[str, list[dict]] = field(default_factory=lambda: {"A": [], "B": []})
    incidents: dict[str, list[dict]] = field(default_factory=lambda: {"A": [], "B": []})
    slabs: dict[str, list[dict]] = field(default_factory=lambda: {"A": [], "B": []})
    sections: list[dict] = field(default_factory=list)
    end_supports: dict[str, list[dict]] = field(default_factory=lambda: {"start": [], "end": []})
    provenance: dict[str, Any] = field(default_factory=dict)
    # Trechos da face cobertos por LINHA REAL do DXF (invariante do dono
    # 2026-09-25: destaque que nao esta' sobre linha do estrutural e' erro).
    face_coverage: dict[str, list[list[float]]] = field(default_factory=lambda: {"A": [], "B": []})

    def line_coverage(self, side: str, a0: float, a1: float) -> float:
        lo, hi = min(a0, a1), max(a0, a1)
        if hi - lo <= 0:
            return 0.0
        covered = sum(max(0.0, min(hi, y) - max(lo, x)) for x, y in self.face_coverage.get(side, []))
        return covered / (hi - lo)

    @property
    def width(self) -> float:
        return self.t_hi - self.t_lo

    def face_t(self, side: str) -> float:
        return self.t_lo if side == "A" else self.t_hi

    def point(self, axis_value: float, side: str) -> tuple[float, float]:
        t = self.face_t(side)
        return (axis_value, t) if self.is_horizontal else (t, axis_value)

    def rect(self, a0: float, a1: float, t0: float, t1: float):
        if self.is_horizontal:
            return box(min(a0, a1), min(t0, t1), max(a0, a1), max(t0, t1))
        return box(min(t0, t1), min(a0, a1), max(t0, t1), max(a0, a1))

    def axis_bounds(self, geom) -> tuple[float, float]:
        minx, miny, maxx, maxy = geom.bounds
        return (minx, maxx) if self.is_horizontal else (miny, maxy)

    def section_at(self, axis_value: float) -> Optional[dict]:
        best = None
        for zone in self.sections:
            if zone["start"] - 0.5 <= axis_value <= zone["end"] + 0.5:
                return zone
            dist = min(abs(axis_value - zone["start"]), abs(axis_value - zone["end"]))
            if best is None or dist < best[0]:
                best = (dist, zone)
        return best[1] if best else None


# ---------------------------------------------------------------- geometria

def _line_segments(lines: Iterable[dict]) -> list[tuple[float, float, float, float]]:
    segs = []
    for item in lines or []:
        pts = item.get("points") if isinstance(item, dict) else None
        if not pts and isinstance(item, dict) and "start" in item:
            pts = [item["start"], item["end"]]
        if not pts or len(pts) < 2:
            continue
        for p, q in zip(pts, pts[1:]):
            try:
                segs.append((float(p[0]), float(p[1]), float(q[0]), float(q[1])))
            except (TypeError, ValueError, IndexError):
                continue
    return segs


class _EdgeIndex:
    """Linhas axiais (horizontais/verticais) indexadas pela coordenada transversal."""

    def __init__(self, segs: list[tuple[float, float, float, float]]):
        self.h: list[tuple[float, float, float]] = []  # (y, x0, x1)
        self.v: list[tuple[float, float, float]] = []  # (x, y0, y1)
        for x0, y0, x1, y1 in segs:
            if abs(y1 - y0) <= 0.05 and abs(x1 - x0) > 0.5:
                self.h.append(((y0 + y1) / 2, min(x0, x1), max(x0, x1)))
            elif abs(x1 - x0) <= 0.05 and abs(y1 - y0) > 0.5:
                self.v.append(((x0 + x1) / 2, min(y0, y1), max(y0, y1)))

    def along(self, horizontal: bool) -> list[tuple[float, float, float]]:
        return self.h if horizontal else self.v

    def coverage(self, horizontal: bool, t: float) -> list[list[float]]:
        return _merge(
            ((a, b) for tt, a, b in self.along(horizontal) if abs(tt - t) <= AXIS_TOL),
            gap=0.05,
        )


def _find_band(
    label: dict, horizontal: bool, edges: _EdgeIndex, width_hint: Optional[float],
) -> Optional[tuple[float, float]]:
    lx, ly = float(label["pos"][0]), float(label["pos"][1])
    la, lt = (lx, ly) if horizontal else (ly, lx)
    near = [
        (tt, a, b) for tt, a, b in edges.along(horizontal)
        if abs(tt - lt) <= LABEL_BAND_DIST and a - 60.0 <= la <= b + 400.0 and b - a >= 15.0
    ]
    ts = sorted({round(tt, 1) for tt, _, _ in near})
    best = None
    for i, t0 in enumerate(ts):
        for t1 in ts[i + 1:]:
            w = t1 - t0
            if w < 8.0 or w > 60.0:
                continue
            if width_hint and abs(w - width_hint) > 1.5:
                continue
            gap = 0.0 if t0 <= lt <= t1 else min(abs(lt - t0), abs(lt - t1))
            score = (0 if width_hint else abs(w - 19.0) / 50.0) + gap
            if best is None or score < best[0]:
                best = (score, t0, t1)
    return (best[1], best[2]) if best else None


def _nearest_section_width(label: dict, horizontal: bool, sections: list[dict]) -> Optional[float]:
    lx, ly = float(label["pos"][0]), float(label["pos"][1])
    best = None
    for s in sections:
        if _rotation_axis(s.get("rotation")) is not horizontal:
            continue
        sx, sy = float(s["pos"][0]), float(s["pos"][1])
        dt = abs(sy - ly) if horizontal else abs(sx - lx)
        da = abs(sx - lx) if horizontal else abs(sy - ly)
        if dt > 8.0 or da > 700.0:
            continue
        if best is None or da < best[0]:
            best = (da, s["section"][0])
    return best[1] if best else None


# ------------------------------------------------------------------ montagem

def _pillar_polygons(pillar_report: Any) -> list[tuple[str, str, Any]]:
    items = pillar_report.items() if isinstance(pillar_report, dict) else (
        (p.get("name"), p) for p in (pillar_report or []) if isinstance(p, dict)
    )
    out = []
    for name, data in items:
        if not isinstance(data, dict) or data.get("is_invalid"):
            continue
        # Mesma regra canonica dos obstaculos de viga (main.py, "Coletar
        # obstaculos visuais"): so' e' SOLIDO o pilar que nao e' `is_invalid`,
        # nem `ignore_in_beams` (NASCE, visual_only/visual_noise ou decisao do
        # humano na pre-interpretacao/convencao de pilares), nem NASCE. Pilar
        # nao solido: as paredes da lateral atravessam, sem parar e sem abertura
        # — o mesmo que o FV faz ao ligar o vao de um PILAR_NASCENTE.
        if data.get("ignore_in_beams"):
            continue
        if str(data.get("classification") or "").strip().upper() == "NASCE":
            continue
        pts = data.get("points") or []
        poly = None
        if len(pts) >= 3:
            try:
                poly = make_valid(Polygon([(float(p[0]), float(p[1])) for p in pts]))
            except (TypeError, ValueError):
                poly = None
        if poly is None or poly.is_empty:
            bbox = data.get("bbox")
            if not bbox:
                continue
            poly = box(*[float(v) for v in bbox])
        out.append((str(data.get("name") or name), str(data.get("classification") or ""), poly))
    return out


def _slab_polygons(slabs: Any) -> list[tuple[dict, Any]]:
    out = []
    for slab in slabs or []:
        if not isinstance(slab, dict):
            continue
        pts = slab.get("points") or []
        if len(pts) < 3:
            continue
        try:
            poly = make_valid(Polygon([(float(p[0]), float(p[1])) for p in pts]))
        except (TypeError, ValueError):
            continue
        if not poly.is_empty:
            out.append((slab, poly))
    return out


def _fv_reference_boundaries(beam: dict, scene: LvScene) -> list[float]:
    """Divisores do fundo da mesma viga, dentro da faixa — so' REFERENCIA."""
    out = []
    for key, slots in (beam.get("links") or {}).items():
        if not re.match(r"^viga_fundo_seg_\d+_area_segs$", str(key)) or not isinstance(slots, dict):
            continue
        for link in slots.get("contour") or []:
            pts = (link or {}).get("points") or []
            if len(pts) < 3:
                continue
            ts = [float(p[1] if scene.is_horizontal else p[0]) for p in pts]
            if min(ts) < scene.t_lo - 1.0 or max(ts) > scene.t_hi + 1.0:
                continue  # fundo de outra faixa (contaminacao) nao e' referencia
            axs = [float(p[0] if scene.is_horizontal else p[1]) for p in pts]
            out.extend([min(axs), max(axs)])
    return sorted(set(round(v, 2) for v in out))


def _extent(
    scene_h: bool, t_lo: float, t_hi: float, label_axis: float,
    edges: _EdgeIndex, blockers: list[tuple[float, float]],
) -> Optional[tuple[float, float]]:
    lo_cov = edges.coverage(scene_h, t_lo)
    hi_cov = edges.coverage(scene_h, t_hi)
    pieces = _merge([tuple(i) for i in lo_cov + hi_cov], gap=0.05)
    if not pieces:
        return None

    def both_edges(a: float, b: float) -> bool:
        def cov(c):
            return sum(max(0.0, min(b, y) - max(a, x)) for x, y in c)
        return cov(lo_cov) > 5.0 and cov(hi_cov) > 5.0

    pieces = [p for p in pieces if both_edges(p[0], p[1])]
    if not pieces:
        return None
    seed = min(
        range(len(pieces)),
        key=lambda i: 0.0 if pieces[i][0] - 60 <= label_axis <= pieces[i][1] + 60
        else min(abs(label_axis - pieces[i][0]), abs(label_axis - pieces[i][1])),
    )
    if not (pieces[seed][0] - 400 <= label_axis <= pieces[seed][1] + 400):
        return None

    def blocked(a: float, b: float) -> bool:
        return any(x <= a + 1.0 and y >= b - 1.0 for x, y in blockers)

    start, end = pieces[seed]
    i = seed
    while i + 1 < len(pieces):
        gap = pieces[i + 1][0] - end
        if gap > MAX_EDGE_GAP and not blocked(end, pieces[i + 1][0]):
            break
        if gap > 1.0 and not blocked(end, pieces[i + 1][0]) and gap > 60.0:
            break
        i += 1
        end = pieces[i][1]
    i = seed
    while i - 1 >= 0:
        gap = start - pieces[i - 1][1]
        if gap > MAX_EDGE_GAP and not blocked(pieces[i - 1][1], start):
            break
        if gap > 1.0 and not blocked(pieces[i - 1][1], start) and gap > 60.0:
            break
        i -= 1
        start = pieces[i][0]
    return start, end


def build_band_scene(
    beam: dict,
    texts: list[dict],
    edges: _EdgeIndex,
    section_texts: list[dict],
    other_labels: list[dict],
    pillars: list[tuple[str, str, Any]],
    only_label: Optional[dict] = None,
) -> Optional[LvScene]:
    name = _norm_name(beam.get("name"))
    labels = (
        [only_label] if only_label is not None
        else [t for t in texts if _norm_name(t.get("text")) == name and t.get("pos")]
    )
    if not labels:
        return None
    axes = [_rotation_axis(t.get("rotation")) for t in labels]
    if any(a is None for a in axes) or len(set(axes)) != 1:
        return None  # diagonal ou orientacao mista: use build_scene_runs (um trecho por rotulo)
    horizontal = bool(axes[0])

    candidates = []
    for label in labels:
        width = _nearest_section_width(label, horizontal, section_texts)
        band = _find_band(label, horizontal, edges, width) or (
            _find_band(label, horizontal, edges, None) if width is None else None
        )
        if band:
            candidates.append((label, band))
    if not candidates:
        return None
    label, (t_lo, t_hi) = candidates[0]
    label_axis = float(label["pos"][0] if horizontal else label["pos"][1])

    tmp = LvScene(name, horizontal, t_lo, t_hi, 0.0, 0.0)
    blockers = []
    for _, _, poly in pillars:
        inter = poly.intersection(tmp.rect(-1e7, 1e7, t_lo + 0.2, t_hi - 0.2))
        if not inter.is_empty:
            blockers.append(tmp.axis_bounds(inter))
    ext = _extent(horizontal, t_lo, t_hi, label_axis, edges, blockers)
    if not ext:
        return None
    start, end = ext
    # Outra viga rotulada sobre a mesma faixa limita a extensao.
    for other in other_labels:
        if _norm_name(other.get("text")) == name or _rotation_axis(other.get("rotation")) is not horizontal:
            continue
        ox, oy = float(other["pos"][0]), float(other["pos"][1])
        oa, ot = (ox, oy) if horizontal else (oy, ox)
        if not (t_lo - 8.0 <= ot <= t_hi + 8.0):
            continue
        if start + 5.0 < oa < end - 5.0:
            if oa > label_axis:
                end = min(end, oa)
            else:
                start = max(start, oa)
    scene = LvScene(name, horizontal, t_lo, t_hi, start, end)
    scene.face_coverage = {
        "A": edges.coverage(horizontal, t_lo),
        "B": edges.coverage(horizontal, t_hi),
    }
    scene.labels = [{"text": t.get("text"), "pos": tuple(t["pos"])} for t, _ in candidates]
    scene.provenance = {
        "band_source": "dxf_edges_from_own_label",
        "orientation_source": "label_rotation",
    }
    return scene


def _sections(scene: LvScene, beam: dict, section_texts: list[dict], pillar_texts: list[dict]) -> None:
    labels = []
    for s in section_texts:
        if _rotation_axis(s.get("rotation")) is not scene.is_horizontal:
            continue
        sx, sy = float(s["pos"][0]), float(s["pos"][1])
        sa, st = (sx, sy) if scene.is_horizontal else (sy, sx)
        if not (scene.start - 10.0 <= sa <= scene.end + 10.0):
            continue
        dist = 0.0 if scene.t_lo <= st <= scene.t_hi else min(abs(st - scene.t_lo), abs(st - scene.t_hi))
        if dist > SECTION_LABEL_DIST:
            continue
        if abs(s["section"][0] - scene.width) > 2.0:
            continue
        # Rotulo de pilar (P43 + 19/50 empilhados) nao e' secao da viga.
        if any(abs(float(p["pos"][0]) - sx) <= 8.0 and abs(float(p["pos"][1]) - sy) <= 20.0 for p in pillar_texts):
            continue
        labels.append((sa, s))
    labels.sort(key=lambda item: item[0])
    if not labels:
        scene.sections = []
        return
    refs = _fv_reference_boundaries(beam, scene)
    zones = []
    cur_start = scene.start
    for i, (sa, s) in enumerate(labels):
        depth = s["section"][1]
        if zones and abs(zones[-1]["depth"] - depth) < 0.01:
            continue
        if zones:
            prev_label = zones[-1]["_label_axis"]
            between = [r for r in refs if prev_label < r < sa]
            if between:
                boundary = max(between)
                source = "fv_reference_boundary"
            else:
                boundary = (prev_label + sa) / 2.0
                source = "midpoint_between_labels"
            zones[-1]["end"] = boundary
            zones[-1]["end_source"] = source
            cur_start = boundary
        zones.append({
            "start": cur_start, "end": scene.end, "dim": s["text"].strip().replace(" ", ""),
            "width": s["section"][0], "depth": depth, "_label_axis": sa,
            "end_source": "beam_end",
        })
    for z in zones:
        z.pop("_label_axis", None)
    scene.sections = zones


def _face_strips(scene: LvScene, side: str, a0: float, a1: float):
    t = scene.face_t(side)
    inward = 1.0 if side == "A" else -1.0
    inside = scene.rect(a0, a1, t + inward * 0.2, t + inward * 1.0)
    outside = scene.rect(a0, a1, t - inward * 0.2, t - inward * 1.0)
    return inside, outside


def _attach_context(
    scene: LvScene,
    pillars: list[tuple[str, str, Any]],
    other_scenes: list[LvScene],
    slabs: list[tuple[dict, Any]],
) -> None:
    margin = 80.0
    for side in ("A", "B"):
        inside, outside = _face_strips(scene, side, scene.start - margin, scene.end + margin)
        for name, classification, poly in pillars:
            inter = poly.intersection(inside)
            if inter.is_empty or inter.area <= 1e-6:
                continue
            geoms = getattr(inter, "geoms", [inter])
            for g in geoms:
                a0, a1 = scene.axis_bounds(g)
                if a1 - a0 < 0.5:
                    continue
                item = {"name": name, "start": a0, "end": a1, "classification": classification}
                if classification.strip().upper() in ("", "INDETERMINADO"):
                    item["flag"] = "pilar_classificacao_indeterminada_tratado_como_solido"
                if a1 <= scene.start + 1.0:
                    if not any(s["name"] == name for s in scene.end_supports["start"]):
                        scene.end_supports["start"].append(dict(item, type="pilar"))
                elif a0 >= scene.end - 1.0:
                    if not any(s["name"] == name for s in scene.end_supports["end"]):
                        scene.end_supports["end"].append(dict(item, type="pilar"))
                else:
                    scene.pillars[side].append(item)
        for other in other_scenes:
            if other is scene or other.beam_name == scene.beam_name:
                continue
            if other.is_horizontal == scene.is_horizontal:
                continue
            band = other.rect(other.start, other.end, other.t_lo, other.t_hi)
            touch = band.intersection(outside)
            through = band.intersection(inside)
            hit = touch if not touch.is_empty else through
            if hit.is_empty:
                continue
            a0, a1 = scene.axis_bounds(hit)
            if a1 - a0 < 0.5:
                continue
            opposite_inside, _ = _face_strips(scene, "B" if side == "A" else "A", a0, a1)
            crossing = not band.intersection(opposite_inside).is_empty
            junction = other.t_lo + (other.t_hi - other.t_lo) / 2.0
            face_t = scene.face_t(side)
            zone = other.section_at(face_t)
            item = {
                "name": other.beam_name, "start": a0, "end": a1,
                "dim": zone["dim"] if zone else "", "depth": zone["depth"] if zone else None,
                "width": other.width, "crossing": crossing, "axis_center": junction,
            }
            if a1 <= scene.start + 1.0:
                scene.end_supports["start"].append(dict(item, type="viga"))
            elif a0 >= scene.end - 1.0:
                scene.end_supports["end"].append(dict(item, type="viga"))
            elif not any(i["name"] == item["name"] and abs(i["start"] - a0) < 1.0 for i in scene.incidents[side]):
                scene.incidents[side].append(item)
        for slab, poly in slabs:
            far = scene.rect(
                scene.start, scene.end,
                scene.face_t(side) - (1.0 if side == "A" else -1.0) * 0.5,
                scene.face_t(side) - (1.0 if side == "A" else -1.0) * 6.0,
            )
            inter = poly.intersection(far)
            if inter.is_empty or inter.area <= 1e-6:
                continue
            a0, a1 = scene.axis_bounds(inter)
            if a1 - a0 < 5.0:
                continue
            fields = slab.get("fields") or {}
            scene.slabs[side].append({
                "name": str(slab.get("name") or fields.get("nome") or ""),
                "level": str(fields.get("laje_nivel") or slab.get("laje_nivel") or slab.get("nivel") or ""),
                "height": str(fields.get("laje_dim") or slab.get("laje_dim") or slab.get("height") or ""),
                "start": a0, "end": a1,
            })
    for key in ("A", "B"):
        scene.pillars[key].sort(key=lambda i: i["start"])
        scene.incidents[key].sort(key=lambda i: i["start"])
        scene.slabs[key].sort(key=lambda i: i["start"])
    _trim_end_pillars(scene)


def _trim_end_pillars(scene: LvScene) -> None:
    """Pilar que ocupa as DUAS faces numa ponta e' apoio de extremidade.

    As bordas da viga costumam atravessar o pilar de canto (P41 na V301); a
    lateral comeca na face interna dele, nao no lado de fora.
    """
    def full_band(item: dict) -> bool:
        return any(
            o["name"] == item["name"] and abs(o["start"] - item["start"]) < 1.0
            for o in scene.pillars["B"]
        )

    changed = True
    while changed:
        changed = False
        for item in list(scene.pillars["A"]):
            if not full_band(item):
                continue
            if item["start"] <= scene.start + 1.0 and item["end"] > scene.start + 0.5:
                scene.start = item["end"]
                scene.end_supports["start"].append(dict(item, type="pilar"))
                changed = True
            elif item["end"] >= scene.end - 1.0 and item["start"] < scene.end - 0.5:
                scene.end = item["start"]
                scene.end_supports["end"].append(dict(item, type="pilar"))
                changed = True
        for side in ("A", "B"):
            scene.pillars[side] = [
                i for i in scene.pillars[side]
                if i["end"] > scene.start + 0.5 and i["start"] < scene.end - 0.5
            ]
    for side in ("A", "B"):
        keep = []
        for inc in scene.incidents[side]:
            if inc["end"] <= scene.start + 0.5:
                if not any(s["name"] == inc["name"] for s in scene.end_supports["start"]):
                    scene.end_supports["start"].append(dict(inc, type="viga"))
            elif inc["start"] >= scene.end - 0.5:
                if not any(s["name"] == inc["name"] for s in scene.end_supports["end"]):
                    scene.end_supports["end"].append(dict(inc, type="viga"))
            else:
                keep.append(inc)
        scene.incidents[side] = keep
        scene.slabs[side] = [
            dict(sl, start=max(sl["start"], scene.start), end=min(sl["end"], scene.end))
            for sl in scene.slabs[side]
            if sl["end"] > scene.start + 1.0 and sl["start"] < scene.end - 1.0
        ]
    for zone in scene.sections:
        zone["start"] = max(zone["start"], scene.start)
        zone["end"] = min(zone["end"], scene.end)
    scene.sections = [z for z in scene.sections if z["end"] - z["start"] > 0.5]


def build_scene_runs(
    beams: list[dict],
    texts: list[dict],
    lines: list[dict],
    pillar_report: Any,
    slabs: Any = None,
) -> dict[str, list[LvScene]]:
    """Um ou mais TRECHOS por viga: cada rotulo ortogonal abre uma faixa.

    Viga em "L" (V330 no 13_PAV: um rotulo a 90 e outro a 0 graus) vira dois
    trechos, cada um com orientacao e A/B proprios (G0). Rotulos da mesma
    faixa colapsam num trecho so'. Rotulo diagonal (Caso 8) fica de fora.
    """
    edges = _EdgeIndex(_line_segments(lines))
    section_texts = []
    pillar_texts = []
    beam_labels = []
    for t in texts or []:
        if not isinstance(t, dict) or not t.get("pos"):
            continue
        txt = str(t.get("text") or "").strip()
        sec = parse_section(txt)
        if sec:
            section_texts.append(dict(t, section=sec))
        elif PILLAR_NAME_RE.match(txt):
            pillar_texts.append(t)
        elif BEAM_NAME_RE.match(_norm_name(txt)):
            beam_labels.append(t)
    pillars = _pillar_polygons(pillar_report)
    runs: dict[str, list[LvScene]] = {}
    by_name: dict[str, dict] = {}
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        name = _norm_name(beam.get("name"))
        if not name or name in runs:
            continue
        own = [t for t in beam_labels if _norm_name(t.get("text")) == name]
        found: list[LvScene] = []
        for label in sorted(own, key=lambda t: (float(t["pos"][0]), float(t["pos"][1]))):
            if _rotation_axis(label.get("rotation")) is None:
                continue
            scene = build_band_scene(
                beam, texts, edges, section_texts, beam_labels, pillars, only_label=label,
            )
            if scene is None:
                continue
            duplicate = any(
                other.is_horizontal == scene.is_horizontal
                and abs(other.t_lo - scene.t_lo) < 1.0
                and min(other.end, scene.end) - max(other.start, scene.start) > 1.0
                for other in found
            )
            if not duplicate:
                found.append(scene)
        if found:
            runs[name] = found
            by_name[name] = beam
    for name, scenes in runs.items():
        for scene in scenes:
            _sections(scene, by_name[name], section_texts, pillar_texts)
    slab_polys = _slab_polygons(slabs)
    others = [scene for scenes in runs.values() for scene in scenes]
    for scene in others:
        _attach_context(scene, pillars, others, slab_polys)
    return runs


def build_scenes(
    beams: list[dict],
    texts: list[dict],
    lines: list[dict],
    pillar_report: Any,
    slabs: Any = None,
) -> dict[str, LvScene]:
    """Compatibilidade: primeiro trecho de cada viga."""
    return {
        name: scenes[0]
        for name, scenes in build_scene_runs(beams, texts, lines, pillar_report, slabs).items()
    }
