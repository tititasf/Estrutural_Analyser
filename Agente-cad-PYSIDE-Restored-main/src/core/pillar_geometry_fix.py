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


def repair_truncated_named_pillars_from_dxf(
    pillar_report: dict[str, dict],
    *,
    polylines: list[dict],
    texts: list[dict],
) -> list[dict[str, Any]]:
    """Recupera a planta completa quando o vínculo atual é um trecho truncado.

    Alguns pilares que ``nascem`` no pavimento seguinte aparecem na planta como
    um curto trecho sólido/visual junto à viga. Esse trecho pode receber o nome
    certo, mas não representa a seção inteira do pilar. A correção procura
    exclusivamente alternativas detectadas com o *mesmo nome* no DXF e só troca
    quando a alternativa é retangular, mantém a espessura curta e estende o eixo
    longo de modo significativo. Assim não depende de GOLDEN nem escolhe outro
    pilar apenas por proximidade.
    """
    try:
        from src.core.analysis_helpers import detect_pilares_from_polylines
        detected = detect_pilares_from_polylines(polylines or [], texts or [])
    except Exception:
        return []

    def dims(points: list) -> tuple[float, float, tuple[float, float, float, float]] | None:
        bb = _bbox(points)
        if not bb:
            return None
        w, h = abs(bb[2] - bb[0]), abs(bb[3] - bb[1])
        if w <= 0 or h <= 0:
            return None
        return min(w, h), max(w, h), bb

    def rectangular(points: list) -> bool:
        if not points:
            return False
        # Retângulos fechados têm quatro vértices distintos; evita escolher
        # desenhos de viga/corte com o mesmo texto próximo ao pilar.
        unique = {(round(float(p[0]), 2), round(float(p[1]), 2)) for p in points}
        return len(unique) == 4

    by_name: dict[str, list[dict]] = {}
    for candidate in detected:
        name = str(candidate.get("name") or (candidate.get("fields") or {}).get("nome") or "").strip().upper()
        if name:
            by_name.setdefault(name, []).append(candidate)

    repaired: list[dict[str, Any]] = []
    for key, pillar in pillar_report.items():
        name = str(pillar.get("name") or key or "").strip().upper()
        current = dims(pillar.get("points") or [])
        if not name or not current:
            continue
        short, long, old_bb = current
        # Apenas contornos suspeitos: seção estreita com eixo longo truncado.
        if short < 8.0 or short > 40.0 or long >= 45.0:
            continue
        choices: list[tuple[float, dict, tuple[float, float, tuple[float, float, float, float]]]] = []
        for candidate in by_name.get(name, []):
            points = candidate.get("points") or []
            cd = dims(points)
            if not cd or not rectangular(points):
                continue
            cshort, clong, _ = cd
            if abs(cshort - short) > max(2.0, short * 0.12) or clong < max(45.0, long * 1.8):
                continue
            # Menor extensão válida primeiro: reduz risco de capturar uma
            # geometria arquitetônica muito maior que compartilhe o rótulo.
            choices.append((clong, candidate, cd))
        if not choices:
            continue
        _, chosen, (_, new_long, new_bb) = min(choices, key=lambda value: value[0])
        pillar["points"] = [[float(x), float(y)] for x, y in chosen["points"]]
        pillar["bbox"] = new_bb
        pillar["_geometry_repaired"] = {
            "from": {"short": round(short, 2), "long": round(long, 2), "bbox": old_bb},
            "to": {"short": round(short, 2), "long": round(new_long, 2), "bbox": new_bb},
            "source": "DXF: alternativa retangular homônima (contorno truncado por pilar nasce)",
        }
        repaired.append({"item": name, **pillar["_geometry_repaired"]})
    return repaired
