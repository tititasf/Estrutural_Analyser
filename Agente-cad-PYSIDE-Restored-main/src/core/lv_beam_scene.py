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

from shapely import affinity
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
    # Trechos da face que coincidem com LINHA DE COTA (antialucinacao).
    dimension_coverage: dict[str, list[list[float]]] = field(default_factory=lambda: {"A": [], "B": []})
    # Viga diagonal (guia Caso 8): a cena vive num referencial GIRADO de
    # ``angle`` graus em torno da origem, no qual o eixo da viga e' horizontal
    # e o sentido de leitura do A aponta para +x. A = lado direito desse
    # sentido (o mesmo que G0 da' para horizontal e vertical). 0 = ortogonal.
    angle: float = 0.0
    # Diagonal: cada face termina onde a PROPRIA linha termina (pontas em
    # esquadro obliquo deixam as duas faces com comprimentos diferentes).
    face_extent: dict[str, tuple[float, float]] = field(default_factory=dict)
    # Full, per-face measurements retained before endpoint trimming. Only Passa
    # consumes these; Para continues using its existing topology.
    passa_pillars: Optional[dict[str, list[dict]]] = None
    passa_incidents: Optional[dict[str, list[dict]]] = None

    def to_world(self, x: float, y: float) -> tuple[float, float]:
        if not self.angle:
            return (x, y)
        c, s = math.cos(math.radians(self.angle)), math.sin(math.radians(self.angle))
        return (x * c - y * s, x * s + y * c)

    def to_local(self, x: float, y: float) -> tuple[float, float]:
        if not self.angle:
            return (x, y)
        c, s = math.cos(math.radians(self.angle)), math.sin(math.radians(self.angle))
        return (x * c + y * s, -x * s + y * c)

    def to_local_geom(self, geom):
        if not self.angle:
            return geom
        return affinity.rotate(geom, -self.angle, origin=(0.0, 0.0))

    def world_band(self, pad: float = 0.0):
        band = self.rect(self.start - pad, self.end + pad, self.t_lo, self.t_hi)
        if not self.angle:
            return band
        return affinity.rotate(band, self.angle, origin=(0.0, 0.0))

    def local_axis(self, x: float, y: float) -> float:
        lx, ly = self.to_local(x, y)
        return lx if self.is_horizontal else ly

    @property
    def axis_angle(self) -> float:
        """Direcao do eixo no DXF, em graus [0, 180)."""
        return (self.angle + (0.0 if self.is_horizontal else 90.0)) % 180.0

    def dimension_overlap(self, side: str, a0: float, a1: float) -> float:
        """Fracao do segmento que so' existe SOBRE cota/chamada.

        Chamada deitada sobre a face real (V301) nao e' alucinacao: ali existe
        a borda estrutural. Alucinacao e' o trecho coberto por cota e SEM borda
        estrutural por baixo.
        """
        lo, hi = min(a0, a1), max(a0, a1)
        if hi - lo <= 0:
            return 0.0
        real = _merge([tuple(i) for i in self.face_coverage.get(side, [])], gap=0.05)
        only_dim = 0.0
        for x, y in self.dimension_coverage.get(side, []):
            x, y = max(lo, x), min(hi, y)
            if y <= x:
                continue
            under = sum(max(0.0, min(y, b) - max(x, a)) for a, b in real)
            only_dim += (y - x) - under
        return max(0.0, only_dim) / (hi - lo)

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

    def point_local(self, axis_value: float, side: str) -> tuple[float, float]:
        t = self.face_t(side)
        return (axis_value, t) if self.is_horizontal else (t, axis_value)

    def point(self, axis_value: float, side: str) -> tuple[float, float]:
        return self.to_world(*self.point_local(axis_value, side))

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


# ------------------------------------------------------- antialucinacao: cotas
#
# Pedido do dono (2026-09-26): nenhum segmento pode nascer sobre LINHA DE COTA
# do estrutural limpo. O DXF do 13_PAV nao tem entidade DIMENSION — as cotas
# sao LINE + TEXT soltos —, e a extracao nunca usa nome de layer. A cota e'
# reconhecida pela GEOMETRIA, medida na cadeia sob a V301 (305,5 | 100 | 19 ...):
# cada trecho e' uma LINE axial com um TIQUE obliquo (~10 cm a 45 graus)
# cruzando cada ponta; a linha de chamada e' a perpendicular curta que passa
# pelo meio de um tique.

TICK_LEN = (4.0, 16.0)
TICK_TOL = 1.5
WITNESS_END_TOL = 12.0  # chamada passa do tique ~10 cm no 13_PAV (3313,1 -> 3323,1)


def _is_tick(seg: tuple[float, float, float, float]) -> bool:
    x0, y0, x1, y1 = seg
    length = math.hypot(x1 - x0, y1 - y0)
    if not (TICK_LEN[0] <= length <= TICK_LEN[1]):
        return False
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180.0
    return 25.0 <= ang <= 65.0 or 115.0 <= ang <= 155.0


