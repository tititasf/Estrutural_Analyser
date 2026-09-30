"""CIMA DXF de pilar especial (L) — conversão do motor SCR.

O legado (``CIMA_FUNCIONAL_EXCEL.calcular_globais_pilar_especial_L``) gera
dois scripts retangulares (CIMA_1 + CIMA_2) e aplica globais de tamanho/posição
em PAI, grade, parafuso e metal. Aqui o DXF desenha a seção L de uma vez,
com as mesmas fórmulas, a partir do contorno N1 (não só da ficha N2).
"""
from __future__ import annotations

import math
from typing import Any

from src.core.cima_l_contract import (
    _grade_starts_widths,
    _n1_base,
    build_cima_l_contract,
    flatten_cima_l_into_robot,
    globais_pilar_especial_l,
    paineis_l_from_secao,
    secao_l_do_payload,
)
from src.core.pillar_special_faces import physical_ring


# Sanduíche N2 CIMA (cm): concreto → chapa 1.8 → sarrafo 2.2 → madeira 7 → perfil 10.
TC = 1.8
TS = 2.2
CORNER_W = 7.0
CORNER_H = 2.0
SARR_H = 7.0
PERFIL_EXT = 18.0  # extra em cada ponta livre da face externa (N2 240+36≈276)


def _centered_ring(points: Any, ox: float, oy: float) -> list[tuple[float, float]]:
    ring = physical_ring(points)
    if len(ring) < 6:
        return []
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    return [(p[0] - cx + ox, p[1] - cy + oy) for p in ring]


def _canonical_l_ring(ox: float, oy: float, secao: dict[str, float]) -> list[tuple[float, float]]:
    ex, ix = secao["externa_x"], secao["interna_x"]
    ey, iy = secao["externa_y"], secao["interna_y"]
    x0, y0 = ox - ex / 2.0, oy - ey / 2.0
    return [
        (x0, y0), (x0 + ex, y0), (x0 + ex, y0 + ey - iy),
        (x0 + ix, y0 + ey - iy), (x0 + ix, y0 + ey), (x0, y0 + ey),
    ]


def _signed_area(ring: list[tuple[float, float]]) -> float:
    total = 0.0
    for i, p0 in enumerate(ring):
        p1 = ring[(i + 1) % len(ring)]
        total += p0[0] * p1[1] - p1[0] * p0[1]
    return total / 2.0


def _intersect(p1, p2, p3, p4) -> tuple[float, float] | None:
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def offset_ring(ring: list[tuple[float, float]], dist: float) -> list[tuple[float, float]]:
    """Offset para fora por arestas paralelas + interseção (canto interno do L)."""
    n = len(ring)
    if n < 3 or abs(dist) < 1e-9:
        return list(ring)
    ccw = _signed_area(ring) > 0.0
    shifted: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for i, p0 in enumerate(ring):
        p1 = ring[(i + 1) % n]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        length = math.hypot(dx, dy) or 1.0
        if ccw:
            nx, ny = dy / length, -dx / length
        else:
            nx, ny = -dy / length, dx / length
        shifted.append((
            (p0[0] + nx * dist, p0[1] + ny * dist),
            (p1[0] + nx * dist, p1[1] + ny * dist),
        ))
    out: list[tuple[float, float]] = []
    for i in range(n):
        a0, a1 = shifted[i - 1]
        b0, b1 = shifted[i]
        hit = _intersect(a0, a1, b0, b1)
        out.append(hit if hit is not None else b0)
    return out


def _add_closed(msp, pts, layer, entities, color=None):
    e = msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})
    if color is not None:
        e.dxf.color = color
    entities.append(e)
    return e


