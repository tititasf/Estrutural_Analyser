#!/usr/bin/env python
"""Desenha destaque PIL sobre N1 SVG (HI-FI DXF + faces coloridas + tags).

Camadas (sempre as mesmas tags — padrão PADRAO-TAGS):
  - sa  → motor SA (baseline; embutido no HTML N1)
  - l1  → 1ª proposta QA vs SA
  - l2  → refino pós-atenção humana
  - l3  → alvo validado pré-fix do motor

Padrão visual: docs/PADRAO-TAGS-DESTAQUE-AGENTICO-PIL.md
Loop:          docs/LOOPING-AGENTICO-INTERPRETACAO-PILARES-ABCD.md

Cores: A amarelo/laranja · B verde claro/escuro · C roxo/rosa · D azul claro/escuro

Uso:
  py -3.12 scripts/arete/pil_agentic_highlight_draw.py \\
    --pack .../13_PAV_..._pilares_abcd --items P1 P2 ... P10

  # export HTML já gera SA+tags + L1/L2/L3 (não é opcional)
  py -3.12 scripts/arete/export_pilares_abcd_fichas.py ...
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core.niveis_extractor import get_pavimento_niveis_abs  # noqa: E402
from src.core.pillar_abcd_tables import build_abcd_tables_from_pillar  # noqa: E402
from src.core.pil_qa_notes_chrome import pil_keys  # noqa: E402

# wall, text
FACE_COLORS = {
    "A": ("#ffeb3b", "#ff9800"),  # amarelo / laranja
    "B": ("#81c784", "#1b5e20"),  # verde claro / verde escuro
    "C": ("#9c27b0", "#f48fb1"),  # roxo / rosa
    "D": ("#4fc3f7", "#0d47a1"),  # azul claro / azul escuro
}
FACE_LABELS = {
    "A": "A · esq (oeste)",
    "B": "B · dir (leste)",
    "C": "C · topo (norte)",
    "D": "D · base (sul)",
}


def _natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s or "")]


def _bbox(pts: list) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


_CORNER_OK = frozenset({"AC", "AD", "BC", "BD", "CA", "CB", "DA", "DB"})


def _single_corner(fid: str, canto: str, *, kind: str) -> str:
    """Um único marcador por tag: AC|AD|BC|BD|CA|CB|DA|DB ou AA|BB|CC|DD.

    - passa/chega no canto → só aquela esquina (nunca AC-AD junto)
    - chega fora de esquina → AA / BB / CC / DD (meio da face)
    - passa sem canto → esquina padrão da face (uma só)
    """
    c = (canto or "").upper().strip()
    # se veio composto "AC-AD" / "AC/AD", pega o primeiro
    if c and c not in _CORNER_OK:
        m = re.search(r"\b(AC|AD|BC|BD|CA|CB|DA|DB)\b", c)
        c = m.group(1) if m else ""
    if c in _CORNER_OK:
        return c
    if kind == "chega":
        # chega no meio da face (não esquina)
        return {"A": "AA", "B": "BB", "C": "CC", "D": "DD"}.get(fid, "AA")
    if kind == "passa":
        # uma esquina canônica por face (não as duas)
        return {"A": "AD", "B": "BD", "C": "CA", "D": "DA"}.get(fid, "")
    if kind == "interior":
        return {"A": "AA", "B": "BB", "C": "CC", "D": "DD"}.get(fid, "")
    # laje: sem esquina; vazio
    return ""


def _fmt_nivel(nivel: Any) -> str:
    s = str(nivel or "").strip()
    if s in ("", "—", "None"):
        return ""
    s = s.replace("cm", "").strip()
    # só número/ponto
    m = re.search(r"(\d+(?:[.,]\d+)?)", s)
    if not m:
        return ""
    return f"{m.group(1).replace(',', '.')}cm"


def _row_bits(r: dict, kind: str, *, fid: str = "") -> str:
    """Chip multilinha:
    V.chega BC
    VF301
    19/66
    852.19cm
    """
    nome = str(r.get("nome") or "").strip()
    if nome in ("", "—", "nenhuma"):
        return ""
    dim = str(r.get("dim") or "").strip()
    if dim in ("—",):
        dim = ""
    canto = str(r.get("canto") or "").strip()
    if canto in ("—",):
        canto = ""
    nivel = _fmt_nivel(r.get("nivel"))
    papel = {
        "lajes": "laje",
        "passa": "V.passa",
        "chega": "V.chega",
        "interior": "V.interior",
    }.get(kind, kind)
    mark = _single_corner(fid, canto, kind=kind)
    # L1: tipo + canto/marca (um só)
    line1 = f"{papel} {mark}".strip() if mark else papel
    lines = [line1, nome]
    if dim:
        lines.append(dim)
    if nivel:
        lines.append(nivel)
    return "\n".join(lines)

def face_lines_from_tables(tables: dict) -> dict[str, list[str]]:
    faces = (tables or {}).get("faces") or {}
    out: dict[str, list[str]] = {f: [] for f in "ABCD"}
    for fid in "ABCD":
        data = faces.get(fid) or {}
        for kind in ("lajes", "passa", "chega", "interior"):
            for r in data.get(kind) or []:
                bit = _row_bits(r, kind, fid=fid)
                if bit:
                    out[fid].append(bit)
        if not out[fid]:
            out[fid].append("(vazio)")
    return out


def analyze_verdict(name: str, tables: dict, pillar: dict) -> tuple[str, str]:
    """Heurística agentica: validou|invalidou + motivos (texto QA)."""
    faces = (tables or {}).get("faces") or {}
    issues: list[str] = []
    oks: list[str] = []

    def real(kind_rows):
        return [
            r
            for r in (kind_rows or [])
            if (r.get("nome") or "") not in ("", "—", "nenhuma")
        ]

    # dualidade AC↔CA / BC↔CB
    for fl, cl, fs, cs in (("A", "AC", "C", "CA"), ("B", "BC", "C", "CB")):
        chega = [
            r
            for r in real(faces.get(fl, {}).get("chega"))
            if (r.get("canto") or "").upper() == cl
        ]
        passa = [
            r
            for r in real(faces.get(fs, {}).get("passa"))
            if (r.get("canto") or "").upper() == cs
        ]
        for r in chega:
            nomes = {(x.get("nome") or "").strip() for x in passa}
            if (r.get("nome") or "").strip() not in nomes:
                issues.append(
                    f"dualidade: chega {fl}@{cl} {r.get('nome')} sem passa C@{cs}"
                )
            else:
                oks.append(f"dualidade {fl}@{cl}↔C@{cs} {r.get('nome')} ok")

    # banda topo A/B
    bands = []
    for fid, canto in (("A", "AC"), ("B", "BC")):
        for r in real(faces.get(fid, {}).get("chega")):
            if (r.get("canto") or "").upper() != canto:
                continue
            de = str(r.get("dist_esq") or "")
            dd = str(r.get("dist_dir") or "")
            m1 = re.search(r"([\d.]+)", de)
            m2 = re.search(r"([\d.]+)", dd)
            if m1 and m2:
                # face longa ~ de+dd+band
                bands.append((fid, float(m1.group(1)), float(m2.group(1)), r.get("dim")))
    if len(bands) >= 2:
        # occupied = face - de - dd; compare residual
        # use de+dd as free span; band proxy = not comparable without face len
        # check classic 47 bug: dim 19/66 with free 47
        for fid, de, dd, dim in bands:
            if dim and re.match(r"19\s*/\s*66", str(dim)) and abs(de - 47) < 0.6:
                issues.append(
                    f"{fid} chega usa 19 de 19/66 como banda (d.esq~47) — deveria faixa topo ~14 → 52"
                )

    # C multi-seg se A/B tem chega topo
    top_cheg = any(
        (r.get("canto") or "").upper() in ("AC", "BC")
        for fid in "AB"
        for r in real(faces.get(fid, {}).get("chega"))
    )
    c_passa = real(faces.get("C", {}).get("passa"))
    if top_cheg and not c_passa:
        issues.append("há chega de topo em A/B mas C.passa vazio (falta multi-seg CA/CB)")
    elif top_cheg and c_passa:
        oks.append(f"C.passa multi-seg n={len(c_passa)}")

    # interior D se passa longas com V de interior típico
    d_int = real(faces.get("D", {}).get("interior"))
    if d_int:
        oks.append(f"D.interior {[r.get('nome') for r in d_int]}")

    # lajes assimétricas (pode ser real — nota, não fail automático)
    la_a = real(faces.get("A", {}).get("lajes"))
    la_b = real(faces.get("B", {}).get("lajes"))
    if bool(la_a) != bool(la_b):
        oks.append(
            f"lajes assimétricas A={bool(la_a)} B={bool(la_b)} "
            f"(pode ser borda — conferir N1)"
        )

    orient = pillar.get("orientation") or tables.get("orientation")
    if orient == "horizontal":
        # tags ABCD já usam mapa horizontal; multi-seg em face B (norte) ainda evolutivo
        oks.append("pilar HORIZONTAL: faces A sul / B norte / C oeste / D leste")

    if issues:
        verdict = "invalidou"
        body = (
            f"INVALIDOU interpretação SA de {name}.\n"
            f"Motivos:\n- " + "\n- ".join(issues) + "\n"
        )
        if oks:
            body += "Pontos ok:\n- " + "\n- ".join(oks) + "\n"
        body += (
            "Destaque agêntico: paredes A–D coloridas + textos de laje/passa/chega/interior "
            "no N1 próximo. Ajustar motor só após humano Validar o agêntico."
        )
    else:
        verdict = "validou"
        body = (
            f"VALIDOU interpretação SA de {name} no N1 contextual (heurística).\n"
            f"Compreensão:\n- " + "\n- ".join(oks or ["tabelas ABCD coerentes com dualidade/faces"]) + "\n"
            "Destaque agêntico desenha a mesma leitura (paredes + rótulos) para conferência visual."
        )
    return verdict, body


def _face_items(tables: dict, fid: str) -> list[tuple[str, dict]]:
    """Lista (kind, row) reais da face."""
    faces = (tables or {}).get("faces") or {}
    data = faces.get(fid) or {}
    out: list[tuple[str, dict]] = []
    for kind in ("lajes", "passa", "chega", "interior"):
        for r in data.get(kind) or []:
            if (r.get("nome") or "") in ("", "—", "nenhuma"):
                continue
            out.append((kind, r))
    return out


def _orient_from_bbox(
    px0: float, py0: float, px1: float, py1: float, tables: dict | None = None
) -> str:
    """vertical se face longa ≈ N–S; horizontal se face longa ≈ E–W."""
    o = str((tables or {}).get("orientation") or "").lower()
    if o in ("horizontal", "vertical"):
        return o
    pw, ph = abs(px1 - px0), abs(py1 - py0)
    return "horizontal" if pw >= ph else "vertical"


def _beam_seg_on_face(
    fid: str,
    kind: str,
    row: dict,
    px0: float,
    py0: float,
    px1: float,
    py1: float,
    *,
    pad: float,
    horizontal: bool = False,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Segmento da viga/laje na face + ponto âncora do texto (fora do pilar).

    Convenção INTERPRETACAO-PILARES-ABCD:
      vertical:   A oeste, B leste, C norte, D sul
      horizontal: A sul (longa), B norte (longa), C oeste (curta), D leste (curta)

    Retorna ((x0,y0), (x1,y1), (tx,ty)).
    """
    canto = (row.get("canto") or "").upper()
    # fração ao longo da face
    if kind == "chega" and canto in ("AC", "BC", "CA", "CB", "AD", "BD", "DA", "DB"):
        t0, t1 = 0.72, 1.0
        if canto in ("AD", "BD", "DA", "DB") and not (
            canto in ("AC", "BC") or (horizontal and canto in ("AC", "AD"))
        ):
            t0, t1 = 0.0, 0.28
        if canto in ("CA", "AC") and fid in ("C", "A"):
            t0, t1 = 0.0, 0.45
        if canto in ("CB", "BC") and fid in ("C", "B"):
            t0, t1 = 0.55, 1.0
    elif kind == "passa":
        t0, t1 = 0.12, 0.88
    elif kind == "interior":
        t0, t1 = 0.25, 0.75
    else:
        t0, t1 = 0.05, 0.70

    de = dd = None
    m1 = re.search(r"([\d.]+)", str(row.get("dist_esq") or ""))
    m2 = re.search(r"([\d.]+)", str(row.get("dist_dir") or ""))
    if m1 and m2 and kind != "passa":
        try:
            de, dd = float(m1.group(1)), float(m2.group(1))
        except Exception:
            de = dd = None

    if horizontal:
        # A = sul (y=py0), esq=AC (x=px0) → dir=AD (x=px1)
        # B = norte (y=py1), esq=BC (x=px0) → dir=BD (x=px1)  [INTERPRETACAO]
        # C = oeste (x=px0), esq=CA (y=py0) → dir=CB (y=py1)
        # D = leste (x=px1), esq=DA (y=py0) → dir=DB (y=py1)
        if fid == "A":  # sul, E–W
            fl = abs(px1 - px0)
            if de is not None and dd is not None and fl > 1:
                s0, s1 = de, fl - dd
                x0, x1 = px0 + s0, px0 + s1
            else:
                x0, x1 = px0 + t0 * fl, px0 + t1 * fl
            y = py0
            return (x0, y), (x1, y), ((x0 + x1) / 2, y - pad)
        if fid == "B":  # norte, E–W
            fl = abs(px1 - px0)
            if de is not None and dd is not None and fl > 1:
                s0, s1 = de, fl - dd
                x0, x1 = px0 + s0, px0 + s1
            else:
                x0, x1 = px0 + t0 * fl, px0 + t1 * fl
            y = py1
            return (x0, y), (x1, y), ((x0 + x1) / 2, y + pad)
        if fid == "C":  # oeste, S–N
            fl = abs(py1 - py0)
            if de is not None and dd is not None and fl > 1:
                s0, s1 = de, fl - dd
                y0, y1 = py0 + s0, py0 + s1
            else:
                y0, y1 = py0 + t0 * fl, py0 + t1 * fl
            x = px0
            return (x, y0), (x, y1), (x - pad, (y0 + y1) / 2)
        # D leste
        fl = abs(py1 - py0)
        if de is not None and dd is not None and fl > 1:
            s0, s1 = de, fl - dd
            y0, y1 = py0 + s0, py0 + s1
        else:
            y0, y1 = py0 + t0 * fl, py0 + t1 * fl
        x = px1
        return (x, y0), (x, y1), (x + pad, (y0 + y1) / 2)

    # ── vertical (legado) ──────────────────────────────────────────────
    L = abs(py1 - py0)
    W = abs(px1 - px0)
    if fid == "A":  # oeste
        fl = L
        if de is not None and dd is not None and fl > 1:
            s0, s1 = de, fl - dd
            y_hi, y_lo = py1 - s0, py1 - s1
        else:
            y_hi = py1 - t0 * fl
            y_lo = py1 - t1 * fl
        x = px0
        p0, p1 = (x, max(y_lo, y_hi)), (x, min(y_lo, y_hi))
        if p0[1] < p1[1]:
            p0, p1 = p1, p0
        midy = (p0[1] + p1[1]) / 2
        return p0, p1, (px0 - pad, midy)

    if fid == "B":  # leste
        fl = L
        if de is not None and dd is not None and fl > 1:
            s0, s1 = de, fl - dd
            y_lo, y_hi = py0 + s0, py0 + s1
        else:
            y_lo = py0 + t0 * fl
            y_hi = py0 + t1 * fl
        x = px1
        p0, p1 = (x, y_lo), (x, y_hi)
        midy = (y_lo + y_hi) / 2
        return p0, p1, (px1 + pad, midy)

    if fid == "C":  # norte
        fl = W
        if de is not None and dd is not None and fl > 1 and kind != "passa":
            s0, s1 = de, fl - dd
            x0, x1 = px0 + s0, px0 + s1
        elif canto == "CA":
            x0, x1 = px0, px0 + 0.48 * fl
        elif canto == "CB":
            x0, x1 = px0 + 0.52 * fl, px1
        else:
            x0, x1 = px0 + t0 * fl, px0 + t1 * fl
        y = py1
        mid = ((x0 + x1) / 2, y + pad * 0.55)
        return (x0, y), (x1, y), mid

    # D sul
    fl = W
    if de is not None and dd is not None and fl > 1 and kind != "passa":
        s0, s1 = de, fl - dd
        x_a, x_b = px1 - s0, px1 - s1
    else:
        x_a = px1 - t0 * fl
        x_b = px1 - t1 * fl
    y = py0
    mid = (((x_a + x_b) / 2), y - pad * 0.55)
    return (x_a, y), (x_b, y), mid


