from __future__ import annotations

import io
import json
import html
import sqlite3
import math
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
ARETE_DIR = Path(__file__).resolve().parent
for entry in (ROOT, ARETE_DIR):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import ezdxf

from scripts.arete.ficha_adapter import get_recorte_path, query_fichas
from scripts.gerar_fv_dxf_stog import setup_doc, draw_viga
from src.ui.widgets.svg_embed_utils import strip_fixed_size

DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
OBRA_DIR = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1")
FASE4_FV = OBRA_DIR / "Fase-4_Sincronizacao" / "JSON_Vigas_Fundo"


# ─── Coleta de segmentos do DXF (sem ezdxf.drawing pipeline completo) ────────
def _collect_segs_texts(dxf_path: Path):
    """Coleta linhas, polilinhas e textos do DXF para renderização rápida."""
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
    except Exception:
        return [], [], None

    segs, texts, all_xs, all_ys = [], [], [], []
    skip_layers = {"folhas", "carimbo"}

    for e in msp:
        try:
            layer = e.dxf.layer.strip().lower()
        except Exception:
            layer = "0"
        if layer in skip_layers:
            continue
        dt = e.dxftype()
        try:
            if dt == "LINE":
                s, en = e.dxf.start, e.dxf.end
                xs, ys = [s.x, en.x], [s.y, en.y]
                if any(x < -9999 for x in xs): continue
                segs.append((xs, ys, e.dxf.layer))
                all_xs.extend(xs); all_ys.extend(ys)
            elif dt in ("LWPOLYLINE", "POLYLINE"):
                pts = list(e.get_points())
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                if any(x < -9999 for x in xs): continue
                if e.closed and pts:
                    xs.append(xs[0]); ys.append(ys[0])
                segs.append((xs, ys, e.dxf.layer))
                all_xs.extend(xs); all_ys.extend(ys)
            elif dt in ("TEXT", "MTEXT"):
                ins = e.dxf.insert
                if ins.x < -9999: continue
                txt = e.dxf.text if dt == "TEXT" else e.plain_text()
                texts.append((ins.x, ins.y, str(txt or "")[:30]))
                all_xs.append(ins.x); all_ys.append(ins.y)
            elif dt == "DIMENSION":
                for virt in e.virtual_entities():
                    vdt = virt.dxftype()
                    if vdt == "LINE":
                        st2, en2 = virt.dxf.start, virt.dxf.end
                        if st2.x < -9999: continue
                        segs.append(([st2.x, en2.x], [st2.y, en2.y], e.dxf.layer))
                        all_xs.extend([st2.x, en2.x]); all_ys.extend([st2.y, en2.y])
                    elif vdt == "TEXT":
                        ins2 = virt.dxf.insert
                        if ins2.x < -9999: continue
                        texts.append((ins2.x, ins2.y, str(virt.dxf.text or "")[:30]))
                        all_xs.append(ins2.x); all_ys.append(ins2.y)
        except Exception:
            pass

    if not all_xs:
        return segs, texts, None
    bbox = (min(all_xs), min(all_ys), max(all_xs), max(all_ys))
    return segs, texts, bbox