def _l_orientation(ring: list[tuple[float, float]], thick: float) -> tuple[bool, bool]:
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    x0, y0, y1 = min(xs), min(ys), max(ys)
    mid_y = (y0 + y1) / 2.0
    top_xs = [p[0] for p in ring if p[1] >= mid_y]
    stem_left = (min(top_xs) if top_xs else x0) <= x0 + thick + 1.0
    mid_x = (min(xs) + max(xs)) / 2.0
    right_ys = [p[1] for p in ring if p[0] >= mid_x]
    bar_bottom = (min(right_ys) if right_ys else y0) <= y0 + thick + 1.0
    return stem_left, bar_bottom


def _pt(origin, along, across, u, v) -> tuple[float, float]:
    return (origin[0] + along[0] * u + across[0] * v,
            origin[1] + along[1] * u + across[1] * v)


def _rect(msp, entities, origin, along, across, u0, v0, du, dv, layer, color=None):
    pts = [
        _pt(origin, along, across, u0, v0),
        _pt(origin, along, across, u0 + du, v0),
        _pt(origin, along, across, u0 + du, v0 + dv),
        _pt(origin, along, across, u0, v0 + dv),
    ]
    return _add_closed(msp, pts, layer, entities, color)


PERFIL_H = 10.0
# Distâncias N2 (cm, antes do 2×): ticks saem da borda do perfil.
# Face externa (240/176): pilha larga. Face interna (210/153): pilha justa
# para o L do vazio não cruzar texto de 210 com 153.
COTA_OUTER = (18.0, 28.0, 56.0)
COTA_INNER = (6.0, 17.0, 33.0)
TICK = 1.6


def _fmt_cm(value: float) -> str:
    return f"{value:.0f}" if abs(value - round(value)) < 1e-6 else f"{value:g}"


def _add_centered_text(msp, entities, xy, text, height, rot, layer="COTA"):
    """Centro visual na linha da cota. Insert DXF é baseline-esquerda; matplotlib ignora align."""
    width = 0.70 * height * max(1, len(text or " "))
    cx, cy = float(xy[0]), float(xy[1])
    if abs(rot) >= 45.0:
        insert = (cx + 0.18 * height, cy - width / 2.0)
    else:
        insert = (cx - width / 2.0, cy - 0.18 * height)
    e = msp.add_text(
        text,
        dxfattribs={"layer": layer, "insert": insert, "height": height, "rotation": rot},
    )
    entities.append(e)
    return e


def _text_aabb(x: float, y: float, text: str, height: float, rot: float) -> tuple[float, float, float, float]:
    """Caixa aproximada do TEXT (insert = centro). Rot 90 troca os eixos."""
    width = max(3.5, 0.62 * height * max(1, len(text)))
    tall = height * 1.3
    if abs(rot) >= 45.0:
        width, tall = tall, width
    return (x - width / 2.0, y - tall / 2.0, x + width / 2.0, y + tall / 2.0)


def _boxes_overlap(a, b, pad: float = 1.6) -> bool:
    return not (
        a[2] + pad <= b[0] or b[2] + pad <= a[0]
        or a[3] + pad <= b[1] or b[3] + pad <= a[1]
    )


def _line_hits_box(x1, y1, x2, y2, box, thick: float = 1.4) -> bool:
    xmin, ymin, xmax, ymax = box
    xmin -= thick
    ymin -= thick
    xmax += thick
    ymax += thick
    dx, dy = x2 - x1, y2 - y1
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return xmin <= x1 <= xmax and ymin <= y1 <= ymax
    hits = []
    if abs(dx) > 1e-9:
        for xedge in (xmin, xmax):
            t = (xedge - x1) / dx
            if 0.0 <= t <= 1.0:
                y = y1 + t * dy
                if ymin <= y <= ymax:
                    hits.append(True)
    if abs(dy) > 1e-9:
        for yedge in (ymin, ymax):
            t = (yedge - y1) / dy
            if 0.0 <= t <= 1.0:
                x = x1 + t * dx
                if xmin <= x <= xmax:
                    hits.append(True)
    if xmin <= x1 <= xmax and ymin <= y1 <= ymax:
        return True
    if xmin <= x2 <= xmax and ymin <= y2 <= ymax:
        return True
    return bool(hits)


