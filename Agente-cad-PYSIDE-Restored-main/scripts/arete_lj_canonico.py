#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comparador canonico LAJ para a frente Arete Laje.

Compara conteudo semantico: contorno, linhas internas, cotas-valor,
HLAZ, nome, obstaculos e modo. Textos de contexto definidos em
arete_config.LJ_CONTEXTO ficam fora do diff.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import ezdxf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "arete"))

from arete_config import LJ_CONTEXTO  # noqa: E402
from motor_reverso_laj import _extract_laj_from_dxf  # noqa: E402

TOL = 0.5


def _plain_text(e) -> str:
    if e.dxftype() == "MTEXT":
        try:
            return e.plain_text().strip()
        except Exception:
            return str(getattr(e, "text", "")).strip()
    return str(getattr(e.dxf, "text", "")).strip()


def _round_cm(v: float) -> float:
    # Paridade canonica LAJ trabalha com tolerancia de painel de 0,5 cm.
    return round(round(float(v) * 2) / 2, 1)


def _close(a: float, b: float, tol: float = TOL) -> bool:
    return abs(float(a) - float(b)) <= tol


def _line_axis(e) -> tuple[str | None, float, float] | None:
    a = e.dxf.start
    b = e.dxf.end
    x1, y1 = float(a.x), float(a.y)
    x2, y2 = float(b.x), float(b.y)
    dx = abs(x1 - x2)
    dy = abs(y1 - y2)
    if dx <= TOL and dy > TOL:
        return "v", _round_cm((x1 + x2) / 2), dy
    if dy <= TOL and dx > TOL:
        return "h", _round_cm((y1 + y2) / 2), dx
    return None


def _entity_points(e) -> list[tuple[float, float]]:
    if e.dxftype() == "LWPOLYLINE":
        return [(float(x), float(y)) for x, y, *_ in e.get_points()]
    if e.dxftype() == "POLYLINE":
        return [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in e.vertices]
    if e.dxftype() == "LINE":
        a = e.dxf.start
        b = e.dxf.end
        return [(float(a.x), float(a.y)), (float(b.x), float(b.y))]
    return []


def _bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float] | None:
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _hatch_boxes(doc) -> list[tuple[float, float, float, float]]:
    boxes = []
    for e in doc.modelspace():
        if e.dxftype() != "HATCH":
            continue
        pts: list[tuple[float, float]] = []
        for path in e.paths:
            if hasattr(path, "vertices"):
                pts.extend((float(x), float(y)) for x, y, *_ in path.vertices)
        box = _bbox(pts)
        if box:
            boxes.append(box)
    return boxes


def _bbox_from_form(doc) -> tuple[float, float, float, float] | None:
    pts: list[tuple[float, float]] = []
    for e in doc.modelspace():
        layer = str(getattr(e.dxf, "layer", ""))
        if layer not in {"3", "Painéis", "Paineis", "Hachura"}:
            continue
        if e.dxftype() in {"LINE", "LWPOLYLINE", "POLYLINE"}:
            pts.extend(_entity_points(e))
    return _bbox(pts)


