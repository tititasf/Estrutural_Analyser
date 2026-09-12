"""Gerador granular das páginas HTML de fundos de viga.

Mantém lado a lado as evidências das quatro etapas usadas para depurar FV:
N1/SA, N2 humano, N3 robô via SA e N4 robô via engenharia reversa.

Versão HTML 2.0 (viewer contextual HI-FI):
- SA | C1 | C2 | C3 | **N3** no mesmo pan/zoom (viewBox)
- envelope quadrado + zoom inicial 2× + tags verticais à esquerda
- N3 materializado em ``fundos_viga/n3/{viga}_n3.svg`` no momento da geração
"""

from __future__ import annotations

import base64
import glob
import html
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Callable

from src.ui.widgets.svg_embed_utils import embed_visual as _embed_visual
from src.core.fv_generation_contract import (
    PANEL_MODULE,
    chain_linear_segment_apoios,
    compute_panel_modules,
)

# N3 ficha viewer: space between N1 segments and vertical b-dim offset.
N3_SEG_GAP_CM = 50.0
N3_DIM_B_OFFSET_CM = 20.0

# Marcador de contrato do pack (consumidores / notes server / QA)
FV_HTML_CONTRACT_VERSION = "2.0"


def _qa_presentation_banner(*, dossier_path=None) -> str:
    return ""


def materialize_fv_n3_svg(
    dxf_path: str | os.PathLike | None,
    out_svg: str | os.PathLike,
    *,
    inline_svg: str = "",
    width: int = 1600,
    height: int = 1600,
) -> str:
    """Garante ``out_svg`` com markup N3 e devolve o SVG (ou '').

    Preferência:
    1. ``inline_svg`` já renderizado (ex. dialog desktop ``_render_ezdxf_b64``)
    2. re-render do DXF N3 (ezdxf + matplotlib) — headless / gerador SA
    """
    out = Path(out_svg)
    out.parent.mkdir(parents=True, exist_ok=True)
    markup = ""
    raw = (inline_svg or "").strip()
    if raw.startswith("data:"):
        try:
            payload = raw.split(",", 1)[-1]
            markup = base64.b64decode(payload).decode("utf-8", errors="replace")
        except Exception:
            markup = ""
    elif raw and "<svg" in raw:
        markup = raw
    if not markup and dxf_path and os.path.isfile(str(dxf_path)):
        try:
            import io

            import ezdxf
            from ezdxf.addons.drawing import Frontend, RenderContext
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            dpi = 120
            doc = ezdxf.readfile(str(dxf_path))
            msp = doc.modelspace()
            dark = "#0a0a0a"
            with matplotlib.rc_context({"svg.fonttype": "none"}):
                fig = plt.figure(
                    figsize=(width / dpi, height / dpi),
                    dpi=dpi,
                    facecolor=dark,
                )
                ax = fig.add_axes([0, 0, 1, 1])
                ax.set_facecolor(dark)
                Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(msp)
                buf = io.BytesIO()
                fig.savefig(
                    buf,
                    format="svg",
                    dpi=dpi,
                    facecolor=dark,
                    edgecolor="none",
                    bbox_inches="tight",
                    pad_inches=0.02,
                )
                plt.close(fig)
            markup = buf.getvalue().decode("utf-8", errors="replace")
        except Exception as exc:
            print(f"[HTML] N3 render falhou ({Path(dxf_path).name}): {exc}", flush=True)
            markup = ""
    if not markup:
        return ""
    try:
        from src.ui.widgets.fv_hifi_n1_render import repair_n3_inline_svg as _sanitize_svg
    except Exception:
        try:
            from src.ui.widgets.fv_hifi_n1_render import sanitize_inline_svg as _sanitize_svg
        except Exception:
            _sanitize_svg = None  # type: ignore
    if _sanitize_svg:
        markup = _sanitize_svg(markup)
    else:
        markup = re.sub(r"<\?xml[^>]*\?>", "", markup).strip()
        markup = re.sub(r"<!DOCTYPE[^>]*>", "", markup, flags=re.I | re.S)
        i = markup.find("<svg")
        markup = markup[i:].strip() if i >= 0 else ""
        markup = re.sub(
            r'(<svg\b[^>]*?)\s(width|height)="[^"]*"', r"\1", markup, count=4
        )
    try:
        out.write_text(markup, encoding="utf-8")
    except Exception as exc:
        print(f"[HTML] N3 write falhou {out}: {exc}", flush=True)
    return markup if out.is_file() else ""


# ── JavaScript para colapso de fichas ───────────────────────────────────────
_COLLAPSE_JS = (
    '<script>'
    '(function(){'
    # Colapsa .sec; contextual HI-FI (#fvctx-main) começa ABERTO
    'function initSec(){'
    '  document.querySelectorAll(".sec").forEach(function(sec){'
    '    var t=sec.querySelector(".sec-title");'
    '    var b=sec.querySelector(".sec-body");'
    '    if(!t||!b)return;'
    '    var keepOpen=sec.id==="fvctx-main";'
    '    b.style.display=keepOpen?"":"none";'
    '    t.style.cursor="pointer";'
    '    t.style.userSelect="none";'
    '    t.dataset.collapsed=keepOpen?"0":"1";'
    '    var orig=t.innerHTML;'
    '    var chev=keepOpen?"\u25BC":"\u25B6";'
    '    t.innerHTML="<span class=\'fv-chevron\'>"+chev+"</span><span class=\'fv-sec-label\'>"+orig+"</span>";'
    '    t.addEventListener("click",function(){'
    '      var open=t.dataset.collapsed==="1";'
    '      b.style.display=open?"":"none";'
    '      t.dataset.collapsed=open?"0":"1";'
    '      t.querySelector(".fv-chevron").textContent=open?"\u25BC":"\u25B6";'
    '    });'
    '  });'
    '}'
    # Colapsa .ficha-col-title (colunas dentro das fichas: "Ficha N1/SA", "Vértices", "Quality gates")
    'function initFichaCol(){'  
    '  document.querySelectorAll(".ficha-col-title").forEach(function(t){'  
    '    var cell=t.nextElementSibling;'  
    '    if(!cell)return;'  
    '    cell.style.display="none";'  
    '    t.style.cursor="pointer";'  
    '    t.style.userSelect="none";'  
    '    t.style.padding="3px 6px";'  
    '    t.style.borderRadius="3px";'  
    '    t.style.transition="background 0.15s";'  
    '    t.dataset.collapsed="1";'  
    '    var orig=t.innerHTML;'  
    '    t.innerHTML="<span style=\'color:#555;margin-right:5px;font-size:9px;\'>\u25B6</span>"+orig;'  
    '    t.addEventListener("mouseenter",function(){t.style.background="#1a1a2a";});'  
    '    t.addEventListener("mouseleave",function(){t.style.background="";});'  
    '    t.addEventListener("click",function(){'  
    '      var open=t.dataset.collapsed==="1";'  
    '      cell.style.display=open?"":"none";'  
    '      t.dataset.collapsed=open?"0":"1";'  
    '      t.querySelector("span").textContent=open?"\u25BC":"\u25B6";'  
    '    });'  
    '  });'  
    '}'  
    # Colapsa .evidence-card (cards N2, N3, N4 com imagens grandes)
    'function initEvidence(){'  
    '  document.querySelectorAll(".evidence-card").forEach(function(card){'  
    '    var titleDiv=card.querySelector(".evidence-title");'  
    '    if(!titleDiv)return;'  
    '    var children=[].slice.call(card.children).filter(function(c){return c!==titleDiv;});'  
    '    children.forEach(function(c){c.style.display="none";});'  
    '    titleDiv.style.cursor="pointer";'  
    '    titleDiv.style.userSelect="none";'  
    '    titleDiv.style.padding="4px 2px";'  
    '    titleDiv.dataset.collapsed="1";'  
    '    var arrow=document.createElement("span");'  
    '    arrow.textContent="\u25B6";'  
    '    arrow.style.cssText="color:#555;margin-right:6px;font-size:9px;flex-shrink:0";'  
    '    titleDiv.insertBefore(arrow,titleDiv.firstChild);'  
    '    titleDiv.addEventListener("click",function(){'  
    '      var open=titleDiv.dataset.collapsed==="1";'  
    '      children.forEach(function(c){c.style.display=open?"":"none";});'  
    '      titleDiv.dataset.collapsed=open?"0":"1";'  
    '      arrow.textContent=open?"\u25BC":"\u25B6";'  
    '    });'  
    '  });'  
    '}'  
    'document.addEventListener("DOMContentLoaded",function(){'  
    '  initSec();initFichaCol();initEvidence();'  
    '});'  
    '})();'  
    '</script>'
)


def _safe_slug(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or ""))
    return clean.strip("._") or "item"


def _table_row(label: str, value, color: str = "#7eb8f7") -> str:
    if isinstance(value, (dict, list, tuple)):
        rendered = json.dumps(value, ensure_ascii=False, indent=2)
    else:
        rendered = "—" if value in (None, "") else str(value)
    return (
        "<tr>"
        f'<td style="color:{color};padding:2px 5px;white-space:nowrap;'
        f'vertical-align:top;font-weight:600">{html.escape(str(label))}</td>'
        f'<td style="padding:2px 5px;white-space:pre-wrap">'
        f"{html.escape(rendered)}</td></tr>"
    )


def _fmt_seg_cell(value) -> str:
    if value in (None, "", "N/A", "n/a", "-", "—"):
        return "—"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value).strip() or "—"


def _parse_dim_wh(text) -> tuple[str, str]:
    """Largura / altura de um texto SA ``19/50`` ou ``25/120``.

    Convenção do motor: a altura (profundidade da viga) é o maior número.
    """
    nums: list[float] = []
    for raw in re.findall(r"(\d+(?:[.,]\d+)?)", str(text or "")):
        try:
            nums.append(float(raw.replace(",", ".")))
        except ValueError:
            continue
    if not nums:
        return "", ""
    if len(nums) == 1:
        return f"{nums[0]:g}", ""
    return f"{min(nums):g}", f"{max(nums):g}"


def _niveis_from_beam_fields(fields: dict | None) -> str:
    """Cota da viga: o maior nível encontrado nas laterais/lajes da mesma viga."""
    best: float | None = None
    for key, raw in (fields or {}).items():
        k = str(key).lower()
        if "nivel_viga" not in k and k not in ("nivel_lado_a", "nivel_lado_b"):
            continue
        val = _fmt_seg_cell(raw)
        if val in ("—", "0"):
            continue
        try:
            num = float(val.replace(",", "."))
        except ValueError:
            continue
        if best is None or num > best:
            best = num
    return f"{best:g}" if best is not None else ""


def _exception_summary(payload: dict | None, prefixes: tuple[str, ...]) -> str:
    if not isinstance(payload, dict):
        return "—"
    parts: list[str] = []
    for key, raw in payload.items():
        k = str(key).lower()
        if not any(p in k for p in prefixes):
            continue
        val = _fmt_seg_cell(raw)
        if val == "—":
            continue
        short = str(key).replace("chanfro_", "").replace("abertura_", "")
        parts.append(f"{short} {val}")
    return ", ".join(parts) if parts else "—"


