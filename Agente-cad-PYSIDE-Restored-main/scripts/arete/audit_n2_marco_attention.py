#!/usr/bin/env python3
"""Audit visual + loop do marco vermelho N2 (itens com atenção LAJ).

Uso:
  python scripts/arete/audit_n2_marco_attention.py --loop --max-iter 6
  python scripts/arete/audit_n2_marco_attention.py

Gera PNG (N2 + overlays motor/Painéis/vermelho + N4) e INDEX.html.
No --loop: escolhe strategy, GRAVA polígono mundo no DB (n2_highlight_world)
para o CE ler e mudar de verdade, re-audita até PASS ou max-iter.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import ezdxf

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from src.core.n2_anchor import resolve_n2_anchor  # noqa: E402
from src.core.n2_marco_highlight import (  # noqa: E402
    bb_size,
    best_strategy_for_item,
    open_ring,
    resolve_highlight,
    save_highlight_override,
    score_item,
)

DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DADOS = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")


def load_notes(obra: str) -> dict[str, str]:
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    rows = conn.execute(
        """
        SELECT item_id, note FROM item_attention_notes
        WHERE obra_name=? AND UPPER(classe) IN ('LJ','LAJ') AND scope='N4'
          AND TRIM(COALESCE(note,''))!=''
        ORDER BY item_id
        """,
        (obra,),
    ).fetchall()
    conn.close()
    return {r[0]: r[1] or "" for r in rows}


def segs_from_dxf(path: Path):
    doc = ezdxf.readfile(str(path))
    segs, pts = [], []
    for e in doc.modelspace():
        try:
            ly = str(getattr(e.dxf, "layer", "") or "")
            if e.dxftype() == "LINE":
                a = (float(e.dxf.start.x), float(e.dxf.start.y))
                b = (float(e.dxf.end.x), float(e.dxf.end.y))
                segs.append((a, b, ly))
                pts.extend([a, b])
            elif e.dxftype() == "LWPOLYLINE":
                poly = [(float(x), float(y)) for x, y, *_ in e.get_points("xy")]
                if len(poly) < 2:
                    continue
                if (bool(e.closed) or poly[0] == poly[-1]) and poly[0] != poly[-1]:
                    poly = poly + [poly[0]]
                for a, b in zip(poly, poly[1:]):
                    segs.append((a, b, ly))
                pts.extend(poly)
        except Exception:
            continue
    return segs, pts


def render_item(item, note, obra, pav, out_dir, strategy="auto", use_override=True):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon

    anc = resolve_n2_anchor(obra, "LAJ", item, pav)
    if not anc:
        return {"item": item, "error": "no_anchor", "pass": False}
    path = Path(anc["recorte_path"])
    res = resolve_highlight(
        path, item, obra, note, strategy=strategy, use_override=use_override
    )
    sc = score_item(
        note, res["red"], res["motor"], res["paineis"], res.get("pillars")
    )
    segs, all_pts = segs_from_dxf(path)
    n4 = DADOS / obra / "Fase-6_Execucao_CAD" / "n4" / f"LJ_preview_{item}.dxf"
    n4_segs, n4_pts = ([], [])
    if n4.exists():
        n4_segs, n4_pts = segs_from_dxf(n4)

    n_panels = 2 if n4_pts else 1
    fig, axes = plt.subplots(1, n_panels, figsize=(7 * n_panels, 6), facecolor="#0b0b16")
    if n_panels == 1:
        axes = [axes]
    ax = axes[0]
    ax.set_facecolor("#1a1a22")
    ax.set_aspect("equal")
    status = "PASS" if sc["pass"] else "FAIL"
    ax.set_title(
        f"N2+marco {item} [{status}] {strategy}/{res['reason']}\n{note[:72]}",
        color="#0f0" if sc["pass"] else "#f66",
        fontsize=10,
    )
    for a, b, ly in segs:
        ly_u = str(ly).upper()
        if "PAIN" in ly_u:
            c, lw, al = "#00e5a0", 1.0, 0.85
        elif ly_u.strip() == "3":
            c, lw, al = "#6aa0ff", 0.7, 0.55
        elif ly_u.strip() == "7":
            c, lw, al = "#ffaa00", 0.9, 0.7
        else:
            c, lw, al = "#555a66", 0.5, 0.35
        ax.plot([a[0], b[0]], [a[1], b[1]], color=c, lw=lw, alpha=al, zorder=1)

    def add_poly(ax_, pts, color, label, lw=2.0, alpha_fill=0.18, z=5):
        if not pts or len(pts) < 3:
            return
        ring = list(pts)
        if ring[0] != ring[-1]:
            ring = ring + [ring[0]]
        ax_.plot(
            [p[0] for p in ring],
            [p[1] for p in ring],
            color=color,
            lw=lw,
            zorder=z,
            label=label,
        )
        ax_.add_patch(
            Polygon(
                ring[:-1],
                closed=True,
                facecolor=color,
                edgecolor="none",
                alpha=alpha_fill,
                zorder=z - 1,
            )
        )

    add_poly(ax, res.get("paineis") or [], "#ffcc00", "Painéis band", lw=1.5, alpha_fill=0.08, z=3)
    add_poly(ax, res.get("motor") or [], "#00d4ff", "Motor", lw=1.8, alpha_fill=0.10, z=4)
    add_poly(ax, res.get("red") or [], "#ff3333", f"CE red ({res['reason']})", lw=2.6, alpha_fill=0.25, z=6)
    ax.legend(loc="upper right", fontsize=7, facecolor="#222", labelcolor="white")
    if all_pts:
        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        pad = 40
        ax.set_xlim(min(xs) - pad, max(xs) + pad)
        ax.set_ylim(min(ys) - pad, max(ys) + pad)

    if n4_pts:
        ax2 = axes[1]
        ax2.set_facecolor("#1a1a22")
        ax2.set_aspect("equal")
        ax2.set_title(f"N4 {item}", color="white", fontsize=10)
        for a, b, ly in n4_segs:
            c = "#00e5a0" if "PAIN" in str(ly).upper() or str(ly) in ("3", "COTA") else "#666"
            ax2.plot([a[0], b[0]], [a[1], b[1]], color=c, lw=0.9, alpha=0.8)
        xs = [p[0] for p in n4_pts]
        ys = [p[1] for p in n4_pts]
        pad = 40
        ax2.set_xlim(min(xs) - pad, max(xs) + pad)
        ax2.set_ylim(min(ys) - pad, max(ys) + pad)

    png = out_dir / f"{item}_n2_marco.png"
    fig.tight_layout()
    fig.savefig(png, dpi=140, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)

    rw, rh = bb_size(res["red"]) if res.get("red") else (0, 0)
    return {
        "item": item,
        "note": note,
        "recorte": path.name,
        "reason": res["reason"],
        "strategy": res.get("strategy") or strategy,
        "pass": sc["pass"],
        "fails": sc["fails"],
        "metrics": sc["metrics"],
        "red_wh": [round(rw, 1), round(rh, 1)],
        "png": png.name,
        "red_pts": open_ring(res.get("red") or []),
    }


def write_html(out_dir: Path, metrics: list, title: str):
    rows = []
    for m in metrics:
        if m.get("error"):
            rows.append(f"<tr><td>{m.get('item')}</td><td colspan=3>ERROR {m['error']}</td></tr>")
            continue
        badge = (
            "<b style=color:#0f0>PASS</b>"
            if m.get("pass")
            else f"<b style=color:#f66>FAIL</b> {m.get('fails')}"
        )
        rows.append(
            f"<tr><td><b>{m['item']}</b><br><small>{m.get('note','')}</small><br>{badge}</td>"
            f"<td>{m.get('strategy')}/{m.get('reason')}<br>red {m.get('red_wh')}</td>"
            f"<td><pre style=color:#aaa;font-size:11px>{json.dumps(m.get('metrics'),indent=0)}</pre></td>"
            f"<td><img src='{m.get('png')}' style='max-width:740px;border:1px solid #444'/></td></tr>"
        )
    html = f"""<!DOCTYPE html><html><head><meta charset=utf-8><title>{title}</title>