def _derive_lines_from_geometry(path: Path, comp: float, larg: float, pose: dict | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    if pose and pose.get("x") is not None and pose.get("y") is not None:
        px = float(pose.get("x"))
        py = float(pose.get("y"))
        form_box = (px, py, px + comp, py + larg)
    else:
        form_box = _bbox_from_form(doc) or (0.0, 0.0, comp, larg)
    x0, y0, _, _ = form_box
    hatches = _hatch_boxes(doc)

    xs: set[float] = set()
    ys: set[float] = set()
    for e in msp:
        layer = str(getattr(e.dxf, "layer", ""))
        if layer not in {"Painéis", "Paineis"} or e.dxftype() != "LINE":
            continue
        axis = _line_axis(e)
        if not axis:
            continue
        kind, coord, length = axis
        if kind == "v" and length >= max(10.0, larg * 0.7):
            rel = _round_cm(coord - x0)
            if TOL < rel < comp - TOL:
                xs.add(rel)
        elif kind == "h" and length >= max(10.0, comp * 0.7):
            rel = _round_cm(coord - y0)
            if TOL < rel < larg - TOL:
                ys.add(rel)

    hlaz = []
    for hx0, hy0, hx1, hy1 in hatches:
        hw = _round_cm(hx1 - hx0)
        hh = _round_cm(hy1 - hy0)
        rel_x = _round_cm(hx0 - x0)
        rel_y = _round_cm(hy0 - y0)
        if hw > 0 and hh > 0:
            hlaz.append({"x": rel_x, "y": rel_y, "width": hw, "height": hh})

    def _is_union_x(pos: float) -> bool:
        return any(_close(pos, h["x"] + h["width"]) and h["height"] >= larg * 0.7 for h in hlaz)

    def _is_union_y(pos: float) -> bool:
        return any(_close(pos, h["y"] + h["height"]) and h["width"] >= comp * 0.7 for h in hlaz)

    linhas_v = [{"value": x, "is_union": _is_union_x(x)} for x in sorted(xs)]
    linhas_h = [{"value": y, "is_union": _is_union_y(y)} for y in sorted(ys)]
    return linhas_v, linhas_h, hlaz


def _segment_values(total: float, lines: list[dict]) -> list[float]:
    edges = [0.0] + [float(x["value"]) for x in sorted(lines, key=lambda i: i["value"])] + [float(total)]
    return [_round_cm(edges[i + 1] - edges[i]) for i in range(len(edges) - 1)]


def _cotas_paineis_signature(ficha: dict) -> list[dict]:
    cotas = []
    for item in ficha.get("cotas_paineis") or []:
        try:
            cotas.append(_round_cm(float(item.get("value", 0.0))))
        except Exception:
            continue
    return sorted(Counter(cotas).elements())


def _context_patterns() -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in LJ_CONTEXTO["padroes_texto"]]


def _is_context_text(txt: str) -> bool:
    clean = txt.strip()
    return any(p.fullmatch(clean) for p in _context_patterns())


def _texts(path: Path) -> dict:
    names: list[str] = []
    context: list[str] = []
    ignored_numeric: list[str] = []
    for e in ezdxf.readfile(str(path)).modelspace():
        if e.dxftype() not in {"TEXT", "MTEXT"}:
            continue
        txt = _plain_text(e)
        if not txt:
            continue
        if _is_context_text(txt):
            context.append(txt)
        elif re.fullmatch(r"\d+(?:[,.]\d+)?", txt):
            ignored_numeric.append(txt)
        elif re.fullmatch(r"L\d+[A-Z]?", txt, re.IGNORECASE):
            names.append(txt.upper())
    return {
        "nomes": sorted(Counter(names).elements()),
        "contexto": sorted(Counter(context).elements()),
        "numericos_cota": sorted(Counter(ignored_numeric).elements()),
    }


def canonical(path: Path) -> dict:
    ficha = _extract_laj_from_dxf(str(path))
    comp = float(ficha.get("comprimento") or 0)
    larg = float(ficha.get("largura") or 0)

    linhas_v = list(ficha.get("linhas_verticais") or [])
    linhas_h = list(ficha.get("linhas_horizontais") or [])
    hlaz = list(ficha.get("_hlaz") or [])

    geom_v, geom_h, geom_hlaz = _derive_lines_from_geometry(path, comp, larg, ficha.get("_stog_pose"))
    if not linhas_v and geom_v:
        linhas_v = geom_v
    if not linhas_h and geom_h:
        linhas_h = geom_h
    if not hlaz and geom_hlaz:
        hlaz = geom_hlaz

    cotas = sorted(_segment_values(comp, linhas_v) + _segment_values(larg, linhas_h))
    textos = _texts(path)
    modo = ficha.get("modo_selecionado")
    if geom_v or geom_h:
        modo = 1 if len(linhas_h) > len(linhas_v) else 0

    return {
        "outline": {
            "comprimento": _round_cm(comp),
            "largura": _round_cm(larg),
            "coordenadas": ficha.get("coordenadas") or [],
        },
        "linhas_verticais": [
            {"value": _round_cm(x["value"]), "is_union": bool(x.get("is_union"))}
            for x in sorted(linhas_v, key=lambda i: i["value"])
        ],
        "linhas_horizontais": [
            {"value": _round_cm(x["value"]), "is_union": bool(x.get("is_union"))}
            for x in sorted(linhas_h, key=lambda i: i["value"])
        ],
        "cotas_valor": cotas,
        "hlaz": [
            {k: _round_cm(v) for k, v in h.items() if k in {"x", "y", "width", "height"}}
            for h in hlaz
        ],
        "cotas_paineis_info": _cotas_paineis_signature(ficha),
        "nomes": textos["nomes"],
        "contexto_ignorado": textos["contexto"],
        "obstaculos": ficha.get("obstaculos") or [],
        "modo_selecionado": modo,
    }


