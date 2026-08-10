"""Correção dinâmica de contorno de pilar (geometria vinculada errada).

Usa ficha GOLDEN (comprimento×largura em planta) quando o polígono no DB
está truncado/degenerado vs a seção canônica — sem hardcode de P#.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


def _bbox(pts: list) -> tuple[float, float, float, float] | None:
    if not pts or len(pts) < 2:
        return None
    try:
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        return None


def load_golden_plan_size(
    name: str,
    *,
    obra: str = "Obra_TREINO_1",
    pav: str = "13_PAV",
    repo_root: Optional[Path] = None,
) -> tuple[Optional[float], Optional[float]]:
    """Retorna (lado_menor, lado_maior) em cm da ficha GOLDEN, se existir."""
    root = repo_root or Path(__file__).resolve().parents[2]
    ficha = root / "GOLDEN" / obra / pav / "PIL" / name / "ficha.json"
    if not ficha.is_file():
        return None, None
    try:
        d = json.loads(ficha.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    # comprimento/largura = planta; altura = pé-direito (ignorar)
    a = d.get("comprimento") or d.get("comp") or d.get("length")
    b = d.get("largura") or d.get("larg") or d.get("width")
    try:
        fa, fb = float(a), float(b)
    except Exception:
        return None, None
    if fa <= 0 or fb <= 0:
        return None, None
    return min(fa, fb), max(fa, fb)


def diagnose_plan_geometry(
    pts: list,
    *,
    name: str = "",
    golden_short: Optional[float] = None,
    golden_long: Optional[float] = None,
    min_major_cm: float = 40.0,
) -> dict[str, Any]:
    """Diagnóstico: contorno truncado vs GOLDEN / razão anômala."""
    bb = _bbox(pts)
    out: dict[str, Any] = {
        "ok": True,
        "reason": "",
        "w": None,
        "h": None,
        "major": None,
        "minor": None,
    }
    if not bb:
        out["ok"] = False
        out["reason"] = "sem pontos"
        return out
    x0, y0, x1, y1 = bb
    w, h = abs(x1 - x0), abs(y1 - y0)
    major, minor = max(w, h), min(w, h)
    out.update(w=w, h=h, major=major, minor=minor)
    # polígono não retangular (trapézio) — um lado com dy grande
    try:
        ys = [float(p[1]) for p in pts]
        xs = [float(p[0]) for p in pts]
        if len(set(round(y, 2) for y in ys)) > 2 and len(set(round(x, 2) for x in xs)) > 2:
            # mais de 2 Y e 2 X distintos em retângulo ok; trapézio tem 3+ Y em lados
            y_sorted = sorted(ys)
            if abs(y_sorted[-1] - y_sorted[-2]) > 1.5 and abs(y_sorted[0] - y_sorted[1]) > 0.01:
                # dois max Y diferentes = trapézio típico truncado
                if abs(y_sorted[-1] - y_sorted[-2]) > 2.0:
                    out["ok"] = False
                    out["reason"] = "contorno não retangular (possível truncamento)"
    except Exception:
        pass
    if golden_short and golden_long:
        aspect_g = golden_long / max(golden_short, 1e-6)
        # Ficha GOLDEN comprimento×largura às vezes é painel/altura, não planta.
        # Só confiar se a seção GOLDEN for alongada (típica de pilar em planta).
        if aspect_g < 1.35:
            # quase quadrado (ex. 45×45) — não usar para “consertar” 19×100
            pass
        elif major + 1.0 < golden_long * 0.55 and minor <= golden_short * 1.25:
            # truncado clássico: 19×26 vs GOLDEN 19×98
            out["ok"] = False
            out["reason"] = (
                f"eixo maior {major:.1f}cm << GOLDEN {golden_long:.1f}cm "
                f"(geometria vinculada truncada/errada)"
            )
        elif (
            abs(minor - golden_short) > 3.0
            and minor < golden_short * 0.7
            and major < golden_long * 0.7
            and aspect_g >= 1.35
        ):
            out["ok"] = False
            out["reason"] = (
                f"seção {minor:.1f}×{major:.1f} << GOLDEN "
                f"{golden_short:.1f}×{golden_long:.1f}"
            )
    elif major < min_major_cm and minor >= 15:
        # seção típica de pilar 19×66+; major <40 suspeito se não for horizontal curto
        out["ok"] = False
        out["reason"] = f"eixo maior só {major:.1f}cm (suspeito de truncamento)"
    return out


def repair_rect_from_golden(
    pts: list,
    *,
    golden_short: float,
    golden_long: float,
) -> list[list[float]]:
    """Reconstrói retângulo centrado no contorno atual, eixos alinhados XY.

    Mantém a orientação (horizontal se w>h do contorno atual, senão vertical)
    e aplica short×long do GOLDEN.
    """
    bb = _bbox(pts)
    if not bb:
        return list(pts or [])
    x0, y0, x1, y1 = bb
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    w, h = abs(x1 - x0), abs(y1 - y0)
    if w >= h:
        # horizontal: long E–W, short N–S
        hw, hh = golden_long / 2.0, golden_short / 2.0
    else:
        hw, hh = golden_short / 2.0, golden_long / 2.0
    return [
        [cx - hw, cy - hh],
        [cx + hw, cy - hh],
        [cx + hw, cy + hh],
        [cx - hw, cy + hh],
        [cx - hw, cy - hh],
    ]


def maybe_repair_pillar_points(
    pillar: dict,
    *,
    obra: str = "Obra_TREINO_1",
    pav: str = "13_PAV",
    repo_root: Optional[Path] = None,
    apply: bool = True,
) -> dict[str, Any]:
    """Diagnostica e opcionalmente repara ``pillar['points']`` via GOLDEN.

    Retorna dict com ok, reason, repaired, points.
    """
    name = str(pillar.get("name") or "")
    pts = pillar.get("points") or []
    gs, gl = load_golden_plan_size(name, obra=obra, pav=pav, repo_root=repo_root)
    diag = diagnose_plan_geometry(
        pts, name=name, golden_short=gs, golden_long=gl
    )
    result = {
        "name": name,
        "ok": diag["ok"],
        "reason": diag.get("reason") or "",
        "repaired": False,
        "w": diag.get("w"),
        "h": diag.get("h"),
        "golden_short": gs,
        "golden_long": gl,
        "points": pts,
    }
    if diag["ok"] or not gs or not gl:
        return result
    if not apply:
        return result
    new_pts = repair_rect_from_golden(pts, golden_short=gs, golden_long=gl)
    pillar["points"] = new_pts
    pillar["_geometry_repaired"] = {
        "from": {"w": diag["w"], "h": diag["h"]},
        "to": {"short": gs, "long": gl},
        "source": "GOLDEN.ficha comprimento×largura",
    }
    result["repaired"] = True
    result["points"] = new_pts
    result["reason"] = (result["reason"] or "") + " → retângulo GOLDEN aplicado"
    return result