class CotaBook:
    """Livro de obstáculos: linhas de cota ficam; só o texto desliza se colidir."""

    def __init__(self):
        self.lines: list[tuple[float, float, float, float]] = []
        self.boxes: list[tuple[float, float, float, float]] = []

    def add_line(self, p1, p2):
        self.lines.append((float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1])))

    def blocked(self, box, rot: float) -> bool:
        if any(_boxes_overlap(box, other) for other in self.boxes):
            return True
        vertical_text = abs(rot) >= 45.0
        for x1, y1, x2, y2 in self.lines:
            line_vertical = abs(x2 - x1) < abs(y2 - y1)
            # Só linhas que CRUZAM o texto (a cota própria é paralela e deve ficar).
            if vertical_text == line_vertical:
                continue
            if _line_hits_box(x1, y1, x2, y2, box):
                return True
        return False

    def place(self, origin, along, across, u0, u1, v_line, text, height, rot) -> tuple[float, float]:
        u0, u1 = (u0, u1) if u1 >= u0 else (u1, u0)
        mid = (u0 + u1) / 2.0
        upper = (text or "").upper()
        # Totais GRADE / PAINEL / PARAFUSOS: sempre no centro da linha da cota.
        is_total = any(tag in upper for tag in ("GRADE", "PAINEL", "PARAFUSO"))
        if is_total or len(text) <= 3:
            us = [mid]
            vs = [v_line + 3.0, v_line + 6.5]
        else:
            lo, hi = u0 + 0.18 * (u1 - u0), u1 - 0.12 * (u1 - u0)
            step = max(3.0, min(8.0, (u1 - u0) / 10.0))
            us = [mid]
            k = 1
            while mid + k * step <= hi:
                us.append(mid + k * step)
                k += 1
            k = 1
            while mid - k * step >= lo:
                us.append(mid - k * step)
                k += 1
            vs = [v_line + 3.0, v_line + 7.0, v_line + 11.0, v_line + 1.2]
        for v in vs:
            for u in us:
                x, y = _pt(origin, along, across, u, v)
                box = _text_aabb(x, y, text, height, rot)
                if not self.blocked(box, rot):
                    self.boxes.append(box)
                    return x, y
        x, y = _pt(origin, along, across, mid, v_line + 3.0)
        self.boxes.append(_text_aabb(x, y, text, height, rot))
        return x, y


def _cota_chain(msp, entities, origin, along, across, u0, segments, v_attach, v_line, labels, height=5.0, book: CotaBook | None = None):
    """Cota N2/legado: ticks da borda (perfil) até a linha; texto desvia de colisão."""
    if not segments:
        return
    rot = 90.0 if abs(along[1]) >= abs(along[0]) else 0.0
    bounds = [u0]
    cursor = u0
    for seg in segments:
        cursor += float(seg)
        bounds.append(cursor)
    attribs = {"layer": "COTA"}
    p_line_a = _pt(origin, along, across, bounds[0], v_line)
    p_line_b = _pt(origin, along, across, bounds[-1], v_line)
    entities.append(msp.add_line(p_line_a, p_line_b, dxfattribs=attribs))
    if book is not None:
        book.add_line(p_line_a, p_line_b)
    for u in bounds:
        tick_a = _pt(origin, along, across, u, v_attach)
        tick_b = _pt(origin, along, across, u, v_line)
        entities.append(msp.add_line(tick_a, tick_b, dxfattribs=attribs))
        if book is not None:
            book.add_line(tick_a, tick_b)
        entities.append(msp.add_line(
            _pt(origin, along, across, u - TICK, v_line),
            _pt(origin, along, across, u + TICK, v_line),
            dxfattribs=attribs,
        ))
    cursor = u0
    for seg, lab in zip(segments, labels):
        u_a, u_b = cursor, cursor + float(seg)
        if book is not None:
            x, y = book.place(origin, along, across, u_a, u_b, v_line, lab, height, rot)
        else:
            x, y = _pt(origin, along, across, (u_a + u_b) / 2.0, v_line + 3.0)
        _add_centered_text(msp, entities, (x, y), lab, height, rot, "COTA")
        cursor += float(seg)


