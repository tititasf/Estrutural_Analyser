# -*- coding: utf-8 -*-
"""Âncora multi-unidade LV: face_units N2 ↔ bandas VIEW_A/B N4.

Pareamento por label + geometria (larguras/h), não por índice cego.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import ezdxf


def panel_widths(unit: dict) -> list[float]:
    segs = unit.get("segments") or unit.get("panels") or []
    out = []
    for s in segs:
        w = float(s.get("largura_cm", s.get("width", 0)) or 0)
        if w > 0:
            out.append(w)
    return out


def unit_label(unit: dict, idx: int = 0) -> str:
    lab = str(unit.get("label") or "").strip()
    if lab:
        return lab
    side = str(unit.get("side") or "?").upper()
    return f"UNIT.{side}#{idx + 1}"


def n2_geom_key(unit: dict) -> tuple:
    side = str(unit.get("side") or "?").upper()
    h = float(unit.get("h_body") or unit.get("h") or 0)
    w = tuple(round(x, 1) for x in panel_widths(unit))
    return (side, round(h, 1), w)


def _n4_widths_in_band(msp, x_left: float, x_right: float, y_bot: float, h_body: float) -> list[float]:
    """Larguras por V de silhueta no band (inclui degrau: V só no topo)."""
    xs = []
    y_top = y_bot + max(h_body, 20.0)
    for e in msp:
        if e.dxftype() != "LINE":
            continue
        if e.dxf.layer not in ("Painéis", "Paineis"):
            continue
        s, e2 = e.dxf.start, e.dxf.end
        if abs(s.x - e2.x) > 0.35:
            continue
        x = float(s.x)
        if not (x_left - 2 <= x <= x_right + 2):
            continue
        y1, y2 = min(s.y, e2.y), max(s.y, e2.y)
        if y2 - y1 < 18:
            continue
        # interseção com [y_bot, y_top] — não exige y_mid (degrau vazio embaixo)
        if y2 < y_bot - 5 or y1 > y_top + 5:
            continue
        xs.append(round(x, 2))
    xs = sorted(set(xs))
    if len(xs) < 2:
        return []
    return [round(b - a, 1) for a, b in zip(xs, xs[1:]) if b - a >= 3.0]


def split_n4_view(path: Path, side: str) -> list[dict]:
    """Particiona VIEW_A/B por labels TEXT V* / CONT.

    O arquivo combinado (LV_preview_{item}_A.dxf) traz TODAS as ocorrencias
    (A e B) em coordenadas absolutas na mesma folha; sem filtrar por lado o
    band do ultimo label de um lado engolia todas as ocorrencias do OUTRO
    lado que vierem depois em X (nao ha proximo label do MESMO lado para
    fechar a banda). Rotulo LV sempre termina em ".A"/".A#N" ou ".B"/".B#N"
    — usar esse sufixo para restringir aos labels do lado pedido.
    """
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    labels = []
    all_labels_x = []
    side_re = re.compile(rf"\.{re.escape(side)}(#\d+)?$", re.I)
    for e in msp.query("TEXT"):
        t = (e.dxf.text or "").strip()
        if not t:
            continue
        if not re.search(r"V\d+|CONT", t, re.I):
            continue
        lx = float(e.dxf.insert.x)
        all_labels_x.append(lx)
        if side_re.search(t):
            labels.append((lx, float(e.dxf.insert.y), t))
    labels.sort(key=lambda x: x[0])
    all_labels_x.sort()
    xs, ys = [], []
    for e in msp:
        if e.dxftype() == "LINE":
            xs += [e.dxf.start.x, e.dxf.end.x]
            ys += [e.dxf.start.y, e.dxf.end.y]
    xmax = max(xs) if xs else 0.0
    ymin = min(ys) if ys else 0.0
    units = []
    for i, (lx, ly, lab) in enumerate(labels):
        # label N4 fica em x0+3 (esquerda da face) — band começa no label
        x0 = lx - 8
        # Limite direito: proximo label do MESMO lado se houver; senao, o
        # proximo label de QUALQUER lado (arquivo combinado intercala A/B
        # na mesma folha) — nunca xmax global, que engoliria todas as
        # ocorrencias restantes do OUTRO lado na ultima unidade de cada
        # lado (achado real: UNIT.A#4/V301.B com "EXTRA estrutural" e
        # phantoms MARCO_MID_V nas centenas, evidencia visual + numerica).
        next_any = next((v for v in all_labels_x if v > lx + 0.5), None)
        if i + 1 < len(labels):
            x1 = labels[i + 1][0] - 35
        elif next_any is not None:
            x1 = next_any - 35
        else:
            x1 = xmax + 40
        # y_bot = menor H; y_body_top = H mais LONGA (topo do corpo, nao marco)
        y_bot = None
        y_hi = None
        best_top = None  # (width, y) topo do corpo
        for e in msp:
            if e.dxftype() != "LINE" or e.dxf.layer not in ("Painéis", "Paineis"):
                continue
            s, e2 = e.dxf.start, e.dxf.end
            if abs(s.y - e2.y) > 0.4:
                continue
            mx = 0.5 * (s.x + e2.x)
            w = abs(float(e2.x) - float(s.x))
            if x0 <= mx <= x1 and w > 30:
                y = float(s.y)
                y_bot = y if y_bot is None else min(y_bot, y)
                y_hi = y if y_hi is None else max(y_hi, y)
                # Empate de largura (degrau costuma ter 2 H iguais: ombro e
                # topo real) — preferir a mais alta, nunca a primeira da
                # ordem de iteracao do DXF (nao-deterministico e escolhia o
                # ombro por acaso, ver UNIT.B#7 h_body=65 em vez de 108.6).
                if best_top is None or w > best_top[0] or (
                    w == best_top[0] and y > best_top[1]
                ):
                    best_top = (w, y)
        if y_bot is None:
            y_bot = ymin
        y_body_top = best_top[1] if best_top else (y_hi if y_hi is not None else y_bot + 100)
        # se a H mais longa e a base, usar segundo nivel
        if abs(y_body_top - y_bot) < 5 and y_hi is not None:
            y_body_top = y_hi

        # Origem = V mais a ESQUERDA no band (degrau: esquerda nao toca base;
        # com marco, y_top sobe e "touch top" falhava → origem no ombro 1480).
        any_xs: list[float] = []
        base_xs: list[float] = []
        for e in msp:
            if e.dxftype() != "LINE" or e.dxf.layer not in ("Painéis", "Paineis"):
                continue
            s, e2 = e.dxf.start, e.dxf.end
            if abs(s.x - e2.x) > 0.4:
                continue
            x = float(s.x)
            if not (x0 - 15 <= x <= x1):
                continue
            y1, y2 = min(s.y, e2.y), max(s.y, e2.y)
            if y2 - y1 < 18:
                continue
            any_xs.append(x)
            if y1 <= y_bot + 8.0:
                base_xs.append(x)
        origin_x = min(any_xs) if any_xs else x0 + 5
        h_body = max(20.0, float(y_body_top) - float(y_bot))
        # body_end: V de base mais a direita no corpo (nao marco short)
        end_base = []
        for e in msp:
            if e.dxftype() != "LINE" or e.dxf.layer not in ("Painéis", "Paineis"):
                continue
            s, e2 = e.dxf.start, e.dxf.end
            if abs(s.x - e2.x) > 0.4:
                continue
            x = float(s.x)
            if not (origin_x <= x <= x1 + 5):
                continue
            y1 = min(s.y, e2.y)
            if y1 <= y_bot + 8.0 and abs(e2.y - s.y) > 40:
                end_base.append(x)
        body_end_x = max(end_base) if end_base else (
            max(any_xs) if any_xs else x1
        )
        # No degrau espelhado, a base termina na parede do passo, mas a faixa
        # alta continua até a direita. A H principal define o fim real do
        # corpo e impede que o preview/corte seja truncado nessa parede.
        if best_top is not None:
            body_end_x = max(body_end_x, origin_x + float(best_top[0]))
        widths = _n4_widths_in_band(msp, origin_x, body_end_x + 2, y_bot, h_body)
        geom = (side, round(h_body, 1), tuple(round(w, 1) for w in widths))
        units.append(
            {
                "label": lab,
                "side": side,
                "x_band": (x0, x1),
                "origin": (origin_x, y_bot),
                "h_body": h_body,
                "body_end_x": body_end_x,
                "widths": widths,
                "geom_key": geom,
            }
        )
    return units


def _norm_lab(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().upper())


def pair_score(n2_unit: dict, n4_unit: dict) -> float:
    h2 = float(n2_unit.get("h_body") or n2_unit.get("h") or 0)
    h4 = float(n4_unit.get("h_body") or 0)
    w2 = panel_widths(n2_unit)
    w4 = list(n4_unit.get("widths") or [])
    sc = 0.0
    raw = _norm_lab(n2_unit.get("label"))
    n4lab = _norm_lab(n4_unit.get("label"))
    # label exacto (V301.A ↔ V301.A) tem prioridade absoluta
    if raw and n4lab == raw:
        sc = max(sc, 0.98)
    elif raw and n4lab and (raw in n4lab or n4lab in raw):
        # CONT. V301.A ↔ CONT. V301.A ; evitar V301.A em V301.A#2
        if "CONT" in raw and "CONT" in n4lab:
            sc = max(sc, 0.92)
        elif "CONT" not in raw and "CONT" not in n4lab and "#" not in n4lab:
            sc = max(sc, 0.88)
        else:
            sc = max(sc, 0.55)
    if abs(h2 - h4) <= 3.0:
        sc = max(sc, sc + 0.05 if sc >= 0.9 else 0.25)
    s2, s4 = sum(w2), sum(w4)
    if s2 > 50 and s4 > 50 and abs(s2 - s4) < 12:
        sc = max(sc, 0.55)
    # O N4 suprime divisores internos da zona curta do degrau. Total e
    # primeira/ultima parede comum ainda identificam a mesma silhueta.
    if (
        w2 and w4
        and abs(s2 - s4) <= 3.0
        and abs(h2 - h4) <= 2.0
        and (
            abs(w2[0] - w4[0]) <= 3.0
            or abs(w2[-1] - w4[-1]) <= 3.0
        )
    ):
        sc = max(sc, 0.90)
    if s2 > 50 and s4 > 50 and abs(s2 - s4) < 40 and abs(h2 - h4) < 2:
        sc = max(sc, 0.45)
    if w2 and w4:
        n = min(len(w2), len(w4))
        mean_d = sum(abs(w2[i] - w4[i]) for i in range(n)) / max(n, 1)
        if mean_d <= 12:
            sc = max(sc, 1.0 - mean_d / 12.0)
        # prefix match (N4 pode truncar marco)
        if n >= 2 and all(abs(w2[i] - w4[i]) <= 3.0 for i in range(min(n, 3))):
            sc = max(sc, 0.8)
    # unlabeled N2 não pode roubar label nominal N4
    if not raw and n4lab and re.match(r"^V\d+\.[AB]$", n4lab):
        sc = min(sc, 0.5)
    if not raw and "CONT" in n4lab:
        sc = min(sc, 0.55)
    return sc


def pair_units(
    n2_units: list[dict],
    n4_units: list[dict],
    *,
    min_score: float = 0.65,
) -> list[dict]:
    """Pareia N2→N4: 1º labels exactos, depois greedy geométrico."""
    used: set[int] = set()
    pairs: list[dict] = []
    assigned_n2: set[int] = set()

    # Passo 1 — match exacto de label (protege V301.A/B e CONT)
    for i, u2 in enumerate(n2_units):
        raw = _norm_lab(u2.get("label"))
        if not raw:
            continue
        best_j, best_sc = None, 0.0
        for j, u4 in enumerate(n4_units):
            if j in used:
                continue
            if _norm_lab(u4.get("label")) != raw:
                continue
            sc = pair_score(u2, u4)
            if sc > best_sc:
                best_sc = sc
                best_j = j
        if best_j is not None and best_sc >= 0.9:
            used.add(best_j)
            assigned_n2.add(i)
            pairs.append(
                {
                    "n2": u2,
                    "n4": n4_units[best_j],
                    "score": round(best_sc, 3),
                    "status": "paired",
                }
            )

    # Passo 2 — restante por score
    for i, u2 in enumerate(n2_units):
        if i in assigned_n2:
            continue
        best_j, best_sc = None, 0.0
        for j, u4 in enumerate(n4_units):
            if j in used:
                continue
            sc = pair_score(u2, u4)
            if sc > best_sc:
                best_sc = sc
                best_j = j
        thr = min_score
        # unlabeled exige score alto (evita roubar CONT/nominal)
        if not _norm_lab(u2.get("label")):
            thr = max(thr, 0.75)
        if best_j is not None and best_sc >= thr:
            used.add(best_j)
            pairs.append(
                {
                    "n2": u2,
                    "n4": n4_units[best_j],
                    "score": round(best_sc, 3),
                    "status": "paired",
                }
            )
        else:
            pairs.append(
                {
                    "n2": u2,
                    "n4": None,
                    "score": round(best_sc, 3),
                    "status": "n2_only",
                }
            )
    for j, u4 in enumerate(n4_units):
        if j not in used:
            pairs.append(
                {
                    "n2": None,
                    "n4": u4,
                    "score": 0.0,
                    "status": "n4_only",
                }
            )
    return pairs


def n2_anchor(unit: dict) -> dict:
    """origin, h, widths, clip for GeometryIndex.from_dxf."""
    bb = unit.get("bbox") or {}
    ox = float(bb.get("x_left") or 0)
    oy = float(bb.get("y_bot") or 0)
    widths = panel_widths(unit)
    total_w = sum(widths) if widths else max(
        1.0, float(bb.get("x_right") or ox) - ox
    )
    h = float(unit.get("h_body") or unit.get("h") or 100)
    # Margem esquerda alinhada a direita (+55): cota "classic_deg"/marco pode
    # ancorar em x0 com offset ate DIM_L2(50)+texto(~4) — -25 cortava essa
    # cota da leitura visual (nao e ausencia real, e corte de enquadramento).
    clip = (-65.0, -70.0, total_w + 55.0, h + 35.0)
    return {
        "origin": (ox, oy),
        "h_body": h,
        "total_w": total_w,
        "panel_widths": widths,
        "clip": clip,
        "side": str(unit.get("side") or "A"),
        "label": unit_label(unit),
    }


def n4_anchor(unit: dict, widths_fallback: list[float] | None = None) -> dict:
    """Âncora N4: larguras do N2 têm prioridade (extração V em N4 é frágil)."""
    ox, oy = unit["origin"]
    # Preferir larguras do face_unit N2 (fonte de verdade do corpo)
    fb = list(widths_fallback or [])
    local = list(unit.get("widths") or [])
    if fb and (not local or abs(sum(fb) - sum(local)) > 30 or len(local) < len(fb) - 1):
        widths = fb
    else:
        widths = local or fb
    total_w = sum(widths) if widths else 10.0
    # body_end geométrico (não o band até o próximo label — engolia vizinho)
    be = unit.get("body_end_x")
    if be is not None:
        total_w = max(total_w, float(be) - float(ox) + 2.0)
    if total_w < 10.0:
        total_w = max(10.0, float(unit["x_band"][1]) - float(ox))
    h = float(unit.get("h_body") or 100)
    # margem cota lateral L2=50 + texto(~4): -30 cortava a cota "classic_deg"
    # ancorada em x0 (dim_side=-1) da leitura visual — nao e ausencia real
    # no DXF (confirmado via query direta de DIMENSION), so corte de
    # enquadramento. Alinhar com a margem direita (+55).
    clip = (-65.0, -75.0, total_w + 55.0, h + 40.0)
    return {
        "origin": (ox, oy),
        "h_body": h,
        "total_w": total_w,
        "panel_widths": widths,
        "clip": clip,
        "side": str(unit.get("side") or "A"),
        "label": str(unit.get("label") or ""),
    }
