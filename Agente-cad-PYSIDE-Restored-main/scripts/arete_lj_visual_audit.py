#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera auditoria visual autonoma ARETE LAJ.

Cada item recebe uma prancha com:
1. recorte N2 bruto;
2. ficha N2 extraida, desenhada como produto canonico;
3. N4 oficial;
4. overlay de produto N2 extraido x N4 em coordenadas CAD.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from arete_lj_batch_13pav import (  # noqa: E402
    DADOS,
    OBRA_NAME,
    db_items,
    preferred_recorte,
    text_summary,
)
from arete_lj_canonico import canonical, diff  # noqa: E402
from motor_reverso_laj import extrair_ficha_laje  # noqa: E402


OUT_ROOT = Path("D:/Agente-cad-PYSIDE/test_output/arete_lj/visual_audit_13_PAV")


def _abs_points(ficha: dict) -> list[tuple[float, float]]:
    coords = ficha.get("coordenadas") or []
    if not coords:
        return []
    xs = [float(c[0]) for c in coords]
    ys = [float(c[1]) for c in coords]
    pose = ficha.get("_stog_pose") or {}
    off_x = float(pose.get("x", 0.0)) if pose and abs(min(xs)) <= 0.5 else 0.0
    off_y = float(pose.get("y", 0.0)) if pose and abs(min(ys)) <= 0.5 else 0.0
    pts = [(float(c[0]) + off_x, float(c[1]) + off_y) for c in coords]
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def _bbox_pts(points: list[tuple[float, float]], pad: float = 35.0):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def _detail_origin(ficha: dict) -> tuple[float, float]:
    pose = ficha.get("_stog_pose") or {}
    return float(pose.get("x", 0.0)), float(pose.get("y", 0.0))


def _draw_ficha_detail(ax, ficha: dict, color="#19ff49", label_values=True):
    detail = ficha.get("_stog_detail_primitives") or {}
    if not isinstance(detail, dict) or not (detail.get("lines") or detail.get("polylines") or detail.get("texts")):
        return []
    off_x, off_y = _detail_origin(ficha)
    pts: list[tuple[float, float]] = []

    for hz in ficha.get("_hlaz") or []:
        hx = off_x + float(hz.get("x", 0))
        hy = off_y + float(hz.get("y", 0))
        hw = float(hz.get("width", 0))
        hh = float(hz.get("height", 0))
        if hw > 0 and hh > 0:
            ax.fill([hx, hx + hw, hx + hw, hx], [hy, hy, hy + hh, hy + hh],
                    color="#ffffff", alpha=0.85, zorder=0)
            pts.extend([(hx, hy), (hx + hw, hy + hh)])

    for item in detail.get("polylines") or []:
        poly = [(off_x + float(p[0]), off_y + float(p[1])) for p in item.get("points") or []]
        if len(poly) < 2:
            continue
        if item.get("closed") and poly[0] != poly[-1]:
            poly.append(poly[0])
        line_color = color if not label_values else "#19ff49"
        ax.plot([p[0] for p in poly], [p[1] for p in poly], color=line_color, lw=1.6)
        pts.extend(poly)

    for item in detail.get("lines") or []:
        p1 = item.get("start") or [0, 0]
        p2 = item.get("end") or [0, 0]
        a = (off_x + float(p1[0]), off_y + float(p1[1]))
        b = (off_x + float(p2[0]), off_y + float(p2[1]))
        if label_values:
            line_color = "#ff2dff" if str(item.get("layer")) == "Painéis" else "#19ff49"
        else:
            line_color = color
        ax.plot([a[0], b[0]], [a[1], b[1]], color=line_color, lw=1.2)
        pts.extend([a, b])

    if label_values:
        for item in detail.get("texts") or []:
            p = item.get("insert") or [0, 0]
            x = off_x + float(p[0])
            y = off_y + float(p[1])
            txt = str(item.get("text", ""))
            txt_color = "#00f5ff" if txt.upper().startswith("L") else "#ff2d55"
            ax.text(x, y, txt, color=txt_color, fontsize=7 if not txt.upper().startswith("L") else 11,
                    ha="center", va="center")
            pts.append((x, y))
    return pts


