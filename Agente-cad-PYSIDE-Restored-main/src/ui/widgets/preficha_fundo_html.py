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


def _artifact_card(
    stage: str,
    subtitle: str,
    b64_value: str,
    path: str = "",
    image_class: str = "img-n4",
) -> str:
    if b64_value:
        image = (
            f'<img class="{image_class}" src="data:image/png;base64,{b64_value}" '
            f'alt="{html.escape(stage)}">'
        )
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
    """Grava índice e uma ficha granular por segmento FV."""
    section_dir = os.path.join(output_dir, "fundos_viga")
    os.makedirs(section_dir, exist_ok=True)
    # Evidências em coluna única: cada estágio ocupa toda a largura útil.
    # Os bitmaps são gerados em 2x abaixo, então o browser reduz a imagem
    # preservando detalhes em vez de ampliar um raster pequeno.
    page_css += (
        ".evidence-grid{display:grid!important;grid-template-columns:1fr!important;"
        "gap:18px!important}"
        ".evidence-card{width:100%;box-sizing:border-box;padding:10px!important}"
        ".evidence-card img{display:block;width:100%!important;height:auto!important;"
        "max-height:none!important;object-fit:contain;background:#111}"
        ".artifact-path{font-size:9px!important}"
    )

    entries: list[tuple[str, str, dict, str]] = []
    used: set[str] = set()
    for row in rows:
        segment = row.get("_segment") or {}
        beam = str(segment.get("beam_name") or row.get("_beam") or "VIGA")
        label = str(segment.get("segment_label") or row.get("Segmento") or "1")
        base_slug = _safe_slug(f"{beam}_{label}")
        page_slug = base_slug
        suffix = 2
        while page_slug in used:
            page_slug = f"{base_slug}_{suffix}"
            suffix += 1
        used.add(page_slug)
        entries.append((beam, label, row, page_slug))

    def page(index: int) -> str:
        beam, label, row, _ = entries[index]
        segment = row.get("_segment") or {}
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

        n3_path = dialog._find_beam_dxf("FV", beam, n4=False)
        n4_path = dialog._find_beam_dxf("FV", beam, n4=True)
        n2_path = dialog._find_n2_recorte_dxf("FV", beam)
        if metrics["orientation"] == "horizontal":
            context_width, context_height = 2400, 600
        elif metrics["orientation"] == "vertical":
            context_width, context_height = 840, 2000
        else:
            context_width, context_height = 1800, 1360
        sa_b64 = (
            dialog._render_pilar_dxf_context_b64(
                points,
                width=context_width,
                height=context_height,
                focus_mode="segment",
            )
            if points
            else ""
        )
        if not sa_b64:
            sa_b64 = photo_fn(points)
        n3_b64 = dialog._render_ezdxf_b64(n3_path, 1900, 1240) if n3_path else ""
        n4_b64 = dialog._render_ezdxf_b64(n4_path, 1900, 1240) if n4_path else ""
        n2_b64 = dialog._render_ezdxf_b64(n2_path, 1900, 1240) if n2_path else ""

        previous = f"{entries[index - 1][3]}.html" if index else ""
        following = (
            f"{entries[index + 1][3]}.html"
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
            f'<span class="nav-pos"><b>{html.escape(beam)} · '
            f"seg.{html.escape(label)}</b> ({index + 1}/{len(entries)})"
            f'<span class="tag">FV</span>'
            f'<span class="tag">{html.escape(str(row.get("Status") or "valid"))}</span>'
            f"</span>{next_link}</div>"
        )
        sidebar_items = "".join(
            f'<li{" class=\"active\"" if item_index == index else ""}>'
            f'<a href="{html.escape(item_slug)}.html">'
            f"{html.escape(item_beam)} · {html.escape(item_label)}</a></li>"
            for item_index, (item_beam, item_label, _, item_slug)
            in enumerate(entries)
        )
        sidebar = (
            f'<aside class="sidebar"><h3>Fundos FV ({len(entries)})</h3>'
            '<a class="sb-back" href="../index.html">← índice geral</a>'
            '<a class="sb-back" href="index.html">← índice FV</a>'
            '<a class="sb-back" href="interpretacao_fundos.html">Guia</a>'
            f"<ul>{sidebar_items}</ul></aside>"
        )

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
            + _table_row("campos SA do segmento", segment_fields)
            + _table_row("slots vinculados", link_slots)
        )
        identity_section = (
            '<div class="sec"><div class="sec-title">'
            "Ficha N1/SA — Segmento e rastreabilidade</div>"
            '<div class="sec-body"><table style="font-size:9px;background:#181818">'
            f"{identity_rows}</table></div></div>"
        )

        vertex_rows = "".join(
            f"<tr><td>{point_index + 1}</td>"
            f"<td>{float(point[0]):.3f}</td><td>{float(point[1]):.3f}</td></tr>"
            for point_index, point in enumerate(points)
            if isinstance(point, (list, tuple)) and len(point) >= 2
        )
        vertices_section = (
            '<div class="sec"><div class="sec-title">'
            "N1/SA — Vértices brutos do contorno</div>"
            '<div class="sec-body"><div class="vertex-table">'
            "<table><tr><th>#</th><th>X</th><th>Y</th></tr>"
            f"{vertex_rows}</table></div></div></div>"
        )

        evidence = (
            _artifact_card(
                "N1 / SA",
                "DXF estrutural com o segmento destacado",
                sa_b64,
                image_class="img-geo",
            )
            + _artifact_card(
                "N2", "Recorte humano usado pelo motor reverso", n2_b64, n2_path
            )
            + _artifact_card(
                "N3 / NOVA",
                "Robô SA/N1 renderizado explicitamente no modo visual NOVA",
                n3_b64,
                n3_path,
            )
            + _artifact_card(
                "N4",
                "Robô gerado a partir da engenharia reversa N2",
                n4_b64,
                n4_path,
            )
        )
        evidence_section = (
            '<div class="sec"><div class="sec-title">'
            "Evidências visuais por etapa</div>"
            f'<div class="sec-body"><div class="evidence-grid">{evidence}</div>'
            "</div></div>"
        )

        pipeline = "".join(
            [
                _pipeline_stage(
                    dialog,
                    "N1 / SA",
                    bool(sa_b64),
                    "Segmentação geométrica e vínculo autoritativo do SA.",
                    beam,
                    label,
                ),
                _pipeline_stage(
                    dialog,
                    "N2 / STOG real",
                    bool(n2_b64),
                    "Recorte humano e ficha do motor reverso.",
                    beam,
                    label,
                ),
                _pipeline_stage(
                    dialog,
                    "N3 / Robô SA",
                    bool(n3_b64),
                    "Resultado produzido pela rota SA/N1 no modo visual NOVA.",
                    beam,
                    label,
                ),
                _pipeline_stage(
                    dialog,
                    "N4 / Robô ER",
                    bool(n4_b64),
                    "Resultado produzido pela rota N2.",
                    beam,
                    label,
                ),
            ]
        )
        pipeline_section = (
            '<div class="sec"><div class="sec-title">'
            "Diagnóstico da cadeia SA → N3 / N2 → N4</div>"
            f'<div class="sec-body"><div class="pipeline-grid">{pipeline}</div>'
            "</div></div>"
        )

        n2_ficha = dialog._n2_ficha_html("FV", beam)
        n3_ficha = dialog._n3_ficha_html_beam("FV", beam)
        ficha_section = (
            '<div class="sec"><div class="sec-title">'
            "Fichas informacionais completas</div>"
            '<div class="sec-body"><div class="fichas-grid">'
            '<div><div class="ficha-col-title">N1 / SA</div>'
            f'<div class="ficha-cell"><table>{identity_rows}</table></div></div>'
            '<div><div class="ficha-col-title">N2 / Motor Reverso</div>'
            f'<div class="ficha-cell">{n2_ficha}</div></div>'
            '<div><div class="ficha-col-title">N3 / JSON Fase-4</div>'
            f'<div class="ficha-cell">{n3_ficha}</div></div>'
            "</div></div></div>"
        )

        checks = [
            ("contorno com 3+ vértices", metrics["unique_vertex_count"] >= 3),
            ("área geométrica positiva", metrics["area"] > 0),
            ("largura declarada", bool(segment.get("width"))),
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
            '<div class="sec"><div class="sec-title">Quality gates da ficha FV</div>'
            f'<div class="sec-body"><table>{check_rows}</table></div></div>'
        )

        main = (
            nav_bar
            + identity_section
            + vertices_section
            + pipeline_section
            + evidence_section
            + ficha_section
            + checks_section
            + '<pre id="_aten_export" style="display:none"></pre>'
            + '<button onclick="exportAnotacoes()" style="margin:12px 0;'
            'background:#2a2a00;color:#f0b840;border:1px solid #554400;'
            'padding:3px 10px;cursor:pointer;font-size:10px">'
            "Exportar Anotações</button>"
        )
        return (
            '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
            f"<title>FV — {html.escape(beam)} · {html.escape(label)}</title>"
            f"<style>{page_css}</style>{javascript}</head><body>{sidebar}"
            '<div class="main-wrap"><div class="main-content">'
            '<h2 style="font-size:13px;color:#7eb8f7;margin:0 0 8px">'
            f"FV — {html.escape(beam)} · segmento {html.escape(label)}</h2>"
            f"{main}</div></div></body></html>"
        )

    for index, (_, _, _, page_slug) in enumerate(entries):
        page_path = os.path.join(section_dir, f"{page_slug}.html")
        with open(page_path, "w", encoding="utf-8") as file:
            file.write(page(index))
        print(
            f"[HTML] fundos_viga {index + 1}/{len(entries)}: {page_slug}",
            flush=True,
        )

    index_rows = "".join(
        "<tr>"
        f"<td>{idx + 1}</td><td>{html.escape(beam)}</td>"
        f"<td>{html.escape(label)}</td>"
        f'<td>{html.escape(str(row.get("Comprimento") or "—"))}</td>'
        f'<td>{html.escape(str(row.get("Largura") or "—"))}</td>'
        f'<td>{html.escape(str(row.get("Status") or "—"))}</td>'
        f'<td><a href="{html.escape(page_slug)}.html">abrir →</a></td>'
        "</tr>"
        for idx, (beam, label, row, page_slug) in enumerate(entries)
    )
    index_document = (
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
        f"<title>{html.escape(title)}</title><style>{page_css}</style></head>"
        '<body style="margin:16px"><a class="nav-arrow" href="../index.html">'
        "← índice geral</a><h1>Fundos de Viga — Fichas Granulares</h1>"
        f'<p class="meta">{len(entries)} segmentos · evidências N1/N2/N3/N4</p>'
        "<table><tr><th>#</th><th>Viga</th><th>Segmento</th>"
        "<th>Comprimento</th><th>Largura</th><th>Status</th><th></th></tr>"
        f"{index_rows}</table></body></html>"
    )
    with open(os.path.join(section_dir, "index.html"), "w", encoding="utf-8") as file:
        file.write(index_document)

    _copy_latest_guide(output_dir, section_dir)
    return ("fundos_viga/index.html", title, len(rows))
