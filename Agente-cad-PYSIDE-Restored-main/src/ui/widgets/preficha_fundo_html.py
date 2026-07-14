"""Gerador granular das páginas HTML de fundos de viga.

Mantém lado a lado as evidências das quatro etapas usadas para depurar FV:
N1/SA, N2 humano, N3 robô via SA e N4 robô via engenharia reversa.
"""

from __future__ import annotations

import glob
import html
import json
import os
import re
import shutil
from typing import Callable

from src.ui.widgets.svg_embed_utils import embed_visual as _embed_visual


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
    """Grava índice e uma ficha por viga, com N1 granular por segmento."""
    section_dir = os.path.join(output_dir, "fundos_viga")
    os.makedirs(section_dir, exist_ok=True)
    # Evidências em coluna única: cada estágio ocupa toda a largura útil.
    # Os bitmaps são gerados em 2x abaixo, então o browser reduz a imagem
    # preservando detalhes em vez de ampliar um raster pequeno.
    page_css += (
        ".evidence-grid{display:grid!important;grid-template-columns:1fr!important;"
        "gap:18px!important}"
        ".evidence-card{width:100%;box-sizing:border-box;padding:10px!important}"
        ".evidence-card img,.evidence-card svg{display:block;width:100%!important;"
        "height:auto!important;max-height:none!important;object-fit:contain;background:#111}"
        ".artifact-path{font-size:9px!important}"
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
        nav_bar = (
            f'<div class="nav-bar">{previous_link}'
            f'<span class="nav-pos"><b>{html.escape(beam)}</b> '
            f"({index + 1}/{len(entries)} vigas)"
            f'<span class="tag">FV</span>'
            f'<span class="tag">{len(beam_rows)} segmento(s)</span>'
            f"</span>{next_link}</div>"
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
        for row in beam_rows:
            segment = row.get("_segment") or {}
            label = str(segment.get("segment_label") or row.get("Segmento") or "1")
            points = segment.get("points") or row.get("_points") or []
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
            if metrics["orientation"] == "horizontal":
                context_width, context_height = 2400, 600
            elif metrics["orientation"] == "vertical":
                context_width, context_height = 840, 2000
            else:
                context_width, context_height = 1800, 1360
            context_points = _fv_context_points(raw_beam)
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
                f"Segmento {label} · {source_key} · dimensão {segment.get('width') or '—'}"
                f" · apoios locais {support_start or '—'} → {support_end or '—'}"
            )
            sa_local_b64 = (
                dialog._render_pilar_dxf_context_b64(
                    points,
                    width=context_width,
                    height=context_height,
                    focus_mode="segment",
                    focus_label=f"FV {source_key} · local",
                    fmt="svg",
                    context_view="near",
                )
                if points
                else ""
            )
            sa_context_b64 = (
                dialog._render_pilar_dxf_context_b64(
                    points,
                    width=context_width,
                    height=context_height,
                    focus_mode="segment",
                    focus_label=f"FV {source_key} · contexto",
                    fmt="svg",
                    context_view="far",
                    context_points=context_points,
                )
                if points
                else ""
            )
            # A ficha FV tem exatamente duas provas N1: local e contextual.
            # Não há fallback PNG nem terceiro zoom que poderia mascarar a
            # proveniência vetorial exigida pelo gate.
            n1_available += bool(sa_local_b64 and sa_context_b64)

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
            n1_sections.append(
                '<div class="sec"><div class="sec-title">'
                f"N1 / SA — {html.escape(beam)} · segmento {html.escape(label)}"
                '</div><div class="sec-body">'
                '<div class="evidence-grid">'
                + _artifact_card(
                    "N1 / SA local",
                    local_subtitle,
                    sa_local_b64,
                    image_class="img-geo",
                    fmt="svg",
                )
                + _artifact_card(
                    "N1 / SA contextual",
                    f"Mesma origem DXF; continuidade da viga sem criar apoios. "
                    f"Destaque: {source_key}.",
                    sa_context_b64,
                    image_class="img-geo",
                    fmt="svg",
                )
                + '</div><div class="fichas-grid" style="margin-top:10px">'
                '<div><div class="ficha-col-title">Ficha N1/SA do segmento</div>'
                '<div class="ficha-cell"><table>'
                f"{identity_rows}</table></div></div>"
                '<div><div class="ficha-col-title">Vértices brutos do contorno</div>'
                '<div class="ficha-cell vertex-table"><table>'
                '<tr><th>#</th><th>X</th><th>Y</th></tr>'
                f"{vertex_rows}</table></div></div>"
                '<div><div class="ficha-col-title">Quality gates N1</div>'
                f'<div class="ficha-cell"><table>{segment_check_rows}</table></div></div>'
                '</div></div></div>'
            )
            n1_pipeline.append(
                _pipeline_stage(
                    dialog,
                    "N1 / SA",
                    bool(sa_local_b64 and sa_context_b64),
                    f"Segmentação e vínculo SA do segmento {label}.",
                    beam,
                    label,
                )
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
            + "".join(n1_sections)
            + pipeline_section
            + evidence_section
            + ficha_section
            + checks_section
            + '<pre id="_aten_export" style="display:none"></pre>'
            + '<button onclick="exportAnotacoes()" style="margin:12px 0;'
            'background:#2a2a00;color:#f0b840;border:1px solid #554400;'
            'padding:3px 10px;cursor:pointer;font-size:10px">'
            "Exportar Anotações</button>"
            + _error_marker_block(dialog, beam)
        )
        return (
            '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
            f"<title>FV — {html.escape(beam)}</title>"
            f"<style>{page_css}</style>{javascript}</head><body>{sidebar}"
            '<div class="main-wrap"><div class="main-content">'
            '<h2 style="font-size:13px;color:#7eb8f7;margin:0 0 8px">'
            f"FV — {html.escape(beam)} · {len(beam_rows)} segmento(s)</h2>"
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
    index_document = (
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
        f"<title>{html.escape(title)}</title><style>{page_css}</style></head>"
        '<body style="margin:16px"><a class="nav-arrow" href="../index.html">'
        "← índice geral</a><h1>Fundos de Viga — Fichas Granulares</h1>"
        f'<p class="meta">{len(entries)} vigas · {len(rows)} segmentos · '
        "evidências N1/N2/N3/N4</p>"
        "<table><tr><th>#</th><th>Viga</th><th>Qtd. segmentos</th>"
        "<th>Segmentos</th><th>Status</th><th></th></tr>"
        f"{index_rows}</table></body></html>"
    )
    with open(os.path.join(section_dir, "index.html"), "w", encoding="utf-8") as file:
        file.write(index_document)

    _copy_latest_guide(output_dir, section_dir)
    return ("fundos_viga/index.html", title, len(entries))
