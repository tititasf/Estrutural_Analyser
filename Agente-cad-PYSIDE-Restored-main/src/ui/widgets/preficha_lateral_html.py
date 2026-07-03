"""Gerador granular das páginas HTML de laterais de viga (LV).

Mantém lado a lado as evidências das quatro etapas usadas para depurar LV:
N1/SA, N2 humano, N3 robô via SA e N4 robô via engenharia reversa. Uma
página por viga (não por lado nem por combinação lado×comportamento) — a
página tem uma seção "Lado A" e uma "Lado B", cada uma reunindo os
segmentos Para e Passa daquele lado.

Essa granularidade foi decidida com base em evidência real de arquivo (ver
`docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md` §5.2):
- a ficha N2 (`reverse_eng_fichas`, classe LV) é UMA por viga (`elemento_id`
  = nome bare, ex. "V301") e já contém `panels_A`/`panels_B`/`h_A`/`h_B`
  juntos — não faz sentido duplicar a comparação por lado;
- o recorte N2 (`reverse_eng_recortes`) também é UM por viga (nome bare);
- mas os DXFs N3/N4 SÃO por lado (`LV_preview_{VIGA}_A.dxf`,
  `LV_preview_{VIGA}_B.dxf`) — por isso as evidências N3/N4 (mas não N2)
  são específicas de cada seção de lado dentro da página.
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
        f"aten_lv_{stage}_{dialog._obra}_{dialog._pavimento}_{beam}_{label}"
        .replace(" ", "_")
    )
    return (
        '<div class="atencao-cell" contenteditable="true" '
        f'data-atkey="{html.escape(key)}" onblur="saveAten(this)" '
        f'title="Anotação {html.escape(stage)} — '
        f'{html.escape(beam)} · {html.escape(label)}"></div>'
    )


def _error_marker_block(dialog, beam: str) -> str:
    key = f"aten_erro_lv_{dialog._obra}_{dialog._pavimento}_{beam}".replace(" ", "_")
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
        '  var key=("aten_erro_lv_"+obra+"_"+pav+"_"+nome).replace(/ /g,"_");'
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


def _copy_latest_guide(output_dir: str, section_dir: str) -> None:
    """Copia somente documentação do pack anterior; nunca artefatos N3/N4.

    `interpretacao_laterais.html` é um guia com diagramas feitos à mão
    (ver aviso em ARETE-LOOP-PROCEDIMENTO-GERAL.md §5.2) — NUNCA regenerado
    por este módulo, só copiado adiante de um run anterior para o novo,
    exatamente como `_copy_latest_guide` de preficha_fundo_html.py faz para
    `interpretacao_fundos.html`.
    """
    base_dir = os.path.dirname(output_dir)
    previous_sections = sorted(
        (
            candidate
            for candidate in glob.glob(os.path.join(base_dir, "*", "laterais_viga"))
            if os.path.normcase(candidate) != os.path.normcase(section_dir)
        ),
        reverse=True,
    )
    for previous in previous_sections:
        guide = os.path.join(previous, "interpretacao_laterais.html")
        if not os.path.isfile(guide):
            continue
        shutil.copy2(guide, os.path.join(section_dir, "interpretacao_laterais.html"))
        images = os.path.join(previous, "imgs")
        if os.path.isdir(images):
            shutil.copytree(
                images, os.path.join(section_dir, "imgs"), dirs_exist_ok=True
            )
        return


def write_lateral_pages(
    dialog,
    title: str,
    rows_by_kind: dict[str, list[dict]],
    output_dir: str,
    page_css: str,
    javascript: str,
    photo_fn: Callable[[list], str],
    metrics_fn: Callable[[list], dict],
) -> tuple[str, str, int]:
    """Grava índice e uma ficha por viga, com seções Lado A / Lado B.

    `rows_by_kind` = {'lateral_a_para': [...], 'lateral_b_para': [...],
    'lateral_a_passa': [...], 'lateral_b_passa': [...]} — mesmas linhas já
    construídas pelo loop de `_export_html_snapshot` para os relatórios
    tabulares genéricos (mesmo `row['_segment']`/`row['_points']`/
    `row['Status']` usados por FV), só que aqui consolidadas por viga.
    """
    section_dir = os.path.join(output_dir, "laterais_viga")
    os.makedirs(section_dir, exist_ok=True)
    page_css += (
        ".evidence-grid{display:grid!important;grid-template-columns:1fr!important;"
        "gap:18px!important}"
        ".evidence-card{width:100%;box-sizing:border-box;padding:10px!important}"
        ".evidence-card img,.evidence-card svg{display:block;width:100%!important;"
        "height:auto!important;max-height:none!important;object-fit:contain;background:#111}"
        ".artifact-path{font-size:9px!important}"
        ".side-block{border:1px solid #223;border-radius:5px;margin:14px 0;padding:10px}"
        ".side-block h3{color:#f0b840;font-size:11px;margin:0 0 8px;"
        "text-transform:uppercase;letter-spacing:.04em}"
    )

    grouped_rows: dict[str, list[dict]] = {}
    for rows in rows_by_kind.values():
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
        beam_rows_sorted = sorted(
            beam_rows,
            key=lambda row: (
                str((row.get("_segment") or {}).get("side") or "A"),
                int((row.get("_segment") or {}).get("segment_index") or 1),
                int((row.get("_segment") or {}).get("occurrence") or 1),
            ),
        )
        entries.append((beam, beam_rows_sorted, page_slug))

    def _n1_card_for_segment(row: dict, beam: str) -> tuple[str, bool]:
        segment = row.get("_segment") or {}
        side = str(segment.get("side") or "A")
        behavior = str(segment.get("behavior") or "—")
        label = str(segment.get("segment_label") or row.get("Segmento") or "1")
        full_label = f"{label} ({behavior})"
        points = segment.get("points") or row.get("_points") or []
        metrics = metrics_fn(points)
        raw_beam = _beam_for(dialog, segment)
        fields = raw_beam.get("fields") or {}
        segment_index = int(segment.get("segment_index") or 1)
        field_prefix = f"viga_{side.lower()}_seg_{segment_index}"
        segment_fields = {
            key: value
            for key, value in fields.items()
            if str(key).startswith(field_prefix)
        }
        link_slots = (
            (raw_beam.get("links") or {}).get(segment.get("source_key") or "")
            or {}
        )
        details = segment.get("details") or {}
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
                fmt="svg",
            )
            if points
            else ""
        )
        sa_fmt = "svg"
        if not sa_b64:
            sa_b64 = photo_fn(points)
            sa_fmt = "png"

        identity_rows = (
            _table_sep("IDENTIDADE E DECISÃO SA")
            + _table_row("UID", segment.get("uid"))
            + _table_row("Viga", beam)
            + _table_row("Segmento", full_label)
            + _table_row(
                "Índice / ocorrência",
                f'{segment.get("segment_index", "—")} / '
                f'{segment.get("occurrence", "—")}',
            )
            + _table_row(
                "Classe / lado / comportamento",
                f'LV / {side} / {behavior}',
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
            + _table_row("Altura declarada", segment.get("height"))
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
        )
        if details:
            identity_rows += (
                _table_sep("VÍNCULOS DE CONTEXTO (apoio, laje, continuidade)")
                + _table_row("Apoio início", details.get("support_start"))
                + _table_row("Apoio fim", details.get("support_end"))
                + _table_row("Nível da viga", details.get("beam_level"))
                + _table_row("Lajes adjacentes", details.get("slabs"))
                + _table_row("Continuidade", details.get("continuity"))
                + _table_row("Ajuste de comprimento", details.get("adjustment"))
                + _table_row("Pilares passantes", details.get("passing_pillars"))
                + _table_row("Aberturas na viga", details.get("beam_openings"))
            )
        identity_rows += (
            _table_sep("RASTREABILIDADE DO VÍNCULO")
            + _table_row("beam_identity", segment.get("beam_identity"))
            + _table_row("source_key", segment.get("source_key"))
            + _table_row("source_slot", segment.get("source_slot"))
            + _table_row("tag", segment.get("tag"))
            + _table_row("ficha do link", segment.get("ficha") or {})
            + _table_row("campos SA do segmento", segment_fields)
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
            ("comprimento declarado", bool(segment.get("length"))),
        ]
        segment_check_rows = "".join(
            f'<tr><td style="color:{"#4fc3a1" if ok else "#e17055"}">'
            f'{"OK" if ok else "ATENÇÃO"}</td>'
            f"<td>{html.escape(check_label)}</td></tr>"
            for check_label, ok in segment_checks
        )
        card_html = (
            '<div class="sec"><div class="sec-title">'
            f"N1 / SA — {html.escape(beam)} · lado {html.escape(side)} · "
            f"segmento {html.escape(full_label)}</div><div class=\"sec-body\">"
            '<div class="evidence-grid">'
            + _artifact_card(
                "N1 / SA",
                f"DXF estrutural focado no segmento {full_label} (lado {side})",
                sa_b64,
                image_class="img-geo",
                fmt=sa_fmt,
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
        return card_html, bool(sa_b64)

    def page(index: int) -> str:
        beam, beam_rows, _ = entries[index]

        n2_path = dialog._find_n2_recorte_dxf("LV", beam)
        n2_b64 = dialog._render_ezdxf_b64(n2_path, 1900, 1240, fmt="svg") if n2_path else ""

        rows_by_side: dict[str, list[dict]] = {}
        for row in beam_rows:
            side = str((row.get("_segment") or {}).get("side") or "A").upper()
            rows_by_side.setdefault(side, []).append(row)

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
            f'<span class="tag">LV</span>'
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
            f'<aside class="sidebar"><h3>Laterais LV ({len(entries)} vigas)</h3>'
            '<a class="sb-back" href="../index.html">← índice geral</a>'
            '<a class="sb-back" href="index.html">← índice LV</a>'
            '<a class="sb-back" href="interpretacao_laterais.html">Guia</a>'
            f"<ul>{sidebar_items}</ul></aside>"
            + _sidebar_error_flags_script(dialog)
        )

        n1_available = 0
        n1_total = len(beam_rows)
        side_sections: list[str] = []
        side_checks: dict[str, dict] = {}
        for side in ("A", "B"):
            side_rows = rows_by_side.get(side) or []
            n3_path = dialog._find_beam_dxf("LV", f"{beam}_{side}", n4=False)
            n4_path = dialog._find_beam_dxf("LV", f"{beam}_{side}", n4=True)
            n3_b64 = dialog._render_ezdxf_b64(n3_path, 1900, 1240, fmt="svg") if n3_path else ""
            n4_b64 = dialog._render_ezdxf_b64(n4_path, 1900, 1240, fmt="svg") if n4_path else ""

            n1_cards = []
            side_available = 0
            for row in side_rows:
                card_html, has_geo = _n1_card_for_segment(row, beam)
                n1_cards.append(card_html)
                side_available += bool(has_geo)
            n1_available += side_available

            side_evidence = (
                _artifact_card(
                    "N2", "Recorte humano da viga (compartilhado entre os lados)",
                    n2_b64, n2_path,
                )
                + _artifact_card(
                    f"N3 · Lado {side}", "Robô via N1 (Fase-4 → DXF), específico do lado",
                    n3_b64, n3_path,
                )
                + _artifact_card(
                    f"N4 · Lado {side}", "Robô via engenharia reversa N2, específico do lado",
                    n4_b64, n4_path,
                )
            )
            if side_rows or n3_b64 or n4_b64:
                side_sections.append(
                    f'<div class="side-block"><h3>Lado {side} — '
                    f'{len(side_rows)} segmento(s)</h3>'
                    + "".join(n1_cards)
                    + '<div class="sec"><div class="sec-title">'
                    f"Evidências do Lado {side} — N2 / N3 / N4</div>"
                    f'<div class="sec-body"><div class="evidence-grid">{side_evidence}</div>'
                    "</div></div></div>"
                )
            side_checks[side] = {
                "n1_ok": side_available == len(side_rows) if side_rows else True,
                "n3_ok": bool(n3_b64),
                "n4_ok": bool(n4_b64),
                "rows": len(side_rows),
            }

        pipeline = "".join(
            _pipeline_stage(
                dialog, f"N1 · Lado {side}",
                side_checks[side]["n1_ok"] and side_checks[side]["rows"] > 0,
                f"{side_checks[side]['rows']} segmento(s) no lado {side}.",
                beam, f"lado_{side.lower()}",
            )
            for side in ("A", "B")
        ) + _pipeline_stage(
            dialog, "N2 / STOG real", bool(n2_b64),
            "Recorte humano da viga (ambos os lados).", beam, "viga",
        ) + "".join(
            _pipeline_stage(
                dialog, f"N3/N4 · Lado {side}",
                side_checks[side]["n3_ok"] or side_checks[side]["n4_ok"],
                f"Artefatos gerados do lado {side}.", beam, f"lado_{side.lower()}",
            )
            for side in ("A", "B")
        )
        pipeline_section = (
            '<div class="sec"><div class="sec-title">'
            "Diagnóstico da cadeia por viga</div>"
            f'<div class="sec-body"><div class="pipeline-grid">{pipeline}</div>'
            "</div></div>"
        )

        n2_ficha = dialog._n2_ficha_html("LV", beam)
        n3_ficha = dialog._n3_ficha_html_beam("LV", beam)
        ficha_section = (
            '<div class="sec"><div class="sec-title">'
            "Fichas agregadas da viga</div>"
            '<div class="sec-body"><div class="fichas-grid">'
            '<div><div class="ficha-col-title">N2 / Motor Reverso (ambos os lados)</div>'
            f'<div class="ficha-cell">{n2_ficha}</div></div>'
            '<div><div class="ficha-col-title">N3 / JSON Fase-4 '
            '(limitação conhecida: mostra só 1 lado, A prioritário — '
            'ver `_n3_ficha_html_beam`)</div>'
            f'<div class="ficha-cell">{n3_ficha}</div></div>'
            "</div></div></div>"
        )

        checks = [
            ("N1 disponível para todos os segmentos", n1_available == n1_total),
            ("recorte N2 (viga) localizado", bool(n2_b64)),
            ("artefato N3 Lado A ou B localizado",
             side_checks["A"]["n3_ok"] or side_checks["B"]["n3_ok"]),
            ("artefato N4 Lado A ou B localizado",
             side_checks["A"]["n4_ok"] or side_checks["B"]["n4_ok"]),
        ]
        check_rows = "".join(
            f'<tr><td style="color:{"#4fc3a1" if ok else "#e17055"}">'
            f'{"OK" if ok else "ATENÇÃO"}</td>'
            f"<td>{html.escape(check_label)}</td></tr>"
            for check_label, ok in checks
        )
        checks_section = (
            '<div class="sec"><div class="sec-title">Quality gates da viga LV</div>'
            f'<div class="sec-body"><table>{check_rows}</table></div></div>'
        )

        main = (
            nav_bar
            + "".join(side_sections)
            + pipeline_section
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
            f"<title>LV — {html.escape(beam)}</title>"
            f"<style>{page_css}</style>{javascript}</head><body>{sidebar}"
            '<div class="main-wrap"><div class="main-content">'
            '<h2 style="font-size:13px;color:#7eb8f7;margin:0 0 8px">'
            f"LV — {html.escape(beam)} · {len(beam_rows)} segmento(s)</h2>"
            f"{main}</div></div></body></html>"
        )

    for index, (beam, _, page_slug) in enumerate(entries):
        page_path = os.path.join(section_dir, f"{page_slug}.html")
        with open(page_path, "w", encoding="utf-8") as file:
            file.write(page(index))
        print(
            f"[HTML] laterais_viga {index + 1}/{len(entries)}: {beam}",
            flush=True,
        )

    index_rows = "".join(
        "<tr>"
        f"<td>{idx + 1}</td><td>{html.escape(beam)}</td>"
        f"<td>{len(beam_rows)}</td>"
        f'<td>{html.escape(", ".join(dict.fromkeys(str((row.get("_segment") or {}).get("side") or "—") for row in beam_rows)))}</td>'
        f'<td>{html.escape(", ".join(dict.fromkeys(str(row.get("Status") or "—") for row in beam_rows)))}</td>'
        f'<td><a href="{html.escape(page_slug)}.html">abrir →</a></td>'
        "</tr>"
        for idx, (beam, beam_rows, page_slug) in enumerate(entries)
    )
    total_segments = sum(len(rows) for rows in rows_by_kind.values())
    index_document = (
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
        f"<title>{html.escape(title)}</title><style>{page_css}</style></head>"
        '<body style="margin:16px"><a class="nav-arrow" href="../index.html">'
        "← índice geral</a><h1>Laterais de Viga — Fichas Granulares</h1>"
        f'<p class="meta">{len(entries)} vigas · {total_segments} segmentos · '
        "evidências N1/N2/N3/N4</p>"
        "<table><tr><th>#</th><th>Viga</th><th>Qtd. segmentos</th>"
        "<th>Lados</th><th>Status</th><th></th></tr>"
        f"{index_rows}</table></body></html>"
    )
    with open(os.path.join(section_dir, "index.html"), "w", encoding="utf-8") as file:
        file.write(index_document)

    _copy_latest_guide(output_dir, section_dir)
    return ("laterais_viga/index.html", title, len(entries))