def _same_value(ref, n4) -> bool:
    if isinstance(ref, bool) or isinstance(n4, bool):
        return ref is n4
    if isinstance(ref, (int, float)) and isinstance(n4, (int, float)):
        return _close(float(ref), float(n4))
    if isinstance(ref, dict) and isinstance(n4, dict):
        if set(ref.keys()) != set(n4.keys()):
            return False
        return all(_same_value(ref[k], n4[k]) for k in ref)
    if isinstance(ref, list) and isinstance(n4, list):
        if len(ref) != len(n4):
            return False
        return all(_same_value(a, b) for a, b in zip(ref, n4))
    return ref == n4


def _same_list(ref, n4) -> bool:
    return _same_value(ref, n4)


def _same_outline(ref: dict | None, n4: dict | None) -> bool:
    if not isinstance(ref, dict) or not isinstance(n4, dict):
        return False
    if not _close(ref.get("comprimento", 0), n4.get("comprimento", 0)):
        return False
    if not _close(ref.get("largura", 0), n4.get("largura", 0)):
        return False
    ref_pts = ref.get("coordenadas") or []
    n4_pts = n4.get("coordenadas") or []
    try:
        from shapely.geometry import Polygon

        rp = Polygon(ref_pts).buffer(0)
        np = Polygon(n4_pts).buffer(0)
        if rp.is_empty or np.is_empty:
            return _same_value(ref_pts, n4_pts)
        return rp.symmetric_difference(np).area <= 30.0
    except Exception:
        return _same_value(ref_pts, n4_pts)


def diff(ref: dict, n4: dict) -> dict:
    fields = [
        "outline",
        "linhas_verticais",
        "linhas_horizontais",
        "cotas_valor",
        "hlaz",
        "nomes",
        "obstaculos",
        "modo_selecionado",
    ]
    diffs = {}
    for field in fields:
        if field == "outline":
            same = _same_outline(ref.get(field), n4.get(field))
        else:
            same = _same_list(ref.get(field), n4.get(field))
        if not same:
            diffs[field] = {"ref": ref.get(field), "n4": n4.get(field)}
    return {"pass": not diffs, "diffs": diffs}


def render_side_by_side(recorte: Path, n4: Path, out_png: Path) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        docs = [ezdxf.readfile(str(recorte)), ezdxf.readfile(str(n4))]
        titles = ["Recorte N2 (gabarito)", "N4 gerado"]
        fig, axes = plt.subplots(1, 2, figsize=(16, 6), facecolor="#0a0a14")
        for ax, doc, title in zip(axes, docs, titles):
            ax.set_facecolor("#0a0a14")
            Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(doc.modelspace(), finalize=True)
            ax.set_aspect("equal", adjustable="box")
            ax.set_title(title, color="white", fontsize=10)
            ax.tick_params(colors="#a8a8c8", labelsize=7)
        plt.tight_layout()
        out_png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(out_png), dpi=160, bbox_inches="tight", facecolor="#0a0a14")
        plt.close(fig)
        return True
    except Exception as exc:
        print(f"[WARN] render: {exc}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("recorte")
    ap.add_argument("n4")
    ap.add_argument("--png", default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    recorte = Path(args.recorte)
    n4 = Path(args.n4)
    ref_fc = canonical(recorte)
    n4_fc = canonical(n4)
    result = {
        "resultado": "PASS" if diff(ref_fc, n4_fc)["pass"] else "FAIL",
        "ref": ref_fc,
        "n4": n4_fc,
        **diff(ref_fc, n4_fc),
    }
    if args.png:
        ok = render_side_by_side(recorte, n4, Path(args.png))
        result["png_path"] = str(Path(args.png)) if ok else None
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["resultado"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