# No N3 de fundo a medida vertical do painel é a largura da chapa (máx. 122).
N3_PANEL_VERT_MAX = 122.0
_CHANFER_KEYS = (
    ("chanfro_esq_top", "Esq. topo"),
    ("chanfro_esq_fun", "Esq. fundo"),
    ("chanfro_dir_top", "Dir. topo"),
    ("chanfro_dir_fun", "Dir. fundo"),
)
_OPENING_KEYS = (
    ("abertura_topo_esq", "Topo esq."),
    ("abertura_topo_dir", "Topo dir."),
    ("abertura_fundo_esq", "Fundo esq."),
    ("abertura_fundo_dir", "Fundo dir."),
)


def _modules(total: float, module: float, minimum: float = 30.0) -> list[float]:
    value = 0.0
    try:
        value = float(str(total).replace(",", "."))
    except (TypeError, ValueError):
        return []
    if value <= 0:
        return []
    if value <= module:
        return [round(value, 3)]
    full = int(value // module)
    remainder = value - full * module
    if remainder < 0.5:
        return [module] * full
    if remainder < minimum:
        return [module] * (full - 1) + [round(module + remainder, 3)]
    return [module] * full + [round(remainder, 3)]


def _n3_panels_for_segment(length: Any, width: Any) -> list[dict]:
    """Painéis usados no N3: comprimento ≤ 244, largura vertical ≤ 122."""
    try:
        length_f = float(str(length).replace(",", "."))
    except (TypeError, ValueError):
        length_f = 0.0
    try:
        width_f = float(str(width).replace(",", "."))
    except (TypeError, ValueError):
        width_f = 0.0
    lengths = compute_panel_modules(length_f) or ([length_f] if length_f > 0 else [])
    widths = (
        _modules(width_f, N3_PANEL_VERT_MAX, minimum=1.0)
        if width_f > 0
        else [width_f]
    )
    panels: list[dict] = []
    index = 0
    for along in lengths:
        for vert in widths:
            index += 1
            panels.append(
                {
                    "i": index,
                    "comprimento": along,
                    "largura": vert,
                }
            )
    return panels


def _n3_tag_label(label) -> str:
    lab = str(label or "").strip() or "1"
    if lab.upper().startswith("S"):
        return lab
    return f"S{lab}"


def _n3_row_length(row: dict) -> float:
    raw = row.get("comprimento")
    try:
        val = float(str(raw).replace(",", "."))
        if val > 0:
            return val
    except (TypeError, ValueError):
        pass
    panels = _n3_panels_for_segment(row.get("comprimento"), row.get("largura"))
    return sum(float(p["comprimento"]) for p in panels) if panels else 0.0


def _n3_content_bbox(svg: str) -> tuple[float, float, float, float] | None:
    """BBox of CAD strokes, ignoring full-canvas matplotlib fills."""
    xs: list[float] = []
    ys: list[float] = []
    try:
        from src.ui.widgets.fv_hifi_n1_render import _path_xy
    except Exception:
        return None
    for d in re.findall(r'<path\b[^>]*\bd="([^"]+)"', svg, flags=re.I):
        px, py = _path_xy(d)
        if not px or not py:
            continue
        if max(px) - min(px) > 800 and max(py) - min(py) > 80:
            continue
        xs.extend(px)
        ys.extend(py)
    if len(xs) < 4 or len(ys) < 4:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def overlay_n3_segment_tags(
    svg: str, seg_rows: list[dict], *, seg_gap: float = N3_SEG_GAP_CM
) -> str:
    """Keep the robot N3 drawing; add SA-style S* tags at N1 length proportions."""
    if not svg or "<svg" not in svg or not seg_rows:
        return svg
    if 'data-n3-composed="1"' in svg:
        return ""
    s = re.sub(
        r'<g class="fv-n3-seg"[^>]*>.*?</g>',
        "",
        svg,
        flags=re.S,
    )
    lengths = [_n3_row_length(row) for row in seg_rows]
    if all(v <= 0 for v in lengths):
        lengths = [1.0] * len(seg_rows)
    gap = max(float(seg_gap or 0.0), 0.0)
    total = sum(lengths) + gap * max(len(lengths) - 1, 0)
    total = total or float(len(lengths))
    bbox = _n3_content_bbox(s)
    vb_m = re.search(r'viewBox="([^"]+)"', s)
    if vb_m:
        parts = [float(x) for x in vb_m.group(1).replace(",", " ").split() if x]
    else:
        parts = []
    if len(parts) < 4 and bbox:
        parts = [bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]]
    if len(parts) < 4:
        return svg
    vb_x, vb_y, vb_w, vb_h = parts[:4]
    if bbox:
        x0, y0, x1, y1 = bbox
    else:
        x0, y0, x1, y1 = vb_x, vb_y, vb_x + vb_w, vb_y + vb_h
    span = max(x1 - x0, 1.0)
    beam_h = max(y1 - y0, 1.0)
    tag_h = max(7.5, min(11.0, beam_h * 0.28))
    leader = max(4.0, tag_h * 0.55)
    tag_space = tag_h + leader + 3.0
    fs = max(5.2, tag_h * 0.62)
    groups: list[str] = []
    acc = 0.0
    for i, row in enumerate(seg_rows):
        label = str(row.get("label") or (i + 1)).strip() or str(i + 1)
        safe = html.escape(label, quote=True)
        tag = html.escape(_n3_tag_label(label))
        L = lengths[i]
        seg_x0 = x0 + span * (acc / total)
        acc += L
        seg_x1 = x0 + span * (acc / total)
        if i < len(lengths) - 1:
            acc += gap
        cx = (seg_x0 + seg_x1) / 2.0
        even = i % 2 == 0
        tag_bg = "#b71c1c" if even else "#ad1457"
        tag_edge = "#ff8a80" if even else "#f48fb1"
        tw = max(tag_h * 1.15, fs * (len(tag) * 0.72 + 0.8))
        ty = y0 - leader - tag_h
        groups.append(
            f'<g class="fv-n3-seg" data-n3-seg="{safe}" data-seg="{safe}">'
            f'<rect class="fv-n3-focus" x="{seg_x0:.3f}" y="{y0:.3f}" '
            f'width="{max(seg_x1 - seg_x0, 0.5):.3f}" height="{beam_h:.3f}" '
            f'fill="none" stroke="none"/>'
            f'<line x1="{cx:.3f}" y1="{y0:.3f}" x2="{cx:.3f}" y2="{ty + tag_h:.3f}" '
            f'stroke="{tag_edge}" stroke-width="0.6"/>'
            f'<rect class="fv-n3-tag-bg" x="{cx - tw / 2:.3f}" y="{ty:.3f}" '
            f'width="{tw:.3f}" height="{tag_h:.3f}" rx="{tag_h * 0.22:.2f}" '
            f'fill="{tag_bg}" stroke="{tag_edge}" stroke-width="0.5"/>'
            f'<text class="fv-n3-tag" x="{cx:.3f}" y="{ty + tag_h * 0.72:.3f}" '
            f'text-anchor="middle" fill="#ffffff" font-size="{fs:.2f}" '
            f'font-weight="700" font-family="Segoe UI,system-ui,sans-serif">'
            f"{tag}</text></g>"
        )
    new_y = min(vb_y, y0 - tag_space)
    new_h = (vb_y + vb_h) - new_y
    s = re.sub(
        r'viewBox="[^"]*"',
        f'viewBox="{vb_x:.3f} {new_y:.3f} {vb_w:.3f} {new_h:.3f}"',
        s,
        count=1,
    )
    if "</svg>" not in s:
        return svg
    return s.replace("</svg>", "".join(groups) + "</svg>", 1)


def _n3_stog_panels_from_rows(seg_rows: list[dict]) -> list[dict]:
    """One STOG segment per N1 ficha row, length = comprimento da ficha."""
    panels: list[dict] = []
    for row in seg_rows:
        length = _n3_row_length(row)
        if length <= 0:
            continue
        modules = compute_panel_modules(length) or [length]
        item = {
            "total_width": length,
            "width": length,
            "panels": [{"width": float(m)} for m in modules],
        }
        ini = str(row.get("ponto_inicial") or "").strip()
        fim = str(row.get("ponto_final") or "").strip()
        if ini and ini not in ("—", "-", "N/A"):
            item["texto_esq"] = ini
        if fim and fim not in ("—", "-", "N/A"):
            item["texto_dir"] = fim
        try:
            b = float(str(row.get("largura") or "").replace(",", "."))
        except (TypeError, ValueError):
            b = 0.0
        if b > 0:
            item["b"] = b
        panels.append(item)
    return panels


def _stog_fv_mod():
    root = Path(__file__).resolve().parents[3]
    scripts = root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import gerar_fv_dxf_stog as stog

    return stog


def render_n3_svg_from_seg_rows(
    seg_rows: list[dict],
    beam: str,
    *,
    out_svg: str = "",
) -> str:
    """Official STOG N3 drawing from N1 ficha segments (244 modules, sarrafo)."""
    panels = _n3_stog_panels_from_rows(seg_rows)
    if not panels:
        return ""
    widths = []
    for row in seg_rows:
        try:
            w = float(str(row.get("largura") or "").replace(",", "."))
        except (TypeError, ValueError):
            w = 0.0
        if w > 0:
            widths.append(w)
    viga_b = widths[0] if widths else 19.0
    name = str(beam or "VIGA").split()[0]
    if not name.upper().endswith(".C"):
        name = f"{name}.C"
    tmp_dxf = ""
    try:
        stog = _stog_fv_mod()
        doc = stog.setup_doc()
        stog.draw_viga(
            doc.modelspace(),
            0,
            0,
            panels,
            viga_b,
            name,
            label_left=str(panels[0].get("texto_esq") or ""),
            label_right=str(panels[-1].get("texto_dir") or ""),
            inter_segment_gap=N3_SEG_GAP_CM,
            dim_b_every_segment=True,
            dim_b_offset=N3_DIM_B_OFFSET_CM,
            coalesce_junction_labels=True,
        )
        fd, tmp_dxf = tempfile.mkstemp(suffix=".dxf")
        os.close(fd)
        doc.saveas(tmp_dxf)
        out = out_svg or (tmp_dxf + ".svg")
        markup = materialize_fv_n3_svg(tmp_dxf, out)
        return markup or ""
    except Exception as exc:
        print(f"[HTML] N3 STOG render falhou ({name}): {exc}", flush=True)
        return ""
    finally:
        if tmp_dxf:
            try:
                os.unlink(tmp_dxf)
            except OSError:
                pass


