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
from pathlib import Path
from typing import Callable

from src.ui.widgets.svg_embed_utils import embed_visual as _embed_visual

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
    markup = re.sub(r"<\?xml[^>]*\?>", "", markup).strip()
    # remove width/height fixos para o pan/zoom preencher o layer
    markup = re.sub(r'\s(width|height)="[^"]*"', "", markup, count=4)
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
            _n3_inline = materialize_fv_n3_svg(
                n3_path,
                _n3_out,
                inline_svg=n3_b64 or "",
            )
            _ctx_viewer = _wrap_panzoom_viewer(
                _ctx_id,
                _ctx_svg,
                mode="contextual",
                n3_svg=_n3_inline,
                n3_src=_n3_src,
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
                '<div class="fv-ctx-notes" style="margin-top:14px;display:grid;'
                'grid-template-columns:1fr 1fr;gap:12px">'
                f"{_human_html}"
                f"{_agent_html}"
                "</div>"
                '<style>@media(max-width:900px){.fv-ctx-notes{grid-template-columns:1fr!important}}</style>'
            )
            _n_segs = len(_hifi_segments)
            _ctx_section = (
                '<!--FVCTX_START-->'
                '<div class="sec" id="fvctx-main">'
                '<div class="sec-title">📐 N1 / SA — Contextual unificado · '
                f'{_n_segs} segmento(s) '
                '<span style="color:#4fc3a1;font-size:10px">HI-FI</span></div>'
                '<div class="sec-body">'
                f'<div style="color:#777;font-size:9px;margin-bottom:8px">'
                f'Viga {html.escape(beam)} completa — todos os segmentos destacados. '
                'Scroll=zoom · Arrastar=pan · Duplo-clique=reset. '
                'O N1 local (abaixo) isola o segmento selecionado no mesmo estilo.</div>'
                f"{_ctx_atbox}{_ctx_viewer}"
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