<style>body{{background:#111;color:#eee;font-family:system-ui;padding:16px}}
td{{vertical-align:top;padding:12px;border-bottom:1px solid #333}} small{{color:#9ab}}</style>
</head><body>
<h1>{title}</h1>
<p style=color:#8cf>Fundo=DXF N2 · <b style=color:#f33>vermelho=marco CE</b> ·
<b style=color:#0df>ciano=motor</b> · <b style=color:#fc0>amarelo=faixa Painéis</b> ·
laranja=pilares · direita=N4</p>
<table>{''.join(rows)}</table></body></html>"""
    (out_dir / "INDEX.html").write_text(html, encoding="utf-8")


def run_audit(obra, pav, out_dir, use_override=True):
    notes = load_notes(obra)
    if not notes:
        print("Sem notas de atenção")
        return [], out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = []
    for item, note in notes.items():
        print(f"  render {item}...")
        try:
            m = render_item(item, note, obra, pav, out_dir, use_override=use_override)
            metrics.append(m)
            st = "PASS" if m.get("pass") else "FAIL"
            print(f"    {st} {m.get('strategy')}/{m.get('reason')} red={m.get('red_wh')} {m.get('fails')}")
        except Exception as exc:
            metrics.append({"item": item, "error": str(exc)[:400], "pass": False})
            print(f"    ERROR {exc}")
    (out_dir / "metrics.json").write_text(
        json.dumps(
            [{k: v for k, v in m.items() if k != "red_pts"} for m in metrics],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    n_ok = sum(1 for m in metrics if m.get("pass"))
    write_html(out_dir, metrics, f"Marco N2 atenção — {n_ok}/{len(metrics)} PASS")
    return metrics, out_dir


def run_loop(obra, pav, max_iter, root):
    last_metrics, last_dir = [], root
    for it in range(1, max_iter + 1):
        print(f"\n=== LOOP {it}/{max_iter} ===")
        # 1) calcular SEM override (estado "cru")
        notes = load_notes(obra)
        fixed = 0
        for item, note in notes.items():
            anc = resolve_n2_anchor(obra, "LAJ", item, pav)
            if not anc:
                continue
            best = best_strategy_for_item(anc["recorte_path"], item, obra, note)
            red = best.get("red") or []
            if len(red) < 3:
                print(f"  {item}: sem red")
                continue
            ok = save_highlight_override(
                obra,
                item,
                red,
                reason=str(best.get("reason") or ""),
                strategy=str(best.get("strategy") or "auto"),
                note=note,
            )
            wh = bb_size(red)
            sc = best.get("score") or {}
            print(
                f"  WRITE {item}: strat={best.get('strategy')} reason={best.get('reason')} "
                f"red={wh[0]:.1f}x{wh[1]:.1f} pass={sc.get('pass')} db={ok}"
            )
            fixed += 1
        print(f"  gravados {fixed} overrides no DB")

        # 2) audit COM override (o que o CE vai mostrar)
        out_dir = root / f"iter_{it:02d}"
        metrics, last_dir = run_audit(obra, pav, out_dir, use_override=True)
        last_metrics = metrics
        n_pass = sum(1 for m in metrics if m.get("pass"))
        print(f"  RESULT {n_pass}/{len(metrics)} PASS")
        if n_pass == len(metrics) and metrics:
            print("TODOS PASS")
            break
    summary = {
        "final_pass": sum(1 for m in last_metrics if m.get("pass")),
        "final_total": len(last_metrics),
        "html": str(last_dir / "INDEX.html"),
        "items": [
            {k: v for k, v in m.items() if k != "red_pts"} for m in last_metrics
        ],
    }
    (root / "LOOP_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n=== FINAL {summary['final_pass']}/{summary['final_total']} ===")
    print(f"HTML: {summary['html']}")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--obra", default="Obra_TREINO_1")
    ap.add_argument("--pav", default="14_PAV")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--max-iter", type=int, default=4)
    args = ap.parse_args(argv)
    ts = time.strftime("%Y%m%d_%H%M%S")
    root = REPO / "scripts/arete/relatorios" / f"n2_marco_attention_{ts}"
    root.mkdir(parents=True, exist_ok=True)
    if args.loop:
        s = run_loop(args.obra, args.pav, args.max_iter, root)
        return 0 if s["final_pass"] == s["final_total"] else 1
    metrics, out = run_audit(args.obra, args.pav, root / "once", use_override=True)
    print(f"HTML: {out / 'INDEX.html'}")
    return 0 if all(m.get("pass") for m in metrics) else 1


if __name__ == "__main__":
    raise SystemExit(main())