def _outward(fid: str, *, horizontal: bool = False) -> tuple[float, float]:
    if horizontal:
        return {"A": (0.0, -1.0), "B": (0.0, 1.0), "C": (-1.0, 0.0), "D": (1.0, 0.0)}[fid]
    return {"A": (-1.0, 0.0), "B": (1.0, 0.0), "C": (0.0, 1.0), "D": (0.0, -1.0)}[fid]


def _along(fid: str, *, horizontal: bool = False) -> tuple[float, float]:
    """Direção tangente à face (para stack sem overlap)."""
    if horizontal:
        return {"A": (1.0, 0.0), "B": (1.0, 0.0), "C": (0.0, 1.0), "D": (0.0, 1.0)}[fid]
    return {"A": (0.0, 1.0), "B": (0.0, 1.0), "C": (1.0, 0.0), "D": (1.0, 0.0)}[fid]


def _corner_xy(
    canto: str,
    px0: float,
    py0: float,
    px1: float,
    py1: float,
    *,
    horizontal: bool = False,
) -> tuple[float, float] | None:
    """Coordenada da esquina do pilar (AC/AD/BC/BD/CA/CB/DA/DB)."""
    c = (canto or "").upper()
    # Cantos são interseções de faces — mesmos pontos em vertical e horizontal:
    # A∩C = oeste+norte?  vertical: A oeste C norte → (px0,py1)
    # horizontal: A sul C oeste → (px0,py0)  **DIFERE**
    if horizontal:
        table = {
            "AC": (px0, py0),  # sul ∩ oeste
            "CA": (px0, py0),
            "AD": (px1, py0),  # sul ∩ leste
            "DA": (px1, py0),
            "BC": (px0, py1),  # norte ∩ oeste
            "CB": (px0, py1),
            "BD": (px1, py1),  # norte ∩ leste
            "DB": (px1, py1),
            "AA": ((px0 + px1) / 2, py0),
            "BB": ((px0 + px1) / 2, py1),
            "CC": (px0, (py0 + py1) / 2),
            "DD": (px1, (py0 + py1) / 2),
        }
        return table.get(c)
    table = {
        "AC": (px0, py1),
        "CA": (px0, py1),
        "AD": (px0, py0),
        "DA": (px1, py0),
        "BC": (px1, py1),
        "CB": (px1, py1),
        "BD": (px1, py0),
        "DB": (px0, py0),
        "AA": (px0, (py0 + py1) / 2),
        "BB": (px1, (py0 + py1) / 2),
        "CC": ((px0 + px1) / 2, py1),
        "DD": ((px0 + px1) / 2, py0),
    }
    table["DA"] = (px1, py0)
    table["DB"] = (px0, py0)
    return table.get(c)


