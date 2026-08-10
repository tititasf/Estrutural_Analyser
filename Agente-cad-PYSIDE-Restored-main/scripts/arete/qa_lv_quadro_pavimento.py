"""Quadro QA read-only de estado por pavimento para Laterais de Viga.

O arquivo apenas le ``project_data.vision`` e artefatos canonicos ja existentes.
Ele nunca materializa N1/N3, nao executa gate, nao grava selos e nao altera DXF/N2/N4.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTRACTS = (("Para", "A"), ("Para", "B"), ("Passa", "A"), ("Passa", "B"))
SEALS = ("azul", "laranja", "verde", "rosa")
HEADERS = (
    ("etapa", "Etapa atual / próximo passo"),
    ("item", "Item LV"),
    ("n2", "S1 · N2 — validação / estado técnico"),
    ("n2_segmentos", "S1 · Ficha N2 — segmentos/painéis"),
    ("n4", "S2 · N4 — humano + QA · G2/G2-V"),
    ("n1_segmentos", "S3 · N1 — segmentos por lateral"),
    ("n1_sa", "S4 · N1 / SA — campos, origem e quatro contratos"),
    ("n1_v", "S5 · N1-V CLI (SVG)"),
    ("n1_n2", "S5 · N1×N2 — diagnóstico"),
    ("n3", "S6 · N3 somente de N1 + quatro selos"),
    ("n3_n4", "S7 · N3×N4 — comparação"),
    ("n3_n2", "S7 · N3×N2 — diagnóstico"),
    ("rag_html", "S8 · RAG HTML — ingestão pós-QA"),
)


def _json(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return default


def _item_key(name: str) -> tuple[int, str]:
    match = re.search(r"(\d+)", name)
    return (int(match.group(1)) if match else 10**9, name)


def _contract_key(behavior: str, side: str) -> str:
    return f"{side}_{behavior.upper()}"


def _seals(raw: Any, *, n4: bool = False) -> dict[str, bool]:
    """Normaliza estados sem inferir aprovação por presença de artefato."""
    result = {seal: False for seal in SEALS}
    if isinstance(raw, dict):
        for seal in SEALS:
            result[seal] = bool(raw.get(seal))
    elif isinstance(raw, list):
        for value in raw:
            normalized = str(value).lower()
            if normalized in result:
                result[normalized] = True
    if n4:
        return {seal: result[seal] for seal in ("azul", "laranja")}
    return result


def _seal_line(values: dict[str, bool], *, n4: bool = False) -> str:
    order = ("azul", "laranja") if n4 else SEALS
    labels = {"azul": "🔵 humano", "laranja": "🟠 QA", "verde": "🟢", "rosa": "🌸"}
    return " · ".join(f"{labels[key]}={'SIM' if values.get(key) else '—'}" for key in order)


def _latest_g2v(repo_root: Path, pavement: str) -> dict[str, dict[str, str]]:
    """Indexa apenas relatórios SVG/CLI persistidos; ausência não vira FAIL."""
    result: dict[str, dict[str, str]] = {}
    root = repo_root / "scripts" / "arete" / "relatorios" / "g2v"
    if not root.exists():
        return result
    for report_path in root.glob("**/relatorio.json"):
        report = _json(report_path.read_text(encoding="utf-8"), {})
        if not isinstance(report, dict) or report.get("classe") != "LV" or report.get("pavimento") != pavement:
            continue
        if report.get("par") not in {"n2xn4", "n1xn2", "n3xn4", "n3xn2"}:
            continue
        for item in report.get("itens") or []:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("elemento_id") or "").upper()
            if not item_id:
                continue
            cli = (item.get("vereditos") or {}).get("cli") or {}
            if item.get("erro"):
                verdict = f"BLOQUEADO — {item['erro']}"
            elif item.get("fonte_imagem") != "html_svg_vetorial":
                continue
            else:
                verdict = str(cli.get("veredito") or "PENDENTE").upper()
            if cli.get("aguardando_agente"):
                verdict = "PENDENTE"
            record = result.setdefault(item_id, {})
            record[str(report.get("par"))] = verdict
            record["svg"] = "; ".join(str(path) for path in item.get("svg_paths") or [])
            record["report"] = str(report_path)
    return result


def _latest_lv_diagnostic(repo_root: Path, obra: str, pav: str) -> dict[str, Any]:
    root = repo_root / "scripts" / "arete" / "relatorios" / "diagnosticos_lv" / obra / pav
    candidates = sorted(root.glob("**/triagem_auto_lv.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True) if root.exists() else []
    if not candidates:
        return {"path": None, "items": {}}
    items: dict[str, Any] = {}
    for line in candidates[0].read_text(encoding="utf-8").splitlines():
        row = _json(line, {})
        if isinstance(row, dict):
            item = str(row.get("item") or row.get("elemento_id") or "").upper()
            if item:
                items[item] = row
    return {"path": str(candidates[0]), "items": items}


def _latest_lv_html_pack(repo_root: Path, obra: str) -> tuple[Path | None, dict[str, set[str]]]:
    """Localiza o último pacote completo de fichas LV sem mudar qualquer dado.

    O pacote é evidência de execução do headless, não evidência de contrato já
    persistido. Por isso o chamador sempre explicita esse limite na célula S3.
    """
    root = repo_root / "scripts" / "arete" / "html_fichas" / obra
    candidates = [
        path for path in root.glob("*_laterais_viga_*")
        if (path / "laterais_viga" / "LV-PARA").is_dir()
        and (path / "laterais_viga" / "LV-PASSA").is_dir()
    ] if root.exists() else []
    if not candidates:
        return None, {"Para": set(), "Passa": set()}
    pack = max(candidates, key=lambda path: path.stat().st_mtime)
    result = {"Para": set(), "Passa": set()}
    for behavior, folder in (("Para", "LV-PARA"), ("Passa", "LV-PASSA")):
        suffix = f"-{behavior}.html"
        for page in (pack / "laterais_viga" / folder).glob("*.html"):
            if page.name.endswith(suffix):
                result[behavior].add(page.name[:-len(suffix)].upper())
    return pack, result


def _n4_artifacts(db_path: Path, obra: str) -> set[str]:
    """Itens LV que têm o DXF N4 canônico já materializado (somente leitura)."""
    root = db_path.parent / "DADOS-OBRAS" / obra / "Fase-6_Execucao_CAD" / "n4"
    if not root.exists():
        return set()
    result: set[str] = set()
    for path in root.glob("LV_preview_*.dxf"):
        match = re.fullmatch(r"LV_preview_(.+)", path.stem, flags=re.IGNORECASE)
        if match:
            result.add(match.group(1).upper())
    return result


def _rag_html_status(records: list[sqlite3.Row], item: str, behavior: str) -> tuple[str, bool]:
    """Expõe ingestão já registrada, sem promover candidato ou HTML sozinho."""
    behavior_key = behavior.upper()
    relevant = [
        row for row in records
        if str(row["item_id"] or "").upper() == item
        and (not str(row["scope"] or "").strip() or behavior_key in str(row["scope"] or "").upper())
    ]
    accepted_statuses = {"APPROVED", "INGESTED", "ACTIVE", "VALID"}
    active = [
        row for row in relevant
        if str(row["status"] or "").upper() in accepted_statuses
        and not row["revoked_at"]
        and "qa" in str(row["validation_origin"] or "").lower()
        and str(row["artifact_path"] or "").lower().endswith((".html", ".htm"))
    ]
    if active:
        row = active[-1]
        return (
            "Ingerido RAG HTML pós-QA: SIM\n"
            f"status={row['status']} · origem={row['validation_origin']}\n"
            f"escopo={row['scope']} · em={row['validated_at'] or row['updated_at']}\n"
            f"artefato={row['artifact_path']}",
            True,
        )
    if relevant:
        row = relevant[-1]
        return (
            "Ingestão RAG HTML: bloqueada/não elegível\n"
            f"status={row['status']} · origem={row['validation_origin']} · revogado={row['revoked_at'] or 'não'}\n"
            "Exige registro QA ativo e artefato HTML após todas as validações do item.",
            False,
        )
    return (
        "Não ingerido no RAG HTML.\n"
        "Pré-requisito: validações QA exigidas do item registradas e ingestão HTML ativa persistida.",
        False,
    )


def _contract_summary(contract: dict[str, Any], behavior: str, side: str) -> dict[str, Any]:
    segments = contract.get("structural_segments") or []
    panels = contract.get("panels") or []
    events = contract.get("endpoint_events") or []
    meta = contract.get("_sa_meta") or {}
    source_pairs = [
        f"{segment.get('source_key') or '—'} / {segment.get('source_slot') or '—'}"
        for segment in segments
    ]
    supports = contract.get("endpoint_labels") or {}
    return {
        "partition": _contract_key(behavior, side),
        "present": bool(contract),
        "contract_id": str(contract.get("contract_id") or "—"),
        "generation_ready": bool(contract.get("generation_ready")),
        "dimensions": f"L={contract.get('total_length', '—')} · H={contract.get('total_height', '—')} · seção={contract.get('h_section', '—')}",
        "segments": len(segments),
        "panels": len(panels),
        "support": f"início={supports.get('start') or '—'}; fim={supports.get('end') or '—'}",
        "continuity": f"ajustes {contract.get('start_adjustment', 0):g}/{contract.get('end_adjustment', 0):g}; eventos={len(events)}",
        "crops": ", ".join(str(event.get("kind") or event.get("type") or "evento") for event in events) or "nenhum",
        "source": "; ".join(source_pairs) or "não persistida",
        "isolated": meta.get("behavior_isolated") is True,
        "fv_fallback": meta.get("fv_dimension_fallback") is True,
    }


def _partition_text(partitions: list[dict[str, Any]]) -> str:
    lines = []
    for part in partitions:
        if not part["present"]:
            lines.append(f"{part['partition']}: ausente")
            continue
        state = "pronto" if part["generation_ready"] else "não pronto"
        isolation = "isolado" if part["isolated"] and not part["fv_fallback"] else "ISOLAMENTO FALHOU"
        lines.append(
            f"{part['partition']} · {part['contract_id']} · {state}, {isolation}\n"
            f"seg={part['segments']}; painéis={part['panels']}; {part['dimensions']}\n"
            f"{part['support']} · {part['continuity']} · recortes/exceções: {part['crops']}\n"
            f"origem permitida: {part['source']}"
        )
    return "\n\n".join(lines)


def _segments_text(partitions: list[dict[str, Any]]) -> str:
    """Resumo curto para a coluna geométrica, separado do detalhe de proveniência."""
    return "\n".join(
        f"{part['partition']}: {part['segments']} segmento(s); {part['panels']} painel(is); {part['dimensions']}"
        for part in partitions
    )


def _next_step(partitions: list[dict[str, Any]], g2v: dict[str, str], diagnostic: Any) -> str:
    if any(not part["present"] for part in partitions):
        return "S3 — materializar os quatro contratos LV pelo headless canônico; faltam partições"
    if any(not part["generation_ready"] or not part["isolated"] or part["fv_fallback"] for part in partitions):
        return "S4 — probe four_contracts_and_support; corrigir isolamento/origem sem usar FV"
    if not diagnostic:
        return "S5 — diagnóstico N1×N2 por lateral, sem preencher N1 por N2"
    if g2v.get("n1xn2") in {None, "PENDENTE"}:
        return "S5 — N1-V CLI SVG + registrar N1×N2 por A/B e Para/Passa"
    if g2v.get("n3xn4") in {None, "PENDENTE"}:
        return "S7 — gerar N3 de N1 e comparar N3×N4 no CLI SVG"
    return "S8 — revisar divergências registradas; manter G2/G2-V dentro do N4"


def build_report(project_id: str, obra: str, pav: str, db_path: Path, repo_root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        beam_rows = connection.execute(
            "SELECT name, data_json, is_validated, validated_fields_json FROM beams WHERE project_id = ? ORDER BY name",
            (project_id,),
        ).fetchall()
        historical_rows = connection.execute("SELECT data_json FROM beams").fetchall()
        ficha_rows = connection.execute(
            "SELECT elemento_id, status, recorte_path, aprovado_at, campos_json FROM reverse_eng_fichas "
            "WHERE obra_name = ? AND pavimento = ? AND classe = 'LV'", (obra, pav)
        ).fetchall()
        classification_rows = connection.execute(
            "SELECT item_id, tipo, updated_at FROM lv_para_passa "
            "WHERE obra = ? AND pavimento = ? AND classe = 'LV'", (obra, pav)
        ).fetchall()
        rag_rows = connection.execute(
            "SELECT item_id, scope, artifact_path, status, validation_origin, validated_at, revoked_at, updated_at "
            "FROM rag_artifact_validations WHERE obra_name = ? AND pavimento = ? AND classe = 'LV'",
            (obra, pav),
        ).fetchall()
    finally:
        connection.close()
    fichas = {str(row["elemento_id"] or "").upper(): row for row in ficha_rows}
    classifications = {str(row["item_id"] or "").upper(): row for row in classification_rows}
    beams_by_name = {str(row["name"] or "").upper(): row for row in beam_rows}
    g2v = _latest_g2v(repo_root, pav)
    diagnostics = _latest_lv_diagnostic(repo_root, obra, pav)
    html_pack, html_items = _latest_lv_html_pack(repo_root, obra)
    n4_items = _n4_artifacts(db_path, obra)
    rows: list[dict[str, str]] = []
    global_counts = Counter()
    historical_counts = Counter()
    rag_ingested = 0
    for historical in historical_rows:
        historical_contracts = (_json(historical["data_json"], {}) or {}).get("lv_generation_contracts") or {}
        for behavior, side in CONTRACTS:
            if (historical_contracts.get(behavior) or {}).get(side):
                historical_counts[_contract_key(behavior, side)] += 1
    # A topologia é do contrato, nunca só da viga: Para/Passa pode divergir
    # mesmo com a mesma seção. Isto também impede que o quadro esconda uma
    # terceira forma real por ter o mesmo nome de item.
    snapshots: dict[tuple[str, int, int, int], str] = {}
    # A lista de laterais vem da classificação LV/N2 persistida. A ausência de
    # contrato SA torna-se estado explícito S3, em vez de ocultar a viga.
    item_names = set(classifications) | set(fichas)
    for item in sorted(item_names, key=_item_key):
        beam = beams_by_name.get(item)
        data = _json(beam["data_json"], {}) if beam else {}
        contracts = data.get("lv_generation_contracts") or {}
        parts = [_contract_summary((contracts.get(behavior) or {}).get(side) or {}, behavior, side) for behavior, side in CONTRACTS]
        for part in parts:
            global_counts[part["partition"]] += int(part["present"])
        item_g2v = g2v.get(item, {})
        diagnostic = diagnostics["items"].get(item)
        for part in parts:
            if not part["present"]:
                continue
            signature = (
                # comportamento, contagem, painel e eventos distinguem uma
                # topologia real; lado não é usado sozinho como atalho.
                "PASSA" if "PASSA" in part["partition"] else "PARA",
                part["segments"],
                part["panels"],
                0 if part["crops"] == "nenhum" else len(part["crops"].split(", ")),
            )
            snapshots.setdefault(signature, f"{item}:{part['partition']}")
        ficha = fichas.get(item)
        ficha_fields = _json(ficha["campos_json"], {}) if ficha else {}
        ficha_field_count = len(ficha_fields) if isinstance(ficha_fields, dict) else 0
        n4_seals = _seals({}, n4=True)  # Sem política N4 persistida, não inventar selo.
        n1_seals = _seals(_json(beam["validated_fields_json"], {}) if beam else {})
        for behavior in ("Para", "Passa"):
            behavior_parts = [part for part in parts if part["partition"].endswith(behavior.upper())]
            behavior_name = behavior.upper()
            html_generated = item in html_items[behavior]
            n4_generated = item in n4_items
            rag_status, rag_ready = _rag_html_status(rag_rows, item, behavior)
            rag_ingested += int(rag_ready)
            n4_status = (
                ("DXF N4 presente: artefato gerado; ainda sem selo de validação.\n" if n4_generated and behavior == "Passa" else "")
                + ("N4 disponível apenas como referência PASSA; não preenche nem valida PARA.\n" if n4_generated and behavior == "Para" else "")
                + f"{_seal_line(n4_seals, n4=True)}\n"
                "G2: não é card independente; paridade canônica somente dentro desta etapa.\n"
                f"G2-V CLI N2×N4: {item_g2v.get('n2xn4', 'não registrado')}"
            )
            n1_status = (
                f"Selos N1 / SA — {behavior_name}\n{_seal_line(n1_seals)}\n"
                + ("Ficha HTML recém-gerada pelo headless: presente; snapshot ainda não persistido no DB.\n" if html_generated else "Ficha HTML desta execução: não encontrada.\n")
                + _partition_text(behavior_parts)
            )
            n3_status = (
                f"Selos N3 — {behavior_name}\n{_seal_line(n1_seals)}\n"
                "N3 só pode derivar dos source_key/source_slot desta tabela; smoke: não registrado."
            )
            n2_status = (
                f"{'ficha presente' if ficha else 'sem ficha LV persistida'}\n"
                f"recorte: {ficha['recorte_path'] if ficha else '—'}\nstatus técnico: {ficha['status'] if ficha else '—'}"
                if behavior == "Passa" else
                "N2 separado PARA: não persistido neste pavimento.\n"
                "A referência N2 disponível é PASSA e serve somente para comparação; não preenche este contrato PARA."
            )
            rows.append({
                "etapa": _next_step(behavior_parts, item_g2v, diagnostic),
                "item": f"{item} — {behavior_name}",
                "behavior": behavior,
                "n2": n2_status,
                "n2_segmentos": (
                    "N2 separado PARA: não persistido; não espelhar nem copiar do PASSA."
                    if behavior == "Para" else
                    (f"Ficha N2 LV: {ficha_field_count} campos extraídos; segmentos/painéis vêm somente da ficha N2."
                     if ficha else "Ficha N2 LV não persistida no DB deste escopo; painéis N2 não são inferidos do N1.")
                ),
                "n4": n4_status if n4_generated else "DXF N4 não encontrado para este item.\n" + n4_status,
                "n1_segmentos": (("Ficha HTML de segmentos gerada nesta execução.\n" if html_generated else "Ficha HTML de segmentos não encontrada.\n") + _segments_text(behavior_parts)),
                "n1_sa": n1_status,
                "n1_v": f"CLI SVG N1×N2: {item_g2v.get('n1xn2', 'não registrado')}\nSVG: {item_g2v.get('svg', 'não encontrado')}",
                "n1_n2": "diagnóstico presente" if diagnostic else "não registrado",
                "n3": n3_status,
                "n3_n4": f"CLI SVG N3×N4: {item_g2v.get('n3xn4', 'não registrado')}",
                "n3_n2": f"CLI SVG N3×N2: {item_g2v.get('n3xn2', 'não registrado')}",
                "rag_html": rag_status,
            })
    rows.sort(key=lambda row: (_item_key(row["item"]), row["behavior"]))
    summary = {
        "schema": "arete.qa_lv_quadro_pavimento/v1",
        "mode": "read_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_id": project_id,
        "obra": obra,
        "pavimento": pav,
        "items": len({row["item"].split(" — ", 1)[0] for row in rows}),
        "table_rows": len(rows),
        "partitions": dict(global_counts),
        "all_time_partitions": dict(historical_counts),
        "selected_topology_snapshots": list(snapshots.values())[:3],
        "diagnostic_path": diagnostics["path"],
        "html_pack": str(html_pack) if html_pack else None,
        "html_generated": {behavior: len(items) for behavior, items in html_items.items()},
        "n4_generated": len(n4_items & item_names),
        "rag_html_ingested": rag_ingested,
        "limits": [
            "O quadro lê DB e artefatos canônicos; nunca altera dados, selos, N2/N4, DXF ou JSON Fase-4.",
            "FV nunca é fallback LV. PIL/LAJ só aparecem se já estiverem permitidos e rastreados pelo contrato LV.",
            "Corte é contexto comum: não espelha A/B nem Para/Passa.",
            "N2/N4 comparam; não alimentam N1/N3.",
            "G2 e G2-V pertencem à etapa N4; G2-V somente é lido do g2v_harness --backend cli com SVG.",
            "Ausência de veredito ou selo permanece não registrada; não é convertida em FAIL nem aprovação.",
            "Marca ✓ significa evidência realizada/disponível; somente selos declarados significam validação.",
            "Ficha HTML de headless sem --persist-db é snapshot de execução; não altera nem comprova contrato persistido no DB.",
            "S8 somente marca RAG quando rag_artifact_validations contém HTML ativo, não revogado e de origem QA; HTML exportado não basta.",
        ],
    }
    return summary, rows


def _status(value: str) -> str:
    lowered = value.lower()
    if "bloqueado" in lowered or "blocked" in lowered:
        return "pending"
    # A primeira linha de algumas células registra um artefato efetivamente
    # produzido; pendências posteriores de selo/gate não devem esconder esse
    # fato. O tooltip do ícone deixa claro que ✓ não é aprovação.
    if lowered.startswith(("dxf n4 presente", "ficha html de segmentos gerada", "selos n1 / sa")) or "ficha n2 lv:" in lowered:
        return "pass"
    if "não registrado" in lowered or "não encontrada" in lowered or "ausente" in lowered or "sem " in lowered or "falt" in lowered or "s3 —" in lowered or "s5 —" in lowered or "s7 —" in lowered:
        return "pending"
    if "falhou" in lowered or "fail" in lowered:
        return "fail"
    if "pronto" in lowered or "presente" in lowered:
        return "pass"
    return "neutral"


def _status_icon(value: str) -> tuple[str, str]:
    """Ícone de realização, não um selo de aprovação inventado."""
    status = _status(value)
    return {
        "pass": ("✓", "realizado / evidência disponível"),
        "pending": ("◌", "pendente de evidência ou validação"),
        "fail": ("×", "falhou / requer correção"),
        "neutral": ("•", "estado informativo"),
    }[status]


def write_reports(summary: dict[str, Any], rows: list[dict[str, str]], output_dir: Path) -> tuple[Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "QUADRO-LV-PAVIMENTO.md"
    csv_path = output_dir / "QUADRO-LV-PAVIMENTO.csv"
    json_path = output_dir / "QUADRO-LV-PAVIMENTO.json"
    html_path = output_dir / "QUADRO-LV-PAVIMENTO.html"
    json_path.write_text(json.dumps({"summary": summary, "items": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=[key for key, _ in HEADERS])
        writer.writeheader()
        writer.writerows({key: row[key] for key, _ in HEADERS} for row in rows)
    md = ["# Quadro QA — Laterais de Viga por pavimento", "", f"- Escopo: `{summary['obra']}/{summary['pavimento']}/LV`", f"- Project ID: `{summary['project_id']}`", "- Modo: `read_only`", f"- Gerado: `{summary['generated_at']}`", "", "## Todos os tempos", "", f"- Partições persistidas: `{json.dumps(summary['all_time_partitions'], ensure_ascii=False)}`", "", "## Pavimento atual", "", f"- Itens LV com contrato persistido: **{summary['items']}**", f"- Linhas de tabela: **{summary['table_rows']}** (uma por item/comportamento)", f"- Partições: `{json.dumps(summary['partitions'], ensure_ascii=False)}`", f"- S8 RAG HTML pós-QA ativo: **{summary['rag_html_ingested']}**", f"- Snapshots reais selecionados: `{', '.join(summary['selected_topology_snapshots']) or 'menos de três disponíveis'}`"]
    for behavior in ("Para", "Passa"):
        md += ["", f"## Laterais de Viga — {behavior.upper()}", "", "| " + " | ".join(label for _, label in HEADERS) + " |", "|" + "|".join("---" for _ in HEADERS) + "|"]
        for row in (row for row in rows if row["behavior"] == behavior):
            md.append("| " + " | ".join(str(row[key]).replace("\n", "<br>") for key, _ in HEADERS) + " |")
    md += ["", "## Limites", "", *[f"- {value}" for value in summary["limits"]], ""]
    md_path.write_text("\n".join(md), encoding="utf-8")
    head = "".join(f'<th class="col-{key}">{html.escape(label)}</th>' for key, label in HEADERS)
    def table_body(behavior: str) -> str:
        body = []
        for row in (row for row in rows if row["behavior"] == behavior):
            cells = "".join(
                f'<td class="col-{key} {_status(row[key])}"><span class="stage-icon" title="{_status_icon(row[key])[1]}">{_status_icon(row[key])[0]}</span>{html.escape(row[key]).replace(chr(10), "<br>")}</td>'
                for key, _ in HEADERS
            )
            body.append(f"<tr>{cells}</tr>")
        return "".join(body)
    all_time_cards = "".join(f"<article><small>{html.escape(key)}</small><strong>{value}</strong></article>" for key, value in summary["all_time_partitions"].items())
    current_cards = "".join(f"<article><small>{html.escape(key)}</small><strong>{value}</strong></article>" for key, value in summary["partitions"].items())
    current_cards += f"<article><small>S8 · RAG HTML pós-QA ativo</small><strong>{summary['rag_html_ingested']}</strong></article>"
    html_path.write_text(f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Quadro LV — {html.escape(summary['obra'])}/{html.escape(summary['pavimento'])}</title>
<style>:root{{color-scheme:dark;--bg:#10151d;--panel:#182231;--line:#30445c;--text:#eaf2fc;--muted:#a8b8ca;--pass:#166534;--fail:#991b1b;--pending:#854d0e;--neutral:#253548;--accent:#22d3ee}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}}main{{max-width:100%;padding:24px}}h1{{margin:0 0 4px;font-size:26px}}h2{{margin:28px 0 12px;font-size:19px}}.meta,small{{color:var(--muted)}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin-top:22px}}article{{min-height:112px;padding:14px;border:1px solid var(--line);border-radius:10px;background:var(--panel)}}article strong{{display:block;margin:8px 0;color:var(--accent);font-size:21px}}.wrap{{overflow:auto;border:1px solid var(--line);border-radius:10px;background:var(--panel)}}table{{border-collapse:collapse;table-layout:fixed;min-width:3360px;width:3360px}}th,td{{padding:10px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);text-align:left;vertical-align:top;white-space:normal;overflow-wrap:anywhere;line-height:1.5}}th{{position:sticky;top:0;z-index:2;background:#223047;color:#f7fbff;font-size:12px}}tr:hover td{{outline:1px solid #3d648a}}td:first-child{{position:sticky;left:0;z-index:1;font-weight:700;background:#223047}}.stage-icon{{display:inline-flex;width:18px;height:18px;margin:0 6px 3px 0;border:1px solid currentColor;border-radius:50%;align-items:center;justify-content:center;font-weight:800;vertical-align:top}}td.pending{{background:color-mix(in srgb,var(--pending) 33%,var(--panel));color:#ffd08a}}td.fail{{background:color-mix(in srgb,var(--fail) 31%,var(--panel));color:#ffb4b4}}td.pass{{background:color-mix(in srgb,var(--pass) 38%,var(--panel));color:#b9f6cb}}td.neutral{{background:var(--neutral)}}.col-etapa{{--column:#94a3b8}}.col-item{{--column:#64748b}}.col-n2{{--column:#0ea5e9}}.col-n2_segmentos{{--column:#14b8a6}}.col-n4{{--column:#8b5cf6}}.col-n1_segmentos{{--column:#6366f1}}.col-n1_sa{{--column:#f59e0b}}.col-n1_v{{--column:#eab308}}.col-n1_n2{{--column:#38bdf8}}.col-n3{{--column:#22c55e}}.col-n3_n4{{--column:#a855f7}}.col-n3_n2{{--column:#ec4899}}th[class*="col-"]{{background:color-mix(in srgb,var(--column) 36%,#182231)}}td[class*="col-"]{{background:color-mix(in srgb,var(--column) 18%,var(--panel));box-shadow:inset 3px 0 var(--column)}}td[class*="col-"].pass{{background:color-mix(in srgb,var(--pass) 48%,var(--column))!important}}td[class*="col-"].fail{{background:color-mix(in srgb,var(--fail) 48%,var(--column))!important}}td[class*="col-"].pending{{background:color-mix(in srgb,var(--pending) 48%,var(--column))!important}}td.col-etapa{{font-weight:700}}details{{margin-top:20px;padding:14px;border:1px solid var(--line);border-radius:10px;background:var(--panel)}}a{{color:var(--accent)}}</style>
<main><h1>Quadro QA — Laterais de Viga</h1><p class="meta">{html.escape(summary['obra'])} / {html.escape(summary['pavimento'])} / LV · <code>{html.escape(summary['project_id'])}</code> · read-only</p>
<h2>Todos os tempos</h2><section class="cards">{all_time_cards}</section><h2>Pavimento atual</h2><section class="cards">{current_cards}</section><p class="meta">Duas tabelas independentes: PARA não mistura fatos de PASSA. Cada tabela mantém Lado A e Lado B como contratos isolados.</p>
<h2>Laterais de Viga — PARA ({sum(1 for row in rows if row['behavior'] == 'Para')} itens)</h2><div class="wrap"><table><thead><tr>{head}</tr></thead><tbody>{table_body('Para')}</tbody></table></div>
<h2>Laterais de Viga — PASSA ({sum(1 for row in rows if row['behavior'] == 'Passa')} itens)</h2><div class="wrap"><table><thead><tr>{head}</tr></thead><tbody>{table_body('Passa')}</tbody></table></div>
<details><summary>Proveniência, evidência SVG e limites</summary><p>Snapshots reais: {html.escape(', '.join(summary['selected_topology_snapshots']) or 'menos de três disponíveis')}</p><p>Diagnóstico LV: {html.escape(str(summary['diagnostic_path'] or 'não encontrado'))}</p><ul>{''.join('<li>'+html.escape(limit)+'</li>' for limit in summary['limits'])}</ul><p><a href="{md_path.name}">Markdown</a> · <a href="{csv_path.name}">CSV</a> · <a href="{json_path.name}">JSON</a></p></details></main></html>''', encoding="utf-8")
    return html_path, json_path, csv_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--obra", required=True)
    parser.add_argument("--pav", required=True)
    parser.add_argument("--db", type=Path, default=Path(r"D:\Agente-cad-PYSIDE\project_data.vision"))
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary, rows = build_report(args.project_id, args.obra, args.pav, args.db, args.repo_root)
    reports = write_reports(summary, rows, args.output_dir)
    print(json.dumps({"summary": summary, "reports": [str(path) for path in reports]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
