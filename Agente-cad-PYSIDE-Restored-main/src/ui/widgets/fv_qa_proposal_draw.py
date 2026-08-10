"""Capacidade de desenho do QA no N1 contextual FV.

O agente propõe geometrias corretas de segmentos de fundo sobre o mesmo
enquadramento do N1 contextual. Destaques de **sugestão**:

- ímpar → ciano ``#00e5ff``
- par   → verde claro ``#69f0ae``

Tags: ``P1…Pn`` (proposta) com líder ~100 cm acima (mesma linguagem da ficha).

Entrada típica: lista de polígonos CAD ``[{label, points, index?}, ...]``
ou JSON em disco. Saída: SVG standalone + opcional PNG.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

# Cores de proposta (QA) — ciano / verde claro alternados
PROP_CYAN = "#00e5ff"
PROP_GREEN = "#69f0ae"
PROP_CYAN_EDGE = "#00b8d4"
PROP_GREEN_EDGE = "#00c853"
N1_DIM_FILL = "#ff1744"
N1_DIM_EDGE = "#ff8a80"
BG = "#0a0a0a"
TAG_DY = 100.0


def _as_xy(points: Sequence[Any]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in points or []:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            try:
                out.append((float(p[0]), float(p[1])))
            except (TypeError, ValueError):
                continue
    return out


def _norm_segs(segments: Sequence[dict], *, prefix: str = "") -> list[dict]:
    cleaned: list[dict] = []
    for i, raw in enumerate(segments or []):
        if not isinstance(raw, dict):
            continue
        pts = _as_xy(raw.get("points") or [])
        if len(pts) < 2:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        if len(pts) >= 3:
            poly = pts if pts[0] != pts[-1] else pts[:-1]
            if len(poly) < 3:
                poly = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
        else:
            poly = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        lab = str(raw.get("label") or raw.get("segment_label") or (i + 1))
        if prefix and not str(lab).startswith(prefix):
            # force P1 style if requested
            pass
        cleaned.append(
            {
                "label": lab,
                "index": int(raw.get("index") if raw.get("index") is not None else i),
                "poly": poly,
                "c": (cx, cy),
                "bbox": (xmin, ymin, xmax, ymax),
                "note": str(raw.get("note") or raw.get("reason") or ""),
            }
        )
    return cleaned


def _envelope(segs_lists: list[list[dict]], pad_factor: float = 0.15) -> tuple[float, float, float, float]:
    bbs = []
    for segs in segs_lists:
        for s in segs:
            bbs.append(s["bbox"])
    if not bbs:
        return 0.0, 100.0, 0.0, 100.0
    xmin = min(b[0] for b in bbs)
    ymin = min(b[1] for b in bbs)
    xmax = max(b[2] for b in bbs)
    ymax = max(b[3] for b in bbs)
    span_x = max(xmax - xmin, 1.0)
    span_y = max(ymax - ymin, 1.0)
    pad_x = max(180.0, span_x * pad_factor)
    pad_y = max(TAG_DY + 40.0, span_y * 9.0, span_x * 0.09)
    return xmin - pad_x, xmax + pad_x, ymin - pad_y, ymax + pad_y + TAG_DY + 30.0


def _poly_svg(poly: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.3f},{y:.3f}" for x, y in poly)


def render_qa_proposal_svg(
    *,
    beam: str,
    n1_segments: Sequence[dict] | None = None,
    proposed_segments: Sequence[dict],
    show_n1_dimmed: bool = True,
    title: str | None = None,
    width: int = 1400,
    height: int = 420,
) -> str:
    """SVG 2D (viewBox em coordenadas CAD) com N1 fraco + proposta ciano/verde.

    ``proposed_segments``: [{label|segment_label, points: [[x,y],...], note?}, ...]
    Labels de proposta usam prefixo visual ``P`` se o label for só número.
    """
    n1 = _norm_segs(n1_segments or [])
    prop = _norm_segs(proposed_segments or [])
    if not prop and not n1:
        return ""

    # renumber proposal tags as P1.. if pure numeric
    for i, s in enumerate(prop):
        lab = str(s["label"])
        if re.fullmatch(r"\d+", lab):
            s["label"] = f"P{lab}"
        elif not lab.upper().startswith("P"):
            s["label"] = f"P{i + 1}" if not lab else lab

    vx0, vx1, vy0, vy1 = _envelope([n1, prop])
    vw, vh = max(vx1 - vx0, 1.0), max(vy1 - vy0, 1.0)
    # SVG y-down: flip CAD y for display
    def ty(y: float) -> float:
        return vy1 - (y - vy0) + vy0  # reflect about mid… simpler: map CAD y → SVG
    # Use CAD coords with transform scale(1,-1) translate
    # viewBox in CAD space, transform group flip Y
    title = title or f"{beam} · QA proposta de correção N1-CTX"

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vx0:.2f} {vy0:.2f} {vw:.2f} {vh:.2f}" '
        f'width="{width}" height="{height}" class="img-fv-qa-proposal" '
        f'role="img" aria-label="{_esc(title)}" '
        f'style="display:block;width:100%;height:auto;background:{BG};max-width:100%">'
        f"<title>{_esc(title)}</title>",
        f'<rect x="{vx0:.2f}" y="{vy0:.2f}" width="{vw:.2f}" height="{vh:.2f}" fill="{BG}"/>',
        # flip Y so CAD up matches visual expectation
        f'<g transform="translate(0 {vy0 + vy1}) scale(1,-1)">',
    ]

    # N1 atual (dimmed) — vermelho/rosa apagado
    if show_n1_dimmed and n1:
        parts.append('<g id="n1-atual" opacity="0.28">')
        for s in n1:
            pts = _poly_svg(s["poly"])
            parts.append(
                f'<polygon points="{pts}" fill="{N1_DIM_FILL}" fill-opacity="0.35" '
                f'stroke="{N1_DIM_EDGE}" stroke-width="2" vector-effect="non-scaling-stroke"/>'
            )
        parts.append("</g>")

    # Propostas ciano / verde claro
    parts.append('<g id="qa-proposta">')
    for i, s in enumerate(prop):
        cyan = i % 2 == 0
        fill = PROP_CYAN if cyan else PROP_GREEN
        edge = PROP_CYAN_EDGE if cyan else PROP_GREEN_EDGE
        pts = _poly_svg(s["poly"])
        parts.append(
            f'<polygon points="{pts}" fill="{fill}" fill-opacity="0.42" '
            f'stroke="{edge}" stroke-width="2.2" vector-effect="non-scaling-stroke" '
            f'data-prop-label="{_esc(str(s["label"]))}"/>'
        )
        cx, cy = s["c"]
        # leader + tag (in flipped group, text needs un-flip)
        tag_y = cy + TAG_DY
        parts.append(
            f'<line x1="{cx:.2f}" y1="{cy:.2f}" x2="{cx:.2f}" y2="{tag_y:.2f}" '
            f'stroke="{edge}" stroke-width="1.2" vector-effect="non-scaling-stroke"/>'
        )
        parts.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="4" fill="#fff" stroke="{edge}" '
            f'stroke-width="1.2" vector-effect="non-scaling-stroke"/>'
        )
        # text unflipped via local counter-transform
        parts.append(
            f'<g transform="translate({cx:.2f} {tag_y:.2f}) scale(1,-1)">'
            f'<rect x="-22" y="-14" width="44" height="18" rx="4" ry="4" '
            f'fill="#004d40" stroke="{edge}" stroke-width="1.2"/>'
            f'<text x="0" y="0" text-anchor="middle" dominant-baseline="middle" '
            f'fill="#ffffff" font-size="12" font-weight="700" '
            f'font-family="Segoe UI, Arial, sans-serif">{_esc(str(s["label"]))}</text>'
            f"</g>"
        )
        if s.get("note"):
            parts.append(
                f'<g transform="translate({cx:.2f} {tag_y + 28:.2f}) scale(1,-1)">'
                f'<text x="0" y="0" text-anchor="middle" fill="#b2dfdb" font-size="8" '
                f'font-family="Segoe UI, Arial, sans-serif">{_esc(s["note"][:40])}</text></g>'
            )
    parts.append("</g>")
    parts.append("</g>")  # flip

    # legend (screen space bottom — use CAD coords at bottom of view)
    parts.append(
        f'<g font-family="Segoe UI, Arial, sans-serif" font-size="{max(vh * 0.04, 12):.1f}">'
        f'<text x="{vx0 + vw * 0.02:.2f}" y="{vy0 + vh * 0.08:.2f}" fill="#9ec9ff">'
        f"{_esc(title)}</text>"
        f'<text x="{vx0 + vw * 0.02:.2f}" y="{vy0 + vh * 0.14:.2f}" fill="#888" font-size="{max(vh * 0.028, 9):.1f}">'
        f"vermelho fraco = N1 atual · ciano/verde = proposta QA</text>"
        f"</g>"
    )
    parts.append("</svg>")
    return "\n".join(parts)


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def load_proposal_json(path: str | Path) -> dict:
    """JSON: {beam, proposed:[{label, points, note?}], n1?: optional}"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("proposal root must be object")
    return data