def _contact_tip(
    fid: str,
    kind: str,
    row: dict,
    p0: tuple[float, float],
    p1: tuple[float, float],
    px0: float,
    py0: float,
    px1: float,
    py1: float,
    *,
    horizontal: bool = False,
) -> tuple[float, float]:
    """Pontinho de contato da seta.

    - passa → esquina de contato (AC/AD/…)
    - chega → **centro da viga que chega** (meio do trecho p0–p1 na face),
      nunca a esquina isolada
    - interior → centro da parede
    - laje → centro do contato laje–parede (meio do span)
    """
    mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
    canto = (row.get("canto") or "").upper()
    nx, ny = _outward(fid, horizontal=horizontal)
    if kind == "passa":
        mark = _single_corner(fid, canto, kind="passa")
        if mark in _CORNER_OK:
            xy = _corner_xy(mark, px0, py0, px1, py1, horizontal=horizontal)
            if xy:
                return xy
        return mid
    if kind == "chega":
        # Chegada CENTRAL AA/BB/CC/DD: bolinha no meio da face (não esquina)
        if canto in ("AA", "BB", "CC", "DD") or canto == f"{fid}{fid}":
            if horizontal:
                center = {
                    "A": ((px0 + px1) / 2, py0),
                    "B": ((px0 + px1) / 2, py1),
                    "C": (px0, (py0 + py1) / 2),
                    "D": (px1, (py0 + py1) / 2),
                }[fid]
            else:
                center = {
                    "A": (px0, (py0 + py1) / 2),
                    "B": (px1, (py0 + py1) / 2),
                    "C": ((px0 + px1) / 2, py1),
                    "D": ((px0 + px1) / 2, py0),
                }[fid]
            return center[0] + nx * max(2.0, abs(px1 - px0) * 0.02), center[
                1
            ] + ny * max(2.0, abs(py1 - py0) * 0.02)
        # chega de canto: centro do trecho da viga, DENTRO do corpo da viga.
        # `band` = largura do contato na face ≈ largura da viga que chega, então
        # deslocar ~0.9*band para fora crava o ponto no corpo dela (e não colado
        # na parede do pilar, onde some no meio dos outros pontos).
        # Padrão: docs/PADRAO-TAGS-DESTAQUE-AGENTICO-PIL.md §4 (chega → centro da viga).
        band = abs(p1[0] - p0[0]) + abs(p1[1] - p0[1])
        off = max(2.0, band * 0.9)
        return mid[0] + nx * off, mid[1] + ny * off
    if kind == "interior":
        if horizontal:
            return {
                "A": ((px0 + px1) / 2, py0),
                "B": ((px0 + px1) / 2, py1),
                "C": (px0, (py0 + py1) / 2),
                "D": (px1, (py0 + py1) / 2),
            }[fid]
        if fid == "A":
            return (px0, (py0 + py1) / 2)
        if fid == "B":
            return (px1, (py0 + py1) / 2)
        if fid == "C":
            return ((px0 + px1) / 2, py1)
        return ((px0 + px1) / 2, py0)
    return mid


