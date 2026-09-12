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


TC = 2.0
TS = 2.0
CORNER_W = 7.0
CORNER_H = 2.0
SARR_H = 7.0


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


def _cota_chain(msp, entities, origin, along, across, u0, segments, v_attach, v_line, labels, height=5.0):
    """Cota N2/legado: ticks da borda (perfil) até a linha, texto no meio. Sem DIMENSION.

    O 2× final escala LINE+TEXT juntos; DIMENSION+transform desalinha defpoint e texto.
    """
    if not segments:
        return
    rot = 90.0 if abs(along[1]) >= abs(along[0]) else 0.0
    bounds = [u0]
    cursor = u0
    for seg in segments:
        cursor += float(seg)
        bounds.append(cursor)
    attribs = {"layer": "COTA"}
    entities.append(msp.add_line(
        _pt(origin, along, across, bounds[0], v_line),
        _pt(origin, along, across, bounds[-1], v_line),
        dxfattribs=attribs,
    ))
    for u in bounds:
        entities.append(msp.add_line(
            _pt(origin, along, across, u, v_attach),
            _pt(origin, along, across, u, v_line),
            dxfattribs=attribs,
        ))
        entities.append(msp.add_line(
            _pt(origin, along, across, u - TICK, v_line),
            _pt(origin, along, across, u + TICK, v_line),
            dxfattribs=attribs,
        ))
    cursor = u0
    for seg, lab in zip(segments, labels):
        entities.append(msp.add_text(
            lab,
            dxfattribs={
                "layer": "COTA",
                "insert": _pt(origin, along, across, cursor + float(seg) / 2.0, v_line + 3.0),
                "height": height,
                "rotation": rot,
            },
        ))
        cursor += float(seg)


def _draw_face_strip(msp, entities, origin, along, across, arm: dict, *, outer: bool):
    """Madeira + quadradinhos + G-labels + parafusos 7×7 (MEIO_PONT) numa face longa."""
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

    rot = 90.0 if abs(along[1]) >= abs(along[0]) else 0.0
    perfil_v0 = madeira_v0 + madeira_h
    if outer:
        perfil_u0, perfil_w = -18.0, panel + 36.0
    else:
        perfil_u0, perfil_w = 0.0, panel + 11.0
    _rect(msp, entities, origin, along, across, perfil_u0, perfil_v0, perfil_w, PERFIL_H, "Perfil Metálico", 224)
    _rect(msp, entities, origin, along, across, perfil_u0, perfil_v0 + TC, perfil_w, PERFIL_H - 2 * TC, "Perfil Metálico", 224)

    v_attach = perfil_v0 + PERFIL_H
    d_quad, d_grade, d_panel = COTA_OUTER if outer else COTA_INNER
    v_quad = v_attach + d_quad
    v_grade = v_attach + d_grade
    v_panel = v_attach + d_panel

    def _label(u, v, txt, height=5.0, layer="COTA"):
        entities.append(msp.add_text(
            txt,
            dxfattribs={
                "layer": layer,
                "insert": _pt(origin, along, across, u, v),
                "height": height,
                "rotation": rot,
            },
        ))

    for gi, start in enumerate(starts):
        segs = [float(s) for s in (divs[gi] if gi < len(divs) else []) if float(s) > 0]
        if segs:
            _cota_chain(
                msp, entities, origin, along, across, start, segs,
                v_attach, v_quad, [_fmt_cm(s) for s in segs],
            )
        gw = widths[gi]
        _label(start + gw / 2.0, madeira_v0 + 1.5, f"G{gw:.0f}", 4.5, "NOMENCLATURA")
        _cota_chain(
            msp, entities, origin, along, across, start, [gw],
            v_attach, v_grade, [f"{_fmt_cm(gw)}(GRADE)"],
        )
        if gaps and gi < len(gaps) and gaps[gi] > 0.4:
            _cota_chain(
                msp, entities, origin, along, across, start + gw, [gaps[gi]],
                v_attach, v_quad, [_fmt_cm(gaps[gi])],
            )
    _cota_chain(
        msp, entities, origin, along, across, 0.0, [panel],
        v_attach, v_panel, [f"{_fmt_cm(panel)} PAINEL"],
    )

    spacings = [float(v) for v in (arm.get("parafusos") or []) if v]
    cursor = float(arm.get("parafuso_inicio") or 0.0)
    bolt_us = []
    for spacing in spacings:
        cursor += spacing
        if 0.0 < cursor < panel:
            bolt_us.append(cursor)
    for u in bolt_us:
        _rect(
            msp, entities, origin, along, across,
            u - CORNER_W / 2.0, madeira_v0, CORNER_W, madeira_h, "MEIO_PONT", 93,
        )


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

    strips = (
        ("haste_ext", haste_ext_origin, haste_ext_along, haste_ext_across, True),
        ("haste_int", haste_int_origin, haste_int_along, haste_int_across, False),
        ("ramo_ext", ramo_ext_origin, ramo_ext_along, ramo_ext_across, True),
        ("ramo_int", ramo_int_origin, ramo_int_along, ramo_int_across, False),
    )
    for name, origin, along, across, outer in strips:
        arm = arms.get(name) or arms.get("haste" if name.startswith("haste") else "ramo")
        if arm:
            _draw_face_strip(msp, entities, origin, along, across, arm, outer=outer)

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