def split_dimension_lines(
    segs: list[tuple[float, float, float, float]],
    texts: Optional[list[dict]] = None,
) -> tuple[list[tuple[float, float, float, float]], list[tuple[float, float, float, float]]]:
    """Separa (linhas_estruturais, linhas_de_cota) sem olhar layer.

    Cota COMPROVADA: linha axial com tique nas DUAS pontas e texto numerico ao
    lado cujo valor e' o proprio comprimento (305,5 <-> "305.5"). Trechos com
    tique nas duas pontas encadeados a uma cota comprovada tambem sao cota
    (os "19" da cadeia). Tique solto sobre uma borda NAO basta: a cota vertical
    termina na face da viga, entao a borda real recebe tique (V301, 3692-3731).
    """
    ticks = [((x0 + x1) / 2.0, (y0 + y1) / 2.0) for x0, y0, x1, y1 in segs if _is_tick((x0, y0, x1, y1))]
    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for tx, ty in ticks:
        grid.setdefault((int(tx // 20), int(ty // 20)), []).append((tx, ty))

    def tick_near(x: float, y: float) -> bool:
        gx, gy = int(x // 20), int(y // 20)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for tx, ty in grid.get((gx + dx, gy + dy), ()):
                    if abs(tx - x) <= TICK_TOL and abs(ty - y) <= TICK_TOL:
                        return True
        return False

    numbers = []
    for t in texts or []:
        try:
            value = float(str(t.get("text") or "").strip().replace(",", "."))
            numbers.append((value, float(t["pos"][0]), float(t["pos"][1])))
        except (TypeError, ValueError, KeyError, IndexError):
            continue

    def text_matches(seg) -> bool:
        x0, y0, x1, y1 = seg
        horizontal = abs(y1 - y0) <= 0.05
        length = math.hypot(x1 - x0, y1 - y0)
        lo, hi = (min(x0, x1), max(x0, x1)) if horizontal else (min(y0, y1), max(y0, y1))
        t = (y0 + y1) / 2.0 if horizontal else (x0 + x1) / 2.0
        for value, tx, ty in numbers:
            a, tt = (tx, ty) if horizontal else (ty, tx)
            if abs(value - length) <= 0.6 and lo - 5.0 <= a <= hi + 5.0 and abs(tt - t) <= 12.0:
                return True
        return False

    spans = []  # candidatos: axiais com tique nas duas pontas
    for index, seg in enumerate(segs):
        x0, y0, x1, y1 = seg
        axial = abs(y1 - y0) <= 0.05 or abs(x1 - x0) <= 0.05
        if axial and not _is_tick(seg) and tick_near(x0, y0) and tick_near(x1, y1):
            spans.append(index)
    confirmed = {i for i in spans if text_matches(segs[i])}
    ends: dict[tuple[int, int], set[int]] = {}
    for i in spans:
        x0, y0, x1, y1 = segs[i]
        for x, y in ((x0, y0), (x1, y1)):
            ends.setdefault((round(x), round(y)), set()).add(i)
    frontier = list(confirmed)
    while frontier:
        i = frontier.pop()
        x0, y0, x1, y1 = segs[i]
        for x, y in ((x0, y0), (x1, y1)):
            for j in ends.get((round(x), round(y)), ()):
                if j not in confirmed:
                    confirmed.add(j)
                    frontier.append(j)
    # Linhas de CHAMADA: saem do objeto (com folga) e passam do tique da cota
    # em ~3 cm. Medido no topo da V322/V309A: x=3788,4 de 3212 a 3323,1, com a
    # cadeia "19 | 418" em y=3320. Sao colineares a' face da viga vertical e,
    # sem esta regra, a extensao da viga subia por elas.
    # Criterio: axial, PERPENDICULAR a uma cota comprovada, passando pelo
    # tique dela, e o tique a ate' WITNESS_END_TOL de uma PONTA da linha.
    # Chamada pode ficar COLINEAR a' face da viga (V301, 3692,7-3731,2: chamada
    # de uma cota vertical deitada sobre a face); a face real e' outra linha,
    # que continua estrutural — a cobertura da face nao depende da chamada.
    confirmed_ticks: list[tuple[float, float, bool]] = []  # (x, y, cota_horizontal)
    for i in confirmed:
        x0, y0, x1, y1 = segs[i]
        horizontal = abs(y1 - y0) <= 0.05
        confirmed_ticks.append((x0, y0, horizontal))
        confirmed_ticks.append((x1, y1, horizontal))
    witness: set[int] = set()
    for index, seg in enumerate(segs):
        if index in confirmed or _is_tick(seg):
            continue
        x0, y0, x1, y1 = seg
        horizontal = abs(y1 - y0) <= 0.05
        vertical = abs(x1 - x0) <= 0.05
        if not (horizontal or vertical):
            continue
        lo, hi = (min(x0, x1), max(x0, x1)) if horizontal else (min(y0, y1), max(y0, y1))
        t = (y0 + y1) / 2.0 if horizontal else (x0 + x1) / 2.0
        for tx, ty, chain_horizontal in confirmed_ticks:
            if chain_horizontal == horizontal:
                continue  # chamada e' perpendicular a' cota
            a, tt = (tx, ty) if horizontal else (ty, tx)
            if abs(tt - t) > 0.6 or not (lo - 0.6 <= a <= hi + 0.6):
                continue
            if min(abs(a - lo), abs(a - hi)) <= WITNESS_END_TOL:
                witness.add(index)
                break
    excluded = confirmed | witness
    structural = [seg for i, seg in enumerate(segs) if i not in excluded]
    dimension = [seg for i, seg in enumerate(segs) if i in excluded]
    return structural, dimension


class _EdgeIndex:
    """Linhas axiais (horizontais/verticais) indexadas pela coordenada transversal."""

    def __init__(self, segs: list[tuple[float, float, float, float]], tol: float = 0.05):
        self.h: list[tuple[float, float, float]] = []  # (y, x0, x1)
        self.v: list[tuple[float, float, float]] = []  # (x, y0, y1)
        for x0, y0, x1, y1 in segs:
            if abs(y1 - y0) <= tol and abs(x1 - x0) > 0.5:
                self.h.append(((y0 + y1) / 2, min(x0, x1), max(x0, x1)))
            elif abs(x1 - x0) <= tol and abs(y1 - y0) > 0.5:
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
    *, require_pair_at_label: bool = False,
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
            if require_pair_at_label and not all(
                any(abs(tt - t) <= 0.1 and a - 5.0 <= la <= b + 5.0
                    for tt, a, b in near)
                for t in (t0, t1)
            ):
                continue
            gap = 0.0 if t0 <= lt <= t1 else min(abs(lt - t0), abs(lt - t1))
            score = (0 if width_hint else abs(w - 19.0) / 50.0) + gap
            if best is None or score < best[0]:
                best = (score, t0, t1)
    return (best[1], best[2]) if best else None


def _nearest_section_width(
    label: dict, horizontal: bool, sections: list[dict], combined: bool = False,
) -> Optional[float]:
    lx, ly = float(label["pos"][0]), float(label["pos"][1])
    best = None
    for s in sections:
        if _rotation_axis(s.get("rotation")) is not horizontal:
            continue
        sx, sy = float(s["pos"][0]), float(s["pos"][1])
        dt = abs(sy - ly) if horizontal else abs(sx - lx)
        da = abs(sx - lx) if horizontal else abs(sy - ly)
        # Diagonal: rotulo e secao costumam ficar em lados OPOSTOS da faixa
        # (VF202 em cima, "14/55" embaixo, 34 cm); vale a distancia somada.
        if (dt > (LABEL_BAND_DIST if combined else 8.0)) or da > 700.0:
            continue
        score = da + dt if combined else da
        if best is None or score < best[0]:
            best = (score, s["section"][0])
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
            try:
                local = [scene.to_local(float(p[0]), float(p[1])) for p in pts]
            except (TypeError, ValueError, IndexError):
                continue
            ts = [p[1] if scene.is_horizontal else p[0] for p in local]
            if min(ts) < scene.t_lo - 1.0 or max(ts) > scene.t_hi + 1.0:
                continue  # fundo de outra faixa (contaminacao) nao e' referencia
            axs = [p[0] if scene.is_horizontal else p[1] for p in local]
            out.extend([min(axs), max(axs)])
    return sorted(set(round(v, 2) for v in out))


def _extent(
    scene_h: bool, t_lo: float, t_hi: float, label_axis: float,
    edges: _EdgeIndex, blockers: list[tuple[float, float]],
) -> Optional[tuple[float, float]]:
    lo_cov = _merge([tuple(i) for i in edges.coverage(scene_h, t_lo)], gap=1.0)
    hi_cov = _merge([tuple(i) for i in edges.coverage(scene_h, t_hi)], gap=1.0)
    # Trecho de viga so' existe onde as DUAS paredes existem. Com a uniao,
    # uma linha colinear a UMA face (V310: x=1380,4 desce ate' 2391 passando a
    # ponta da V303) esticava a viga sobre o que nao e' dela.
    pieces = []
    for a0, a1 in lo_cov:
        for b0, b1 in hi_cov:
            x, y = max(a0, b0), min(a1, b1)
            if y - x > 0.5:
                pieces.append([x, y])
    pieces = _merge([tuple(i) for i in pieces], gap=0.05)
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
    combined_section_hint: bool = False,
    allow_width_hint_fallback: bool = False,
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
        width = _nearest_section_width(label, horizontal, section_texts, combined_section_hint)
        band = _find_band(
            label, horizontal, edges, width,
            require_pair_at_label=allow_width_hint_fallback and width is None,
        ) or (
            _find_band(label, horizontal, edges, None,
                       require_pair_at_label=allow_width_hint_fallback)
            if width is None or allow_width_hint_fallback else None
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
    # Outra viga rotulada sobre a mesma faixa limita a extensao. A fronteira e'
    # o PILAR entre os dois rotulos (o mais proximo do proprio rotulo), nao o
    # ponto de insercao do texto vizinho: cortar no texto deixava lascas de
    # 2-15 cm alem do pilar (V329 2,84 no V330; V328 5,37; V309 15 no V309A) e,
    # com o rotulo vizinho colado na ponta, a V329 herdava a V328 inteira
    # (dono 2026-09-28). Sem pilar entre os rotulos, vale o ponto do texto.
    for other in other_labels:
        if _norm_name(other.get("text")) == name or _rotation_axis(other.get("rotation")) is not horizontal:
            continue
        ox, oy = float(other["pos"][0]), float(other["pos"][1])
        oa, ot = (ox, oy) if horizontal else (oy, ox)
        if not (t_lo - 8.0 <= ot <= t_hi + 8.0):
            continue
        if not (start - 5.0 <= oa <= end + 5.0) or abs(oa - label_axis) < 5.0:
            continue
        if oa > label_axis:
            between = [b0 for b0, b1 in blockers if label_axis - 1.0 <= b0 < oa]
            end = min(end, min(between) if between else oa)
        else:
            between = [b1 for b0, b1 in blockers if oa < b1 <= label_axis + 1.0]
            start = max(start, max(between) if between else oa)
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


def _side_face_is_short(scene: LvScene, poly, a0: float, a1: float, side: str) -> Optional[bool]:
    """A face do pilar ao longo da qual a lateral CORRE (paralela a' viga, sobre
    a linha da face ``side`` em [a0, a1]) e' face curta (C/D)?

    D-48/G10 (dono 2026-09-28): o Para PARA nas faces A/B/E/F/G/H do pilar e
    passa pelas C/D. A letra e' a da face por onde a lateral corre: pilar
    colinear (comprido na direcao da viga) corre pela A/B -> para. Curta =
    aresta do comprimento da menor aresta, bem menor que a maior; so' pilar
    retangular tem C/D (L/U: E..H -> False). Quadrado ou sem aresta sobre a
    linha -> None (fica solido, como antes).
    """
    t_face = scene.face_t(side)
    edges: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for g in getattr(poly, "geoms", [poly]):
        ring = getattr(g, "exterior", None)
        if ring is None:
            continue
        pts = [(p[0], p[1]) if scene.is_horizontal else (p[1], p[0]) for p in ring.coords]
        # funde arestas colineares consecutivas (vertice sobrando no contorno)
        merged: list[tuple[float, float]] = []
        for p in pts:
            if len(merged) >= 2:
                (x0, y0), (x1, y1) = merged[-2], merged[-1]
                ux, uy, vx, vy = x1 - x0, y1 - y0, p[0] - x1, p[1] - y1
                if abs(ux * vy - uy * vx) <= 1e-3 * (ux * ux + uy * uy) ** 0.5 * (vx * vx + vy * vy) ** 0.5:
                    merged[-1] = p
                    continue
            merged.append(p)
        edges += list(zip(merged, merged[1:]))
    lengths = [((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** 0.5 for p, q in edges]
    lengths = [v for v in lengths if v > 0.5]
    if not lengths:
        return None
    # Pilar especial (L/U/T, mais de 4 faces): as pontas dos ramos sao E/F/G/H,
    # onde o Para PARA (dono 2026-09-28) — so' o retangular tem C/D.
    if len(lengths) != 4:
        return False
    shortest, longest = min(lengths), max(lengths)
    if shortest >= 0.8 * longest:
        return None
    best = None
    for (p, q) in edges:
        if abs(q[1] - p[1]) > 0.5:
            continue  # so' arestas PARALELAS ao eixo (a lateral corre ao lado)
        t_edge = (p[1] + q[1]) / 2.0
        if abs(t_edge - t_face) > 1.5:
            continue
        lo, hi = min(p[0], q[0]), max(p[0], q[0])
        if min(hi, a1) - max(lo, a0) < 0.5:
            continue
        if best is None or hi - lo > best:
            best = hi - lo
    if best is None:
        return None
    return best <= shortest + 1.0


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
    # Tudo chega em coordenadas do DXF; a cena diagonal mede no proprio referencial.
    pillars = [(n, c, scene.to_local_geom(p)) for n, c, p in pillars]
    slabs = [(s, scene.to_local_geom(p)) for s, p in slabs]
    scene.passa_pillars = {"A": [], "B": []}
    scene.passa_incidents = {"A": [], "B": []}
    for side in ("A", "B"):
        inside, outside = _face_strips(scene, side, scene.start - margin, scene.end + margin)
        for name, classification, poly in pillars:
            lo, hi = scene.axis_bounds(poly)
            pin, pout = _face_strips(scene, side, lo, hi)
            inner = poly.intersection(pin)
            outer = poly.intersection(pout)
            outer_ranges = [scene.axis_bounds(g) for g in getattr(outer, "geoms", [outer]) if not g.is_empty]
            for g in getattr(inner, "geoms", [inner]):
                if g.is_empty or g.area <= 1e-6:
                    continue
                a0, a1 = scene.axis_bounds(g)
                cores = _merge((max(a0, x), min(a1, y)) for x, y in outer_ranges
                               if min(a1, y) - max(a0, x) >= 0.5)
                cursor = a0
                for x, y in cores + [[a1, a1]]:
                    if x - cursor >= 0.5:
                        scene.passa_pillars[side].append(dict(name=name, classification=classification,
                                                            start=cursor, end=x, miolo=False))
                    if y - x >= 0.5:
                        scene.passa_pillars[side].append(dict(name=name, classification=classification,
                                                            start=x, end=y, miolo=True))
                    cursor = y
        for name, classification, poly in pillars:
            inter = poly.intersection(inside)
            if inter.is_empty or inter.area <= 1e-6:
                continue
            outer = poly.intersection(outside)
            geoms = getattr(inter, "geoms", [inter])
            for g in geoms:
                a0, a1 = scene.axis_bounds(g)
                if a1 - a0 < 0.5:
                    continue
                # A face corre pela PAREDE do pilar quando o pilar so' existe do
                # lado de dentro da faixa; se o pilar existe dos DOIS lados da
                # face, ela passaria pelo MIOLO dele (VF301 face A em y=3193
                # dentro dos P2..P8) - ali a lateral tem de parar (dono 26/09).
                interior = False
                if not outer.is_empty and outer.area > 1e-6:
                    over = 0.0
                    for og in getattr(outer, "geoms", [outer]):
                        o0, o1 = scene.axis_bounds(og)
                        over += max(0.0, min(a1, o1) - max(a0, o0))
                    interior = over >= 0.5 * (a1 - a0)
                item = {"name": name, "start": a0, "end": a1,
                        "classification": classification, "miolo": interior,
                        # G10: face do pilar por onde a lateral corre e' C/D?
                        "face_lateral_curta": _side_face_is_short(scene, poly, a0, a1, side)}
                if classification.strip().upper() in ("", "INDETERMINADO"):
                    item["flag"] = "pilar_classificacao_indeterminada_tratado_como_solido"
                if a1 <= scene.start + 1.0 or a0 >= scene.end - 1.0:
                    key = "start" if a1 <= scene.start + 1.0 else "end"
                    found = next((x for x in scene.end_supports[key] if x["name"] == name), None)
                    if found is None:
                        found = dict(item, type="pilar", miolo_por_lado={})
                        scene.end_supports[key].append(found)
                    found.setdefault("miolo_por_lado", {})[side] = interior
                    found.setdefault("face_curta_por_lado", {})[side] = item["face_lateral_curta"]
                else:
                    scene.pillars[side].append(item)
        for other in other_scenes:
            if other is scene or other.beam_name == scene.beam_name:
                continue
            delta = abs(other.axis_angle - scene.axis_angle) % 180.0
            delta = min(delta, 180.0 - delta)
            if delta < 15.0:
                continue  # paralela nao incide
            # Sem folga de ponta: esticar a faixa num encontro obliquo fazia a
            # V306 cortar a face A da V307 e a V307 encurtar a face de fora da
            # V309 no canto em L (la' a diagonal so' vira a esquina).
            band = scene.to_local_geom(other.world_band())
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
            # Secao da incidente no ponto onde ela encosta nesta face.
            hx, hy = scene.to_world(*scene.point_local((a0 + a1) / 2.0, side))
            zone = other.section_at(other.local_axis(hx, hy))
            item = {
                "name": other.beam_name, "start": a0, "end": a1,
                "dim": zone["dim"] if zone else "", "depth": zone["depth"] if zone else None,
                "width": other.width, "crossing": crossing, "axis_center": junction,
                "obliqua": delta < 85.0,
            }
            # A beam reaching an exterior pillar wall is a real junction. It
            # must not inherit the rule for a beam embedded inside the pillar.
            item_passa = dict(item, embedded_in_pillar=any(
                poly.covers(hit) for _, _, poly in pillars
            ))
            scene.passa_incidents[side].append(item_passa)
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
    _trim_oblique_slivers(scene)


def _trim_oblique_slivers(scene: LvScene) -> None:
    """Lasca de ponta antes de viga que chega OBLIQUA nao e' parede.

    Encontro obliquo deixa um triangulo: na V306 a face A comecava 11,8 cm
    antes da VF202, do lado de fora da face da diagonal. Lasca menor que a
    largura da incidente vira ponta; a incidente passa a ser o apoio. So'
    encontro obliquo — T ortogonal com parede curta real fica intocado.
    """
    for side in ("A", "B"):
        lo, hi = scene.face_extent.get(side, (scene.start, scene.end))
        keep = []
        for inc in scene.incidents[side]:
            if inc.get("obliqua") and 0.0 <= inc["start"] - lo < inc["width"]:
                lo = inc["end"]
                scene.end_supports["start"].append(dict(inc, type="viga", face=side))
            elif inc.get("obliqua") and 0.0 <= hi - inc["end"] < inc["width"]:
                hi = inc["start"]
                scene.end_supports["end"].append(dict(inc, type="viga", face=side))
            else:
                keep.append(inc)
        scene.incidents[side] = keep
        if (lo, hi) != (scene.start, scene.end):
            scene.face_extent[side] = (lo, hi)


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
            twin = next(
                (o for o in scene.pillars["B"]
                 if o["name"] == item["name"] and abs(o["start"] - item["start"]) < 1.0),
                {},
            )
            miolo = {"A": bool(item.get("miolo")), "B": bool(twin.get("miolo"))}
            if item["start"] <= scene.start + 1.0 and item["end"] > scene.start + 0.5:
                scene.start = item["end"]
                curta = {"A": item.get("face_lateral_curta"), "B": twin.get("face_lateral_curta")}
                scene.end_supports["start"].append(dict(item, type="pilar", miolo_por_lado=miolo,
                                                        face_curta_por_lado=curta))
                changed = True
            elif item["end"] >= scene.end - 1.0 and item["start"] < scene.end - 0.5:
                scene.end = item["start"]
                curta = {"A": item.get("face_lateral_curta"), "B": twin.get("face_lateral_curta")}
                scene.end_supports["end"].append(dict(item, type="pilar", miolo_por_lado=miolo,
                                                      face_curta_por_lado=curta))
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


def _reading_angle(rotation: float) -> float:
    """Sentido de leitura do A (G0 estendido), em graus no intervalo [-90, 90).

    Horizontal -> 0 (esquerda->direita), vertical -> -90 (cima->baixo); a
    diagonal fica no meio do caminho e A = lado DIREITO desse sentido.
    """
    a = float(rotation or 0.0) % 180.0
    return a - 180.0 if a >= 90.0 else a


def _rotate_segs(segs, angle: float):
    c, s = math.cos(math.radians(-angle)), math.sin(math.radians(-angle))
    return [
        (x0 * c - y0 * s, x0 * s + y0 * c, x1 * c - y1 * s, x1 * s + y1 * c)
        for x0, y0, x1, y1 in segs
    ]


def _rotate_texts(texts: list[dict], angle: float) -> list[dict]:
    c, s = math.cos(math.radians(-angle)), math.sin(math.radians(-angle))
    out = []
    for t in texts:
        x, y = float(t["pos"][0]), float(t["pos"][1])
        out.append(dict(
            t, pos=(x * c - y * s, x * s + y * c),
            rotation=(float(t.get("rotation") or 0.0) - angle) % 360.0,
            _world_pos=tuple(t["pos"]),
        ))
    return out


def _refine_angle(label: dict, segs, angle: float) -> Optional[float]:
    """Angulo real das bordas junto ao rotulo (o texto erra centesimos de grau).

    Media ponderada pelo comprimento das linhas longas quase paralelas ao
    rotulo e a ate' LABEL_BAND_DIST dele. Sem borda: nao ha' viga ali.
    """
    lx, ly = float(label["pos"][0]), float(label["pos"][1])
    acc = weight = 0.0
    for x0, y0, x1, y1 in segs:
        length = math.hypot(x1 - x0, y1 - y0)
        if length < 30.0:
            continue
        ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
        diff = (ang - angle + 90.0) % 180.0 - 90.0
        if abs(diff) > 1.0:
            continue
        # distancia do rotulo a' reta (e a' extensao do trecho, com folga)
        ux, uy = (x1 - x0) / length, (y1 - y0) / length
        along = (lx - x0) * ux + (ly - y0) * uy
        if not (-60.0 <= along <= length + 400.0):
            continue
        if abs(-(lx - x0) * uy + (ly - y0) * ux) > LABEL_BAND_DIST:
            continue
        acc += (angle + diff) * length
        weight += length
    return acc / weight if weight else None


def _diagonal_scene(
    beam: dict, label: dict, structural_segs, dimension_segs, texts: list[dict],
    section_texts: list[dict], pillar_texts: list[dict], beam_labels: list[dict],
    pillars: list[tuple[str, str, Any]],
) -> Optional[LvScene]:
    """Caso 8 do guia: mede a viga diagonal num referencial girado.

    O mesmo codigo das vigas ortogonais roda sobre o desenho girado de
    ``-angle`` (eixo da viga vira horizontal, leitura do A para +x); a cena
    guarda ``angle`` e devolve os pontos ja' no DXF.
    """
    angle = _refine_angle(label, structural_segs, _reading_angle(label.get("rotation")))
    if angle is None:
        return None
    edges = _EdgeIndex(_rotate_segs(structural_segs, angle), tol=0.3)
    rot_label = _rotate_texts([label], angle)[0]
    near = lambda t: math.hypot(  # noqa: E731 - so' o que cabe na vizinhanca
        float(t["pos"][0]) - float(label["pos"][0]), float(t["pos"][1]) - float(label["pos"][1])
    ) <= 1500.0
    rot_sections = _rotate_texts([t for t in section_texts if near(t)], angle)
    rot_pillar_texts = _rotate_texts([t for t in pillar_texts if near(t)], angle)
    rot_beam_labels = _rotate_texts([t for t in beam_labels if near(t)], angle)
    rot_pillars = [(n, c, affinity.rotate(p, -angle, origin=(0.0, 0.0))) for n, c, p in pillars]
    scene = build_band_scene(
        beam, [], edges, rot_sections, rot_beam_labels, rot_pillars, only_label=rot_label,
        combined_section_hint=True,
    )
    if scene is None or not scene.is_horizontal:
        return None
    scene.angle = angle
    scene.labels = [{"text": label.get("text"), "pos": tuple(label["pos"])}]
    scene.provenance.update({
        "orientation_source": "label_rotation_diagonal",
        "angulo_eixo_graus": round(angle, 3),
        "regra": "guia_caso_8_normal_do_eixo",
    })
    _sections(scene, beam, rot_sections, rot_pillar_texts)
    dim_edges = _EdgeIndex(_rotate_segs(dimension_segs, angle), tol=0.3)
    scene.dimension_coverage = {
        "A": dim_edges.coverage(True, scene.t_lo),
        "B": dim_edges.coverage(True, scene.t_hi),
    }
    return scene


def _face_hull(scene: LvScene):
    """Faixa da viga ate' onde as FACES vao (diagonal: face de fora passa da faixa)."""
    if not scene.face_extent:
        return scene.world_band()
    (la, ha), (lb, hb) = (scene.face_extent.get(s, (scene.start, scene.end)) for s in ("A", "B"))
    return Polygon([scene.point(la, "A"), scene.point(ha, "A"),
                    scene.point(hb, "B"), scene.point(lb, "B")]).buffer(0)


def _oblique_ends(scene: LvScene, others: list[LvScene]) -> tuple[str, ...]:
    """Pontas de uma viga ORTOGONAL que encostam numa diagonal (canto em esquadro obliquo)."""
    return tuple(_oblique_end_neighbours(scene, others))


def _oblique_end_neighbours(scene: LvScene, others: list[LvScene]) -> dict[str, LvScene]:
    reach = 3.0 * scene.width
    ends: dict[str, LvScene] = {}
    for end, (a0, a1) in (("start", (scene.start - reach, scene.start + 0.5)),
                          ("end", (scene.end - 0.5, scene.end + reach))):
        probe = (box(a0, scene.t_lo, a1, scene.t_hi) if scene.is_horizontal
                 else box(scene.t_lo, a0, scene.t_hi, a1))
        for o in others:
            if o.angle and o.beam_name != scene.beam_name:
                hit = scene.to_local_geom(o.world_band()).intersection(probe)
                if hit.is_empty or hit.area <= 1e-6:
                    continue
                # canto em L: a diagonal CONTINUA a viga (ocupa a largura dela
                # alem da ponta). Diagonal chegando de fora numa face (VF202
                # na face A da V306) so' encosta na borda da faixa.
                minx, miny, maxx, maxy = hit.bounds
                span = (maxy - miny) if scene.is_horizontal else (maxx - minx)
                if span >= 0.5 * scene.width:
                    ends[end] = o
                    break
    return ends


CORNER_STUB_SOURCE = "trecho_de_canto_em_L"


def _corner_stubs_beyond_pillar(
    scenes: list[LvScene], pillars: list[tuple[str, str, Any]],
) -> list[tuple[str, LvScene]]:
    """Canto em L (ortogonal x diagonal) com PILAR entre o rotulo e o canto.

    Dono 2026-09-28 (V309 x V307 no P25): a viga termina na propria
    delimitacao — o pilar. O trecho pilar -> canto ja' nao e' continuacao dela,
    e' da outra viga (a diagonal que faz o L). A ortogonal passa a comecar no
    pilar e o trecho vira um TRECHO a mais da diagonal, sobre a faixa da
    ortogonal (mesmo mecanismo da viga em L com dois rotulos). Sem pilar entre
    rotulo e canto vale a regra v7: a face de fora vai ate' o canto de fora.
    """
    stubs: list[tuple[str, LvScene]] = []
    for scene in scenes:
        if scene.angle or not scene.labels:
            continue
        pos = scene.labels[0]["pos"]
        label_axis = float(pos[0] if scene.is_horizontal else pos[1])
        strip = scene.rect(-1e7, 1e7, scene.t_lo + 0.2, scene.t_hi - 0.2)
        spans = []
        for _, _, poly in pillars:
            inter = poly.intersection(strip)
            if not inter.is_empty and inter.area > 1e-6:
                spans.append(scene.axis_bounds(inter))
        for end, diag in _oblique_end_neighbours(scene, scenes).items():
            ext = {s: scene.face_extent.get(s, (scene.start, scene.end)) for s in ("A", "B")}
            if end == "start":
                cand = [s for s in spans if s[0] >= scene.start - 1.0 and s[1] <= label_axis]
                if not cand:
                    continue
                cut = min(cand)[0]
                corner = {s: ext[s][0] for s in ext}
            else:
                cand = [s for s in spans if s[1] <= scene.end + 1.0 and s[0] >= label_axis]
                if not cand:
                    continue
                cut = max(cand, key=lambda s: s[1])[1]
                corner = {s: ext[s][1] for s in ext}
            if abs(cut - (scene.start if end == "start" else scene.end)) < 1.0:
                continue  # pilar ja' encosta no canto: nao sobra trecho
            # O lado X do trecho tem de continuar o lado X da diagonal (a face
            # que chega no mesmo canto). Lados trocados: nao repassa (sinaliza).
            diag_ext = {s: diag.face_extent.get(s, (diag.start, diag.end)) for s in ("A", "B")}
            matches = []
            for side in ("A", "B"):
                cx, cy = scene.point(corner[side], side)
                matches.append(min(
                    (math.hypot(cx - px, cy - py), other, k)
                    for other in ("A", "B")
                    for k, (px, py) in enumerate(
                        (diag.point(diag_ext[other][0], other), diag.point(diag_ext[other][1], other)))
                ) + (side,))
            if any(m[1] != m[3] for m in matches):
                scene.provenance.setdefault("canto_em_L_nao_repassado", []).append(
                    {"ponta": end, "viga": diag.beam_name, "motivo": "lados_trocados"})
                continue
            zones = sorted(diag.sections, key=lambda z: z["start"])
            # ponta da diagonal que encosta no canto -> secao daquela ponta
            zone = (zones[0] if matches[0][2] == 0 else zones[-1]) if zones else None
            lo, hi = (scene.start, cut) if end == "start" else (cut, scene.end)
            stub = LvScene(diag.beam_name, scene.is_horizontal, scene.t_lo, scene.t_hi, lo, hi)
            stub.face_extent = {
                s: ((corner[s], cut) if end == "start" else (cut, corner[s])) for s in ("A", "B")
            }
            stub.face_coverage = scene.face_coverage
            stub.dimension_coverage = scene.dimension_coverage
            stub.sections = [dict(zone, start=lo, end=hi, end_source=CORNER_STUB_SOURCE)] if zone else []
            stub.provenance = {
                "band_source": CORNER_STUB_SOURCE,
                "viga_da_faixa": scene.beam_name,
                "regra": "canto_em_L_alem_do_pilar_e_da_outra_viga",
            }
            # A ortogonal comeca na face de LA' do pilar (o pilar vira apoio de
            # ponta dela: Para para na face, Passa engloba).
            far = min(cand)[1] if end == "start" else max(cand, key=lambda s: s[1])[0]
            if end == "start":
                scene.start = far
            else:
                scene.end = far
            for side in ("A", "B"):
                lo_s, hi_s = ext[side]
                scene.face_extent[side] = (far, hi_s) if end == "start" else (lo_s, far)
            scene.provenance.setdefault("canto_em_L_repassado", []).append(
                {"ponta": end, "viga": diag.beam_name, "ate_pilar": round(cut, 2)})
            stubs.append((diag.beam_name, stub))
    return stubs


def _end_depth(scene: LvScene, end: str) -> Optional[float]:
    zones = sorted(scene.sections, key=lambda z: z["start"])
    if not zones:
        return None
    return float((zones[0] if end == "start" else zones[-1])["depth"])


def _cede_shared_end_pillars(scenes: list[LvScene]) -> None:
    """Passa: pilar entre duas vigas COLINEARES, cada uma encostando de um lado.

    Dono 2026-09-28: so' a MAIS PROFUNDA engloba o pilar (a lateral dela
    tapa o pilar); a outra para na face. Mesma altura: as duas mantem.
    """
    for sc in scenes:
        for end in ("start", "end"):
            mine = _end_depth(sc, end)
            for sup in sc.end_supports[end]:
                if sup.get("type") != "pilar":
                    continue
                for other in scenes:
                    if other.beam_name == sc.beam_name or abs(other.axis_angle - sc.axis_angle) > 1.0:
                        continue
                    if abs(other.t_lo - sc.t_lo) > 1.0 or abs(other.t_hi - sc.t_hi) > 1.0:
                        continue
                    for oend in ("start", "end"):
                        if not any(s.get("type") == "pilar" and s.get("name") == sup.get("name")
                                   for s in other.end_supports[oend]):
                            continue
                        theirs = _end_depth(other, oend)
                        if mine is not None and theirs is not None and theirs > mine + 0.01:
                            sup["cede_para"] = other.beam_name
                            # Pilar oco em pecas (P27): a mais profunda engloba
                            # o pilar INTEIRO, inclusive a peca do lado cedido.
                            for s in other.end_supports[oend]:
                                if s.get("type") == "pilar" and s.get("name") == sup.get("name"):
                                    s["engloba_ini"] = min(s.get("engloba_ini", s["start"]), sup["start"])
                                    s["engloba_fim"] = max(s.get("engloba_fim", s["end"]), sup["end"])


def _diagonal_face_extents(scene: LvScene, others: list[LvScene],
                           ends: tuple[str, ...] = ("start", "end")) -> None:
    """Pontas em esquadro obliquo: cada face vai ate' onde a PROPRIA linha vai.

    Nunca entra na faixa de outra viga: a face de baixo da V307 continua reta
    na VF202 (mesmo alinhamento) e ali a lateral da V307 ja' acabou. Vale
    tambem para a ponta da ortogonal que chega numa diagonal (canto em L
    VF203 x VF202: a face de fora vai ate' o canto de fora).
    """
    reach = 3.0 * scene.width
    neighbours = [o for o in others if o is not scene and o.beam_name != scene.beam_name]
    bands = [(scene.to_local_geom(o.world_band()), scene.to_local_geom(_face_hull(o)))
             for o in neighbours]
    for side in ("A", "B"):
        lo, hi = scene.start, scene.end
        for a, b in _merge([tuple(i) for i in scene.face_coverage[side]], gap=1.0):
            if "start" in ends and a <= scene.start + 1.0 and b >= scene.start - 1.0:
                lo = max(a, scene.start - reach)
            if "end" in ends and a <= scene.end + 1.0 and b >= scene.end - 1.0:
                hi = min(b, scene.end + reach)
        for band, hull in bands:
            if hi > scene.end + 0.5:
                inside, outside = _face_strips(scene, side, scene.end + 0.5, hi)
                hit = band.intersection(inside)
                if not hit.is_empty and hit.area > 1e-6:
                    hi = max(scene.end, scene.axis_bounds(hit)[0])
                if not scene.angle and hull.intersection(outside).area > 1e-6:
                    hi = scene.end  # outra viga chega por fora nesse trecho: nao e' canto
            if lo < scene.start - 0.5:
                inside, outside = _face_strips(scene, side, lo, scene.start - 0.5)
                hit = band.intersection(inside)
                if not hit.is_empty and hit.area > 1e-6:
                    lo = min(scene.start, scene.axis_bounds(hit)[1])
                if not scene.angle and hull.intersection(outside).area > 1e-6:
                    lo = scene.start  # VF202 na face A da V306
        scene.face_extent[side] = (lo, hi)


def _split_shared_diagonal_faces(diagonals: list[LvScene]) -> None:
    """Duas vigas diagonais alinhadas dividindo a MESMA linha de face.

    V307 (19/55) e VF202 (14/55) no 13_PAV: a face A e' uma linha continua e
    cada uma estendia a propria ponta sobre a outra. Convencao (a revisar
    pelo dono): a primeira termina onde acaba o trecho comum as duas faces
    dela; a seguinte comeca exatamente ali — sem sobreposicao nem buraco.
    """
    for first in diagonals:
        for second in diagonals:
            if first is second or first.beam_name == second.beam_name:
                continue
            if abs(first.axis_angle - second.axis_angle) > 1.0:
                continue
            for side in ("A", "B"):
                if side not in first.face_extent:
                    continue
                wx, wy = first.point(first.end, side)
                sx = second.local_axis(wx, wy)
                st = second.to_local(wx, wy)[1]
                if sx < second.start - 3.0 * second.width or sx > second.start + 0.5:
                    continue  # second nao vem logo depois de first
                for other_side in ("A", "B"):
                    if abs(second.face_t(other_side) - st) > 1.0:
                        continue
                    lo2, hi2 = second.face_extent.get(other_side, (second.start, second.end))
                    lo1, hi1 = first.face_extent[side]
                    if hi1 <= first.end + 0.5 and lo2 >= sx - 0.5:
                        continue
                    first.face_extent[side] = (lo1, first.end)
                    second.face_extent[other_side] = (min(sx, second.start), hi2)
                    first.provenance.setdefault("fronteira_face_compartilhada", []).append(
                        {"face": side, "com": second.beam_name, "convencao": "fim_do_trecho_comum"})
                    second.provenance.setdefault("fronteira_face_compartilhada", []).append(
                        {"face": other_side, "com": first.beam_name, "convencao": "fim_do_trecho_comum"})


def build_scene_runs(
    beams: list[dict],
    texts: list[dict],
    lines: list[dict],
    pillar_report: Any,
    slabs: Any = None,
    *, allow_width_hint_fallback: bool = False,
) -> dict[str, list[LvScene]]:
    """Um ou mais TRECHOS por viga: cada rotulo ortogonal abre uma faixa.

    Viga em "L" (V330 no 13_PAV: um rotulo a 90 e outro a 0 graus) vira dois
    trechos, cada um com orientacao e A/B proprios (G0). Rotulos da mesma
    faixa colapsam num trecho so'. Rotulo diagonal (Caso 8) fica de fora.
    """
    structural_segs, dimension_segs = split_dimension_lines(_line_segments(lines), texts)
    edges = _EdgeIndex(structural_segs)
    dim_edges = _EdgeIndex(dimension_segs)
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
                scene = _diagonal_scene(
                    beam, label, structural_segs, dimension_segs, texts,
                    section_texts, pillar_texts, beam_labels, pillars,
                )
            else:
                scene = build_band_scene(
                    beam, texts, edges, section_texts, beam_labels, pillars, only_label=label,
                    allow_width_hint_fallback=allow_width_hint_fallback,
                )
            if scene is None:
                continue
            duplicate = any(
                abs(other.axis_angle - scene.axis_angle) < 1.0
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
            if scene.angle:
                continue  # diagonal ja' mediu secoes e cotas no proprio referencial
            _sections(scene, by_name[name], section_texts, pillar_texts)
            scene.dimension_coverage = {
                "A": dim_edges.coverage(scene.is_horizontal, scene.t_lo),
                "B": dim_edges.coverage(scene.is_horizontal, scene.t_hi),
            }
            scene.provenance["linhas_de_cota_excluidas"] = len(dimension_segs)
    slab_polys = _slab_polygons(slabs)
    others = [scene for scenes in runs.values() for scene in scenes]
    for scene in others:
        if scene.angle:
            _diagonal_face_extents(scene, others)
    _split_shared_diagonal_faces([sc for sc in others if sc.angle])
    for scene in others:
        if not scene.angle:
            ends = _oblique_ends(scene, others)
            if ends:
                _diagonal_face_extents(scene, others, ends)
    stubs = _corner_stubs_beyond_pillar(others, pillars)
    for scene in others:
        _attach_context(scene, pillars, others, slab_polys)
    for owner, stub in stubs:
        _attach_context(stub, pillars, others, slab_polys)
        # O pilar e' a delimitacao da viga da faixa: o trecho de canto para
        # na face dele tambem no Passa.
        for sup in stub.end_supports["start"] + stub.end_supports["end"]:
            if sup.get("type") == "pilar":
                sup["cede_para"] = stub.provenance["viga_da_faixa"]
        runs.setdefault(owner, []).append(stub)
    _cede_shared_end_pillars([sc for scs in runs.values() for sc in scs])
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