def _estimate_tag_half(
    label: str, *, scale: float, fs: float
) -> tuple[float, float]:
    """Half-size chip multilinha em unidades CAD (anti-overlap)."""
    lines = [ln for ln in str(label).split("\n") if ln]
    n_lines = max(1, len(lines))
    max_chars = max((len(ln) for ln in lines), default=4)
    char_w = scale * 0.010 + fs * 0.28
    half_w = max(scale * 0.04, max_chars * char_w * 0.32)
    half_h = max(scale * 0.035, n_lines * fs * 0.52)
    return half_w, half_h


def _resolve_tag_pos(
    x: float,
    y: float,
    half_w: float,
    half_h: float,
    placed: list[tuple[float, float, float, float]],
    prefer: tuple[float, float],
    *,
    gap: float,
) -> tuple[float, float]:
    """Empurra a tag até não colidir com as já colocadas."""
    nx, ny = prefer
    nlen = (nx * nx + ny * ny) ** 0.5 or 1.0
    nx, ny = nx / nlen, ny / nlen
    # tangente
    tx, ty = -ny, nx
    for step in range(60):
        hit = False
        for ox, oy, ow, oh in placed:
            if abs(x - ox) < (half_w + ow) + gap and abs(y - oy) < (half_h + oh) + gap:
                # primeiro empurra na normal (para longe), depois ao longo da face
                if step < 25:
                    x += nx * (half_h + oh + gap) * 0.55
                    y += ny * (half_h + oh + gap) * 0.55
                else:
                    # alterna lado da tangente
                    s = 1.0 if step % 2 == 0 else -1.0
                    x += s * tx * (half_w + ow + gap) * 0.45
                    y += s * ty * (half_w + ow + gap) * 0.45
                hit = True
                break
        if not hit:
            break
    return x, y