def _render_dxf_svg(dxf_path: Path, width: int = 1200, height: int = 700,
                    zoom_bbox=None, highlight_rect=None) -> str:
    """
    Renderiza um DXF para SVG embutível.
    zoom_bbox: (x0, y0, x1, y1) em coordenadas DXF — define o recorte de visualização.
    highlight_rect: (x0, y0, x1, y1) — retângulo de destaque laranja neon desenhado por cima.
    """
    segs, texts, bbox = _collect_segs_texts(dxf_path)
    if not bbox:
        return "<div style='color:#ff6666;padding:20px;'>DXF vazio ou inválido.</div>"

    view_x0, view_y0, view_x1, view_y1 = zoom_bbox if zoom_bbox else bbox
    view_w = max(view_x1 - view_x0, 1e-6)
    view_h = max(view_y1 - view_y0, 1e-6)

    dpi = 150
    fig, ax = plt.subplots(figsize=(width / dpi, height / dpi), dpi=dpi)
    ax.set_facecolor("#0b0e14")
    fig.patch.set_facecolor("#0b0e14")
    ax.set_aspect("auto")
    ax.set_xlim(view_x0, view_x1)
    ax.set_ylim(view_y0, view_y1)
    ax.axis("off")

    for xs, ys, layer in segs:
        ax.plot(xs, ys, color="#8899cc", linewidth=0.6, alpha=0.9)

    for tx, ty, txt in texts:
        if view_x0 <= tx <= view_x1 and view_y0 <= ty <= view_y1:
            ax.text(tx, ty, txt, fontsize=5, color="#ffff88", alpha=0.8)

    # Destaque laranja neon do segmento
    if highlight_rect:
        hx0, hy0, hx1, hy1 = highlight_rect
        rect = mpatches.FancyBboxPatch(
            (hx0, hy0), hx1 - hx0, hy1 - hy0,
            boxstyle="square,pad=0",
            facecolor="#ff9800", alpha=0.15,
            edgecolor="#ffaa00", linewidth=2.0, zorder=10
        )
        ax.add_patch(rect)
        # Bordas neon mais brilhantes
        ax.plot([hx0, hx1, hx1, hx0, hx0], [hy0, hy0, hy1, hy1, hy0],
                color="#ffcc00", linewidth=2.0, alpha=0.85, zorder=11)

    buf = io.BytesIO()
    with matplotlib.rc_context({'svg.fonttype': 'none'}):
        fig.savefig(buf, format='svg', dpi=dpi, facecolor='#0b0e14', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return strip_fixed_size(buf.read().decode('utf-8'))


def _render_stog_n3_svg(b_name: str, v_data: dict, b_width: float,
                         width: int = 1200, height: int = 700) -> str:
    """Gera SVG do N3 oficial usando gerar_fv_dxf_stog.py draw_viga."""
    doc_n3 = setup_doc()
    msp_n3 = doc_n3.modelspace()
    draw_viga(msp_n3, 0, 0, v_data.get('panels', []), v_data.get('b', b_width), b_name)

    import tempfile, os
    tmp = Path(tempfile.mktemp(suffix='.dxf'))
    doc_n3.saveas(tmp)

    # Reutilizar o mesmo pipeline de renderização
    segs, texts, bbox = _collect_segs_texts(tmp)
    try: tmp.unlink()
    except: pass

    if not bbox:
        return "<div style='color:#ff6666;padding:20px;'>Gerador N3 não produziu geometria.</div>"

    dpi = 150
    fig, ax = plt.subplots(figsize=(width / dpi, height / dpi), dpi=dpi)
    ax.set_facecolor("#0b0e14")
    fig.patch.set_facecolor("#0b0e14")
    ax.set_aspect("auto")

    bx0, by0, bx1, by1 = bbox
    pad_x = (bx1 - bx0) * 0.04
    pad_y = (by1 - by0) * 0.08
    ax.set_xlim(bx0 - pad_x, bx1 + pad_x)
    ax.set_ylim(by0 - pad_y, by1 + pad_y)
    ax.axis("off")

    for xs, ys, layer in segs:
        ax.plot(xs, ys, color="#66ccaa", linewidth=0.7, alpha=0.9)

    for tx, ty, txt in texts:
        ax.text(tx, ty, txt, fontsize=5, color="#ffff88", alpha=0.8)

    buf = io.BytesIO()
    with matplotlib.rc_context({'svg.fonttype': 'none'}):
        fig.savefig(buf, format='svg', dpi=dpi, facecolor='#0b0e14', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return strip_fixed_size(buf.read().decode('utf-8'))


def _estimate_segment_bbox(segs, texts, bbox, seg_index: int, total_segs: int, pad_pct=0.05):
    """
    Estima um bbox de zoom para o segmento seg_index (0-based) dentro do DXF.
    Divide horizontalmente (ou verticalmente) o bbox total por número de segmentos.
    """
    if not bbox:
        return None
    bx0, by0, bx1, by1 = bbox
    w = bx1 - bx0
    h = by1 - by0

    if w >= h:  # Viga horizontal
        seg_w = w / max(total_segs, 1)
        sx0 = bx0 + seg_index * seg_w
        sx1 = sx0 + seg_w
        pad_x = w * pad_pct
        pad_y = h * pad_pct
        return (sx0 - pad_x, by0 - pad_y, sx1 + pad_x, by1 + pad_y)
    else:  # Viga vertical
        seg_h = h / max(total_segs, 1)
        sy0 = by0 + (total_segs - seg_index - 1) * seg_h
        sy1 = sy0 + seg_h
        pad_x = w * pad_pct
        pad_y = h * pad_pct
        return (bx0 - pad_x, sy0 - pad_y, bx1 + pad_x, sy1 + pad_y)


# ─── Montagem de páginas HTML ─────────────────────────────────────────────────

def build_fv_unvalidated_n1_n3_html(
        project_id: str = "dd238e47-1dc6-4f63-a760-4e7ce19a7386",
        out_dir: Path | None = None) -> Path:

    if out_dir is None:
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_dir = ROOT / 'scripts' / 'arete' / 'relatorios' / f'revisao_fv_n1_n3_{stamp}'
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fichas do DB (ficha_adapter)
    rows_fv = query_fichas("FV", "13_PAV")
    row_map = {r["elemento_id"]: r for r in rows_fv}

    # 2. Vigas não validadas no SQLite
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT id, name, data_json, links_json, validated_fields_json FROM beams WHERE project_id=?", (project_id,))
    beams_db = c.fetchall()
    conn.close()

    unvalidated_beams = []
    for b_id, b_name, d_j, l_j, v_j in beams_db:
        data  = json.loads(d_j) if d_j else {}
        links = json.loads(l_j) if l_j else {}
        val   = json.loads(v_j) if v_j else []

        is_val = bool(data.get("is_validated") or
                      ("viga_fundo_seg_1_area_segs" in val and "viga_fundo_seg_1_dim" in val))
        if is_val:
            continue

        # Extrair índices de segmentos
        seg_indices: set[int] = set()
        for k in links.keys():
            if "viga_fundo_seg_" in k:
                parts = k.split('_')
                if 'seg' in parts:
                    try:
                        seg_indices.add(int(parts[parts.index('seg') + 1]))
                    except: pass
        if not seg_indices:
            seg_indices = {1}

        # Extrair texto dos vínculos por segmento
        segments = []
        for s_idx in sorted(seg_indices):
            def _txt(key):
                v = links.get(f"viga_fundo_seg_{s_idx}_{key}")
                if isinstance(v, dict):
                    return str(v.get("text") or v.get("value") or "Não informado")
                return str(v) if v is not None else "Não informado"

            comp = links.get(f"viga_fundo_seg_{s_idx}_comprimento_total")
            segments.append({
                "index":    s_idx,
                "local_ini": _txt("local_ini"),
                "local_fim": _txt("local_fim"),
                "dim":      _txt("dim"),
                "comp_cm":  float(comp) if isinstance(comp, (int, float)) else 0.0,
            })

        unvalidated_beams.append({
            "id": b_id, "name": b_name,
            "data": data, "links": links,
            "row":  row_map.get(b_name, {}),
            "width": float(data.get("largura") or data.get("width") or 19.0),
            "segments": segments,
        })

    unvalidated_beams.sort(key=lambda x: x["name"])
    total = len(unvalidated_beams)
    print(f"[REVISÃO FV UNVALIDATED] Encontradas {total} vigas NÃO VALIDADAS N1.")

    # 3. Gerar páginas
    for idx_b, b in enumerate(unvalidated_beams):
        b_name   = b["name"]
        segs     = b["segments"]
        row_info = b["row"]
        total_segs = len(segs)

        prev_b = unvalidated_beams[idx_b - 1]["name"] if idx_b > 0 else unvalidated_beams[-1]["name"]
        next_b = unvalidated_beams[idx_b + 1]["name"] if idx_b < total - 1 else unvalidated_beams[0]["name"]

        # --- Carregar DXF N1 real do estrutural ---
        rec_n1_path = get_recorte_path(b_name, "FV", row=row_info)
        n1_dxf_segs, n1_dxf_texts, n1_bbox = None, None, None
        n1_file_name = "Ausente"
        if rec_n1_path and rec_n1_path.exists():
            n1_dxf_segs, n1_dxf_texts, n1_bbox = _collect_segs_texts(rec_n1_path)
            n1_file_name = rec_n1_path.name

        # --- Carregar dados N3 (JSON_Vigas_Fundo) ---
        n3_json_path = FASE4_FV / f"{b_name}_fundo.json"
        v_data_n3 = None
        if n3_json_path.exists():
            with open(n3_json_path, "r", encoding="utf-8") as fj:
                v_data_n3 = json.load(fj)

        # --- Renderizar CONTEXTO AMPLO N1 (viga inteira) ---
        if rec_n1_path and rec_n1_path.exists() and n1_bbox:
            bx0, by0, bx1, by1 = n1_bbox
            pad_x = (bx1 - bx0) * 0.04
            pad_y = (by1 - by0) * 0.06
            svg_n1_ctx = _render_dxf_svg(
                rec_n1_path, width=1200, height=700,
                zoom_bbox=(bx0 - pad_x, by0 - pad_y, bx1 + pad_x, by1 + pad_y)
            )
        else:
            svg_n1_ctx = "<div class='missing-box'>Recorte N1 do Estrutural ausente.</div>"

        # --- Renderizar N3 Oficial STOG ---
        if v_data_n3:
            svg_n3 = _render_stog_n3_svg(b_name, v_data_n3, b["width"], width=1200, height=700)
        else:
            svg_n3 = "<div class='missing-box'>Ficha N3 ausente em JSON_Vigas_Fundo.</div>"

        # --- Montar cards de segmentos com N1 FOCADO ---
        seg_cards: list[str] = []
        for s_loop_idx, s in enumerate(segs):
            s_idx = s["index"]

            # N1 Focado no segmento (zoom + highlight)
            if rec_n1_path and rec_n1_path.exists() and n1_bbox and total_segs > 0:
                seg_zoom = _estimate_segment_bbox(
                    n1_dxf_segs, n1_dxf_texts, n1_bbox,
                    s_loop_idx, total_segs, pad_pct=0.07
                )
                if seg_zoom:
                    hx0, hy0, hx1, hy1 = seg_zoom
                    inner_hx0 = hx0 + (hx1 - hx0) * 0.07
                    inner_hx1 = hx1 - (hx1 - hx0) * 0.07
                    inner_hy0 = hy0 + (hy1 - hy0) * 0.10
                    inner_hy1 = hy1 - (hy1 - hy0) * 0.10
                    svg_n1_focused = _render_dxf_svg(
                        rec_n1_path, width=1000, height=600,
                        zoom_bbox=seg_zoom,
                        highlight_rect=(inner_hx0, inner_hy0, inner_hx1, inner_hy1)
                    )
                else:
                    svg_n1_focused = svg_n1_ctx
            else:
                svg_n1_focused = "<div class='missing-box'>Recorte N1 ausente.</div>"

            seg_cards.append(f'''
<div class="segment-block" data-seg="{s_idx}">
  <div class="segment-header">
    <span>Segmento #{s_idx}</span>
    <label class="seg-check-label">
      <input type="checkbox" class="segment-valid" data-seg="{s_idx}"> Segmento #{s_idx} Validado
    </label>
  </div>

  <!-- N1 FOCADO NO SEGMENTO -->
  <div class="seg-n1-focused">
    <div class="seg-n1-title">🔍 N1 — Focado no Segmento #{s_idx}</div>
    <div class="canvas">{svg_n1_focused}</div>
  </div>

  <!-- VÍNCULOS DE TEXTO DO SA -->
  <div class="segment-links-box">
    <div class="link-item link-ini">🔴 <b>Vínculo Inicial (local_ini):</b>
      <span class="link-val">{html.escape(s["local_ini"])}</span>
    </div>
    <div class="link-item link-fim">🟢 <b>Vínculo Final (local_fim):</b>
      <span class="link-val">{html.escape(s["local_fim"])}</span>
    </div>
    <div class="link-item link-dim">📐 <b>Vínculo Dimensão (dim):</b>
      <span class="link-val">{html.escape(s["dim"])}</span>
    </div>
    <div class="link-item link-comp">📏 <b>Comprimento Calculado:</b>
      <span class="link-val">{s["comp_cm"]:.1f} cm</span>
    </div>
  </div>

  <!-- CAMPO DE OBSERVAÇÕES -->
  <label class="segment-note-label">Observações e Ajustes — Segmento #{s_idx}:
    <textarea class="segment-note" data-seg="{s_idx}" rows="2"
      placeholder="Anotações sobre a coerência dos vínculos e geometria deste segmento..."></textarea>
  </label>
</div>
''')

        # Dropdown de vigas
        options_html = "\n".join(
            f'<option value="{bv["name"]}.html" {"selected" if bv["name"] == b_name else ""}>'
            f'Viga {bv["name"]} ({len(bv["segments"])} seg{"s" if len(bv["segments"]) > 1 else ""})'
            f'</option>'
            for bv in unvalidated_beams
        )

        b_key = f"FV::13_PAV::{b_name}"

        page_html = f'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Revisão N1 × N3 · Viga {html.escape(b_name)}</title>
<style>
:root {{ color-scheme: dark; }}
*,*::before,*::after {{ box-sizing: border-box; }}
body {{ margin: 0; background: #0c1016; color: #d9e4f0; font: 14px/1.5 system-ui, sans-serif; }}
main {{ max-width: 2600px; margin: auto; padding: 16px; }}

/* ── Navbar ── */
.nav-bar {{ position: sticky; top: 0; z-index: 100; background: #131a25; border: 1px solid #2a3d55;
  border-radius: 8px; padding: 10px 16px; margin-bottom: 20px;
  display: flex; justify-content: space-between; align-items: center;
  box-shadow: 0 6px 20px rgba(0,0,0,0.7); gap: 12px; }}
.nav-btn {{ background: #1e3048; color: #00e5ff; border: 1px solid #2e5070; padding: 8px 16px;
  border-radius: 6px; text-decoration: none; font-weight: bold; transition: all 0.2s; white-space: nowrap; }}
.nav-btn:hover {{ background: #00e5ff; color: #0c1016; }}
.nav-center {{ display: flex; align-items: center; gap: 12px; flex: 1; justify-content: center; }}
.nav-center select {{ background: #0d1520; color: #ffe600; border: 1px solid #385068;
  padding: 8px 14px; border-radius: 6px; font-weight: bold; font-size: 14px; cursor: pointer; max-width: 400px; }}
.nav-counter {{ color: #8aafcf; font-weight: 600; font-size: 13px; white-space: nowrap; }}

/* ── Viga Card ── */
.viga-card {{ background: #131a25; border: 1px solid #243040; border-radius: 10px; padding: 18px; margin-bottom: 24px; }}
.viga-header {{ display: flex; justify-content: space-between; align-items: center;
  border-bottom: 1px solid #243040; padding-bottom: 12px; margin-bottom: 16px; }}
h2 {{ margin: 0; color: #ffe600; font-size: 22px; }}
.global-valid-label {{ color: #88e5b0; font-weight: bold; font-size: 14px; cursor: pointer; }}
.global-valid-label input {{ width: 18px; height: 18px; vertical-align: middle; }}

/* ── Views superiores (N1 contexto + N3) ── */
.top-views {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 22px; }}
.view-pane {{ background: #0d1520; border: 1px solid #243040; border-radius: 8px; padding: 12px; }}
.view-pane h3 {{ margin: 0 0 8px; color: #a8c8e8; font-size: 14px; font-weight: 600;
  display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }}
.view-pane h3 small {{ color: #6080a0; font-size: 11px; font-weight: normal; font-family: monospace;
  max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

.canvas {{ height: 500px; background: #0a0e14; border: 1px solid #1e2d40; border-radius: 6px;
  overflow: hidden; display: grid; place-items: stretch; }}
.canvas svg {{ width: 100%; height: 100%; display: block; }}
.missing-box {{ color: #ff7070; font-weight: bold; padding: 24px; text-align: center;
  display: flex; align-items: center; justify-content: center; height: 100%; }}

/* ── Segmentos ── */
h3.segs-title {{ color: #ffe600; margin: 20px 0 10px; font-size: 16px; border-bottom: 1px solid #243040; padding-bottom: 6px; }}
.segment-block {{ background: #0e1620; border: 1px solid #1e2d40; border-radius: 8px;
  padding: 14px; margin-bottom: 18px; }}
.segment-header {{ display: flex; justify-content: space-between; align-items: center;
  color: #00e5ff; font-weight: bold; font-size: 15px;
  border-bottom: 1px dashed #1e2d40; padding-bottom: 8px; margin-bottom: 10px; }}
.seg-check-label {{ font-size: 13px; color: #88e5b0; cursor: pointer; }}

.seg-n1-focused {{ margin-bottom: 12px; }}
.seg-n1-title {{ font-weight: 600; color: #a8c8e8; margin-bottom: 6px; font-size: 13px; }}
.seg-n1-focused .canvas {{ height: 400px; }}

.segment-links-box {{ display: flex; flex-wrap: wrap; gap: 14px 24px; background: #080d14;
  border: 1px solid #1a2738; border-radius: 6px; padding: 10px 14px; margin-bottom: 10px; }}
.link-item {{ font-size: 13px; }}
.link-ini {{ color: #ff8888; }}
.link-fim {{ color: #88ff88; }}
.link-dim {{ color: #ffe600; }}
.link-comp {{ color: #00e5ff; }}
.link-val {{ font-weight: bold; background: #141e2c; border: 1px solid #2a3d55;
  padding: 2px 8px; border-radius: 4px; color: #ffffff; font-family: monospace; font-size: 13px; }}

.segment-note-label {{ display: block; margin-top: 8px; font-weight: 600; color: #a8c8e8; font-size: 12px; }}
textarea.segment-note {{ display: block; width: 100%; margin-top: 5px; background: #0a0f17;
  color: #d9e4f0; border: 1px solid #2a3d55; border-radius: 5px; padding: 8px; font: inherit; }}

.global-note-label {{ display: block; margin-top: 14px; font-weight: 600; color: #a8c8e8; font-size: 13px; }}
textarea.global-note {{ display: block; width: 100%; margin-top: 5px; background: #0a0f17;
  color: #d9e4f0; border: 1px solid #2a3d55; border-radius: 5px; padding: 8px; font: inherit; }}

@media(max-width: 1400px) {{ .top-views {{ grid-template-columns: 1fr; }} .canvas {{ height: 420px; }} }}
</style>
</head>
<body>
<main>

<!-- NAVBAR -->
<div class="nav-bar">
  <a class="nav-btn" href="{prev_b}.html">← {prev_b}</a>
  <div class="nav-center">
    <select id="beam-select" onchange="window.location.href=this.value">
      {options_html}
    </select>
    <span class="nav-counter">({idx_b + 1} / {total})</span>
  </div>
  <a class="nav-btn" href="{next_b}.html">{next_b} →</a>
</div>

<!-- CARD DA VIGA -->
<div class="viga-card" data-key="{html.escape(b_key)}">
  <div class="viga-header">
    <h2>Viga {html.escape(b_name)} — {total_segs} Segmento(s) de Fundo</h2>
    <label class="global-valid-label">
      <input class="global-validated" type="checkbox"> Validar Viga Inteira
    </label>
  </div>

  <!-- VIEWS SUPERIORES: N1 CONTEXTO AMPLO + N3 STOG -->
  <div class="top-views">
    <div class="view-pane">
      <h3>
        <span>📐 N1 · Recorte do Estrutural (Contexto Amplo)</span>
        <small>{html.escape(n1_file_name)}</small>
      </h3>
      <div class="canvas">{svg_n1_ctx}</div>
    </div>
    <div class="view-pane">
      <h3>
        <span>🏗️ N3 · Ficha Técnica Oficial STOG</span>
        <small>gerar_fv_dxf_stog.py</small>
      </h3>
      <div class="canvas">{svg_n3}</div>
    </div>
  </div>

  <!-- SEGMENTOS: cada um com N1 FOCADO + VÍNCULOS DE TEXTO -->
  <h3 class="segs-title">Ficha de Vínculos por Segmento ({total_segs} segmento(s))</h3>
  <div class="segments-container">
    {''.join(seg_cards)}
  </div>

  <label class="global-note-label">Observações Gerais — Viga {html.escape(b_name)}:
    <textarea class="global-note" rows="2" placeholder="Observações gerais sobre esta viga..."></textarea>
  </label>
</div>

</main>
<script>
(function () {{
  const beamKey = {json.dumps(b_key)};
  const sk = 'cad_fv_rev_' + beamKey.replace(/[^a-zA-Z0-9]/g, '_');

  function load() {{
    try {{ return JSON.parse(localStorage.getItem(sk) || '{{}}'); }} catch(e) {{ return {{}}; }}
  }}
  function save(st) {{
    try {{ localStorage.setItem(sk, JSON.stringify(st)); }} catch(e) {{}}
  }}

  const saved = load();
  const gCheck = document.querySelector('.global-validated');
  const gNote  = document.querySelector('.global-note');
  if (gCheck) gCheck.checked = !!saved.global_valid;
  if (gNote)  gNote.value   = saved.global_note || '';

  document.querySelectorAll('.segment-block').forEach(block => {{
    const idx   = block.dataset.seg;
    const check = block.querySelector('.segment-valid');
    const note  = block.querySelector('.segment-note');
    const sd    = (saved.segs || {{}})[idx] || {{}};
    if (check) check.checked = !!sd.valid;
    if (note)  note.value    = sd.note || '';

    const upd = () => {{
      const st = load();
      st.segs = st.segs || {{}};
      st.segs[idx] = {{ valid: check?.checked, note: note?.value }};
      st.global_valid = gCheck?.checked;
      st.global_note  = gNote?.value;
      save(st);
    }};
    check?.addEventListener('change', upd);
    note?.addEventListener('input', upd);
  }});
  gCheck?.addEventListener('change', () => {{ const st=load(); st.global_valid=gCheck.checked; save(st); }});
  gNote?.addEventListener('input',   () => {{ const st=load(); st.global_note =gNote.value;   save(st); }});
}})();
</script>
</body>
</html>
'''
        (out_dir / f"{b_name}.html").write_text(page_html, encoding='utf-8')
        print(f"  [{idx_b+1}/{total}] {b_name}.html — {total_segs} seg(s)")

    # index.html
    first = unvalidated_beams[0]["name"]
    (out_dir / 'index.html').write_text(
        f'<!doctype html><html><head><meta http-equiv="refresh" content="0; url={first}.html"></head>'
        f'<body><a href="{first}.html">{first}.html</a></body></html>',
        encoding='utf-8'
    )

    print(f"\n[OK] Painel HTML N1 x N3 Gerado com Sucesso ({total} arquivos HTML):")
    print(f"   file:///{(out_dir / f'{first}.html').as_posix()}")
    return out_dir / f"{first}.html"


if __name__ == '__main__':
    build_fv_unvalidated_n1_n3_html()
