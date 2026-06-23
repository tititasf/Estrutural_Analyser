# -*- coding: utf-8 -*-
"""
fv_render_loop.py — Render headless do pavimento para o loop de qualidade FV.

Gera 2 PNGs a partir dos dados já em memória (sem reabrir DXF, sem GUI):
  1. {prefix}_limpo.png     — DXF puro (linhas/polylines), sem nenhum vínculo
  2. {prefix}_vinculos.png  — mesmo fundo + os vínculos que o motor detectou
                              (label de cada viga + segmentos de fundo + spans)

O objetivo é dar ao revisor (humano ou modelo) uma OPINIÃO VISUAL que complementa
o diagnóstico numérico do fv_loop_runner: "a viga V302 só detectou fundo no canto
do label, não percorreu o vão" etc.

NÃO usa análise por layer (cada obra tem layers diferentes).
"""

from __future__ import annotations

from pathlib import Path

# Paleta (tema escuro, igual fv_render_compare)
BG = "#0a0a14"
CLEAN_LINE = "#3a3a52"      # geometria do DXF (apagada)
SEG_COLOR = "#ff4d6d"       # segmentos de fundo detectados (vínculo)
SPAN_COLOR = "#4dd0ff"      # spans/painéis lógicos
LABEL_COLOR = "#ffe14d"     # marcador do label da viga
TEXT_COLOR = "#ffffff"


def _iter_dxf_segments(dxf_data: dict):
    """Gera segmentos [(x0,y0),(x1,y1)] de todas as lines+polylines do DXF."""
    for line in dxf_data.get("lines", []):
        s, e = line.get("start"), line.get("end")
        if s and e:
            yield [s, e]
    for poly in dxf_data.get("polylines", []):
        pts = poly.get("points", [])
        for i in range(len(pts) - 1):
            yield [pts[i], pts[i + 1]]


def _beam_seg_lines(b: dict):
    """Extrai os segmentos de fundo (seg_bottom) de um beam para desenho."""
    classified = b.get("geometry", {}).get("classified", {})
    segs = []
    for s in classified.get("seg_bottom", []) or []:
        if isinstance(s, (list, tuple)) and len(s) >= 2:
            # s é uma lista de pontos; liga ponto-a-ponto
            for i in range(len(s) - 1):
                p0, p1 = s[i], s[i + 1]
                if _is_pt(p0) and _is_pt(p1):
                    segs.append([p0, p1])
    return segs


def _beam_span_lines(b: dict):
    """Extrai retângulos/grupos lógicos (merged_bottom_groups) de um beam."""
    classified = b.get("geometry", {}).get("classified", {})
    spans = []
    for grp in classified.get("merged_bottom_groups", []) or []:
        rect = grp[0] if grp else None
        if rect and len(rect) >= 2 and _is_pt(rect[0]) and _is_pt(rect[1]):
            spans.append([rect[0], rect[1]])
    return spans


def _is_pt(p) -> bool:
    return isinstance(p, (list, tuple)) and len(p) >= 2 \
        and isinstance(p[0], (int, float)) and isinstance(p[1], (int, float))


def render_pavimento(
    dxf_data: dict,
    beams_found: list[dict],
    out_dir: str | Path,
    prefix: str = "fv_pav",
    exclude_prefixes: tuple[str, ...] = ("L.", "F.", "l.", "f."),
) -> dict:
    """
    Renderiza os 2 PNGs (limpo + vínculos) e retorna {'limpo': path, 'vinculos': path}.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    clean_segs = list(_iter_dxf_segments(dxf_data))
    if not clean_segs:
        return {}

    xs = [p[0] for seg in clean_segs for p in seg]
    ys = [p[1] for seg in clean_segs for p in seg]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    mx = (xmax - xmin) * 0.03 or 10
    my = (ymax - ymin) * 0.03 or 10

    def _new_ax(title: str):
        fig, ax = plt.subplots(1, 1, figsize=(20, 14), facecolor=BG)
        ax.set_facecolor(BG)
        ax.add_collection(LineCollection(clean_segs, colors=CLEAN_LINE, linewidths=0.5))
        ax.set_xlim(xmin - mx, xmax + mx)
        ax.set_ylim(ymin - my, ymax + my)
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(title, color=TEXT_COLOR, fontsize=13, pad=8)
        ax.axis("off")
        return fig, ax

    # ── PNG 1: limpo ────────────────────────────────────────────────────────
    fig, ax = _new_ax("PAVIMENTO LIMPO (sem vínculos)")
    p_limpo = out_dir / f"{prefix}_limpo.png"
    fig.savefig(str(p_limpo), dpi=130, bbox_inches="tight", facecolor=BG)
    plt.close(fig)

    # ── PNG 2: com vínculos ─────────────────────────────────────────────────
    fig, ax = _new_ax("PAVIMENTO + VÍNCULOS DETECTADOS (vermelho=fundo, azul=spans, amarelo=label)")

    n_drawn = 0
    for b in beams_found:
        name = b.get("name", "") or ""
        if any(name.startswith(p) for p in exclude_prefixes):
            continue

        seg_lines = _beam_seg_lines(b)
        span_lines = _beam_span_lines(b)
        if seg_lines:
            ax.add_collection(LineCollection(seg_lines, colors=SEG_COLOR, linewidths=1.4))
        if span_lines:
            ax.add_collection(LineCollection(span_lines, colors=SPAN_COLOR, linewidths=2.2, alpha=0.8))

        pos = b.get("pos")
        if _is_pt(pos):
            ax.plot(pos[0], pos[1], "o", color=LABEL_COLOR, markersize=4)
            ax.annotate(name, (pos[0], pos[1]), color=LABEL_COLOR, fontsize=6,
                        xytext=(3, 3), textcoords="offset points")
        n_drawn += 1

    p_vinc = out_dir / f"{prefix}_vinculos.png"
    fig.savefig(str(p_vinc), dpi=130, bbox_inches="tight", facecolor=BG)
    plt.close(fig)

    return {"limpo": str(p_limpo), "vinculos": str(p_vinc), "beams_desenhados": n_drawn}