def render_agentic_svg(
    dxf_path: Path,
    pillar_pts: list,
    tables: dict,
    *,
    width: int = 900,
    height: int = 640,
    layer: str = "sa",
) -> str:
    """N1 HI-FI + tags de interpretação (padrão PADRAO-TAGS-DESTAQUE-AGENTICO-PIL).

    ``layer``:
      - ``sa`` — leitura atual do **motor** (baseline N1 SA)
      - ``l1`` / ``l2`` / ``l3`` — camadas agênticas de QA (mesmo desenho até o agente divergir)
    """
    import ezdxf
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as pe
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from matplotlib.patches import Polygon as MplPolygon
    from src.ui.widgets.svg_embed_utils import strip_fixed_size

    xs = [float(p[0]) for p in pillar_pts]
    ys = [float(p[1]) for p in pillar_pts]
    px0, py0, px1, py1 = min(xs), min(ys), max(xs), max(ys)
    pw, ph = px1 - px0, py1 - py0
    scale = max(pw, ph)
    # margem ampla p/ tags fora da parede
    margin = (scale * 6.2 + 200) * 1.6
    vx0, vx1 = px0 - margin, px1 + margin
    vy0, vy1 = py0 - margin, py1 + margin

    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    dpi = 140
    stroke = [pe.withStroke(linewidth=0.8, foreground="#0a0a0a", alpha=0.75)]

    # fonttype=path: texto vira path no SVG (sempre visível por cima; não depende de fonte)
    with matplotlib.rc_context({"svg.fonttype": "path", "path.simplify": False}):
        fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor("#0d0d0d")
        fig.patch.set_facecolor("#0d0d0d")
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        Frontend(ctx, out).draw_layout(msp)

        # DXF estrutural SEMPRE por baixo (coleções/lines/patches do ezdxf)
        for coll in list(ax.collections):
            try:
                coll.set_zorder(0)
            except Exception:
                pass
        for line in list(ax.lines):
            try:
                line.set_zorder(0)
            except Exception:
                pass
        for p in list(ax.patches):
            try:
                p.set_zorder(0)
            except Exception:
                pass
        for art in list(ax.get_children()):
            try:
                if getattr(art, "get_zorder", lambda: 0)() < 5:
                    art.set_zorder(0)
            except Exception:
                pass

        poly = list(zip(xs, ys))
        if len(poly) >= 3:
            ax.add_patch(
                MplPolygon(
                    poly,
                    closed=True,
                    facecolor="#ff1744",
                    edgecolor="none",
                    alpha=0.12,
                    zorder=10,
                )
            )
            ax.add_patch(
                MplPolygon(
                    poly,
                    closed=True,
                    fill=False,
                    edgecolor="#ff8a80",
                    linewidth=0.25,
                    alpha=0.55,
                    zorder=11,
                )
            )

        wall_off = max(0.8, min(pw, ph) * 0.04)
        # chips mini fora da parede (seta/bolinha iguais; só o box muda)
        text_pad = scale * 1.75 + 62.0
        wall_lw = 0.35
        tag_fs = 1.7  # ainda menor; multilinha + path SVG
        tag_fs_empty = 1.6
        face_tag_fs = 2.0
        box_pad = 0.10  # chip mini com quebra de linha
        arrow_lw = 0.4
        arrow_ms = 4.0
        z_draw = 20
        z_tag = 10000
        horizontal = _orient_from_bbox(px0, py0, px1, py1, tables) == "horizontal"
        if horizontal:
            # A sul, B norte, C oeste, D leste (INTERPRETACAO-PILARES-ABCD)
            walls = {
                "A": ((px0, py0 - wall_off), (px1, py0 - wall_off)),
                "B": ((px0, py1 + wall_off), (px1, py1 + wall_off)),
                "C": ((px0 - wall_off, py0), (px0 - wall_off, py1)),
                "D": ((px1 + wall_off, py0), (px1 + wall_off, py1)),
            }
            face_label_off = scale * 0.20 + 7.0
            face_label_pos = {
                "A": ((px0 + px1) / 2, py0 - face_label_off),
                "B": ((px0 + px1) / 2, py1 + face_label_off),
                "C": (px0 - face_label_off, (py0 + py1) / 2),
                "D": (px1 + face_label_off, (py0 + py1) / 2),
            }
        else:
            walls = {
                "A": ((px0 - wall_off, py0), (px0 - wall_off, py1)),
                "B": ((px1 + wall_off, py0), (px1 + wall_off, py1)),
                "C": ((px0, py1 + wall_off), (px1, py1 + wall_off)),
                "D": ((px0, py0 - wall_off), (px1, py0 - wall_off)),
            }
            face_label_off = scale * 0.20 + 7.0
            face_label_pos = {
                "A": (px0 - face_label_off, (py0 + py1) / 2),
                "B": (px1 + face_label_off, (py0 + py1) / 2),
                "C": ((px0 + px1) / 2, py1 + face_label_off),
                "D": ((px0 + px1) / 2, py0 - face_label_off),
            }

        def _ink_on(bg: str) -> str:
            bg = (bg or "#888").lstrip("#")
            if len(bg) >= 6:
                r, g, b = int(bg[0:2], 16), int(bg[2:4], 16), int(bg[4:6], 16)
                lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
                return "#ffffff" if lum < 0.55 else "#111111"
            return "#111111"

        def _draw_pill_tag(
            tip: tuple[float, float],
            pos: tuple[float, float],
            label: str,
            *,
            bg: str,
            arrow_c: str,
            fs: float,
            z: float,
        ) -> None:
            """Chip moderno compacto; seta/bolinha como já estavam."""
            ink = _ink_on(bg)
            # seta (inalterada em estilo fino)
            ax.annotate(
                "",
                xy=tip,
                xytext=pos,
                zorder=z,
                clip_on=False,
                annotation_clip=False,
                arrowprops=dict(
                    arrowstyle="-|>",
                    color=arrow_c,
                    lw=arrow_lw,
                    mutation_scale=arrow_ms,
                    connectionstyle="arc3,rad=0.0",
                    shrinkA=2,
                    shrinkB=2,
                ),
            )
            # chip multilinha: contorno branco fino
            ax.text(
                pos[0],
                pos[1],
                label,
                fontsize=fs,
                fontfamily="DejaVu Sans",
                fontweight="normal",
                color=ink,
                ha="center",
                va="center",
                linespacing=1.05,
                zorder=z + 5,
                clip_on=False,
                bbox=dict(
                    boxstyle="round,pad=0.14,rounding_size=0.55",
                    facecolor=bg,
                    edgecolor="#ffffff",
                    linewidth=0.35,
                    alpha=0.94,
                ),
            )
            # bolinha de contato (como antes)
            ax.plot(
                tip[0],
                tip[1],
                "o",
                color="#ffffff",
                markersize=1.4,
                markeredgecolor=arrow_c,
                markeredgewidth=0.3,
                zorder=z + 6,
                clip_on=False,
            )

        placed: list[tuple[float, float, float, float]] = []
        gap = scale * 0.12 + 10.0  # chips não se tocam

        for fid in "ABCD":
            wcol, tcol = FACE_COLORS[fid]
            (x0, y0), (x1, y1) = walls[fid]
            ax.plot(
                [x0, x1],
                [y0, y1],
                color=wcol,
                linewidth=wall_lw,
                solid_capstyle="round",
                zorder=z_draw,
                alpha=0.95,
            )
            flx, fly = face_label_pos[fid]
            ax.text(
                flx,
                fly,
                fid,
                color=wcol,
                fontsize=face_tag_fs,
                fontweight="bold",
                ha="center",
                va="center",
                zorder=z_tag,
                clip_on=False,
                path_effects=stroke,
            )

            items = _face_items(tables, fid)
            nx, ny = _outward(fid, horizontal=horizontal)
            axn, ayn = _along(fid, horizontal=horizontal)

            if not items:
                if horizontal:
                    tip = {
                        "A": ((px0 + px1) / 2, py0),
                        "B": ((px0 + px1) / 2, py1),
                        "C": (px0, (py0 + py1) / 2),
                        "D": (px1, (py0 + py1) / 2),
                    }[fid]
                else:
                    tip = {
                        "A": (px0, (py0 + py1) / 2),
                        "B": (px1, (py0 + py1) / 2),
                        "C": ((px0 + px1) / 2, py1),
                        "D": ((px0 + px1) / 2, py0),
                    }[fid]
                txx = tip[0] + nx * text_pad
                tyy = tip[1] + ny * text_pad
                hw, hh = _estimate_tag_half(f"{fid} · —", scale=scale, fs=tag_fs_empty)
                txx, tyy = _resolve_tag_pos(
                    txx, tyy, hw, hh, placed, (nx, ny), gap=gap
                )
                placed.append((txx, tyy, hw, hh))
                _draw_pill_tag(
                    tip,
                    (txx, tyy),
                    f"{fid} · —",
                    bg=wcol,
                    arrow_c=wcol,
                    fs=tag_fs_empty,
                    z=z_tag,
                )
                continue

            n_it = len(items)
            for i, (kind, row) in enumerate(items):
                p0, p1, _ = _beam_seg_on_face(
                    fid,
                    kind,
                    row,
                    px0,
                    py0,
                    px1,
                    py1,
                    pad=text_pad,
                    horizontal=horizontal,
                )
                mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
                tip = _contact_tip(
                    fid,
                    kind,
                    row,
                    p0,
                    p1,
                    px0,
                    py0,
                    px1,
                    py1,
                    horizontal=horizontal,
                )

                if kind in ("passa", "chega", "interior"):
                    lw = 0.35 if kind == "chega" else 0.28
                    ax.plot(
                        [p0[0], p1[0]],
                        [p0[1], p1[1]],
                        color=tcol,
                        linewidth=lw,
                        solid_capstyle="round",
                        zorder=z_draw + 1,
                        alpha=0.95,
                    )
                elif kind == "lajes":
                    ax.plot(
                        [p0[0], p1[0]],
                        [p0[1], p1[1]],
                        color=wcol,
                        linewidth=0.28,
                        linestyle="--",
                        solid_capstyle="round",
                        zorder=z_draw + 1,
                        alpha=0.85,
                    )

                label = _row_bits(row, kind, fid=fid)
                if not label:
                    continue

                # stack generoso vs altura do chip compacto
                # Face C (multi-seg) precisa de mais ar — tags sobrepostas (P10)
                stack_step = scale * 0.38 + 26.0
                if fid == "C" and n_it >= 2:
                    stack_step = scale * 0.55 + 42.0
                stack = (i - (n_it - 1) / 2.0) * stack_step
                wall_mid = mid
                txx = wall_mid[0] + nx * text_pad + axn * stack
                tyy = wall_mid[1] + ny * text_pad + ayn * stack
                hw, hh = _estimate_tag_half(label, scale=scale, fs=tag_fs)
                txx, tyy = _resolve_tag_pos(
                    txx, tyy, hw, hh, placed, (nx, ny), gap=gap
                )
                pad_in = scale * 0.15
                if (
                    px0 - pad_in <= txx <= px1 + pad_in
                    and py0 - pad_in <= tyy <= py1 + pad_in
                ):
                    txx = wall_mid[0] + nx * (text_pad + scale * 0.5)
                    tyy = wall_mid[1] + ny * (text_pad + scale * 0.5)
                    txx, tyy = _resolve_tag_pos(
                        txx, tyy, hw, hh, placed, (nx, ny), gap=gap
                    )
                placed.append((txx, tyy, hw, hh))

                bg = wcol if kind == "lajes" else tcol
                acol = tcol if kind != "lajes" else wcol
                _draw_pill_tag(
                    tip,
                    (txx, tyy),
                    label,
                    bg=bg,
                    arrow_c=acol,
                    fs=tag_fs,
                    z=z_tag + i,
                )

        _layer = (layer or "sa").lower().strip()
        _banners = {
            "sa": ("SA motor · interpretação atual (tags) · viewBox zoom", "#ff8a80"),
            "l1": ("Ag.L1 · 1ª proposta QA vs SA · viewBox zoom", "#4dd0e1"),
            "l2": ("Ag.L2 · refino pós-atenção humana · viewBox zoom", "#69f0ae"),
            "l3": ("Ag.L3 · alvo validado pré-fix motor · viewBox zoom", "#ffd54f"),
        }
        _btxt, _bcol = _banners.get(_layer, _banners["sa"])
        ax.text(
            vx0 + (vx1 - vx0) * 0.01,
            vy1 - (vy1 - vy0) * 0.015,
            _btxt,
            color=_bcol,
            fontsize=6.5,
            ha="left",
            va="top",
            zorder=z_tag + 50,
            fontweight="bold",
            path_effects=stroke,
            clip_on=False,
        )

        from matplotlib.text import Annotation, Text

        for art in ax.get_children():
            if isinstance(art, (Annotation, Text)):
                try:
                    art.set_zorder(z_tag + 100)
                    art.set_clip_on(False)
                except Exception:
                    pass
                for attr in ("arrow_patch", "_arrow_patch"):
                    ap = getattr(art, attr, None)
                    if ap is not None:
                        try:
                            ap.set_zorder(z_tag + 99)
                            ap.set_linewidth(arrow_lw)
                            ap.set_mutation_scale(arrow_ms)
                            ap.set_clip_on(False)
                        except Exception:
                            pass
                try:
                    bp = art.get_bbox_patch()
                    if bp is not None:
                        bp.set_zorder(z_tag + 100)
                        bp.set_clip_on(False)
                except Exception:
                    pass

        ax.set_xlim(vx0, vx1)
        ax.set_ylim(vy0, vy1)
        ax.set_aspect("equal")
        ax.axis("off")
        import io

        buf = io.BytesIO()
        fig.savefig(buf, format="svg", dpi=dpi, facecolor="#0d0d0d", bbox_inches="tight")
        plt.close(fig)
    buf.seek(0)
    # NÃO fazer lift de grupos: quebrava transform e deixava pills vazias
    return strip_fixed_size(buf.read().decode("utf-8"))


