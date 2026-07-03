"""Gerador granular das páginas HTML de lajes (LJ).

Mantém lado a lado as evidências das quatro etapas usadas para depurar lajes:
N1/SA (contexto estrutural + geometria autoritativa), N2 humano (recorte STOG),
N3 robô via SA/Fase-4 e N4 robô via engenharia reversa (N2).
"""

from __future__ import annotations

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


def _attention(dialog, stage: str, name: str) -> str:
    key = (
        f"aten_lj_{stage}_{dialog._obra}_{dialog._pavimento}_{name}"
        .replace(" ", "_")
    )
    return (
        '<div class="atencao-cell" contenteditable="true" '
        f'data-atkey="{html.escape(key)}" onblur="saveAten(this)" '
        f'title="Anotação {html.escape(stage)} — {html.escape(name)}"></div>'
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
    name: str,
) -> str:
    state_class = "ok" if exists else "missing"
    state_text = "artefato disponível" if exists else "artefato ausente"
    return (
        f'<div class="pipeline-stage {state_class}">'
        f'<div class="stage-name">{html.escape(stage)}</div>'
        f'<div class="stage-state">{html.escape(state_text)}</div>'
        f'<div style="font-size:9px;color:#aaa;min-height:30px">'
        f"{html.escape(detail)}</div>"
        f"{_attention(dialog, stage, name)}</div>"
    )