def write_proposal_artifacts(
    out_dir: str | Path,
    beam: str,
    proposed_segments: Sequence[dict],
    n1_segments: Sequence[dict] | None = None,
    *,
    also_png: bool = True,
    dxf_data: dict | None = None,
    hifi: bool = True,
    show_n1_ghost: bool = True,
) -> dict[str, str]:
    """Grava SVG (+ PNG se possível) e JSON da proposta. Retorna paths relativos.

    Com ``dxf_data`` + ``hifi=True`` (default): mesmo HI-FI estrutural do SA
    (linhas, textos, cotas) + overlays ciano/verde. Sem DXF: SVG simples CAD.

    ``show_n1_ghost=False``: usar quando ``n1_segments`` NÃO é o Destaque SA
    real (looping cego camada 2/3 — é a sugestão da camada anterior, só
    para enquadrar a view, sem tags ``S#`` que confundiriam com o motor).
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    svg = ""
    if hifi and dxf_data is not None:
        try:
            from src.ui.widgets.fv_hifi_n1_render import render_fv_hifi_proposal_svg

            svg = render_fv_hifi_proposal_svg(
                dxf_data,
                proposed_segments,
                n1_segments=n1_segments,
                mode="contextual",
                show_n1_ghost=show_n1_ghost,
            )
        except Exception as exc:
            print(f"[proposal] HI-FI fail, fallback: {exc}", flush=True)
            svg = ""
    if not svg:
        svg = render_qa_proposal_svg(
            beam=beam,
            n1_segments=n1_segments,
            proposed_segments=proposed_segments,
        )
    svg_path = out / f"{beam}_qa_proposta.svg"
    svg_path.write_text(svg, encoding="utf-8")
    meta = {
        "beam": beam,
        "kind": "qa_proposta_n1_ctx",
        "colors": {"odd": PROP_CYAN, "even": PROP_GREEN},
        "proposed": [
            {
                "label": s.get("label"),
                "points": s.get("points"),
                "note": s.get("note") or s.get("reason") or "",
            }
            for s in proposed_segments
        ],
    }
    json_path = out / f"{beam}_qa_proposta.json"
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    png_path = out / f"{beam}_qa_proposta.png"
    if also_png:
        try:
            import cairosvg

            cairosvg.svg2png(
                bytestring=svg.encode("utf-8"),
                write_to=str(png_path),
                dpi=140,
            )
        except Exception:
            # fallback matplotlib from polygons only
            try:
                import matplotlib

                matplotlib.use("Agg")
                import matplotlib.pyplot as plt

                prop = _norm_segs(proposed_segments)
                n1 = _norm_segs(n1_segments or [])
                fig, ax = plt.subplots(figsize=(14, 4), dpi=130)
                fig.patch.set_facecolor(BG)
                ax.set_facecolor(BG)
                for i, s in enumerate(n1):
                    xs = [p[0] for p in s["poly"]] + [s["poly"][0][0]]
                    ys = [p[1] for p in s["poly"]] + [s["poly"][0][1]]
                    ax.fill(xs, ys, color=N1_DIM_FILL, alpha=0.2, zorder=1)
                    ax.plot(xs, ys, color=N1_DIM_EDGE, lw=0.8, alpha=0.4, zorder=1)
                for i, s in enumerate(prop):
                    col = PROP_CYAN if i % 2 == 0 else PROP_GREEN
                    xs = [p[0] for p in s["poly"]] + [s["poly"][0][0]]
                    ys = [p[1] for p in s["poly"]] + [s["poly"][0][1]]
                    ax.fill(xs, ys, color=col, alpha=0.4, zorder=2)
                    ax.plot(xs, ys, color=col, lw=1.4, zorder=3)
                    cx, cy = s["c"]
                    ax.annotate(
                        str(s["label"]),
                        (cx, cy),
                        textcoords="offset points",
                        xytext=(0, 32),
                        color="white",
                        fontsize=9,
                        fontweight="bold",
                        ha="center",
                        arrowprops=dict(arrowstyle="->", color=col, lw=0.9),
                        bbox=dict(boxstyle="round,pad=0.25", fc="#004d40", ec=col),
                        zorder=5,
                    )
                ax.set_aspect("equal")
                ax.axis("off")
                ax.set_title(
                    f"{beam} · QA proposta (ciano/verde) · N1 atual (vermelho fraco)",
                    color="#9ec9ff",
                    fontsize=11,
                )
                fig.savefig(png_path, facecolor=BG, bbox_inches="tight")
                plt.close(fig)
            except Exception:
                png_path = Path("")

    return {
        "svg": str(svg_path),
        "json": str(json_path),
        "png": str(png_path) if png_path and Path(png_path).is_file() else "",
    }