def _svg_lift_text_groups(svg: str) -> str:
    """Move grupos de texto/anotação para o fim do SVG (por cima do estrutural)."""
    import re

    try:
        # text_* = letras; patch_* com fill colorido de tags costumam ser bboxes
        texts = re.findall(r'(<g id="text_\d+"[\s\S]*?</g>\s*)', svg)
        # patches de caixas arredondadas matplotlib (anotações)
        patches = re.findall(r'(<g id="patch_\d+"[\s\S]*?</g>\s*)', svg)
        # mantém só patches que parecem tag (fill opaco colorido) — heurística
        tag_patches = [
            p
            for p in patches
            if re.search(
                r"fill:\s*#(ff9800|1b5e20|f48fb1|0d47a1|ffeb3b|81c784|9c27b0|4fc3f7)",
                p,
                re.I,
            )
            or re.search(r'fill="#(ff9800|1b5e20|f48fb1|0d47a1|ffeb3b|81c784|9c27b0|4fc3f7)"', p, re.I)
        ]
        lift = texts + tag_patches
        if not lift:
            return svg
        out = svg
        for t in lift:
            out = out.replace(t, "", 1)
        # group no topo (último paint order)
        insert = (
            '<g id="pil_agentic_labels_top" style="opacity:1">'
            + "".join(lift)
            + "</g>"
        )
        if "</svg>" in out:
            out = out.replace("</svg>", insert + "</svg>", 1)
        return out
    except Exception:
        return svg