def _draw_ficha(ax, ficha: dict, color="#19ff49", label_values=True):
    detail_pts = _draw_ficha_detail(ax, ficha, color=color, label_values=label_values)
    if detail_pts:
        return detail_pts
    pts = _abs_points(ficha)
    if len(pts) < 2:
        return []
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    comp = float(ficha.get("comprimento") or (x1 - x0))
    larg = float(ficha.get("largura") or (y1 - y0))
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color, lw=1.8)

    for v in ficha.get("linhas_verticais") or []:
        x = x0 + float(v["value"])
        is_union = bool(v.get("is_union"))
        ax.plot([x, x], [y0, y1], color="#ff2dff" if is_union else color, lw=1.5)
        if label_values:
            ax.text(x, y0 - 12, f"{float(v['value']):g}", color="#ff2d55", fontsize=7, ha="center")
    for h in ficha.get("linhas_horizontais") or []:
        y = y0 + float(h["value"])
        is_union = bool(h.get("is_union"))
        ax.plot([x0, x1], [y, y], color="#ff2dff" if is_union else color, lw=1.5)
        if label_values:
            ax.text(x1 + 10, y, f"{float(h['value']):g}", color="#ff2d55", fontsize=7, va="center")
    for hz in ficha.get("_hlaz") or []:
        hx = x0 + float(hz.get("x", 0))
        hy = y0 + float(hz.get("y", 0))
        hw = float(hz.get("width", 0))
        hh = float(hz.get("height", 0))
        if hw > 0 and hh > 0:
            ax.fill([hx, hx + hw, hx + hw, hx], [hy, hy, hy + hh, hy + hh],
                    color="#ffffff", alpha=0.85, zorder=0)
    if label_values:
        for cota in ficha.get("cotas_paineis") or []:
            try:
                value = float(cota.get("value", 0.0))
                ax.text(
                    x0 + float(cota.get("x", 0.0)),
                    y0 + float(cota.get("y", 0.0)),
                    f"{value:g}",
                    color="#ff2d55",
                    fontsize=7,
                    ha="center",
                    va="center",
                    rotation=float(cota.get("rotation", 0.0) or 0.0),
                )
            except Exception:
                pass
    if label_values:
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, ficha.get("nome", ""),
                color="#00f5ff", fontsize=11, ha="center", va="center")
    return pts


def _draw_dxf(ax, path: Path):
    doc = ezdxf.readfile(str(path))
    Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(doc.modelspace(), finalize=True)


def _segments_from_dxf(path: Path):
    doc = ezdxf.readfile(str(path))
    segs = []
    pts = []
    for e in doc.modelspace():
        try:
            if e.dxftype() == "LINE":
                s = e.dxf.start
                t = e.dxf.end
                a = (float(s.x), float(s.y))
                b = (float(t.x), float(t.y))
                segs.append((a, b))
                pts.extend([a, b])
            elif e.dxftype() in {"LWPOLYLINE", "POLYLINE"}:
                if e.dxftype() == "LWPOLYLINE":
                    poly = [(float(x), float(y)) for x, y, *_ in e.get_points()]
                else:
                    poly = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in e.vertices]
                if len(poly) > 1:
                    if getattr(e, "closed", False) or bool(getattr(e, "is_closed", False)):
                        poly = poly + [poly[0]]
                    for a, b in zip(poly, poly[1:]):
                        segs.append((a, b))
                    pts.extend(poly)
        except Exception:
            pass
    return segs, pts