def _draw_face_strip(
    msp, entities, origin, along, across, arm: dict, *,
    outer: bool, book: CotaBook | None = None, thick: float = 19.0,
    arm_id: str = "", globais: dict | None = None,
):
    """Uma face CIMA = o mesmo recorte do retângulo, 4 camadas:

    concreto → chapa 1.8 → sarrafo 2.2 → madeira 7 → perfil 10
    cotas (do perfil para fora): quadradinho → GRADE → PAINEL
    parafuso: 7×7 na madeira nas juntas + traço só na espessura
    """
    widths = [float(w) for w in (arm.get("grade_widths") or []) if w]
    if not widths:
        gw = float(arm.get("grade_width") or 0.0)
        ng = int(arm.get("n_grades") or 1)
        if gw > 0:
            widths = [gw] * max(1, ng)
    if not widths:
        return
    gaps = [float(g) for g in (arm.get("gaps") or [])]
    divs = arm.get("quadradinhos") or []
    starts = _grade_starts_widths(widths, gaps)
    madeira_v0 = TC + TS
    madeira_h = CORNER_W
    panel = float(arm.get("grade_externa") or (starts[-1] + widths[-1]))

    for gi, start in enumerate(starts):
        gw = widths[gi]
        _rect(msp, entities, origin, along, across, start, madeira_v0, gw, madeira_h, "Madeira", 126)
        _rect(msp, entities, origin, along, across, start, madeira_v0, CORNER_W, madeira_h, "Madeira", 126)
        _rect(msp, entities, origin, along, across, start + gw - CORNER_W, madeira_v0, CORNER_W, madeira_h, "Madeira", 126)
        _rect(msp, entities, origin, along, across, start, madeira_v0, CORNER_W, madeira_h, "MEIO_PONT", 93)
        _rect(msp, entities, origin, along, across, start + gw - CORNER_W, madeira_v0, CORNER_W, madeira_h, "MEIO_PONT", 93)
        cumulative = 0.0
        for segment in (divs[gi] if gi < len(divs) else [])[:-1]:
            cumulative += float(segment)
            _rect(
                msp, entities, origin, along, across,
                start + cumulative - CORNER_W / 4.0, madeira_v0,
                CORNER_W / 2.0, madeira_h, "Madeira", 126,
            )
            _rect(
                msp, entities, origin, along, across,
                start + cumulative - CORNER_W / 2.0, madeira_v0,
                CORNER_W, madeira_h, "MEIO_PONT", 93,
            )

    rot = 90.0 if abs(along[1]) >= abs(along[0]) else 0.0
    perfil_v0 = madeira_v0 + madeira_h
    globais = globais or {}
    if outer:
        # N2: canal 10cm com +18 em cada ponta livre (240+36≈276, 176+36≈212).
        perfil_u0, perfil_w = -PERFIL_EXT, panel + 2 * PERFIL_EXT
    else:
        # N2 interno: flush no canto; extra na ponta livre (haste +11, ramo +4.4).
        extra = float(globais.get("chapa_one") or 11.0) if "haste" in arm_id else float(globais.get("sarrafo_thick") or 4.4)
        perfil_u0, perfil_w = 0.0, panel + extra
    _rect(msp, entities, origin, along, across, perfil_u0, perfil_v0, perfil_w, PERFIL_H, "Perfil Metálico", 224)
    _rect(msp, entities, origin, along, across, perfil_u0, perfil_v0 + TC, perfil_w, PERFIL_H - 2 * TC, "Perfil Metálico", 224)

    v_attach = perfil_v0 + PERFIL_H
    d_quad, d_grade, d_panel = COTA_OUTER if outer else COTA_INNER
    v_quad = v_attach + d_quad
    v_grade = v_attach + d_grade
    v_panel = v_attach + d_panel

    def _label(u, v, txt, height=5.0, layer="COTA"):
        _add_centered_text(msp, entities, _pt(origin, along, across, u, v), txt, height, rot, layer)

    for gi, start in enumerate(starts):
        segs = [float(s) for s in (divs[gi] if gi < len(divs) else []) if float(s) > 0]
        if segs:
            _cota_chain(
                msp, entities, origin, along, across, start, segs,
                v_attach, v_quad, [_fmt_cm(s) for s in segs], book=book,
            )
        gw = widths[gi]
        _label(start + gw / 2.0, madeira_v0 + 1.5, f"G{gw:.0f}", 4.5, "NOMENCLATURA")
        _cota_chain(
            msp, entities, origin, along, across, start, [gw],
            v_attach, v_grade, [f"{_fmt_cm(gw)}(GRADE)"], book=book,
        )
        if gaps and gi < len(gaps) and gaps[gi] > 0.4:
            _cota_chain(
                msp, entities, origin, along, across, start + gw, [gaps[gi]],
                v_attach, v_quad, [_fmt_cm(gaps[gi])], book=book,
            )
    _cota_chain(
        msp, entities, origin, along, across, 0.0, [panel],
        v_attach, v_panel, [f"{_fmt_cm(panel)} PAINEL"], book=book,
    )

    stations: list[float] = []
    for gi, start in enumerate(starts):
        gw = widths[gi]
        stations.extend([start, start + gw])
        cursor = 0.0
        for segment in (divs[gi] if gi < len(divs) else [])[:-1]:
            cursor += float(segment)
            stations.append(start + cursor)
    seen: set[float] = set()
    for u in stations:
        key = round(u, 2)
        if key in seen:
            continue
        seen.add(key)
        _rect(msp, entities, origin, along, across, u - 0.5, -thick, 1.0, thick, "Hachura")