def _field_grid_html(title: str, pairs: list[tuple[str, str]], values: dict) -> str:
    cells = []
    for key, label in pairs:
        cells.append(
            '<div class="fv-mini-field">'
            f'<span>{html.escape(label)}</span>'
            f"<b>{html.escape(_fmt_seg_cell(values.get(key)))}</b>"
            "</div>"
        )
    return (
        f'<div class="fv-mini-block"><div class="fv-mini-title">{html.escape(title)}</div>'
        f'<div class="fv-mini-grid">{"".join(cells)}</div></div>'
    )


def _fv_beam_summary_html(beam: str, n_segs: int) -> str:
    return (
        '<div class="fv-ficha-summary">'
        '<div class="fv-sum-item"><span>Nome</span>'
        f"<b>{html.escape(beam)}</b></div>"
        '<div class="fv-sum-item"><span>Quantidade de segmentos</span>'
        f"<b>{int(n_segs)}</b></div>"
        "</div>"
    )


def _fv_seg_table_html(seg_rows: list[dict]) -> str:
    rows_html = []
    for row in seg_rows:
        label = _fmt_seg_cell(row.get("label"))
        length = row.get("comprimento")
        width = row.get("largura")
        panels = _n3_panels_for_segment(length, width)
        panel_rows = []
        for panel in panels:
            panel_rows.append(
                "<tr>"
                f"<td>{panel['i']}</td>"
                f"<td>{html.escape(_fmt_seg_cell(panel['comprimento']))}</td>"
                f"<td>{html.escape(_fmt_seg_cell(panel['largura']))}</td>"
                "</tr>"
            )
        if not panel_rows:
            panel_rows.append(
                '<tr><td colspan="3" class="fv-muted">sem painel N3</td></tr>'
            )
        safe_label = html.escape(str(label), quote=True)
        rows_html.append(
            f'<tr class="fv-seg-item" data-seg="{safe_label}" '
            f'id="fv-seg-item-{safe_label}" tabindex="0" aria-expanded="false">'
            '<td class="fv-col-chev"><span class="fv-seg-chev" aria-hidden="true">'
            "</span></td>"
            f'<td><span class="fv-seg-id">{html.escape(str(label))}</span></td>'
            f'<td class="fv-col-num">{html.escape(_fmt_seg_cell(length))}</td>'
            f'<td class="fv-col-num">{html.escape(_fmt_seg_cell(width))}</td>'
            f'<td class="fv-col-num">{html.escape(_fmt_seg_cell(row.get("altura")))}</td>'
            f'<td class="fv-col-num">{html.escape(_fmt_seg_cell(row.get("nivel")))}</td>'
            f"<td>{html.escape(_fmt_seg_cell(row.get('ponto_inicial')))}</td>"
            f"<td>{html.escape(_fmt_seg_cell(row.get('ponto_final')))}</td>"
            f'<td class="fv-col-num fv-muted">{len(panels)}</td>'
            "</tr>"
            f'<tr class="fv-seg-detail" data-seg="{safe_label}" hidden>'
            '<td colspan="9">'
            '<div class="fv-seg-body">'
            '<div class="fv-mini-block">'
            '<div class="fv-mini-title">Painéis N3 '
            f'(máx. {int(PANEL_MODULE)} × {int(N3_PANEL_VERT_MAX)})</div>'
            '<table class="fv-panel-table">'
            "<thead><tr><th>#</th><th>Comprimento</th>"
            "<th>Largura (vertical N3)</th></tr></thead>"
            f"<tbody>{''.join(panel_rows)}</tbody></table></div>"
            f"{_field_grid_html('Chanfros', _CHANFER_KEYS, row)}"
            f"{_field_grid_html('Aberturas', _OPENING_KEYS, row)}"
            "</div></td></tr>"
        )
    body = (
        "".join(rows_html)
        if rows_html
        else '<tr><td colspan="9" class="fv-muted">Nenhum segmento interpretado.</td></tr>'
    )
    return (
        '<div class="fv-seg-table-wrap" id="fv-seg-list">'
        '<div class="fv-seg-table-title">Interpretação dos segmentos</div>'
        '<table class="fv-seg-table">'
        "<thead><tr>"
        '<th class="fv-col-chev"></th>'
        "<th>Seg.</th>"
        '<th class="fv-col-num">Comprimento</th>'
        '<th class="fv-col-num">Largura</th>'
        '<th class="fv-col-num">Altura da viga</th>'
        '<th class="fv-col-num">Nível da viga</th>'
        "<th>Ponto inicial</th>"
        "<th>Ponto final</th>"
        '<th class="fv-col-num">Painéis N3</th>'
        "</tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )


def _collect_seg_table_row(meta: dict, dialog=None) -> dict:
    segment = meta.get("segment") or {}
    label = str(meta.get("label") or segment.get("segment_label") or "1")
    raw_beam = {}
    if dialog is not None:
        try:
            raw_beam = _beam_for(dialog, segment) or {}
        except Exception:
            raw_beam = {}
    fields = raw_beam.get("fields") or {}
    ficha = segment.get("ficha") if isinstance(segment.get("ficha"), dict) else {}
    try:
        idx = int(segment.get("segment_index") or label)
    except (TypeError, ValueError):
        idx = 1
    prefix = f"viga_fundo_seg_{idx}"
    links = raw_beam.get("links") or {}

    def _link_text(slot: dict | list | str | None) -> str:
        if isinstance(slot, str):
            return slot
        if isinstance(slot, dict):
            labels = slot.get("label") or slot.get("inicio") or slot.get("fim") or []
            if isinstance(labels, dict):
                labels = [labels]
            for item in labels or []:
                if isinstance(item, dict) and item.get("text"):
                    return str(item.get("text"))
                if isinstance(item, str) and item.strip():
                    return item
        return ""

    ini = (
        fields.get(f"{prefix}_local_ini")
        or segment.get("local_ini")
        or _link_text(links.get(f"{prefix}_local_ini"))
        or ""
    )
    fim = (
        fields.get(f"{prefix}_local_fim")
        or segment.get("local_fim")
        or _link_text(links.get(f"{prefix}_local_fim"))
        or ""
    )
    dim_text = (
        fields.get(f"{prefix}_dim")
        or segment.get("dim")
        or ficha.get("dim_text")
        or ""
    )
    largura_dim, altura_dim = _parse_dim_wh(dim_text)
    if not altura_dim:
        w_alt, h_alt = _parse_dim_wh(ficha.get("altura_total"))
        altura_dim = h_alt or w_alt
    largura = (
        largura_dim
        or _fmt_seg_cell(ficha.get("largura_total_fundo"))
        or _fmt_seg_cell(segment.get("width"))
    )
    altura = altura_dim or _fmt_seg_cell(ficha.get("altura_total"))
    nivel = (
        fields.get(f"{prefix}_nivel")
        or fields.get(f"{prefix}_level")
        or segment.get("level")
        or segment.get("nivel")
        or ficha.get("nivel")
        or _niveis_from_beam_fields(fields)
        or "—"
    )
    payload = dict(ficha)
    payload.update(
        {
            k: v
            for k, v in fields.items()
            if str(k).startswith(prefix)
        }
    )
    return {
        "label": label,
        "comprimento": segment.get("length") or ficha.get("comprimento_total_fundo"),
        "largura": largura,
        "altura": altura,
        "nivel": nivel,
        "ponto_inicial": ini,
        "ponto_final": fim,
        "chanfros": _exception_summary(payload, ("chanfro",)),
        "aberturas": _exception_summary(payload, ("abertura", "furo")),
        "chanfro_esq_top": payload.get("chanfro_esq_top") or ficha.get("chanfro_esq_top"),
        "chanfro_esq_fun": payload.get("chanfro_esq_fun") or ficha.get("chanfro_esq_fun"),
        "chanfro_dir_top": payload.get("chanfro_dir_top") or ficha.get("chanfro_dir_top"),
        "chanfro_dir_fun": payload.get("chanfro_dir_fun") or ficha.get("chanfro_dir_fun"),
        "abertura_topo_esq": payload.get("abertura_topo_esq") or ficha.get("abertura_topo_esq"),
        "abertura_topo_dir": payload.get("abertura_topo_dir") or ficha.get("abertura_topo_dir"),
        "abertura_fundo_esq": payload.get("abertura_fundo_esq") or ficha.get("abertura_fundo_esq"),
        "abertura_fundo_dir": payload.get("abertura_fundo_dir") or ficha.get("abertura_fundo_dir"),
    }


def _table_sep(label: str) -> str:
    return (
        '<tr><td colspan="2" style="padding:5px;color:#4fc3a1;'
        'border-top:1px solid #333;font-weight:bold">'
        f"{html.escape(label)}</td></tr>"
    )


def _attention(dialog, stage: str, beam: str, label: str) -> str:
    key = (
        f"aten_fv_{stage}_{dialog._obra}_{dialog._pavimento}_{beam}_{label}"
        .replace(" ", "_")
    )
    return (
        '<div class="atencao-cell" contenteditable="true" '
        f'data-atkey="{html.escape(key)}" onblur="saveAten(this)" '
        f'title="Anotação {html.escape(stage)} — '
        f'{html.escape(beam)} · segmento {html.escape(label)}"></div>'
    )


def _error_marker_block(dialog, beam: str) -> str:
    key = f"aten_erro_fv_{dialog._obra}_{dialog._pavimento}_{beam}".replace(" ", "_")
    key_js = json.dumps(key)
    return (
        '<div class="sec" style="margin-top:16px;border-color:#5a2020">'
        '<div class="sec-title" style="color:#e17055">'
        "Marcação de erro (revisão humana)</div>"
        '<div class="sec-body">'
        '<label style="display:flex;align-items:center;gap:8px;cursor:pointer;'
        'color:#e17055;font-weight:bold">'
        '<input type="checkbox" id="erro_check" style="width:16px;height:16px">'
        "Marcar esta ficha como ERRADA</label>"
        '<textarea id="erro_nota" placeholder='
        '"Descreva o que está errado (N1, N2, N3 ou N4)..." '
        'style="width:100%;min-height:70px;margin-top:8px;background:#1a1a1a;'
        "color:#f0b840;border:1px solid #554400;border-radius:3px;padding:6px;"
        'font-family:monospace;font-size:11px;box-sizing:border-box"></textarea>'
        "</div></div>"
        "<script>(function(){"
        f"var key={key_js};"
        "function save(){"
        '  var chk=document.getElementById("erro_check");'
        '  var txt=document.getElementById("erro_nota");'
        "  if(chk.checked||txt.value.trim()){"
        "    localStorage.setItem(key, JSON.stringify("
        "{erro:chk.checked, nota:txt.value}));"
        "  } else { localStorage.removeItem(key); }"
        "}"
        "function load(){"
        "  var stored=localStorage.getItem(key);"
        "  if(!stored)return;"
        "  try{"
        "    var obj=JSON.parse(stored);"
        '    document.getElementById("erro_check").checked=!!obj.erro;'
        '    document.getElementById("erro_nota").value=obj.nota||"";'
        "  }catch(e){}"
        "}"
        'document.addEventListener("DOMContentLoaded", function(){'
        "  load();"
        '  document.getElementById("erro_check")'
        '    .addEventListener("change", save);'
        '  document.getElementById("erro_nota")'
        '    .addEventListener("input", save);'
        "});"
        "})();</script>"
    )


# ── JavaScript: pan/zoom viewBox (HI-FI CAD) + textarea save/load ───────
# Fonte canônica: fv_hifi_n1_render.PANZOOM_VIEWBOX_JS (V301 aprovado).
try:
    from src.ui.widgets.fv_hifi_n1_render import (  # type: ignore
        HIFI_CSS as _HIFI_CSS,
        NOTES_SAVE_BAR as _NOTES_SAVE_BAR,
        NOTES_STORE_TAG as _NOTES_STORE_TAG,
        PANZOOM_VIEWBOX_JS as _PANZOOM_JS,
        render_fv_hifi_n1_svg as _render_fv_hifi_n1_svg,
        sanitize_inline_svg as _sanitize_inline_svg,
        wrap_panzoom_viewer as _wrap_panzoom_viewer,
    )
except Exception:  # pragma: no cover — fallback mínimo
    _HIFI_CSS = ""
    _PANZOOM_JS = "<script></script>"
    _NOTES_STORE_TAG = ""
    _NOTES_SAVE_BAR = ""

    def _render_fv_hifi_n1_svg(*_a, **_k):  # type: ignore
        return ""

    def _wrap_panzoom_viewer(cid, svg_markup, **_k):  # type: ignore
        return svg_markup or ""

    def _sanitize_inline_svg(markup=""):  # type: ignore
        return markup or ""


def _sidebar_error_flags_script(dialog) -> str:
    obra_js = json.dumps(dialog._obra)
    pav_js = json.dumps(dialog._pavimento)
    return (
        "<script>(function(){"
        f"var obra={obra_js}, pav={pav_js};"
        'document.querySelectorAll(".sidebar li[data-viga]").forEach('
        "function(li){"
        '  var nome=li.getAttribute("data-viga");'
        '  var key=("aten_erro_fv_"+obra+"_"+pav+"_"+nome).replace(/ /g,"_");'
        "  var stored=localStorage.getItem(key);"
        "  if(!stored)return;"
        "  try{"
        "    var obj=JSON.parse(stored);"
        "    if(obj.erro||((obj.nota||'').trim())){"
        '      var flag=li.querySelector(".erro-flag");'
        '      if(flag)flag.style.display="inline";'
        "    }"
        "  }catch(e){}"
        "});"
        "})();</script>"
    )


def _artifact_card(
    stage: str,
    subtitle: str,
    b64_value: str,
    path: str = "",
    image_class: str = "img-n4",
    fmt: str = "svg",
) -> str:
    if b64_value:
        image = _embed_visual(b64_value, fmt, image_class, stage)
    else:
        image = (
            '<div style="height:130px;display:flex;align-items:center;'
            'justify-content:center;color:#a85d55">artefato ausente</div>'
        )
    state = "disponível" if b64_value else "ausente"
    state_color = "#4fc3a1" if b64_value else "#e17055"
    path_html = (
        f'<div class="artifact-path">{html.escape(path)}</div>' if path else ""
    )
    return (
        '<div class="evidence-card">'
        f'<div class="evidence-title"><b>{html.escape(stage)}</b>'
        f'<span style="color:{state_color}">{state}</span></div>'
        f'<div style="color:#777;font-size:9px;margin-bottom:5px">'
        f"{html.escape(subtitle)}</div>{image}{path_html}</div>"
    )


def _pipeline_stage(
    dialog,
    stage: str,
    exists: bool,
    detail: str,
    beam: str,
    label: str,
) -> str:
    state_class = "ok" if exists else "missing"
    state_text = "artefato disponível" if exists else "artefato ausente"
    return (
        f'<div class="pipeline-stage {state_class}">'
        f'<div class="stage-name">{html.escape(stage)}</div>'
        f'<div class="stage-state">{html.escape(state_text)}</div>'
        f'<div style="font-size:9px;color:#aaa;min-height:30px">'
        f"{html.escape(detail)}</div>"
        f"{_attention(dialog, stage, beam, label)}</div>"
    )


def _beam_for(dialog, segment: dict) -> dict:
    identity = str(segment.get("beam_identity") or "")
    beam_name = str(segment.get("beam_name") or "")
    for beam in dialog._beams:
        if not isinstance(beam, dict):
            continue
        if identity and str(beam.get("id") or "") == identity:
            return beam
        if beam_name in {
            str(beam.get("name") or ""),
            str(beam.get("parent_name") or ""),
        }:
            return beam
    return {}


def _fv_context_points(beam: dict) -> list[tuple[float, float]]:
    """Retorna somente contornos FV da própria viga para o SVG contextual.

    O contexto distante explica a continuidade do fundo, mas não pode herdar
    geometria de LV.  Por isso esta coleta aceita exclusivamente os slots
    ``viga_fundo_seg_*_area_segs`` já persistidos no contrato FV.
    """
    points: list[tuple[float, float]] = []
    links = beam.get("links") if isinstance(beam, dict) else {}
    for key, slots in (links or {}).items():
        if not re.match(r"^viga_fundo_seg_\d+_area_segs$", str(key)):
            continue
        for link in (slots or {}).get("contour") or []:
            if not isinstance(link, dict):
                continue
            for point in link.get("points") or []:
                try:
                    points.append((float(point[0]), float(point[1])))
                except (TypeError, ValueError, IndexError):
                    continue
    return points


def _copy_latest_guide(output_dir: str, section_dir: str) -> None:
    """Copia somente documentação do pack anterior; nunca artefatos N3/N4."""
    base_dir = os.path.dirname(output_dir)
    previous_sections = sorted(
        (
            candidate
            for candidate in glob.glob(os.path.join(base_dir, "*", "fundos_viga"))
            if os.path.normcase(candidate) != os.path.normcase(section_dir)
        ),
        reverse=True,
    )
    for previous in previous_sections:
        guide = os.path.join(previous, "interpretacao_fundos.html")
        if not os.path.isfile(guide):
            continue
        shutil.copy2(guide, os.path.join(section_dir, "interpretacao_fundos.html"))
        images = os.path.join(previous, "imgs")
        if os.path.isdir(images):
            shutil.copytree(
                images, os.path.join(section_dir, "imgs"), dirs_exist_ok=True
            )
        return


def write_fundo_pages(
    dialog,
    title: str,
    rows: list[dict],
    output_dir: str,
    page_css: str,
    javascript: str,
    photo_fn: Callable[[list], str],
    metrics_fn: Callable[[list], dict],
) -> tuple[str, str, int]:
    """Grava índice e uma ficha por viga (contrato HTML FV 2.0).

    Viewer contextual: SA|C1|C2|C3|N3, pan/zoom viewBox, envelope quadrado.
    Materializa ``fundos_viga/n3/{slug}_n3.svg`` para cada viga com DXF N3.
    """
    section_dir = os.path.join(output_dir, "fundos_viga")
    n3_dir = os.path.join(section_dir, "n3")
    os.makedirs(section_dir, exist_ok=True)
    os.makedirs(n3_dir, exist_ok=True)
    # manifesto do contrato (QA / notes server / agentes)
    try:
        with open(
            os.path.join(section_dir, "FV_HTML_CONTRACT.json"),
            "w",
            encoding="utf-8",
        ) as mf:
            json.dump(
                {
                    "version": FV_HTML_CONTRACT_VERSION,
                    "viewer": "sa_c1_c2_c3_n3_panzoom_viewbox",
                    "envelope": "square",
                    "initial_zoom": 2.0,
                    "vertical_tags": "left_small",
                    "n3_path_pattern": "n3/{beam}_n3.svg",
                },
                mf,
                ensure_ascii=False,
                indent=2,
            )
    except Exception:
        pass
    # Evidências em coluna única: cada estágio ocupa toda a largura útil.
    # Os bitmaps são gerados em 2x abaixo, então o browser reduz a imagem
    # preservando detalhes em vez de ampliar um raster pequeno.
    page_css += (
        "html{box-sizing:border-box!important;overflow-x:hidden!important}\n"
        "*,*::before,*::after{box-sizing:inherit}\n"
        "body{display:block!important;margin:0!important;padding:16px!important;width:100%!important;"
        "max-width:100%!important;height:auto!important;overflow-x:hidden!important;overflow-y:auto!important;"
        "background:#111!important}\n"
        ".sidebar{display:none!important}\n"
        ".main-wrap{width:100%!important;max-width:100%!important;margin:0!important;padding:0!important;"
        "flex:none!important;height:auto!important;overflow:visible!important}\n"
        ".main-content{padding:0!important;min-width:0!important;width:100%!important;max-width:100%!important}\n"
        ".evidence-grid{display:grid!important;grid-template-columns:1fr!important;gap:18px!important}\n"
        ".evidence-card{width:100%;box-sizing:border-box;padding:10px!important}\n"
        ".evidence-card img,.evidence-card svg{display:block;width:100%!important;height:auto!important;"
        "max-height:none!important;object-fit:contain;background:#111}\n"
        ".artifact-path{font-size:9px!important}\n"
        ".bottom-info-box{margin-top:40px;padding-top:20px;border-top:1px solid #333;width:100%}\n"
    )

    grouped_rows: dict[str, list[dict]] = {}
    for row in rows:
        segment = row.get("_segment") or {}
        beam = str(segment.get("beam_name") or row.get("_beam") or "VIGA")
        grouped_rows.setdefault(beam, []).append(row)

    entries: list[tuple[str, list[dict], str]] = []
    used: set[str] = set()
    for beam, beam_rows in grouped_rows.items():
        base_slug = _safe_slug(beam)
        page_slug = base_slug
        suffix = 2
        while page_slug in used:
            page_slug = f"{base_slug}_{suffix}"
            suffix += 1
        used.add(page_slug)
        entries.append((beam, beam_rows, page_slug))

    def page(index: int) -> str:
        beam, beam_rows, _ = entries[index]
        n3_path = dialog._find_beam_dxf("FV", beam, n4=False)
        n4_path = dialog._find_beam_dxf("FV", beam, n4=True)
        n2_path = dialog._find_n2_recorte_dxf("FV", beam)
        n3_b64 = dialog._render_ezdxf_b64(n3_path, 1900, 1240, fmt="svg") if n3_path else ""
        n4_b64 = dialog._render_ezdxf_b64(n4_path, 1900, 1240, fmt="svg") if n4_path else ""
        n2_b64 = dialog._render_ezdxf_b64(n2_path, 1900, 1240, fmt="svg") if n2_path else ""

        previous = f"{entries[index - 1][2]}.html" if index else ""
        following = (
            f"{entries[index + 1][2]}.html"
            if index + 1 < len(entries)
            else ""
        )
        previous_link = (
            f'<a class="nav-arrow" href="{html.escape(previous)}">← anterior</a>'
            if previous
            else ""
        )
        next_link = (
            f'<a class="nav-arrow" href="{html.escape(following)}">próximo →</a>'
            if following
            else ""
        )
        options_html = "".join(
            f'<option value="{item_slug}.html" {"selected" if item_index == index else ""}>'
            f'{html.escape(item_beam)} ({len(item_rows)} segs)</option>'
            for item_index, (item_beam, item_rows, item_slug) in enumerate(entries)
        )
        select_html = (
            f'<select class="nav-select" onchange="window.location.href=this.value" '
            f'title="Trocar de viga">'
            f'{options_html}</select>'
        )
        _nav_prev_ph = (
            '<span class="nav-arrow" style="opacity:.35;pointer-events:none">'
            "← anterior</span>"
        )
        _nav_next_ph = (
            '<span class="nav-arrow" style="opacity:.35;pointer-events:none">'
            "próximo →</span>"
        )
        nav_bar = (
            f'<div class="nav-bar">'
            f"{previous_link or _nav_prev_ph}"
            f'<span class="nav-pos">'
            f"<b>{html.escape(beam)}</b>"
            f'<span style="color:#8b95a8">{index + 1}/{len(entries)}</span>'
            f"{select_html}"
            f'<span class="tag">FV</span>'
            f'<span class="tag">{len(beam_rows)} segs</span>'
            f"</span>"
            f"{next_link or _nav_next_ph}"
            f"</div>"
        )
        sidebar_items = "".join(
            f'<li{" class=\"active\"" if item_index == index else ""} '
            f'data-viga="{html.escape(item_beam)}">'
            f'<a href="{html.escape(item_slug)}.html">'
            f'<span class="erro-flag" style="display:none">⚠️ </span>'
            f"{html.escape(item_beam)} ({len(item_rows)})</a></li>"
            for item_index, (item_beam, item_rows, item_slug) in enumerate(entries)
        )
        sidebar = (
            f'<aside class="sidebar"><h3>Fundos FV ({len(entries)} vigas)</h3>'
            '<a class="sb-back" href="../index.html">← índice geral</a>'
            '<a class="sb-back" href="index.html">← índice FV</a>'
            '<a class="sb-back" href="interpretacao_fundos.html">Guia</a>'
            f"<ul>{sidebar_items}</ul></aside>"
            + _sidebar_error_flags_script(dialog)
        )

        n1_sections: list[str] = []
        n1_pipeline: list[str] = []
        n1_available = 0
        # ── Coleta de segmentos (payload canônico HI-FI) ───────────────────
        # Contextual = TODOS os segs numa só vista; local = 1 seg isolado.
        # Mesmo estilo visual (fv_hifi_n1_render) — aprovado no V301.
        _hifi_segments: list[dict] = []
        _seg_meta: list[dict] = []  # paralelo: row/fields para fichas
        for _si, row in enumerate(beam_rows):
            segment = row.get("_segment") or {}
            label = str(segment.get("segment_label") or row.get("Segmento") or "1")
            points = segment.get("points") or row.get("_points") or []
            _pts_valid = [
                (float(p[0]), float(p[1]))
                for p in points
                if isinstance(p, (list, tuple)) and len(p) >= 2
            ]
            if _pts_valid:
                _hifi_segments.append(
                    {"label": label, "points": _pts_valid, "index": _si}
                )
            _seg_meta.append(
                {
                    "row": row,
                    "segment": segment,
                    "label": label,
                    "points": points,
                    "index": _si,
                }
            )

        # DXF do dialog (headless e app preenchem _dxf_data)
        _dxf_data = getattr(dialog, "_dxf_data", None)

        def _hifi_svg(segs: list[dict], mode: str) -> str:
            """Prefere API do dialog; senão render puro; senão legado."""
            if hasattr(dialog, "_render_fv_hifi_n1_svg"):
                try:
                    out = dialog._render_fv_hifi_n1_svg(segs, mode=mode)
                    if out:
                        return out
                except Exception as exc:
                    print(f"[HTML] _render_fv_hifi_n1_svg falhou: {exc}", flush=True)
            out = _render_fv_hifi_n1_svg(_dxf_data, segs, mode=mode)
            if out:
                return out
            # Fallback legado (sem multi-highlight embutido)
            if not segs:
                return ""
            pts0 = segs[0].get("points") or []
            if not pts0:
                return ""
            try:
                return dialog._render_pilar_dxf_context_b64(
                    pts0,
                    width=2400 if mode == "local" else 3600,
                    height=900 if mode == "local" else 1100,
                    focus_mode="segment",
                    focus_label=f"FV {beam} · {mode}",
                    fmt="svg",
                    context_view="near" if mode == "local" else "far",
                    context_points=(
                        _fv_context_points(_beam_for(dialog, beam_rows[0].get("_segment") or {}))
                        if mode == "contextual" and beam_rows
                        else None
                    ),
                ) or ""
            except Exception:
                return ""

        _ctx_svg = _hifi_svg(_hifi_segments, "contextual") if _hifi_segments else ""

        for meta in _seg_meta:
            row = meta["row"]
            segment = meta["segment"]
            label = meta["label"]
            points = meta["points"]
            _si = meta["index"]
            metrics = metrics_fn(points)
            raw_beam = _beam_for(dialog, segment)
            fields = raw_beam.get("fields") or {}
            segment_index = int(segment.get("segment_index") or 1)
            field_prefix = f"viga_fundo_seg_{segment_index}"
            segment_fields = {
                key: value
                for key, value in fields.items()
                if str(key).startswith(field_prefix)
            }
            link_slots = (
                (raw_beam.get("links") or {}).get(segment.get("source_key") or "")
                or {}
            )
            source_key = str(segment.get("source_key") or "segmento_fundo")
            support_start = str(segment_fields.get(f"viga_fundo_seg_{segment_index}_local_ini") or "")
            support_end = str(segment_fields.get(f"viga_fundo_seg_{segment_index}_local_fim") or "")
            all_links = raw_beam.get("links") or {}
            local_support_links = {
                "inicio": all_links.get(f"viga_fundo_seg_{segment_index}_local_ini") or {},
                "fim": all_links.get(f"viga_fundo_seg_{segment_index}_local_fim") or {},
            }
            global_boundaries = all_links.get("apoios") or {}
            local_exceptions = {
                "cortes": all_links.get("cortes") or [],
                "aberturas": all_links.get("aberturas") or {},
            }
            local_subtitle = (
                f"Segmento {label} · {source_key} · dimensão {segment.get('width') or '—'} "
                f"· apoios {support_start or '—'} → {support_end or '—'} · "
                f"HI-FI local (mesmo estilo do contextual)"
            )
            _local_payload = [
                {
                    "label": label,
                    "points": [
                        (float(p[0]), float(p[1]))
                        for p in points
                        if isinstance(p, (list, tuple)) and len(p) >= 2
                    ],
                    "index": _si,
                }
            ]
            _local_svg = (
                _hifi_svg(_local_payload, "local") if _local_payload[0]["points"] else ""
            )
            _local_id = (
                f"fvlocal_{beam.replace(' ', '_')}_s{label}".replace("/", "_")
            )
            _local_viewer = _wrap_panzoom_viewer(
                _local_id, _local_svg, mode="local"
            )
            n1_available += bool(_local_svg)

            identity_rows = (
                _table_sep("IDENTIDADE E DECISÃO SA")
                + _table_row("UID", segment.get("uid"))
                + _table_row("Viga", beam)
                + _table_row("Segmento", label)
                + _table_row(
                    "Índice / ocorrência",
                    f'{segment.get("segment_index", "—")} / '
                    f'{segment.get("occurrence", "—")}',
                )
                + _table_row(
                    "Classe / lado / comportamento",
                    f'FV / {segment.get("side") or "Fundo"} / '
                    f'{segment.get("behavior") or "Fundo"}',
                )
                + _table_row(
                    "Status", row.get("Status") or segment.get("status") or "valid"
                )
                + _table_row(
                    "Atenção SA",
                    row.get("Atenção") or segment.get("attention") or "—",
                )
                + _table_sep("GEOMETRIA EXTRAÍDA")
                + _table_row("Comprimento declarado", segment.get("length"))
                + _table_row("Largura declarada", segment.get("width"))
                + _table_row("Orientação", metrics["orientation"])
                + _table_row(
                    "Span X / Span Y",
                    f'{metrics["span_x"]:.2f} / {metrics["span_y"]:.2f}',
                )
                + _table_row("Área do contorno", f'{metrics["area"]:.2f}')
                + _table_row(
                    "Vértices / únicos",
                    f'{metrics["vertex_count"]} / {metrics["unique_vertex_count"]}',
                )
                + _table_row(
                    "Contorno fechado", "Sim" if metrics["closed"] else "Não"
                )
                + _table_row("Centro", metrics["centroid"])
                + _table_row("BBox", metrics["bbox"])
                + _table_sep("RASTREABILIDADE DO VÍNCULO")
                + _table_row("beam_identity", segment.get("beam_identity"))
                + _table_row("source_key", segment.get("source_key"))
                + _table_row("source_slot", segment.get("source_slot"))
                + _table_row("tag", segment.get("tag"))
                + _table_row("ficha do link", segment.get("ficha") or {})
                + _table_row("evidence_segments", link_slots.get("contour") or [])
                + _table_row("campos SA do segmento", segment_fields)
                + _table_row("apoios locais do segmento", local_support_links)
                + _table_row("limites globais da viga", global_boundaries)
                + _table_row(
                    "furos/recortes no contexto local",
                    local_exceptions if any(local_exceptions.values()) else "N/A",
                )
                + _table_row("slots vinculados", link_slots)
            )
            vertex_rows = "".join(
                f"<tr><td>{point_index + 1}</td>"
                f"<td>{float(point[0]):.3f}</td><td>{float(point[1]):.3f}</td></tr>"
                for point_index, point in enumerate(points)
                if isinstance(point, (list, tuple)) and len(point) >= 2
            )
            segment_checks = [
                ("contorno com 3+ vértices", metrics["unique_vertex_count"] >= 3),
                ("área geométrica positiva", metrics["area"] > 0),
                ("largura declarada", bool(segment.get("width"))),
            ]
            segment_check_rows = "".join(
                f'<tr><td style="color:{"#4fc3a1" if ok else "#e17055"}">'
                f'{"OK" if ok else "ATENÇÃO"}</td>'
                f"<td>{html.escape(check_label)}</td></tr>"
                for check_label, ok in segment_checks
            )
            # Textarea de anotação por segmento
            _local_atkey = (
                f"aten_fv_local_{dialog._obra}_{dialog._pavimento}_{beam}_{label}"
                .replace(" ", "_")
            )
            _local_atbox = (
                '<div style="margin-top:10px">'
                '<div class="ficha-col-title" style="color:#f0b840">'
                f'✏️ Anotação / Atenção — segmento {html.escape(label)}</div>'
                f'<textarea data-atkey="{html.escape(_local_atkey)}" '
                f'onblur="saveAtenTA(this)" '
                f'placeholder="Observações do revisor para segmento {html.escape(label)}..." '
                'style="width:100%;min-height:60px;background:#1a1a0a;color:#f0b840;'
                'border:1px solid #554400;border-radius:3px;padding:6px;'
                'font-family:monospace;font-size:10px;box-sizing:border-box;'
                'resize:vertical;margin-top:4px"></textarea>'
                '</div>'
            )
            # Card local: viewer HI-FI (não usa evidence-card img-geo legado)
            n1_sections.append(
                '<div class="sec"><div class="sec-title">'
                f"N1 / SA — {html.escape(beam)} · segmento {html.escape(label)}"
                '</div><div class="sec-body">'
                '<div class="evidence-card">'
                '<div class="evidence-title"><b>N1 / SA local</b>'
                f'<span style="color:{"#4fc3a1" if _local_svg else "#e17055"}">'
                f'{"disponível" if _local_svg else "ausente"}</span></div>'
                f'<div style="color:#777;font-size:9px;margin-bottom:5px">'
                f"{html.escape(local_subtitle)}</div>"
                f"{_local_viewer}</div>"
                '<div class="fichas-grid" style="margin-top:10px">'
                '<div><div class="ficha-col-title">Ficha N1/SA do segmento</div>'
                '<div class="ficha-cell"><table>'
                f"{identity_rows}</table></div></div>"
                '<div><div class="ficha-col-title">Vértices brutos do contorno</div>'
                '<div class="ficha-cell vertex-table"><table>'
                '<tr><th>#</th><th>X</th><th>Y</th></tr>'
                f"{vertex_rows}</table></div></div>"
                '<div><div class="ficha-col-title">Quality gates N1</div>'
                f'<div class="ficha-cell"><table>{segment_check_rows}</table></div></div>'
                f'</div>{_local_atbox}</div></div>'
            )
            n1_pipeline.append(
                _pipeline_stage(
                    dialog,
                    "N1 / SA",
                    bool(_local_svg),
                    f"Segmentação e vínculo SA do segmento {label}.",
                    beam,
                    label,
                )
            )

        # ── Contextual unificado (única vista de todos os segmentos) ─────────
        _ctx_section = ""
        if _ctx_svg or _hifi_segments:
            # Duas caixas no contextual: humana (revisor) + agêntica (loop QA)
            _base_key = (
                f"{dialog._obra}_{dialog._pavimento}_{beam}".replace(" ", "_")
            )
            _ctx_atkey_human = f"aten_fv_ctx_human_{_base_key}"
            _ctx_atkey_agent = f"aten_fv_ctx_agent_{_base_key}"
            # legado: chave antiga sem sufixo (migrada como humana no load)
            _ctx_atkey_legacy = f"aten_fv_ctx_{_base_key}"
            _ctx_id = f"fvctx_{beam.replace(' ', '_')}"
            # N3 no mesmo viewer (aba ao lado de C3) — materializado no pack
            # pelo gerador SA (desktop e headless). Sem hardcode de viga.
            _n3_src = f"n3/{_safe_slug(beam)}_n3.svg"
            _n3_out = os.path.join(n3_dir, f"{_safe_slug(beam)}_n3.svg")
            _table_rows = chain_linear_segment_apoios(
                [_collect_seg_table_row(m, dialog) for m in _seg_meta]
            )
            _n3_robot = render_n3_svg_from_seg_rows(
                _table_rows, beam, out_svg=_n3_out
            ) or materialize_fv_n3_svg(
                n3_path,
                _n3_out,
                inline_svg=n3_b64 or "",
            )
            _n3_inline = overlay_n3_segment_tags(_n3_robot, _table_rows) or _n3_robot
            _seg_labels = [str(m.get("label") or i + 1) for i, m in enumerate(_seg_meta)]
            _ctx_viewer = _wrap_panzoom_viewer(
                _ctx_id,
                _ctx_svg,
                mode="contextual",
                n3_svg=_n3_inline,
                n3_src=_n3_src,
                seg_labels=_seg_labels,
            )
            _ta_css_human = (
                "width:100%;min-height:90px;background:#1a1a0a;color:#f0b840;"
                "border:1px solid #554400;border-radius:8px;padding:10px;"
                "font-family:Segoe UI,system-ui,monospace;font-size:13px;"
                "box-sizing:border-box;resize:vertical;line-height:1.4"
            )
            _ta_css_agent = (
                "width:100%;min-height:110px;background:#0d1520;color:#7ec8ff;"
                "border:1px solid #2a5080;border-radius:8px;padding:10px;"
                "font-family:Segoe UI,system-ui,monospace;font-size:13px;"
                "box-sizing:border-box;resize:vertical;line-height:1.4"
            )
            try:
                from src.ui.widgets.fv_hifi_n1_render import (
                    agent_annotation_boxes_html as _agent_boxes,
                )
            except Exception:
                _agent_boxes = None  # type: ignore
            if _agent_boxes:
                _agent_html = _agent_boxes(
                    _ctx_atkey_agent, beam, ta_css=_ta_css_agent
                )
            else:
                _agent_html = (
                    '<div class="fv-agent-box" style="background:#0a121c;border:1px solid #2a5080;'
                    'border-radius:10px;padding:12px">'
                    '<div style="color:#7ec8ff;font-size:13px;font-weight:700;'
                    f'margin-bottom:6px">🤖 Anotação agêntica — QA / looping {html.escape(beam)}</div>'
                    f'<textarea data-atkey="{html.escape(_ctx_atkey_agent)}" '
                    f'data-atrole="agent" onblur="saveAtenTA(this)" '
                    f'style="{_ta_css_agent}"></textarea></div>'
                )
            try:
                from src.ui.widgets.fv_hifi_n1_render import (
                    human_annotation_box_html as _human_box,
                )
            except Exception:
                _human_box = None  # type: ignore
            if _human_box:
                _human_html = _human_box(
                    _ctx_atkey_human,
                    beam,
                    legacy_key=_ctx_atkey_legacy,
                    ta_css=_ta_css_human,
                )
            else:
                _human_html = (
                    f'<div style="background:#14120a;border:1px solid #554400;'
                    f'border-radius:10px;padding:12px">'
                    f'<textarea data-atkey="{html.escape(_ctx_atkey_human)}" '
                    f'data-atrole="human" style="{_ta_css_human}"></textarea></div>'
                )
            _ctx_atbox = (
                '<div class="fv-ctx-notes" style="margin-top:16px;display:grid;'
                'grid-template-columns:1fr 1fr;gap:12px">'
                f"{_human_html}"
                f"{_agent_html}"
                "</div>"
                '<style>@media(max-width:900px){.fv-ctx-notes{grid-template-columns:1fr!important}}</style>'
            )
            _n_segs = len(_seg_meta) or len(_hifi_segments)
            _ctx_section = (
                '<!--FVCTX_START-->'
                '<div class="sec" id="fvctx-main">'
                '<div class="sec-title">Viewer Unificado N1-N3 · '
                f'{_n_segs} segmento(s) '
                '<span style="color:#4fc3a1;font-size:10px">HI-FI</span></div>'
                '<div class="sec-body">'
                f'<div style="color:#8b95a8;font-size:12px;margin-bottom:10px">'
                f'Viga {html.escape(beam)} — interpretação N1 e desenho N3 no mesmo viewer. '
                'Abas SA/N3 têm subabas de segmento (Todos por padrão). '
                'Scroll=zoom · Arrastar=pan · Duplo-clique=reset.</div>'
                f"{_fv_beam_summary_html(beam, _n_segs)}"
                f"{_fv_seg_table_html(_table_rows)}"
                f"{_ctx_viewer}{_ctx_atbox}"
                '</div></div>'
                '<!--FVCTX_END-->'
            )

        shared_evidence = (
            _artifact_card(
                "N2", "Recorte humano contendo todos os segmentos da viga", n2_b64, n2_path
            )
            + _artifact_card(
                "N3 / NOVA",
                "Robô SA/N1 com todos os segmentos da viga no modo visual NOVA",
                n3_b64,
                n3_path,
            )
            + _artifact_card(
                "N4",
                "Robô com todos os segmentos gerado pela engenharia reversa N2",
                n4_b64,
                n4_path,
            )
        )
        evidence_section = (
            '<div class="sec"><div class="sec-title">'
            "Evidências agregadas da viga — N2 / N3 / N4</div>"
            f'<div class="sec-body"><div class="evidence-grid">{shared_evidence}</div>'
            "</div></div>"
        )

        pipeline = "".join(n1_pipeline + [
                _pipeline_stage(
                    dialog,
                    "N2 / STOG real",
                    bool(n2_b64),
                    "Recorte humano e ficha agregada da viga.",
                    beam,
                    "viga",
                ),
                _pipeline_stage(
                    dialog,
                    "N3 / Robô SA",
                    bool(n3_b64),
                    "Resultado agregado produzido pela rota SA/N1.",
                    beam,
                    "viga",
                ),
                _pipeline_stage(
                    dialog,
                    "N4 / Robô ER",
                    bool(n4_b64),
                    "Resultado agregado produzido pela rota N2.",
                    beam,
                    "viga",
                ),
            ])
        pipeline_section = (
            '<div class="sec"><div class="sec-title">'
            "Diagnóstico da cadeia por viga</div>"
            f'<div class="sec-body"><div class="pipeline-grid">{pipeline}</div>'
            "</div></div>"
        )

        n2_ficha = dialog._n2_ficha_html("FV", beam)
        n3_ficha = dialog._n3_ficha_html_beam("FV", beam)
        ficha_section = (
            '<div class="sec"><div class="sec-title">'
            "Fichas agregadas da viga</div>"
            '<div class="sec-body"><div class="fichas-grid">'
            '<div><div class="ficha-col-title">N2 / Motor Reverso</div>'
            f'<div class="ficha-cell">{n2_ficha}</div></div>'
            '<div><div class="ficha-col-title">N3 / JSON Fase-4</div>'
            f'<div class="ficha-cell">{n3_ficha}</div></div>'
            "</div></div></div>"
        )

        checks = [
            ("N1 disponível para todos os segmentos", n1_available == len(beam_rows)),
            ("recorte N2 localizado", bool(n2_b64)),
            ("artefato N3 localizado", bool(n3_b64)),
            ("artefato N4 localizado", bool(n4_b64)),
        ]
        check_rows = "".join(
            f'<tr><td style="color:{"#4fc3a1" if ok else "#e17055"}">'
            f'{"OK" if ok else "ATENÇÃO"}</td>'
            f"<td>{html.escape(check_label)}</td></tr>"
            for check_label, ok in checks
        )
        checks_section = (
            '<div class="sec"><div class="sec-title">Quality gates da viga FV</div>'
            f'<div class="sec-body"><table>{check_rows}</table></div></div>'
        )

        main = (
            nav_bar
            + _ctx_section
            + "".join(n1_sections)
            + evidence_section
            + ficha_section
            + pipeline_section
            + checks_section
            + '<pre id="_aten_export" style="display:none"></pre>'
            + _NOTES_SAVE_BAR
            + _error_marker_block(dialog, beam)
        )
        return (
            '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
            f'<meta name="fv-html-contract" content="{FV_HTML_CONTRACT_VERSION}">'
            f"<title>FV — {html.escape(beam)}</title>"
            f"<style>{page_css}</style>{_HIFI_CSS}{javascript}"
            f"{_COLLAPSE_JS}{_PANZOOM_JS}</head><body "
            f'data-fv-html-version="{FV_HTML_CONTRACT_VERSION}">'
            f"{_NOTES_STORE_TAG}"
            f"{sidebar}"
            '<div class="main-wrap"><div class="main-content">'
            f'<h2 class="fv-page-title">FV — {html.escape(beam)}'
            f' <span class="tag">{len(beam_rows)} segmento(s)</span>'
            f' <span class="tag" style="background:#1a2a3a;color:#90caf9">'
            f'HTML {FV_HTML_CONTRACT_VERSION}</span></h2>'
            f"{main}</div></div></body></html>"
        )

    for index, (beam, _, page_slug) in enumerate(entries):
        page_path = os.path.join(section_dir, f"{page_slug}.html")
        with open(page_path, "w", encoding="utf-8") as file:
            file.write(page(index))
        print(
            f"[HTML] fundos_viga {index + 1}/{len(entries)}: {beam}",
            flush=True,
        )

    index_rows = "".join(
        "<tr>"
        f"<td>{idx + 1}</td><td>{html.escape(beam)}</td>"
        f"<td>{len(beam_rows)}</td>"
        f'<td>{html.escape(", ".join(str((row.get("_segment") or {}).get("segment_label") or row.get("Segmento") or "—") for row in beam_rows))}</td>'
        f'<td>{html.escape(", ".join(dict.fromkeys(str(row.get("Status") or "—") for row in beam_rows)))}</td>'
        f'<td><a href="{html.escape(page_slug)}.html">abrir →</a></td>'
        "</tr>"
        for idx, (beam, beam_rows, page_slug) in enumerate(entries)
    )
    n3_count = len(
        [f for f in os.listdir(n3_dir) if f.lower().endswith(".svg")]
    ) if os.path.isdir(n3_dir) else 0
    index_document = (
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
        f'<meta name="fv-html-contract" content="{FV_HTML_CONTRACT_VERSION}">'
        f"<title>{html.escape(title)}</title><style>{page_css}</style></head>"
        f'<body style="margin:16px" data-fv-html-version="{FV_HTML_CONTRACT_VERSION}">'
        '<a class="nav-arrow" href="../index.html">'
        "← índice geral</a>"
        f"<h1>Fundos de Viga — HI-FI HTML {FV_HTML_CONTRACT_VERSION}</h1>"
        f'<p class="meta">{len(entries)} vigas · {len(rows)} segmentos · '
        f"N3 materializados: {n3_count} · viewer SA|C1|C2|C3|N3 · "
        "envelope quadrado · zoom 2×</p>"
        "<table><tr><th>#</th><th>Viga</th><th>Qtd. segmentos</th>"
        "<th>Segmentos</th><th>Status</th><th></th></tr>"
        f"{index_rows}</table></body></html>"
    )
    with open(os.path.join(section_dir, "index.html"), "w", encoding="utf-8") as file:
        file.write(index_document)

    _copy_latest_guide(output_dir, section_dir)
    return ("fundos_viga/index.html", title, len(entries))


def _sa_fields_from_html_db(html_text: str, beam: str) -> dict:
    """Lê fields do payload SA persistido (mesma viga) para nível/dimensão."""
    uid_m = re.search(
        rf"fundo\|([A-Za-z0-9_.:-]+)\|",
        html_text,
    )
    beam_id = uid_m.group(1) if uid_m else ""
    project_id = beam_id.rsplit("_b_", 1)[0] if "_b_" in beam_id else ""
    db_candidates = [
        Path(r"D:\Agente-cad-PYSIDE\project_data.vision"),
        Path(__file__).resolve().parents[3] / "project_data.vision",
        Path.cwd() / "project_data.vision",
    ]
    for db in db_candidates:
        if not db.is_file():
            continue
        try:
            import sqlite3

            con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
            row = None
            if beam_id:
                row = con.execute(
                    "SELECT data_json FROM beams WHERE id=? LIMIT 1",
                    (beam_id,),
                ).fetchone()
            if not row and project_id:
                row = con.execute(
                    "SELECT data_json FROM beams WHERE project_id=? AND name=? LIMIT 1",
                    (project_id, beam),
                ).fetchone()
            con.close()
            if not row:
                continue
            data = json.loads(row[0] or "{}")
            fields = data.get("fields") if isinstance(data, dict) else {}
            if isinstance(fields, dict) and fields:
                return fields
        except Exception:
            continue
    return {}


def _extract_seg_rows_from_fv_html(
    html_text: str, beam: str, *, sa_fields: dict | None = None
) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    pat = re.compile(
        rf'<div class="sec-title">N1 / SA — {re.escape(beam)} · segmento ([^<]+)</div>'
    )
    for match in pat.finditer(html_text):
        label = match.group(1).strip()
        if label in seen:
            continue
        seen.add(label)
        chunk = html_text[match.end() : match.end() + 50000]

        def _cell(name: str) -> str:
            found = re.search(
                rf"{re.escape(name)}</td><td[^>]*>([^<]*)</td>",
                chunk,
            )
            return (found.group(1).strip() if found else "") or "—"

        apo = ""
        apo_m = re.search(r"apoios\s+([^·<]+)\s·", chunk)
        if apo_m:
            apo = apo_m.group(1).strip()
        ini, fim = "—", "—"
        if "→" in apo:
            left, right = apo.split("→", 1)
            ini, fim = left.strip() or "—", right.strip() or "—"

        def _quoted_fields(prefixes: tuple[str, ...]) -> str:
            parts: list[str] = []
            for key_m in re.finditer(
                r"&quot;([^&]+)&quot;\s*:\s*&quot;([^&]*)&quot;",
                chunk,
            ):
                key, val = key_m.group(1), key_m.group(2)
                low = key.lower()
                if not any(p in low for p in prefixes):
                    continue
                if val in ("N/A", "n/a", "", "-", "—"):
                    continue
                short = key.replace("chanfro_", "").replace("abertura_", "")
                parts.append(f"{short} {val}")
            # unique preserve order
            uniq: list[str] = []
            for item in parts:
                if item not in uniq:
                    uniq.append(item)
            return ", ".join(uniq) if uniq else "—"

        dim_text = str(
            (sa_fields or {}).get(f"viga_fundo_seg_{label}_dim") or ""
        )
        if not dim_text:
            dim_m = re.search(
                rf"(?:&quot;|\")viga_fundo_seg_{re.escape(label)}_dim(?:&quot;|\")\s*:\s*(?:&quot;|\")([^&\"]+)(?:&quot;|\")",
                html_text,
            )
            dim_text = dim_m.group(1) if dim_m else ""
        largura_dim, altura_dim = _parse_dim_wh(dim_text)
        alt_m = re.search(
            r"(?:&quot;|\")altura_total(?:&quot;|\")\s*:\s*([\d.]+)",
            chunk,
        )
        if not altura_dim and alt_m:
            altura_dim = f"{float(alt_m.group(1)):g}"
        largura = largura_dim or _cell("Largura declarada")
        nivel = _niveis_from_beam_fields(sa_fields)

        def _quoted_one(key: str) -> str:
            found = re.search(
                rf"(?:&quot;|\"){re.escape(key)}(?:&quot;|\")\s*:\s*"
                r"(?:&quot;|\")([^&\"]+)(?:&quot;|\")",
                chunk,
            )
            return found.group(1) if found else ""

        extra = {
            key: _quoted_one(key)
            for key, _label in _CHANFER_KEYS + _OPENING_KEYS
        }
        rows.append(
            {
                "label": label,
                "comprimento": _cell("Comprimento declarado"),
                "largura": largura,
                "altura": altura_dim,
                **extra,
                "nivel": nivel or "—",
                "ponto_inicial": ini,
                "ponto_final": fim,
                "chanfros": _quoted_fields(("chanfro",)),
                "aberturas": _quoted_fields(("abertura", "furo")),
            }
        )
    return chain_linear_segment_apoios(rows)


def _n3_svg_from_viewer(viewer_html: str) -> str:
    start = viewer_html.find('class="fv-layer fv-layer-n3')
    if start < 0:
        return ""
    gt = viewer_html.find(">", start)
    svg_i = viewer_html.find("<svg", gt)
    svg_end = viewer_html.find("</svg>", gt)
    if svg_i < 0 or svg_end < svg_i:
        return ""
    return viewer_html[svg_i : svg_end + len("</svg>")]


def _replace_n3_layer_inner(viewer_html: str, inner: str) -> str:
    """Swap the N3 layer contents (svg or placeholder) for ``inner``."""
    if not inner or 'class="fv-layer fv-layer-n3' not in viewer_html:
        return viewer_html
    start = viewer_html.find('class="fv-layer fv-layer-n3')
    tag_start = viewer_html.rfind("<div", 0, start)
    gt = viewer_html.find(">", start)
    if tag_start < 0 or gt < 0:
        return viewer_html
    svg_end = viewer_html.find("</svg>", gt)
    if svg_end > gt:
        close = viewer_html.find("</div>", svg_end)
    else:
        close = viewer_html.find("</div>", gt)
    if close < 0:
        return viewer_html
    return viewer_html[: gt + 1] + inner + viewer_html[close:]


def _sanitize_n3_layer_html(n3_inner: str, n3_src: str) -> str:
    try:
        from src.ui.widgets.fv_hifi_n1_render import repair_n3_inline_svg
    except Exception:
        from src.ui.widgets.fv_hifi_n1_render import sanitize_inline_svg as repair_n3_inline_svg  # type: ignore
    src_path = n3_src
    inner = n3_inner or ""
    # Never keep the discarded schematic; prefer the robot SVG on disk.
    if 'data-n3-composed="1"' in inner:
        inner = ""
        if src_path and os.path.isfile(src_path):
            try:
                inner = Path(src_path).read_text(encoding="utf-8")
            except Exception:
                inner = ""
    cleaned = repair_n3_inline_svg(inner)
    if "<svg" not in cleaned and src_path and os.path.isfile(src_path):
        try:
            cleaned = repair_n3_inline_svg(
                Path(src_path).read_text(encoding="utf-8")
            )
        except Exception:
            cleaned = ""
    if (
        "<svg" in cleaned
        and 'data-n3-composed="1"' not in cleaned
        and 'class="fv-n3-seg"' not in cleaned
        and src_path
        and os.path.isfile(src_path)
    ):
        try:
            Path(src_path).write_text(cleaned, encoding="utf-8")
        except Exception:
            pass
    if "<svg" not in cleaned:
        cleaned = (
            '<div class="fv-agent-status">N3 (robô SA) ainda não materializado.<br>'
            f'<span style="font-size:11px;opacity:.75">Arquivo: {html.escape(n3_src)}</span></div>'
        )
    return cleaned


def _replace_tagged_div(html_text: str, start_needle: str, replacement: str) -> str:
    """Replace a <div ...>…</div> block by matching nested div depth."""
    start = html_text.find(start_needle)
    if start < 0:
        return html_text
    i = html_text.find(">", start)
    if i < 0:
        return html_text
    i += 1
    depth = 1
    n = len(html_text)
    while i < n and depth:
        nxt_open = html_text.find("<div", i)
        nxt_close = html_text.find("</div>", i)
        if nxt_close < 0:
            return html_text
        if nxt_open >= 0 and nxt_open < nxt_close:
            depth += 1
            i = nxt_open + 4
        else:
            depth -= 1
            i = nxt_close + 6
    return html_text[:start] + replacement + html_text[i:]


def _upgrade_human_annotation_tabs(
    html_text: str,
    *,
    beam: str,
    human_box_html,
) -> str:
    if '<button type="button" class="fv-human-tab-btn" data-htab="points">' in html_text:
        return html_text
    m = re.search(
        r'<div class="fv-human-box"[^>]*>',
        html_text,
    )
    if not m:
        return html_text
    chunk_start = m.start()
    probe = html_text[chunk_start : chunk_start + 8000]
    key_m = re.search(r'data-atkey="(aten_fv_ctx_human_[^"]+)"', probe)
    leg_m = re.search(r'data-atlegacy="([^"]*)"', probe)
    key = key_m.group(1) if key_m else f"aten_fv_ctx_human_{beam}"
    legacy = leg_m.group(1) if leg_m else ""
    new_box = human_box_html(key, beam, legacy_key=legacy)
    return _replace_tagged_div(html_text, m.group(0), new_box)


def relayout_existing_fv_page(html_text: str, *, n3_dir: str = "") -> str:
    """Rewrite the unified viewer block of an already generated FV HTML page."""
    try:
        from src.ui.widgets.fv_hifi_n1_render import (
            HIFI_CSS,
            PANZOOM_VIEWBOX_JS,
            PT_BTN_HTML,
            SA_GHOST_BTN_HTML,
            human_annotation_box_html,
            stamp_sa_highlight_attrs,
        )
    except Exception:
        return html_text

    html_text = re.sub(
        r'<style id="fv-hifi-css">.*?</style>',
        lambda _m: HIFI_CSS,
        html_text,
        count=1,
        flags=re.S,
    )
    html_text = re.sub(
        r'<script id="fv-hifi-panzoom">.*?</script>',
        lambda _m: PANZOOM_VIEWBOX_JS,
        html_text,
        count=1,
        flags=re.S,
    )
    html_text = stamp_sa_highlight_attrs(html_text)
    html_text = re.sub(
        r'>Reset zoom</button>(?!<button type="button" class="fv-pt-btn")',
        ">Reset zoom</button>" + PT_BTN_HTML,
        html_text,
    )

    beam_m = re.search(r'<h2 class="fv-page-title">FV — ([^<]+)', html_text)
    beam = (beam_m.group(1).strip() if beam_m else "VIGA").split()[0]
    html_text = _upgrade_human_annotation_tabs(
        html_text, beam=beam, human_box_html=human_annotation_box_html
    )
    ctx_m = re.search(
        r"<!--FVCTX_START-->.*?<!--FVCTX_END-->",
        html_text,
        flags=re.S,
    )
    if not ctx_m:
        return html_text
    block = ctx_m.group(0)
    sa_fields = _sa_fields_from_html_db(html_text, beam)
    n3_src = f"n3/{_safe_slug(beam)}_n3.svg"
    disk_n3 = os.path.join(n3_dir, f"{_safe_slug(beam)}_n3.svg") if n3_dir else ""

    notes_start = block.find('<div class="fv-ctx-notes"')
    toggle_start = block.find('<div class="fv-layer-toggle"')
    if toggle_start < 0:
        return html_text
    notes_html = ""
    if notes_start >= 0:
        media_i = block.find("<style>@media", notes_start)
        style_end = block.find("</style>", media_i) if media_i >= 0 else -1
        if media_i >= 0 and style_end > media_i:
            notes_html = block[notes_start : style_end + len("</style>")].strip()
        else:
            end_marker = block.find("<!--FVCTX_END-->")
            notes_html = re.sub(
                r"(</div>\s*){1,2}$",
                "",
                block[notes_start:end_marker].strip(),
            )
        notes_html = notes_html.replace(
            'style="margin-top:14px;display:grid;',
            'style="margin-top:16px;display:grid;',
            1,
        )

    btn_i = block.find('onclick="resetZoom', toggle_start)
    if btn_i < 0:
        return html_text
    btn_end = block.find("</button>", btn_i)
    if btn_end < 0:
        return html_text
    pan_close = block.find("</div>", btn_end)
    if pan_close < 0:
        return html_text
    viewer_html = block[toggle_start : pan_close + 6]
    if "fv-sa-ghost-btn" not in viewer_html and "Reset zoom" in viewer_html:
        viewer_html = viewer_html.replace(
            ">Reset zoom</button>",
            ">Reset zoom</button>" + SA_GHOST_BTN_HTML,
            1,
        )
    if "fv-pt-btn" not in viewer_html and "Reset zoom" in viewer_html:
        viewer_html = viewer_html.replace(
            ">Reset zoom</button>",
            ">Reset zoom</button>" + PT_BTN_HTML,
            1,
        )

    n3_cls = block.find('class="fv-layer fv-layer-n3', toggle_start)
    if n3_cls >= 0:
        tag_start = block.rfind("<div", 0, n3_cls)
        tag_gt = block.find(">", n3_cls)
        svg_i = block.find("<svg", tag_gt)
        dt_i = block.find("<!DOCTYPE", tag_gt)
        inner_candidates = [i for i in (svg_i, dt_i) if i > tag_gt]
        inner_start = min(inner_candidates) if inner_candidates else tag_gt + 1
        svg_end = block.find("</svg>", tag_gt)
        if svg_end > inner_start:
            inner_end = svg_end + len("</svg>")
        else:
            inner_end = tag_gt + 1
        n3_open = block[tag_start : tag_gt + 1]
        n3_inner = block[tag_gt + 1 : inner_end]
        src_m = re.search(r'data-n3-src="([^"]+)"', n3_open)
        if src_m:
            n3_src = src_m.group(1)
        cleaned = _sanitize_n3_layer_html(n3_inner, disk_n3 or n3_src)
        if "data-n3-src=" not in n3_open:
            n3_open = n3_open[:-1] + f' data-n3-src="{html.escape(n3_src, quote=True)}">'
        # rewrite n3 inside viewer_html (same offsets relative to block)
        rel_tag = tag_start - toggle_start
        rel_end = inner_end - toggle_start
        viewer_html = viewer_html[:rel_tag] + n3_open + cleaned + viewer_html[rel_end:]

    toggle_end = viewer_html.find("</div>")
    toggle_html = viewer_html[: toggle_end + 6] if toggle_end >= 0 else ""
    if "fv-seg-subtabs" not in viewer_html and toggle_html:
        seg_rows = _extract_seg_rows_from_fv_html(
            html_text, beam, sa_fields=sa_fields
        )
        labels = [r["label"] for r in seg_rows]
        n_segs = len(labels)
        sub_btns = [
            '<button type="button" class="fv-seg-btn active" data-seg="todos">Todos</button>'
        ]
        for lab in labels:
            safe = html.escape(lab, quote=True)
            sub_btns.append(
                f'<button type="button" class="fv-seg-btn" data-seg="{safe}">'
                f"{html.escape(lab)}</button>"
            )
        subtabs = (
            f'<div class="fv-seg-subtabs" data-for-layers="sa,n3" '
            f'data-seg-count="{n_segs}">{"".join(sub_btns)}</div>'
        )
        viewer_html = viewer_html.replace(toggle_html, toggle_html + subtabs, 1)
    else:
        seg_rows = _extract_seg_rows_from_fv_html(
            html_text, beam, sa_fields=sa_fields
        )
        n_segs = len(seg_rows)

    generated = render_n3_svg_from_seg_rows(
        seg_rows, beam, out_svg=disk_n3 or ""
    )
    n3_src_svg = generated or _n3_svg_from_viewer(viewer_html)
    n3_tagged = overlay_n3_segment_tags(n3_src_svg, seg_rows) or n3_src_svg
    if n3_tagged and "<svg" in n3_tagged:
        viewer_html = _replace_n3_layer_inner(viewer_html, n3_tagged)

    new_block = (
        "<!--FVCTX_START-->"
        '<div class="sec" id="fvctx-main">'
        '<div class="sec-title">Viewer Unificado N1-N3 · '
        f"{n_segs} segmento(s) "
        '<span style="color:#4fc3a1;font-size:10px">HI-FI</span></div>'
        '<div class="sec-body">'
        f'<div style="color:#8b95a8;font-size:12px;margin-bottom:10px">'
        f"Viga {html.escape(beam)} — interpretação N1 e desenho N3 no mesmo viewer. "
        "Abas SA/N3 têm subabas de segmento (Todos por padrão). "
        "Scroll=zoom · Arrastar=pan · Duplo-clique=reset.</div>"
        f"{_fv_beam_summary_html(beam, n_segs)}"
        f"{_fv_seg_table_html(seg_rows)}"
        f"{viewer_html}"
        f"{notes_html}"
        "</div></div>"
        "<!--FVCTX_END-->"
    )
    return html_text[: ctx_m.start()] + new_block + html_text[ctx_m.end() :]


def relayout_existing_fv_pack(section_dir: str) -> int:
    """Apply unified-viewer layout to every V*.html in a fundos_viga pack."""
    folder = Path(section_dir)
    n3_dir = str(folder / "n3")
    count = 0
    locked: list[Path] = []
    for page in sorted(folder.glob("V*.html")):
        if page.name.endswith(".relayout.html"):
            continue
        raw = page.read_text(encoding="utf-8")
        updated = relayout_existing_fv_page(raw, n3_dir=n3_dir)
        if updated == raw:
            continue
        tmp = page.with_name(page.name + ".tmp")
        tmp.write_text(updated, encoding="utf-8")
        try:
            tmp.replace(page)
            count += 1
            print(f"[HTML] relayout {page.name}", flush=True)
        except PermissionError:
            alt = page.with_name(page.stem + ".relayout.html")
            try:
                tmp.replace(alt)
            except Exception:
                pass
            locked.append(page)
            print(f"[HTML] locked {page.name} -> {alt.name}", flush=True)
    for page in locked:
        alt = page.with_name(page.stem + ".relayout.html")
        if not alt.is_file():
            continue
        try:
            alt.replace(page)
            count += 1
            print(f"[HTML] relayout retry {page.name}", flush=True)
        except PermissionError:
            print(f"[HTML] still locked {page.name}", flush=True)
    return count