def load_project(
    db: Path, project_id: str, obra: str, pav: str
) -> tuple[Path | None, dict, dict, dict, list, list]:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    dxf_path = None
    prow = conn.execute(
        "SELECT dxf_path FROM projects WHERE id=?", (project_id,)
    ).fetchone()
    if prow and prow["dxf_path"]:
        dxf_path = Path(prow["dxf_path"])

    slab_h, slab_n, slab_pts = {}, {}, {}
    for r in conn.execute(
        "SELECT name, points_json, extra_data_json FROM slabs WHERE project_id=?",
        (project_id,),
    ):
        ex = json.loads(r["extra_data_json"] or "{}") if r["extra_data_json"] else {}
        fields = ex.get("fields") if isinstance(ex.get("fields"), dict) else {}
        h = str(fields.get("laje_dim") or ex.get("laje_dim") or "").replace("h=", "").replace("cm", "").strip()
        n = fields.get("laje_nivel") or ex.get("laje_nivel") or ""
        slab_h[r["name"]] = h
        slab_n[r["name"]] = str(n)
        try:
            slab_pts[r["name"]] = json.loads(r["points_json"] or "[]")
        except Exception:
            slab_pts[r["name"]] = []

    beams = []
    for r in conn.execute(
        "SELECT name, data_json FROM beams WHERE project_id=?", (project_id,)
    ):
        d = json.loads(r["data_json"] or "{}")
        d["name"] = r["name"]
        beams.append(d)

    pillars = []
    for r in conn.execute(
        "SELECT name, points_json, extra_data_json, type FROM pillars WHERE project_id=?",
        (project_id,),
    ):
        pts = json.loads(r["points_json"] or "[]")
        extra = json.loads(r["extra_data_json"] or "{}") if r["extra_data_json"] else {}
        if not isinstance(extra, dict):
            extra = {}
        try:
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            orient = (
                "vertical"
                if (max(ys) - min(ys)) > (max(xs) - min(xs))
                else "horizontal"
            )
        except Exception:
            orient = "vertical"
        pillars.append(
            {
                "name": r["name"],
                "points": pts,
                "orientation": orient,
                "lajes": extra.get("lajes_adjacentes") or [],
                "face_beams": extra.get("face_beams") or {},
            }
        )
    pillars.sort(key=lambda p: _natural_key(p["name"]))
    return dxf_path, slab_h, slab_n, slab_pts, beams, pillars