def draw_cima_l(msp, ox, oy, nome, pj: dict) -> int:
    """CIMA em L: concreto + 4 faces longas (grades, quadradinhos, parafusos 7×7)."""
    secao = secao_l_do_payload(pj)
    if not secao:
        return 0
    contract = build_cima_l_contract(pj)
    if contract:
        flatten_cima_l_into_robot(pj, contract)
    points = pj.get("geometry_points") if isinstance(pj, dict) else None
    if not points:
        points = _n1_base(pj).get("geometry_points")
    ring = _centered_ring(points, ox, oy)
    if len(ring) != 6:
        ring = _canonical_l_ring(ox, oy, secao)
    thick = float((contract or {}).get("secao", {}).get("espessura") or secao["interna_x"])
    paineis = (contract or {}).get("paineis") or paineis_l_from_secao(secao)
    entities: list = []

    _add_closed(msp, ring, "Painéis", entities)
    _add_closed(msp, offset_ring(ring, TC), "CHAPA", entities)
    sarr = offset_ring(ring, TC + TS)
    e = _add_closed(msp, sarr, "SARRAFO", entities)
    e.dxf.color = 251

    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    stem_left, bar_bottom = _l_orientation(ring, thick)
    arms = (contract or {}).get("arms") or {}
    sign_y = 1.0 if bar_bottom else -1.0
    y_bar = y0 if bar_bottom else y1
    y_free = y1 if bar_bottom else y0
    x_stem = x0 if stem_left else x1
    x_free = x1 if stem_left else x0
    sign_x = 1.0 if stem_left else -1.0

    # Haste externa: 11 cm extra em cada ponta, origem na ponta da barra.
    haste_ext_origin = (x_stem, y_bar - 11.0 * sign_y)
    haste_ext_along = (0.0, sign_y)
    haste_ext_across = (-sign_x, 0.0)
    # Haste interna: começa no canto interno, extra só na ponta livre.
    haste_int_origin = (x_stem + thick * sign_x, y_bar + thick * sign_y)
    haste_int_along = (0.0, sign_y)
    haste_int_across = (sign_x, 0.0)
    # Ramo externo: origem no encontro com a haste, extra na ponta livre.
    ramo_ext_origin = (x_stem, y_bar)
    ramo_ext_along = (sign_x, 0.0)
    ramo_ext_across = (0.0, -sign_y)
    # Ramo interno: origem no canto interno, extra na ponta livre.
    ramo_int_origin = (x_stem + thick * sign_x, y_bar + thick * sign_y)
    ramo_int_along = (sign_x, 0.0)
    ramo_int_across = (0.0, sign_y)

    book = CotaBook()
    strips = (
        ("haste_ext", haste_ext_origin, haste_ext_along, haste_ext_across, True),
        ("ramo_ext", ramo_ext_origin, ramo_ext_along, ramo_ext_across, True),
        ("haste_int", haste_int_origin, haste_int_along, haste_int_across, False),
        ("ramo_int", ramo_int_origin, ramo_int_along, ramo_int_across, False),
    )
    for name, origin, along, across, outer in strips:
        arm = arms.get(name) or arms.get("haste" if name.startswith("haste") else "ramo")
        if arm:
            _draw_face_strip(
                msp, entities, origin, along, across, arm,
                outer=outer, book=book, thick=thick,
                arm_id=name, globais=(contract or {}).get("globais") or {},
            )

    inner_h = float(paineis.get("haste") or secao["externa_y"])
    inner_r = float(paineis.get("ramo") or secao["externa_x"])
    entities.append(msp.add_text(
        f"{inner_h:.0f}",
        dxfattribs={"layer": "COTA", "insert": (x_stem + 6.0 * sign_x, (y_bar + y_free) / 2.0), "height": 3.5, "rotation": 90},
    ))
    entities.append(msp.add_text(
        f"{inner_r:.0f}",
        dxfattribs={"layer": "COTA", "insert": ((x_stem + x_free) / 2.0, y_bar + 6.0 * sign_y), "height": 3.5},
    ))
    entities.append(msp.add_text(
        f"{thick:.0f}",
        dxfattribs={"layer": "COTA", "insert": (x_stem + thick / 2.0, y_free - 8.0 * sign_y), "height": 3.5},
    ))

    letters = {
        "D": (x_stem, y_free + 8.0 * sign_y),
        "C": (x_free, y_bar - 8.0 * sign_y),
        "A": (x_stem + thick * sign_x + 8.0 * sign_x, y_bar + 8.0 * sign_y),
        "B": (x_stem + (inner_r / 2.0) * sign_x, y_bar + 8.0 * sign_y),
        "E": (x_stem + 8.0 * sign_x, y_bar + (inner_h / 2.0) * sign_y),
        "F": (x_stem + thick * sign_x - 8.0 * sign_x, y_bar + (inner_h / 2.0) * sign_y),
    }
    for letter, pos in letters.items():
        entities.append(msp.add_text(
            letter, dxfattribs={"layer": "NOMENCLATURA", "insert": pos, "height": 5.5},
        ))

    entities.append(msp.add_text(
        f"{nome} · CIMA L ({secao['externa_x']:.0f}x{secao['externa_y']:.0f} e={thick:.0f})",
        dxfattribs={"layer": "NOMENCLATURA", "insert": (ox, y1 + 96.0), "height": 10},
    ))

    from ezdxf.math import Matrix44
    scale_m = Matrix44.chain(
        Matrix44.translate(-ox, -oy, 0),
        Matrix44.scale(2.0, 2.0, 1.0),
        Matrix44.translate(ox, oy, 0),
    )
    for ent in entities:
        try:
            ent.transform(scale_m)
        except Exception:
            pass
    return len(entities)