def render_item(eid: str, recorte: Path, n4: Path, out_png: Path) -> dict:
    ficha = extrair_ficha_laje(str(recorte), eid, OBRA_NAME)
    ficha["nome"] = eid
    n4_ficha = extrair_ficha_laje(str(n4), eid, OBRA_NAME)
    n4_ficha["nome"] = eid
    ref_fc = canonical(recorte)
    n4_fc = canonical(n4)
    d = diff(ref_fc, n4_fc)
    summary = text_summary(n4)

    fig, axes = plt.subplots(1, 4, figsize=(22, 6), facecolor="#0a0a14")
    titles = [
        f"{eid} N2 recorte bruto",
        "Ficha N2 extraida",
        "N4 oficial",
        "Overlay produto CAD",
    ]
    for ax, title in zip(axes, titles):
        ax.set_facecolor("#202830")
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(title, color="white", fontsize=10)
        ax.tick_params(colors="#a8a8c8", labelsize=6)

    _draw_dxf(axes[0], recorte)
    pts = _draw_ficha(axes[1], ficha)
    _draw_dxf(axes[2], n4)

    _draw_ficha(axes[3], ficha, color="#19ff49", label_values=False)
    n4_segs, n4_pts = _segments_from_dxf(n4)
    for a, b in n4_segs:
        axes[3].plot([a[0], b[0]], [a[1], b[1]], color="#ff2d55", lw=1.6, alpha=0.9)
    overlay_pts = (pts or []) + n4_pts
    if overlay_pts:
        x0, y0, x1, y1 = _bbox_pts(overlay_pts)
        axes[3].set_xlim(x0, x1)
        axes[3].set_ylim(y0, y1)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_png, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)

    return {
        "id": eid,
        "recorte": str(recorte),
        "n4": str(n4),
        "png": str(out_png),
        "ficha": {
            "comprimento": ficha.get("comprimento"),
            "largura": ficha.get("largura"),
            "linhas_verticais": ficha.get("linhas_verticais"),
            "linhas_horizontais": ficha.get("linhas_horizontais"),
            "hlaz": ficha.get("_hlaz"),
            "obstaculos": ficha.get("obstaculos"),
            "modo_selecionado": ficha.get("modo_selecionado"),
            "stog_pose": ficha.get("_stog_pose"),
        },
        "conteudo_pass": bool(d["pass"]),
        "diffs": d["diffs"],
        "has_aux00": summary["has_aux00"],
        "has_c_equals": summary["has_c_equals"],
        "n4_texts": summary["texts"],
    }


def make_sheet(pngs: list[Path], out_path: Path):
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return
    thumbs = []
    for p in pngs:
        im = Image.open(p).convert("RGB")
        im.thumbnail((760, 230))
        canvas = Image.new("RGB", (780, 260), (10, 10, 20))
        canvas.paste(im, ((780 - im.width) // 2, 5))
        ImageDraw.Draw(canvas).text((10, 238), p.stem, fill=(235, 235, 245))
        thumbs.append(canvas)
    cols = 2
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 780, rows * 260), (10, 10, 20))
    for i, im in enumerate(thumbs):
        sheet.paste(im, ((i % cols) * 780, (i // cols) * 260))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def run(out_root: Path) -> list[dict]:
    n4_dir = DADOS / OBRA_NAME / "Fase-6_Execucao_CAD" / "n4"
    png_dir = out_root / "items"
    results = []
    pngs = []
    for row in db_items():
        eid = row["id"]
        recorte = preferred_recorte(eid, row.get("db_recorte"))
        n4 = n4_dir / f"LJ_preview_{eid}.dxf"
        if not recorte or not n4.exists():
            results.append({"id": eid, "erro": "recorte ou n4 ausente"})
            continue
        png = png_dir / f"ARETE_LJ_{eid}_audit.png"
        results.append(render_item(eid, recorte, n4, png))
        pngs.append(png)
        print("audit", eid, png, flush=True)
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "visual_audit_report.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    make_sheet(pngs, out_root / "ARETE_LJ_13PAV_visual_audit_sheet.png")
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT_ROOT))
    args = ap.parse_args()
    results = run(Path(args.out))
    failures = [r for r in results if r.get("erro") or not r.get("conteudo_pass")]
    print(json.dumps({"total": len(results), "fail": len(failures), "out": args.out}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