def process_item(
    pillar: dict,
    *,
    dxf_path: Path,
    slab_h,
    slab_n,
    slab_pts,
    beams,
    nivel_v: str,
    pack: Path,
    obra: str,
    pav: str,
    layers: tuple[str, ...] = ("sa", "l1", "l2", "l3"),
    only_layer: str | None = None,
) -> dict:
    """Gera SVGs por camada + notes.

    Na 1ª passagem L1=L2=L3=SA (mesma interpretação do motor com banners
    diferentes). Loopings de QA reescrevem só a camada pedida via ``only_layer``.
    """
    name = pillar["name"]
    tables = build_abcd_tables_from_pillar(
        pillar,
        slab_height_map=slab_h,
        slab_nivel_map=slab_n,
        slab_points_map=slab_pts,
        beams=beams,
        nivel_viga_default=nivel_v,
    )
    prop_dir = pack / "propostas"
    prop_dir.mkdir(parents=True, exist_ok=True)
    pts = pillar.get("points") or []

    if only_layer:
        to_draw = (only_layer.lower().strip(),)
    else:
        to_draw = tuple(x.lower().strip() for x in layers)

    # Cache: SA e L* começam iguais geometricamente; banners diferem por layer=
    # Se only_layer, desenha só essa.
    rendered: dict[str, str] = {}
    paths: dict[str, Path] = {}

    def _fname(layer: str) -> str:
        if layer == "sa":
            return f"{name}_sa_motor.svg"
        if layer in ("l1", "agent"):
            return f"{name}_qa_L1.svg"
        if layer == "l2":
            return f"{name}_qa_L2.svg"
        if layer == "l3":
            return f"{name}_qa_L3.svg"
        return f"{name}_qa_{layer}.svg"

    for ly in to_draw:
        ly_n = "l1" if ly == "agent" else ly
        svg = render_agentic_svg(dxf_path, pts, tables, layer=ly_n)
        rendered[ly_n] = svg
        p = prop_dir / _fname(ly_n)
        p.write_text(svg, encoding="utf-8")
        paths[ly_n] = p
        # backcompat L1 → _qa_proposta.svg
        if ly_n == "l1":
            (prop_dir / f"{name}_qa_proposta.svg").write_text(svg, encoding="utf-8")

    # Se não pediu only: se faltou alguma L, copia do SA/L1 (mesmo conteúdo)
    if not only_layer:
        base_svg = rendered.get("sa") or rendered.get("l1") or ""
        for ly_n in ("sa", "l1", "l2", "l3"):
            if ly_n in rendered:
                continue
            # regenera com banner certo
            svg = render_agentic_svg(dxf_path, pts, tables, layer=ly_n)
            rendered[ly_n] = svg
            p = prop_dir / _fname(ly_n)
            p.write_text(svg, encoding="utf-8")
            paths[ly_n] = p
            if ly_n == "l1":
                (prop_dir / f"{name}_qa_proposta.svg").write_text(svg, encoding="utf-8")

    lines = face_lines_from_tables(tables)
    verdict, agent_text = analyze_verdict(name, tables, pillar)
    json_path = prop_dir / f"{name}_qa_proposta.json"
    payload = {
        "item": name,
        "class": "PIL",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "layers": {
            "sa": "motor SA — interpretação atual com tags",
            "l1": "1ª proposta QA vs SA",
            "l2": "refino pós-atenção humana",
            "l3": "alvo validado pré-fix motor",
        },
        "files": {
            "sa": f"{name}_sa_motor.svg",
            "l1": f"{name}_qa_L1.svg",
            "l2": f"{name}_qa_L2.svg",
            "l3": f"{name}_qa_L3.svg",
            "legacy_l1": f"{name}_qa_proposta.svg",
        },
        "faces": lines,
        "colors": {k: {"wall": v[0], "text": v[1]} for k, v in FACE_COLORS.items()},
        "proposed": [
            {
                "label": fid,
                "role": f"face_{fid}",
                "note": " | ".join(lines.get(fid) or []),
            }
            for fid in "ABCD"
        ],
        "agent_text": agent_text,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    keys = pil_keys(obra, pav, name)
    notes = {
        keys["agent_verdict"]: verdict,
        keys["agent"]: agent_text,
    }
    notes_path = pack / "pilares" / f"{name}.notes.json"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_doc = {
        "version": 1,
        "page": name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }
    if notes_path.is_file():
        try:
            old = json.loads(notes_path.read_text(encoding="utf-8"))
            old_notes = old.get("notes") or {}
            for k, v in old_notes.items():
                if "human" in k and k not in notes:
                    notes[k] = v
            notes_doc["notes"] = {**old_notes, **notes}
        except Exception:
            pass
    notes_path.write_text(
        json.dumps(notes_doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # NÃO embutir SVGs no HTML (ficam 10–15MB e o browser trava).
    # Só atualiza #pil-notes-store; camadas usam fetch data-proposal-src.
    html_path = pack / "pilares" / f"{name}.html"
    if html_path.is_file():
        html = html_path.read_text(encoding="utf-8")
        store = {
            "version": 1,
            "page": name,
            "updated_at": notes_doc["updated_at"],
            "notes": notes_doc["notes"],
        }
        store_tag = (
            f'<script type="application/json" id="pil-notes-store">\n'
            f"{json.dumps(store, ensure_ascii=False)}\n</script>"
        )
        if 'id="pil-notes-store"' in html:
            html2 = re.sub(
                r'<script type="application/json" id="pil-notes-store">[\s\S]*?</script>',
                store_tag,
                html,
                count=1,
            )
            if html2 != html:
                html_path.write_text(html2, encoding="utf-8")

    l1_path = paths.get("l1") or prop_dir / f"{name}_qa_L1.svg"
    return {
        "name": name,
        "verdict": verdict,
        "svg": str(l1_path),
        "svgs": {k: str(v) for k, v in paths.items()},
        "notes": str(notes_path),
        "summary": agent_text.split("\n")[0],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", default="dd238e47-1dc6-4f63-a760-4e7ce19a7386")
    ap.add_argument("--db", default=str(ROOT.parent / "project_data.vision"))
    ap.add_argument("--obra", default="Obra_TREINO_1")
    ap.add_argument("--pav", default="13_PAV")
    ap.add_argument("--pack", required=True)
    ap.add_argument("--items", nargs="*", default=[])
    ap.add_argument("--pack-index", type=int, default=1)
    ap.add_argument("--pack-size", type=int, default=10)
    args = ap.parse_args()

    pack = Path(args.pack)
    if not pack.is_dir():
        print(f"[ERR] pack {pack}")
        return 2

    dxf_path, slab_h, slab_n, slab_pts, beams, pillars = load_project(
        Path(args.db), args.project_id, args.obra, args.pav
    )
    if not dxf_path or not dxf_path.is_file():
        print(f"[ERR] DXF ausente: {dxf_path}")
        return 2

    niveis = get_pavimento_niveis_abs(args.obra, args.pav) or {"chegada_abs": 852.19}
    nivel_v = f"{niveis.get('chegada_abs')}cm"

    if args.items:
        wanted = {x.strip().upper() for x in args.items}
        batch = [p for p in pillars if p["name"].upper() in wanted]
    else:
        i0 = (args.pack_index - 1) * args.pack_size
        batch = pillars[i0 : i0 + args.pack_size]

    print(f"[RUN] {len(batch)} pilares · DXF={dxf_path.name} · pack={pack.name}")
    results = []
    for i, p in enumerate(batch, 1):
        print(f"  [{i}/{len(batch)}] {p['name']}…", flush=True)
        try:
            r = process_item(
                p,
                dxf_path=dxf_path,
                slab_h=slab_h,
                slab_n=slab_n,
                slab_pts=slab_pts,
                beams=beams,
                nivel_v=nivel_v,
                pack=pack,
                obra=args.obra,
                pav=args.pav,
            )
            results.append(r)
            print(f"    → {r['verdict']}: {r['summary'][:100]}")
        except Exception as exc:
            print(f"    [ERR] {p['name']}: {exc}")
            results.append({"name": p["name"], "verdict": "error", "error": str(exc)})

    rep = pack / "propostas" / f"agentic_pack_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    rep.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    n_inv = sum(1 for r in results if r.get("verdict") == "invalidou")
    n_ok = sum(1 for r in results if r.get("verdict") == "validou")
    print(f"[OK] validou={n_ok} invalidou={n_inv} report={rep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