def _error_marker_block(dialog, name: str) -> str:
    """Checkbox + nota de erro, salvos em localStorage (mesma origem file://
    compartilhada por todas as fichas), para triagem humana rápida: o usuário
    marca visualmente o que está errado e Claude só precisa revisar os itens
    marcados, lendo a nota escrita — sem reler todas as fichas do zero.

    Nota de nomenclatura (auditoria 03/07/2026): a chave usa o código `lj`
    (mesma abreviação de `_find_beam_dxf("LJ", ...)` e dos arquivos
    `LJ_preview_*.dxf`), enquanto o banco usa `classe='LAJ'`
    (`reverse_eng_fichas`) e os scripts de diagnóstico automático
    (`scripts/arete/diagnostico_laj_n1_n2.py`) usam `laj`. São duas
    convenções pré-existentes e independentes (DB/diagnóstico vs.
    checkbox/DXF) — NÃO unificar por rename: já existem marcações humanas
    reais em localStorage com a chave `aten_erro_lj_*` (ver
    `scripts/arete/relatorios/triagem_erros/Obra_TREINO_1_13_PAV_lajes.jsonl`)
    e `reverse_eng_fichas.classe='LAJ'` tem centenas de linhas em produção;
    renomear qualquer um dos dois arrisca perder/quebrar dado real sem
    ganho funcional (`qa_error_review.py` já casa por prefixo genérico
    `aten_erro_*`, então a duplicidade de código não quebra nada na prática).
    """
    key = f"aten_erro_lj_{dialog._obra}_{dialog._pavimento}_{name}".replace(" ", "_")
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
    """Lê localStorage (mesma origem file:// de todas as fichas) e marca
    com ⚠️, na lista da sidebar, os itens que já foram marcados como erro
    em qualquer página visitada nesta sessão de revisão."""
    obra_js = json.dumps(dialog._obra)
    pav_js = json.dumps(dialog._pavimento)
    return (
        "<script>(function(){"
        f"var obra={obra_js}, pav={pav_js};"
        'document.querySelectorAll(".sidebar li[data-laje]").forEach('
        "function(li){"
        '  var nome=li.getAttribute("data-laje");'
        '  var key=("aten_erro_lj_"+obra+"_"+pav+"_"+nome).replace(/ /g,"_");'
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


def _n3_ficha_html_laje(dialog, name: str) -> str:
    """Expõe todos os campos do JSON Fase-4 (JSON_Lajes) usado para gerar o N3."""
    if not dialog._obra:
        return '<span style="color:#555">sem obra</span>'
    json_path = os.path.join(
        "D:/Agente-cad-PYSIDE/DADOS-OBRAS", dialog._obra,
        "Fase-4_Sincronizacao", "JSON_Lajes", f"{name}.json",
    )
    if not os.path.exists(json_path):
        return '<span style="color:#555">sem JSON N3</span>'
    try:
        with open(json_path, encoding="utf-8") as file:
            data = json.load(file)
        rows = []
        for key, value in data.items():
            if value in (None, "", [], {}):
                continue
            rendered = json.dumps(value, ensure_ascii=False, indent=2)
            rows.append(
                "<tr>"
                f'<td style="color:#4fc3a1;padding:2px 5px;white-space:nowrap;'
                f'vertical-align:top">{html.escape(str(key))}</td>'
                f'<td style="padding:2px 5px;white-space:pre-wrap">'
                f"{html.escape(rendered)}</td></tr>"
            )
        return (
            '<table class="kv-table" style="font-size:9px;border-collapse:collapse">'
            f'{"".join(rows)}</table>'
        )
    except Exception as exc:
        return f'<span style="color:#555">erro: {html.escape(str(exc))}</span>'


def _copy_latest_guide(output_dir: str, section_dir: str) -> None:
    """Copia somente documentação do pack anterior; nunca artefatos N3/N4."""
    base_dir = os.path.dirname(output_dir)
    previous_sections = sorted(
        (
            candidate
            for candidate in __import__("glob").glob(
                os.path.join(base_dir, "*", "lajes")
            )
            if os.path.normcase(candidate) != os.path.normcase(section_dir)
        ),
        reverse=True,
    )
    for previous in previous_sections:
        guide = os.path.join(previous, "interpretacao_lajes.html")
        if not os.path.isfile(guide):
            continue
        shutil.copy2(guide, os.path.join(section_dir, "interpretacao_lajes.html"))
        images = os.path.join(previous, "imgs")
        if os.path.isdir(images):
            shutil.copytree(
                images, os.path.join(section_dir, "imgs"), dirs_exist_ok=True
            )
        return


def write_laje_pages(
    dialog,
    title: str,
    rows: list[dict],
    output_dir: str,
    page_css: str,
    javascript: str,
    photo_fn: Callable[[list], str],
    metrics_fn: Callable[[list], dict],
) -> tuple[str, str, int]:
    """Grava índice e uma ficha granular por laje."""
    section_dir = os.path.join(output_dir, "lajes")
    os.makedirs(section_dir, exist_ok=True)
    # Evidências em coluna única: cada estágio ocupa toda a largura útil.
    page_css += (
        ".evidence-grid{display:grid!important;grid-template-columns:1fr!important;"
        "gap:18px!important}"
        ".evidence-card{width:100%;box-sizing:border-box;padding:10px!important}"
        ".evidence-card img,.evidence-card svg{display:block;width:100%!important;"
        "height:auto!important;max-height:none!important;object-fit:contain;background:#111}"
        ".artifact-path{font-size:9px!important}"
        # A tabela de identidade (label/valor) nao tem width no HTML base,
        # entao encolhe para o conteudo e sobra espaco morto a direita do
        # card, mesmo o .sec/.main-content ja ocupando a largura cheia da
        # janela. So essa tabela precisa esticar -- vertices/checks tem
        # poucas colunas curtas e ficam com buracos estranhos se esticadas.
        ".kv-table{width:100%;box-sizing:border-box}"
    )

    entries: list[tuple[str, dict, str]] = []
    used: set[str] = set()
    for row in rows:
        name = str(row.get("_name") or row.get("Nome") or "LAJE")
        base_slug = _safe_slug(name)
        page_slug = base_slug
        suffix = 2
        while page_slug in used:
            page_slug = f"{base_slug}_{suffix}"
            suffix += 1
        used.add(page_slug)
        entries.append((name, row, page_slug))

    def page(index: int) -> str:
        name, row, _ = entries[index]
        points = row.get("_points") or []
        metrics = metrics_fn(points)

        n3_path = dialog._find_beam_dxf("LJ", name, n4=False)
        n4_path = dialog._find_beam_dxf("LJ", name, n4=True)
        n2_path = dialog._find_n2_recorte_dxf("LAJ", name)

        sa_b64 = (
            dialog._render_pilar_dxf_context_b64(
                points, width=1820, height=1300, focus_mode="slab", fmt="svg",
            )
            if points
            else ""
        )
        sa_fmt = "svg"
        if not sa_b64:
            sa_b64 = photo_fn(points)
            sa_fmt = "png"
        n3_b64 = dialog._render_ezdxf_b64(n3_path, 1900, 1240, fmt="svg") if n3_path else ""
        n4_b64 = dialog._render_ezdxf_b64(n4_path, 1900, 1240, fmt="svg") if n4_path else ""
        n2_b64 = dialog._render_ezdxf_b64(n2_path, 1900, 1240, fmt="svg") if n2_path else ""

        previous = f"{entries[index - 1][2]}.html" if index else ""
        following = (
            f"{entries[index + 1][2]}.html" if index + 1 < len(entries) else ""
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
            f'<span class="nav-pos"><b>{html.escape(name)}</b> '
            f"({index + 1}/{len(entries)})"
            f'<span class="tag">LJ</span>'
            f"</span>{next_link}</div>"
        )
        sidebar_items = "".join(
            f'<li{" class=\"active\"" if item_index == index else ""} '
            f'data-laje="{html.escape(item_name)}">'
            f'<a href="{html.escape(item_slug)}.html">'
            f'<span class="erro-flag" style="display:none">⚠️ </span>'
            f"{html.escape(item_name)}</a></li>"
            for item_index, (item_name, _, item_slug) in enumerate(entries)
        )
        sidebar = (
            f'<aside class="sidebar"><h3>Lajes LJ ({len(entries)})</h3>'
            '<a class="sb-back" href="../index.html">← índice geral</a>'
            '<a class="sb-back" href="index.html">← índice LJ</a>'
            '<a class="sb-back" href="interpretacao_lajes.html">Guia</a>'
            f"<ul>{sidebar_items}</ul></aside>"
            + _sidebar_error_flags_script(dialog)
        )

        identity_rows = (
            _table_sep("IDENTIDADE E NÍVEL (SA)")
            + _table_row("Nome", name)
            + _table_row("Nível", row.get("Nível") or "—")
            + _table_row("Espessura", row.get("Espessura") or "—")
            + _table_row("Atenção SA", row.get("Atenção") or "—")
            + _table_sep("GEOMETRIA EXTRAÍDA")
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
        identity_section = (
            '<div class="sec"><div class="sec-title">'
            "Ficha N1/SA — Identidade e geometria</div>"
            '<div class="sec-body"><table class="kv-table" '
            'style="font-size:9px;background:#181818">'
            f"{identity_rows}</table>"
            '<div style="margin-top:8px">'
            '<div class="ficha-col-title">Resumo técnico (apoios, vizinhança, análise)</div>'
            '<pre style="white-space:pre-wrap;font-size:9px;color:#aaa;'
            'background:#101010;padding:8px;border-radius:3px;margin-top:4px">'
            f'{html.escape(str(row.get("Detalhes") or "—"))}</pre></div>'
            "</div></div>"
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
                "DXF estrutural com a laje destacada",
                sa_b64,
                image_class="img-geo",
                fmt=sa_fmt,
            )
            + _artifact_card(
                "N2", "Recorte humano usado pelo motor reverso", n2_b64, n2_path
            )
            + _artifact_card(
                "N3",
                "Robô via N1 (Fase-4 → DXF)",
                n3_b64,
                n3_path,
            )
            + _artifact_card(
                "N4",
                "Robô gerado dinamicamente a partir da engenharia reversa N2",
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
                    "Contorno autoritativo e vínculos do Structural Analyzer.",
                    name,
                ),
                _pipeline_stage(
                    dialog,
                    "N2 / STOG real",
                    bool(n2_b64),
                    "Recorte humano e ficha do motor reverso (LAJ).",
                    name,
                ),
                _pipeline_stage(
                    dialog,
                    "N3 / Robô SA",
                    bool(n3_b64),
                    "Resultado produzido a partir do JSON Fase-4 (N1).",
                    name,
                ),
                _pipeline_stage(
                    dialog,
                    "N4 / Robô ER",
                    bool(n4_b64),
                    "Resultado produzido pela rota N2 (motor dinâmico).",
                    name,
                ),
            ]
        )
        pipeline_section = (
            '<div class="sec"><div class="sec-title">'
            "Diagnóstico da cadeia SA → N3 / N2 → N4</div>"
            f'<div class="sec-body"><div class="pipeline-grid">{pipeline}</div>'
            "</div></div>"
        )

        n2_ficha = dialog._n2_ficha_html("LAJ", name)
        n3_ficha = _n3_ficha_html_laje(dialog, name)
        ficha_section = (
            '<div class="sec"><div class="sec-title">'
            "Fichas informacionais completas</div>"
            '<div class="sec-body"><div class="fichas-grid">'
            '<div><div class="ficha-col-title">N1 / SA</div>'
            f'<div class="ficha-cell"><table class="kv-table">'
            f'{identity_rows}</table></div></div>'
            '<div><div class="ficha-col-title">N2 / Motor Reverso</div>'
            f'<div class="ficha-cell">{n2_ficha}</div></div>'
            '<div><div class="ficha-col-title">N3 / JSON Fase-4</div>'
            f'<div class="ficha-cell">{n3_ficha}</div></div>'
            "</div></div></div>"
        )

        checks = [
            ("contorno com 3+ vértices", metrics["unique_vertex_count"] >= 3),
            ("área geométrica positiva", metrics["area"] > 0),
            ("nível declarado", bool(row.get("Nível") and row.get("Nível") != "—")),
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
            '<div class="sec"><div class="sec-title">Quality gates da ficha LJ</div>'
            f'<div class="sec-body"><table class="kv-table">{check_rows}</table>'
            "</div></div>"
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
            + _error_marker_block(dialog, name)
        )
        return (
            '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
            f"<title>Laje — {html.escape(name)}</title>"
            f"<style>{page_css}</style>{javascript}</head><body>{sidebar}"
            '<div class="main-wrap"><div class="main-content">'
            '<h2 style="font-size:13px;color:#7eb8f7;margin:0 0 8px">'
            f"Laje {html.escape(name)}</h2>"
            f"{main}</div></div></body></html>"
        )

    for index, (_, _, page_slug) in enumerate(entries):
        page_path = os.path.join(section_dir, f"{page_slug}.html")
        with open(page_path, "w", encoding="utf-8") as file:
            file.write(page(index))
        print(f"[HTML] lajes {index + 1}/{len(entries)}: {page_slug}", flush=True)

    index_rows = "".join(
        "<tr>"
        f"<td>{idx + 1}</td><td>{html.escape(name)}</td>"
        f'<td>{html.escape(str(row.get("Nível") or "—"))}</td>'
        f'<td>{html.escape(str(row.get("Espessura") or "—"))}</td>'
        f'<td><a href="{html.escape(page_slug)}.html">abrir →</a></td>'
        "</tr>"
        for idx, (name, row, page_slug) in enumerate(entries)
    )
    # As marcações de erro (checkbox + nota, ver _error_marker_block) ficam
    # em localStorage e são lidas depois via `scripts/arete/qa_error_review.py
    # read` — não há exportação manual aqui; ver docs/ARETE-PLAYWRIGHT-QA-VISUAL.md.
    index_document = (
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
        f"<title>{html.escape(title)}</title><style>{page_css}</style></head>"
        '<body style="margin:16px"><a class="nav-arrow" href="../index.html">'
        "← índice geral</a><h1>Lajes — Fichas Granulares</h1>"
        f'<p class="meta">{len(entries)} lajes · evidências N1/N2/N3/N4</p>'
        "<table><tr><th>#</th><th>Laje</th><th>Nível</th>"
        "<th>Espessura</th><th></th></tr>"
        f"{index_rows}</table></body></html>"
    )
    with open(os.path.join(section_dir, "index.html"), "w", encoding="utf-8") as file:
        file.write(index_document)

    _copy_latest_guide(output_dir, section_dir)
    return ("lajes/index.html", title, len(rows))
