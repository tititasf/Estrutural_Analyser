#!/usr/bin/env python3
"""Quadro read-only de progresso PIL por pavimento.

Não é comparador, gerador, headless ou scorer: consolida apenas o que já está
persistido no DB e nos relatórios canônicos, reusando o adaptador CAD
independente ``PilEvidenceAuditor`` (``qa_evidence_auditor.py``) para as
decisões por campo — a mesma leitura que ``qa_evidence_auditor.py review``
produziria, sem headless e sem escrever nada. Isolado de propósito da
semântica FV/LV/LAJ: nenhuma regra, tolerância ou campo é copiado de outro
quadro; apenas infraestrutura de relatório (cores, cards, serialização) é
reaproveitada de ``qa_fv_quadro_pavimento.py``.

Regras de PIL respeitadas aqui (docs/QA-QUADROS-ESTADO-POR-CLASSE.md):
- geometria/polígono aprovada (``pilar_segs``) nunca é misturada com campos e
  vínculos ainda reescrevíveis (seção/dimensão, nível, convenção nasce/passa,
  faces, vigas/lajes adjacentes, visão/corte, continuidade entre pavimentos);
- N4 mostra somente selos azul/laranja; G2 e G2-V vivem dentro do card N4;
- G2-V/N1-V só têm autoridade quando lidos via ``g2v_harness.py --backend
  cli``; os relatórios PIL existentes ainda usam captura PNG (``html_ficha``),
  não o pipeline SVG-vetorial — isto é reportado como limitação, não escondido.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "scripts" / "arete") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "arete"))

from qa_evidence_auditor import (  # noqa: E402
    Decision,
    PilEvidenceAuditor,
    load_beams_for_project,
    load_pillars,
    load_slabs,
)

SEAL_ORDER = ("azul", "laranja", "verde", "rosa")
FIELD_ORIGIN_TO_SEAL = {
    "humano_app": "azul",
    "qa_agente": "laranja",
    "qa_agent": "laranja",
    "humano_portal": "rosa",
}
POLICY_ITEM_RE = re.compile(r"P\d+[A-Z]?")
_PIL_FACES = ("A", "B", "C", "D", "E", "F", "G", "H")

# Estágios S0-S8 (docs/SA-ANALISE-PROGRESSO-POR-ITEM.md) — mesma numeração em
# todas as classes; a definição fica só aqui pra não divergir por cópia.
STAGE_DEFINITIONS = {
    "S0": "Inventário — item existe e está identificado no escopo.",
    "S1": "N2 aceito — ficha/recorte humano de N2 aceito ou usado como comparação.",
    "S2": "N4 aceito — DXF gerado da ficha N2, com decisão humana/QA sobre a paridade N2×N4.",
    "S3": "N1 interpretado — SA gerou a estrutura bruta do item (schema imutável).",
    "S4": "N1 evidenciado — geometria/contorno do item provado de forma independente.",
    "S5": "Selo QA N1 — cada campo e vínculo confirmado isoladamente pelo adaptador CAD.",
    "S6": "N3 independente — DXF gerado só a partir do N1, com smoke de identidade/camadas.",
    "S7": "Selo QA N3 — comparações N3×N4 e N3×N2, com veredito visual.",
    "S8": "Entrega Arete — selo completo do item; revisão humana antes de promover a RAG.",
    "R1": "RAG multimodal — HTML pós-QA ingerido como evidência T0 (contexto), com hash e run QA registrados; não é gate Arete, não cria selo e nunca alimenta N1/N3; T1 exige curadoria humana.",
}

# (estágio ou None, descrição do que a coluna realmente contém) — usado no
# cabeçalho HTML (2ª linha) e na legenda de MD/HTML; nunca duplicado à mão.
COLUMN_META: dict[str, tuple[str | None, str]] = {
    "etapa_proxima": (None, "Estágio (S0–S8) e ação concreta que falta para este item avançar; a cor aponta para a coluna que precisa de atenção agora."),
    "item": ("S0", "Identificação do pilar no Structural Analyzer."),
    "n2_ficha": ("S1", "Ficha N2 (engenharia reversa humana do recorte STOG): existe; aceite real vem do RECORTE aprovado/auto-aprovado em diagnostic_reverse_hub.py (reverse_eng_recortes.status), não do status da ficha (que fica sempre em draft/extracted); confiança da extração — nunca alimenta N1/N3."),
    "n2_campos": ("S1", "Seção e faces preenchidas declaradas na ficha N2 — ✅ quando o motor reverso já extraiu seção/faces (pronta para gerar N4); comparação de apoio, não gera selo."),
    "n4_g2_g2v_para": ("S2", "N4-PARA: não existe neste pipeline — nenhum gerador N4 tem ramo PARA/PASSA, cada ficha N2 produz 1 DXF só. Sempre ➖ N/A por construção, não por item."),
    "n4_g2_g2v_passa": ("S2", "N4-PASSA (o único N4 que existe hoje): selo Azul (humano/app) e Laranja (QA agente) mostrados separados — N4 nunca tem verde/rosa; paridade numérica G2 do lote; veredito visual G2-V (N2×N4)."),
    "n1_geometria": ("S4", "Polígono (pilar_segs) confirmado por métrica de contorno independente + selo Azul/Laranja/Rosa deste 1 campo; validada, a geometria trava (🔒) e não é reescrita em reanálise."),
    "n1_campos_vinculos": ("S5", "Cobertura de selo (Azul/Laranja/Rosa) dos campos/vínculos reescrevíveis (seção, rótulo, vigas/lajes, faces l1_n/v): total de campos analisados e quantos têm cada selo — o campo específico que falta aparece em 'Etapa atual/próximo passo', não aqui. Nível, convenção e visão/corte ficam fora da contagem (sem adaptador que produza selo por campo)."),
    "n1_visual_cli": ("S5", "Validação VISUAL da interpretação N1 (não é comparação de ficha — isso é a coluna seguinte): agente CLI confere a ficha N1 contra as imagens de contexto do SA (próxima/distante) via g2v_harness; só o agente faz essa leitura, por isso só existe selo Laranja, 1 por item do checklist visual (9 itens reais do harness)."),
    "n1_n2_ficha": ("S5", "Comparação diagnóstica automática N1×N2 (dimensão/faces) — sinal de apoio, nunca um selo."),
    "n3_smoke_para": ("S6", "Prova de que o DXF N3 variante PARA (gerada só do N1) existe, com identidade e camadas mínimas — status derivado dos checks abcd_para.* do smoke."),
    "n3_smoke_passa": ("S6", "Prova de que o DXF N3 variante PASSA (gerada só do N1) existe, com identidade e camadas mínimas — status derivado dos checks abcd_passa.* do smoke."),
    "n3_n4_ficha_para": ("S7", "N/A estrutural — N4-PARA não existe (ver coluna N4); sem N4-PARA não há o que comparar contra N3-PARA."),
    "n3_n4_ficha_passa": ("S7", "Veredito visual G5-V real (g2v_harness --par n3xn4 --backend cli), lido pelo agente CLI nos SVGs vetoriais — N4 é tratado como o lado único (\"passa\") do par, mesma convenção da coluna N4."),
    "n3_n2_ficha_para": ("S7", "Diagnóstico auxiliar S7-N3N2 real (g2v_harness --par n3xn2 --backend cli): N3 (gerado só do N1) × N2 (gabarito humano) — N2 nunca alimenta o motor N3; um único veredito cobre PARA e PASSA."),
    "n3_n2_ficha_passa": ("S7", "Mesmo veredito S7-N3N2 da coluna PARA — o par n3xn2 lê as duas variantes de N3 juntas contra o mesmo N2, não há leitura separada por variante."),
    "selos_n1": ("S5", "Resumo dos selos já persistidos no item N1 (🔵 azul=humano app, 🟠 laranja=QA agente, 🟢 verde=selo completo, 🌸 rosa=portal) — qualquer cor conta como validado."),
    "selos_n3": ("S7", "Resumo dos selos já persistidos no N3 do item (🔵 azul=humano app, 🟠 laranja=QA agente, 🟢 verde=selo completo, 🌸 rosa=portal), lidos de artifact_validation_policies scope='N3' — hoje sempre 0 (nenhuma política N3 persistida para PIL)."),
    "rag_html": ("R1", "R1 — ingestão RAG multimodal: HTML completo do item pós todas as validações do agente QA, com caminho + SHA-256 + run QA registrados em rag_html_ingestoes.jsonl. Não é gate Arete, não cria selo N1/N3 e nunca alimenta N1/N3; T0 é rastreável mas não é memória confiável, T1 exige curadoria humana."),
}


def _decision_symbol(decision: "Decision | None") -> str:
    """Símbolo único por decisão, independente da cor do selo que ela prova.

    ✅ = confirmado/N-A e já persistido (qualquer origem conta);
    🕗 = confirmado/N-A pelo adaptador mas o `apply` ainda não rodou;
    ⚠ = REVISAR_HUMANO (motor e persistido divergem); ⏳ = PENDENTE.
    """
    if decision is None:
        return "❔"
    if decision.decision in {"CONFIRMAR", "N/A_CONFIRMADO"}:
        return "🕗" if decision.operations else "✅"
    if decision.decision == "REVISAR_HUMANO":
        return "⚠"
    return "⏳"


def _json(raw: Any, fallback: Any) -> Any:
    if raw in (None, ""):
        return fallback
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return fallback


def _item_key(name: str) -> tuple[int, str]:
    match = re.search(r"(\d+)", name)
    return (int(match.group(1)) if match else 10**9, name)


def _number(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):.2f}".rstrip("0").rstrip(".")
    return str(value or "?")


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def _html_cell(value: str) -> str:
    return html.escape(str(value)).replace("\n", "<br>")


def _field_origins(validated_fields_json_value: Any) -> dict[str, set[str]]:
    """Lê o formato ``{campo: [{"origem": ..., "quando": ...}, ...]}`` do PIL.

    Cópia isolada da leitura equivalente do quadro FV: mesma forma de dado
    (``src/core/validation_model.py``), mas sem importar o helper privado do
    outro quadro — nenhuma regra semântica atravessa classes.
    """
    data = _json(validated_fields_json_value, {})
    if not isinstance(data, dict):
        return {}
    result: dict[str, set[str]] = {}
    for field_id, entries in data.items():
        if not isinstance(entries, list):
            continue
        result[str(field_id)] = {
            str(entry.get("origem"))
            for entry in entries
            if isinstance(entry, dict) and entry.get("origem") in FIELD_ORIGIN_TO_SEAL
        }
    return result


def _seal_from_origin(origin: Any) -> str | None:
    value = str(origin or "").strip().lower()
    if value in {"human_ui", "legacy_human_ui", "humano_app"}:
        return "azul"
    if value in {"qa_agente", "qa_agent"}:
        return "laranja"
    if value == "humano_portal":
        return "rosa"
    return None


def _policy_seals_by_item(policy_rows: list[sqlite3.Row], known_items: set[str], allowed_seals: set[str] | None = None) -> dict[str, set[str]]:
    seals = {item: set() for item in known_items}
    for policy in policy_rows:
        seal = _seal_from_origin(policy["validation_origin"])
        if not seal or (allowed_seals is not None and seal not in allowed_seals):
            continue
        raw = str(policy["item_id"] or "").upper()
        for item in POLICY_ITEM_RE.findall(raw):
            if item in seals:
                seals[item].add(seal)
    return seals


def _seal_counts(items: set[str], seals_by_item: dict[str, set[str]]) -> dict[str, int]:
    return {seal: sum(seal in seals_by_item.get(item, set()) for item in items) for seal in SEAL_ORDER}


def _pillar_item_seals(pillar_row: dict, origins_by_field: dict[str, set[str]]) -> set[str]:
    seals: set[str] = set()
    if bool(pillar_row.get("is_validated")):
        seals.add("verde")
    all_seals = {seal for seals in origins_by_field.values() for seal in {FIELD_ORIGIN_TO_SEAL.get(o) for o in seals} if seal}
    seals |= all_seals
    return seals


def _origin_counts(field_ids: list[str], origins_by_field: dict[str, set[str]]) -> dict[str, int]:
    counts = {"azul": 0, "laranja": 0, "rosa": 0}
    for field_id in field_ids:
        seals = {FIELD_ORIGIN_TO_SEAL[o] for o in origins_by_field.get(str(field_id), set()) if o in FIELD_ORIGIN_TO_SEAL}
        for seal in seals:
            counts[seal] += 1
    return counts


def _origin_line(counts: dict[str, int]) -> str:
    return f"🔵 Azul {counts['azul']} · 🟠 Laranja {counts['laranja']} · 🌸 Portal {counts['rosa']}"


def _item_seal_line(seals: set[str]) -> str:
    return (
        f"🔵 Azul {int('azul' in seals)} · 🟠 Laranja {int('laranja' in seals)} · "
        f"🟢 Verde {int('verde' in seals)} · 🌸 Rosa {int('rosa' in seals)}"
    )


def _g2_lote_from_status(repo_root: Path, pavimento: str) -> tuple[str, str]:
    status_path = repo_root / "docs" / "STATUS.md"
    if not status_path.exists():
        return "não consultado", "STATUS.md ausente"
    for line in status_path.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in line.strip().split("|") if part.strip()]
        if len(parts) < 8 or parts[0] != "PIL" or parts[1] != pavimento:
            continue
        try:
            passed, failed, blocked = (int(parts[3]), int(parts[4]), int(parts[5]))
            golden = int(parts[7])
        except ValueError:
            continue
        verdict = "PASS" if failed == 0 and blocked == 0 else "FAIL"
        return f"{verdict} {passed}/{passed + failed + blocked}; golden {golden}", str(status_path)
    return "não consultado", f"PIL/{pavimento} não encontrado em {status_path.name}"


def _find_latest_diagnostic(repo_root: Path, obra: str, pavimento_tecnico: str) -> tuple[Path | None, dict[str, Any]]:
    candidates = sorted(
        (repo_root / "scripts" / "arete" / "relatorios" / "diagnosticos_pil" / obra / pavimento_tecnico).glob("**/diagnostico_pil_n1_n2.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        return None, {}
    path = candidates[-1]
    return path, _json(path.read_text(encoding="utf-8"), {})


def _diagnostic_status(diagnostic_item: dict[str, Any] | None) -> str:
    if not diagnostic_item:
        return "⏳ não comparada / QA pendente"
    evidencia = diagnostic_item.get("evidencia") or {}
    symbol = {"EXCELENTE": "✅", "REGULAR": "⚠", "RUIM": "❌"}.get(str(evidencia.get("classificacao")).upper(), "❔")
    return (
        f"{symbol} auto {evidencia.get('classificacao', 'N/A')}: dim_delta={_number(evidencia.get('dim_delta'))}"
        f"; faces N1={evidencia.get('faces_preenchidas_n1', '?')} vs N2={evidencia.get('faces_preenchidas_n2', '?')}"
        f" / QA pendente (diagnóstico automático, não é selo)"
    )


def _g2v_by_item(repo_root: Path, pavimento: str, par: str, gate: str) -> dict[str, dict[str, Any]]:
    """Último veredito CLI por item para um par (n1xn2 ou n2xn4).

    PIL ainda não tem pipeline SVG-vetorial (nenhum relatório com
    ``fonte_imagem == "html_svg_vetorial"`` foi encontrado nesta obra/
    pavimento até 2026-07-16); os relatórios existentes usam captura PNG
    (``html_ficha``). Isso é reportado explicitamente, não escondido nem
    tratado como equivalente ao contrato SVG do gate atual.
    """
    root = repo_root / "scripts" / "arete" / "relatorios" / "g2v"
    verdicts: dict[str, tuple[float, dict[str, Any]]] = {}
    if not root.exists():
        return {}
    for path in root.glob("**/relatorio.json"):
        report = _json(path.read_text(encoding="utf-8"), {})
        if not isinstance(report, dict) or report.get("classe") != "PIL":
            continue
        if report.get("pavimento") != pavimento or report.get("par") != par or report.get("gate") != gate:
            continue
        for item in report.get("itens") or []:
            if not isinstance(item, dict):
                continue
            cli = (item.get("vereditos") or {}).get("cli") or {}
            verdict = str(cli.get("veredito") or "").upper()
            if cli.get("aguardando_agente") or verdict not in {"PASS", "FAIL", "SUSPEITO"}:
                continue
            item_id = str(item.get("elemento_id") or "").upper()
            if not item_id:
                continue
            stamp = path.stat().st_mtime
            if item_id not in verdicts or stamp > verdicts[item_id][0]:
                verdicts[item_id] = (stamp, {
                    "veredito": verdict,
                    "confianca": cli.get("confianca"),
                    "fonte_imagem": item.get("fonte_imagem"),
                    "checklist": cli.get("checklist_visual") or {},
                    "path": str(path),
                })
    return {item: payload for item, (_, payload) in verdicts.items()}


_N3_VARIANT_PREFIX = {"para": "abcd_para.", "passa": "abcd_passa."}


def _n3_smokes(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Smoke N3 por item, com PARA e PASSA separados.

    O relatório de ``qa_n3_smoke.py`` traz um único ``overall`` combinado, mas
    o array ``checks`` identifica cada check por prefixo de id
    (``abcd_para.*`` / ``abcd_passa.*``) — a granularidade real por variante
    vem dali, não do campo agregado. Uma variante ausente de ``variants``
    fica ``None`` (nunca inferida).
    """
    base = repo_root / "scripts" / "arete" / "relatorios"
    result: dict[str, dict[str, Any]] = {}
    for path in base.glob("qa_n3_smoke*.json"):
        report = _json(path.read_text(encoding="utf-8"), {})
        if not isinstance(report, dict):
            continue
        question = str(report.get("question") or "")
        match = re.search(r"PIL:(P[\w.-]+)", question)
        if not match:
            continue
        variants_present = report.get("variants") or {}
        checks = report.get("checks") or []
        per_variant: dict[str, dict[str, Any] | None] = {}
        for label, prefix in _N3_VARIANT_PREFIX.items():
            variant_key = f"ABCD_{label.upper()}"
            if not isinstance(variants_present, dict) or variant_key not in variants_present:
                per_variant[label] = None
                continue
            statuses = [
                str(check.get("status")) for check in checks
                if isinstance(check, dict) and str(check.get("id", "")).startswith(prefix)
            ]
            status = "PASS" if statuses and all(s == "PASS" for s in statuses) else ("FAIL" if statuses else None)
            per_variant[label] = {"status": status, "n_checks": len(statuses)}
        result[match.group(1)] = {"per_variant": per_variant, "path": str(path)}
    return result


def _n3_smoke_cell(variant_data: dict[str, Any] | None, label: str) -> str:
    if not variant_data:
        return f"⏳ não evidenciado (variante {label.upper()} não gerada para este item)"
    status = variant_data.get("status")
    symbol = "✅" if status == "PASS" else ("❌" if status == "FAIL" else "❔")
    return f"{symbol} smoke {status or 'N/A'} ({variant_data.get('n_checks', 0)} checks) / QA visual pendente"


def _rag_html_ingestion_by_item(
    repo_root: Path, *, project_id: str, obra: str, pavimento: str,
) -> dict[str, dict[str, Any]]:
    """Lê o registro append-only de ingestão multimodal por item (R1).

    Espelha ``qa_fv_quadro_pavimento.py`` (mesmo schema/arquivo, filtro
    ``classe='PIL'`` isolado): R1 registra só que um pacote HTML, seu hash e o
    run QA foram enviados ao contexto RAG local, depois de todas as
    validações do agente QA daquele item. Não é promoção T1, não cria selo
    N1/N3 e nunca alimenta N1/N3. Entradas sem HTML+hash são rejeitadas na
    apresentação para impedir um falso "RAG alimentado".
    """
    path = repo_root / "scripts" / "arete" / "relatorios" / "qa_evidencias" / "rag_html_ingestoes.jsonl"
    if not path.exists():
        return {}
    selected: dict[str, tuple[str, dict[str, Any]]] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        row = _json(raw_line, {})
        if not isinstance(row, dict):
            continue
        if row.get("schema") != "arete.qa_rag_html_ingestion/v1":
            continue
        if row.get("project_id") != project_id or row.get("classe") != "PIL":
            continue
        if row.get("obra") != obra or row.get("pavimento") != pavimento:
            continue
        item = str(row.get("item") or "").upper()
        if not item or not row.get("html_path") or not row.get("html_sha256"):
            continue
        stamp = str(row.get("recorded_at") or row.get("ingested_at") or "")
        if item not in selected or stamp > selected[item][0]:
            selected[item] = (stamp, row)
    return {item: row for item, (_, row) in selected.items()}


def _rag_html_status(entry: dict[str, Any] | None) -> str:
    if not entry:
        return "⏳ RAG HTML: NÃO registrado / ingestão pendente"
    status = str(entry.get("status") or "INGESTED_T0").upper()
    if status not in {"INGESTED_T0", "T1_PROMOTED"}:
        return f"⏳ RAG HTML: NÃO ({status})"
    tier = "T1 curado" if status == "T1_PROMOTED" else "T0 contextual"
    symbol = "✅" if status == "T1_PROMOTED" else "🕗"
    return (
        f"{symbol} RAG HTML: SIM ({tier})\n"
        f"HTML: {entry['html_path']}\n"
        f"SHA-256: {entry['html_sha256']}\n"
        f"Run QA: {entry.get('qa_run_id') or 'não informado'}"
    )


def _n2_campos(ficha: dict[str, Any] | None) -> str:
    if not ficha:
        return "⏳ não há ficha N2 (motor reverso ainda não extraiu)"
    comprimento = ficha.get("comprimento")
    largura = ficha.get("largura")
    altura = ficha.get("altura")
    faces_preenchidas = [
        face for face in _PIL_FACES
        if any(float(ficha.get(f"{prefix}_{face}", 0) or 0) != 0.0 for prefix in ("h2", "larg1"))
    ]
    # "Feito" aqui = motor_reverso_pil já extraiu seção/faces desta ficha — a
    # condição real para gerar N4 a partir dela, não uma decisão humana (essa
    # é a coluna "N2 — ficha", que lê o aceite do recorte).
    extraido = bool(comprimento) and bool(largura) and faces_preenchidas
    symbol = "✅" if extraido else "⚠"
    nota = " — pronta para gerar N4" if extraido else " — extração incompleta (seção/faces faltando)"
    return (
        f"{symbol} Seção declarada: {_number(comprimento)}×{_number(largura)} cm; altura {_number(altura)} cm{nota}\n"
        f"Faces preenchidas: {len(faces_preenchidas)} ({', '.join(faces_preenchidas) or '-'})"
    )


def _n2_ficha_status(ficha_row: sqlite3.Row | None, recorte_status: str | None) -> str:
    """Aceite do N2 tem duas fontes reais e distintas no banco.

    ``reverse_eng_fichas.status/aprovado_at`` nunca foi usado neste projeto
    (todas as 906 fichas do DB inteiro estão em 'draft'/'extracted'). O aceite
    real que o dono faz no app é no RECORTE (`_on_aprovar`/`_on_aprovar_auto`
    em diagnostic_reverse_hub.py), persistido em `reverse_eng_recortes.status`
    ('aprovado'/'auto_aprovado'), casado aqui por `recorte_path` exato (mesma
    string em ambas as tabelas). Perdê-lo faria uma aprovação real do dono
    aparecer como "NÃO" — achado corrigido em 2026-07-16.
    """
    if ficha_row is None:
        return "⏳ NÃO (sem ficha N2 persistida)"
    aprovado_ficha = bool(ficha_row["aprovado_at"]) or str(ficha_row["status"] or "").lower() in {"aprovado", "approved", "validated", "valid"}
    aprovado_recorte = recorte_status in {"aprovado", "auto_aprovado"}
    symbol = "✅" if (aprovado_ficha or aprovado_recorte) else "⏳"
    if aprovado_recorte:
        origem = "recorte aprovado manualmente" if recorte_status == "aprovado" else "recorte auto-aprovado"
        estado = f"SIM ({origem})"
    elif aprovado_ficha:
        estado = "SIM (ficha aprovada)"
    else:
        estado = f"NÃO (ficha: {ficha_row['status'] or 'sem status'}; recorte: {recorte_status or 'sem registro'})"
    return f"{symbol} {estado}\nconfiança extração: {_number(ficha_row['confianca'])}"


def _decisions_by_field(decisions: list[Decision]) -> dict[str, Decision]:
    return {decision.field_id: decision for decision in decisions}


def _resolved_but_pending_apply(decision: Decision | None) -> bool:
    return bool(decision) and decision.decision in {"CONFIRMAR", "N/A_CONFIRMADO"} and bool(decision.operations)


def _seal_counts_for_ids(field_ids: list[str], origins_by_field: dict[str, set[str]]) -> dict[str, int]:
    counts = {"azul": 0, "laranja": 0, "rosa": 0}
    for field_id in field_ids:
        for seal in {FIELD_ORIGIN_TO_SEAL[o] for o in origins_by_field.get(field_id, set()) if o in FIELD_ORIGIN_TO_SEAL}:
            counts[seal] += 1
    return counts


def _family_geometria(decision: Decision | None, origins_by_field: dict[str, set[str]]) -> str:
    """Única família travada (``pilar_segs``): mostra os 3 selos possíveis
    (azul/laranja/rosa — qualquer origem serve) para este 1 campo."""
    if decision is None:
        return "❔ polígono: sem decisão do adaptador"
    symbol = _decision_symbol(decision)
    counts = _seal_counts_for_ids(["pilar_segs"], origins_by_field)
    locked = sum(counts.values()) > 0 and decision.decision == "CONFIRMAR"
    lock_note = "\n🔒 geometria aprovada — não é substituída em reanálise" if locked else ""
    selo_line = f"🔵 Azul {counts['azul']}/1 · 🟠 Laranja {counts['laranja']}/1 · 🌸 Rosa {counts['rosa']}/1"
    return f"{symbol} Polígono (pilar_segs): {decision.decision} — {decision.reason}{lock_note}\n{selo_line}"


def _campos_seal_summary(field_ids: list[str], origins_by_field: dict[str, set[str]]) -> str:
    """Cobertura de selo por campo/vínculo reescrevível (seção, rótulo,
    vigas/lajes, faces l1_n/v) — total + quantos têm cada selo, sem descrever
    campo a campo (isso já está em ``etapa_proxima``, que aponta o primeiro
    bloqueio real). Nível, convenção, visão/corte e continuidade ficam fora
    da contagem: não têm adaptador que produza uma decisão/selo por campo.
    """
    counts = _seal_counts_for_ids(field_ids, origins_by_field)
    total = len(field_ids)
    return (
        f"Total de campos analisados: {total}\n"
        f"🔵 Selo Azul: {counts['azul']}/{total}\n"
        f"🟠 Selo Laranja: {counts['laranja']}/{total}\n"
        f"🌸 Selo Rosa: {counts['rosa']}/{total}"
    )


def _visual_cli_verdict_line(verdict: dict[str, Any] | None) -> str:
    """Linha curta de veredito CLI (usada dentro do card N4 para G2-V n2×n4)."""
    if not verdict:
        return "⏳ não registrado / QA pendente"
    symbol = {"PASS": "✅", "SUSPEITO": "⚠", "FAIL": "❌"}.get(str(verdict["veredito"]).upper(), "❔")
    fonte = verdict.get("fonte_imagem") or "?"
    fonte_note = " ⚠ captura PNG (html_ficha), não SVG-vetorial" if fonte != "html_svg_vetorial" else " (SVG-vetorial)"
    return f"{symbol} {verdict['veredito']} (confiança {_number(verdict.get('confianca'))}){fonte_note}"


_N1V_CHECKLIST_KEYS = (
    "fonte_atual_confirmada", "recorte_alvo_preciso", "contorno_area_interna",
    "cotas_valores", "cotas_posicao_legibilidade", "linhas_paineis", "hlaz",
    "hachuras_apoio", "sem_contaminacao_vizinha",
)


def _n1v_checklist_cell(verdict: dict[str, Any] | None) -> str:
    """N1-V CLI: validação VISUAL da interpretação N1 (não é comparação de
    ficha N1×N2 — essa é a coluna ``Ficha N1×N2``, diagnóstico automático).

    O agente CLI lê a ficha N1 junto das imagens do próprio SA (contexto
    próximo e distante) e confirma, item a item, o checklist real do
    ``g2v_harness`` (9 itens: fonte/recorte/contorno/cotas/linhas/hlaz/
    hachuras/contaminação). Só o agente faz essa leitura — por isso só existe
    selo laranja aqui (nunca azul/rosa/verde), e cada item confirmado True
    conta como 1/9 selado.
    """
    if not verdict:
        return "⏳ não registrado / QA pendente"
    checklist = verdict.get("checklist") or {}
    total = len(_N1V_CHECKLIST_KEYS)
    confirmed = sum(1 for key in _N1V_CHECKLIST_KEYS if checklist.get(key) is True)
    symbol = "✅" if confirmed == total else ("⚠" if confirmed > 0 else "⏳")
    fonte = verdict.get("fonte_imagem") or "?"
    fonte_note = " ⚠ captura PNG (html_ficha), não SVG-vetorial" if fonte != "html_svg_vetorial" else " (SVG-vetorial)"
    return (
        f"{symbol} 🟠 Selo Laranja (só o agente CLI valida): {confirmed}/{total} itens do checklist visual confirmados{fonte_note}\n"
        f"Veredito geral do agente: {verdict['veredito']} (confiança {_number(verdict.get('confianca'))})"
    )


def _n4_g2_g2v_passa(n4_seals: set[str], g2_lote: str, g2v_n2xn4: dict[str, Any] | None) -> str:
    """N4 só existe como PASSA neste pipeline (ver ``_n4_g2_g2v_para``).

    N4 admite só 2 selos (azul=humano_app, laranja=qa_agente — nunca
    verde/rosa, que são de N1/N3); mostra os dois sempre, separados, em vez
    de um SIM/NÃO combinado.
    """
    azul = "azul" in n4_seals
    laranja = "laranja" in n4_seals
    linhas = [
        f"{'✅' if azul else '⏳'} 🔵 Selo Azul (humano/app): {'SIM' if azul else 'NÃO'}",
        f"{'✅' if laranja else '⏳'} 🟠 Selo Laranja (QA agente): {'SIM' if laranja else 'NÃO'}",
        f"G2 (paridade canônica, lote): {g2_lote}",
    ]
    g2v = _visual_cli_verdict_line(g2v_n2xn4) if g2v_n2xn4 else "⏳ não registrado / QA pendente"
    linhas.append(f"G2-V CLI (n2×n4) deste item: {g2v}")
    return "\n".join(linhas)


def _n4_g2_g2v_para() -> str:
    """N4-PARA não existe hoje: nenhum gerador N4 (ficha_adapter.py/
    gerar_n4_item.py/gerar_pl_dxf_stog.py) tem ramo PARA/PASSA — cada ficha N2
    produz um único DXF. Só o N3 (a partir do N1) materializa as duas
    variantes via ``PreValidationDialog.materialize_pl_n3_variants``. Célula
    estrutural, não calculada por item — nunca vira ✅/❌ até esse gerador
    existir."""
    return "➖ N/A — pipeline N4 não gera variante PARA (só 1 DXF por ficha N2; PARA/PASSA existe só no N3)"


def _n3_n4_ficha_para() -> str:
    """Mesma razão estrutural de ``_n4_g2_g2v_para``: sem N4-PARA não há o que
    comparar contra N3-PARA nesta variante. Célula estática, nunca por item."""
    return "➖ N/A — pipeline N4 não gera variante PARA (comparação G5-V só existe contra a variante única de N4)"


def _n3_n4_ficha_passa(g2v_n3xn4: dict[str, Any] | None) -> str:
    """G5-V (n3×n4): único veredito por item do ``g2v_harness.py --par
    n3xn4`` — o card N3 do harness já mostra as duas variantes (PARA e PASSA)
    lado a lado contra o único N4; não há um veredito separado por variante,
    por isso a leitura inteira cai na coluna PASSA (mesma convenção da coluna
    N4 acima: N4 é tratado como o lado único, "passa", do par)."""
    if not g2v_n3xn4:
        return "⏳ não comparada / QA pendente"
    return f"G5-V CLI (n3×n4) deste item: {_visual_cli_verdict_line(g2v_n3xn4)}"


def _n3_n2_ficha(g2v_n3xn2: dict[str, Any] | None) -> str:
    """S7-N3N2 (n3×n2): diagnóstico auxiliar do ``g2v_harness.py --par
    n3xn2`` — ao contrário de N4, o N3-PARA existe de verdade (é o N3-PASSA
    que também existe; ambos vêm só do N1, N2 nunca alimenta o motor N3).
    O card do harness mostra as duas variantes (N3-mode1 e N3-mode2) lado a
    lado contra o mesmo N2; um único veredito cobre as duas, por isso o
    mesmo texto aparece nas colunas PARA e PASSA (não é célula estática de
    N/A como a de N4 — aqui as duas variantes foram olhadas de verdade)."""
    if not g2v_n3xn2:
        return "⏳ não comparada / QA pendente"
    return f"S7-N3N2 CLI (n3×n2, ambas variantes) deste item: {_visual_cli_verdict_line(g2v_n3xn2)}"


def _next_step(
    pillar_row: dict[str, Any],
    geometria_decision: Decision | None,
    field_decisions: dict[str, Decision],
    face_decisions: dict[str, list[Decision]],
) -> tuple[str, str]:
    if bool(pillar_row.get("is_validated")):
        return "Selado — 100% dos campos obrigatórios com origem qa_agente; revisão humana antes de RAG", "item"
    if geometria_decision is None or geometria_decision.decision != "CONFIRMAR":
        return "S4 — provar/validar geometria do polígono (pilar_segs)", "n1_geometria"
    for field_id, label in (("name", "rótulo"), ("dim", "seção/dimensão"), ("connections", "vigas/lajes adjacentes")):
        decision = field_decisions.get(field_id)
        if decision is None or decision.decision not in {"CONFIRMAR", "N/A_CONFIRMADO"}:
            return f"S5 — resolver campo '{field_id}' ({label}): {decision.decision if decision else 'sem decisão'}", "n1_campos_vinculos"
    for face, decisions in sorted(face_decisions.items()):
        for decision in decisions:
            if decision.decision not in {"CONFIRMAR", "N/A_CONFIRMADO"}:
                return f"S5 — resolver face {face}/{decision.field_id}: {decision.decision}", "n1_campos_vinculos"
    pending_apply_fields = [
        field_id for field_id, decision in field_decisions.items() if _resolved_but_pending_apply(decision)
    ] + [
        decision.field_id
        for decisions in face_decisions.values()
        for decision in decisions
        if _resolved_but_pending_apply(decision)
    ]
    if pending_apply_fields:
        return (
            f"S5 — aplicar decisões já resolvidas (qa_evidence_auditor.py apply): {', '.join(sorted(pending_apply_fields))}",
            "n1_campos_vinculos",
        )
    return "S6 — gerar/validar N3 PARA e PASSA (smoke + G2-V CLI SVG)", "n3_smoke_para"


def build_report(project_id: str, obra: str, pavimento: str, db_path: Path, repo_root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        project = connection.execute("SELECT pavement_name FROM projects WHERE id=?", (project_id,)).fetchone()
        pavimento_tecnico = project["pavement_name"] if project else pavimento
        pillars = load_pillars(connection, project_id)
        beams = load_beams_for_project(connection, project_id)
        slabs = load_slabs(connection, project_id)
        fichas = connection.execute(
            "SELECT elemento_id, campos_json, status, aprovado_at, confianca, recorte_path FROM reverse_eng_fichas "
            "WHERE obra_name=? AND pavimento=? AND classe='PIL' ORDER BY id DESC",
            (obra, pavimento),
        ).fetchall()
        recorte_rows = connection.execute(
            "SELECT recorte_path, status, created_at FROM reverse_eng_recortes "
            "WHERE obra_name=? AND classe='PIL'",
            (obra,),
        ).fetchall()
        n4_policy_rows = connection.execute(
            "SELECT item_id, validation_origin FROM artifact_validation_policies "
            # O Comparison Engine persiste a classe de pilares como PL,
            # enquanto as fichas N2 e este quadro usam PIL. Ambas são a mesma
            # classe canônica; ler as duas evita esconder selo humano já
            # gravado pela UI, sem materializar uma cópia de política.
            "WHERE obra_name=? AND pavimento=? AND classe IN ('PIL', 'PL') AND scope='N4' AND locked=1",
            (obra, pavimento_tecnico),
        ).fetchall()
        n3_policy_rows = connection.execute(
            "SELECT item_id, validation_origin FROM artifact_validation_policies "
            "WHERE obra_name=? AND pavimento=? AND classe IN ('PIL', 'PL') AND scope='N3' AND locked=1",
            (obra, pavimento_tecnico),
        ).fetchall()
    finally:
        connection.close()

    n2_by_item: dict[str, sqlite3.Row] = {}
    for ficha in fichas:
        n2_by_item.setdefault(str(ficha["elemento_id"]), ficha)

    _recorte_priority = {"aprovado": 3, "auto_aprovado": 2, "manual": 1, "motor": 0}
    recorte_status_by_path: dict[str, str] = {}
    for row in recorte_rows:
        path = str(row["recorte_path"] or "")
        status = str(row["status"] or "")
        current = recorte_status_by_path.get(path)
        if current is None or _recorte_priority.get(status, 0) >= _recorte_priority.get(current, 0):
            recorte_status_by_path[path] = status

    diagnostic_path, diagnostic = _find_latest_diagnostic(repo_root, obra, pavimento_tecnico)
    diagnostic_by_item = {str(row.get("item")): row for row in diagnostic.get("itens", []) if isinstance(row, dict)}
    g2_lote, g2_source = _g2_lote_from_status(repo_root, pavimento)
    g2v_n1xn2 = _g2v_by_item(repo_root, pavimento, "n1xn2", "N1-V")
    g2v_n2xn4 = _g2v_by_item(repo_root, pavimento, "n2xn4", "G2-V")
    g2v_n3xn4 = _g2v_by_item(repo_root, pavimento, "n3xn4", "G5-V")
    g2v_n3xn2 = _g2v_by_item(repo_root, pavimento, "n3xn2", "S7-N3N2")
    smoke_by_item = _n3_smokes(repo_root)
    rag_html_by_item = _rag_html_ingestion_by_item(
        repo_root, project_id=project_id, obra=obra, pavimento=pavimento,
    )

    known_items = {pillar.name for pillar in pillars}
    n4_seals_by_item = _policy_seals_by_item(list(n4_policy_rows), known_items, {"azul", "laranja"})
    # N3 admite os 4 selos (política pode ser azul/laranja/rosa; "verde" nunca
    # vem de artifact_validation_policies — só existiria se um flag próprio de
    # N3 fosse persistido, o que não existe hoje; fica honestamente 0/N.
    n3_seals_by_item = _policy_seals_by_item(list(n3_policy_rows), known_items)

    auditor = PilEvidenceAuditor(pillars, beams, slabs, run_id="qa_pil_quadro_pavimento")
    all_decisions = auditor.audit(include_sealed=True)
    decisions_by_item: dict[str, list[Decision]] = {}
    for decision in all_decisions:
        decisions_by_item.setdefault(decision.item, []).append(decision)

    rows: list[dict[str, str]] = []
    sealed_count = 0
    geometria_confirmed = 0
    for pillar in pillars:
        item = pillar.name
        pillar_row = {"is_validated": pillar.is_validated}
        sealed_count += int(pillar.is_validated)
        item_decisions = decisions_by_item.get(item, [])
        by_field = _decisions_by_field([d for d in item_decisions if not d.field_id.startswith("p_s")])
        face_decisions: dict[str, list[Decision]] = {}
        for decision in item_decisions:
            if decision.field_id.startswith("p_s") and len(decision.field_id) > 3:
                face = decision.field_id[3]
                face_decisions.setdefault(face, []).append(decision)
        geometria_decision = by_field.get("pilar_segs")
        if geometria_decision and geometria_decision.decision == "CONFIRMAR":
            geometria_confirmed += 1

        origins_by_field = _field_origins(pillar.raw_columns.get("validated_fields_json"))
        item_seals = _pillar_item_seals(pillar_row, origins_by_field)

        ficha_row = n2_by_item.get(item)
        ficha = _json(ficha_row["campos_json"], {}) if ficha_row else None
        diag_item = diagnostic_by_item.get(item)
        smoke = smoke_by_item.get(item)

        campos_field_ids = ["dim", "name", "connections"] + [
            decision.field_id for decisions in face_decisions.values() for decision in decisions
        ]
        campos_vinculos = _campos_seal_summary(campos_field_ids, origins_by_field)

        etapa, stage_col = _next_step(pillar_row, geometria_decision, by_field, face_decisions)

        recorte_status = recorte_status_by_path.get(str(ficha_row["recorte_path"] or "")) if ficha_row else None
        smoke_para = (smoke or {}).get("per_variant", {}).get("para")
        smoke_passa = (smoke or {}).get("per_variant", {}).get("passa")
        rows.append({
            "item": item,
            "n2_ficha": _n2_ficha_status(ficha_row, recorte_status),
            "n2_campos": _n2_campos(ficha),
            "n4_g2_g2v_para": _n4_g2_g2v_para(),
            "n4_g2_g2v_passa": _n4_g2_g2v_passa(n4_seals_by_item.get(item, set()), g2_lote, g2v_n2xn4.get(item)),
            "n1_geometria": _family_geometria(geometria_decision, origins_by_field),
            "n1_campos_vinculos": campos_vinculos,
            "n1_visual_cli": _n1v_checklist_cell(g2v_n1xn2.get(item)),
            "n1_n2_ficha": _diagnostic_status(diag_item),
            "n3_smoke_para": _n3_smoke_cell(smoke_para, "para"),
            "n3_smoke_passa": _n3_smoke_cell(smoke_passa, "passa"),
            "n3_n4_ficha_para": _n3_n4_ficha_para(),
            "n3_n4_ficha_passa": _n3_n4_ficha_passa(g2v_n3xn4.get(item)),
            "n3_n2_ficha_para": _n3_n2_ficha(g2v_n3xn2.get(item)),
            "n3_n2_ficha_passa": _n3_n2_ficha(g2v_n3xn2.get(item)),
            "selos_n1": ("✅ " if item_seals else "⏳ ") + _item_seal_line(item_seals),
            "selos_n3": ("✅ " if n3_seals_by_item.get(item) else "⏳ ") + _item_seal_line(n3_seals_by_item.get(item, set())),
            "rag_html": _rag_html_status(rag_html_by_item.get(item)),
            "etapa_proxima": etapa,
            "_stage_col": stage_col,
        })

    rows.sort(key=lambda value: _item_key(value["item"]))

    n1_card = {
        "total": len(pillars),
        "seals": _seal_counts(known_items, {
            pillar.name: _pillar_item_seals({"is_validated": pillar.is_validated}, _field_origins(pillar.raw_columns.get("validated_fields_json")))
            for pillar in pillars
        }),
    }
    n2_card = {"total": len(n2_by_item), "seals": _seal_counts(set(n2_by_item), {item: n4_seals_by_item.get(item, set()) for item in n2_by_item})}
    n4_card = {"total": len(n2_by_item), "seals": n2_card["seals"]}
    n3_card = {"total": len(smoke_by_item), "seals": {seal: 0 for seal in SEAL_ORDER}}

    summary = {
        "schema": "arete.qa_pil_quadro_pavimento/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only",
        "project_id": project_id,
        "obra": obra,
        "pavimento": pavimento,
        "pavimento_tecnico": pavimento_tecnico,
        "items_n1": len(rows),
        "items_n2": len(n2_by_item),
        "items_sealed": sealed_count,
        "items_geometria_confirmada": geometria_confirmed,
        "n4_policy_rows": len(n4_policy_rows),
        "n3_policy_rows": len(n3_policy_rows),
        "levels": {"n1": n1_card, "n2": n2_card, "n3": n3_card, "n4": n4_card},
        "diagnostic_path": str(diagnostic_path) if diagnostic_path else None,
        "diagnostic_items": len(diagnostic_by_item),
        "g2_lote": g2_lote,
        "g2_source": g2_source,
        "limits": [
            "N2/N4 nunca alimentam N1/N3; leitura apenas comparativa.",
            (
                f"artifact_validation_policies registra {len(n4_policy_rows)} política(s) N4 "
                f"e {len(n3_policy_rows)} política(s) N3 para PIL/PL neste escopo; "
                "os selos do quadro são leitura direta dessas políticas."
                if n4_policy_rows or n3_policy_rows
                else "artifact_validation_policies não tem política N4/N3 para PIL/PL neste escopo; "
                "os selos aparecem honestamente como 0, não como erro."
            ),
            "G2-V (n2xn4) PIL ainda usa captura PNG (html_ficha)/dxf_render nos relatórios canônicos existentes — não há relatório com fonte_imagem=='html_svg_vetorial' para este par ainda. G5-V (n3xn4) e S7-N3N2 (n3xn2) já usam o pipeline SVG-vetorial real (evidence-card construído em 2026-07-16, 35/35 itens lidos pelo agente CLI cada) — ver colunas N3×N4 PASSA e N3×N2 PARA/PASSA. N1-V (n1xn2) foi descontinuado como gate para PIL: os cards N1 são geometria bruta do SA, não ficha comparável a N2 (docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md:224-226) — coluna N1 Visual CLI fica honestamente pendente até um novo desenho de N1-V.",
            "Nível e convenção NASCE/MORRE/SEGUE são exibidos como persistidos, mas não têm adaptador _audit_* dedicado ainda — não geram CONFIRMAR/PENDENTE.",
            "Continuidade entre pavimentos está fora de escopo deste quadro (mono-pavimento 13_PAV); nunca inferida por proximidade de nome/posição.",
            "Geometria (pilar_segs) confirmada e validada (qa_agente) é sinalizada como não-regravável; campos/vínculos (seção, nível, convenção, faces, vigas/lajes, corte) continuam reescrevíveis em reanálise.",
            "Decisões vêm de uma execução em memória do PilEvidenceAuditor (mesma leitura de 'qa_evidence_auditor.py review'), sem headless, sem gerar DXF e sem gravar no DB.",
        ],
    }
    return summary, rows


def _status_class(value: str) -> str:
    normalized = value.lower()
    if "revisar_humano" in normalized or "⚠" in value or "fail" in normalized:
        return "fail"
    if "pendente" in normalized or "não evidenciado" in normalized or "não comparada" in normalized or "não registrado" in normalized or "não persistido" in normalized:
        return "pending"
    if "confirmar" in normalized or "sim" in normalized or "pass" in normalized or "selado" in normalized:
        return "pass"
    return "neutral"


def _level_card_html(level: str, card: dict[str, Any], note: str, *, g2_lote: str | None = None) -> str:
    seal_order = ("azul", "laranja") if level == "n4" else SEAL_ORDER
    colors = {"azul": ("Azul", "blue"), "laranja": ("Laranja", "orange"), "verde": ("Verde", "green"), "rosa": ("Rosa", "pink")}
    badges = "".join(f'<span class="seal {css}">{label}: {card["seals"][seal]}</span>' for seal in seal_order for label, css in [colors[seal]])
    g2 = f'<small class="g2">G2 (paridade canônica): {html.escape(g2_lote)}</small>' if g2_lote else ""
    return (
        f'<article class="card level-card {level}"><span>{"N1 / SA" if level == "n1" else level.upper()} — Pilares</span>'
        f'<strong>Total: {card["total"]}</strong><div class="seals">{badges}</div>'
        f'<small>{html.escape(note)}</small>{g2}</article>'
    )


def _level_cards_html(levels: dict[str, dict[str, Any]], *, g2_lote: str | None = None) -> str:
    return "\n".join([
        _level_card_html("n2", levels["n2"], "Azul/laranja herdados read-only da política N4 correspondente; não regrava a ficha N2."),
        _level_card_html("n4", levels["n4"], "N4 só admite azul (humano) e laranja (QA); G2/G2-V ficam neste card.", g2_lote=g2_lote),
        _level_card_html("n1", levels["n1"], "Selos N1 lidos do estado persistido de pillars.validated_fields_json/is_validated."),
        _level_card_html("n3", levels["n3"], "Total somente de N3 com smoke persistido para este item."),
    ])


def _header_cell_html(key: str, label: str) -> str:
    stage, description = COLUMN_META.get(key, (None, ""))
    stage_badge = f'<span class="stage-tag">{html.escape(stage)}</span> ' if stage else ""
    desc_html = f'<br><small class="col-desc">{html.escape(description)}</small>' if description else ""
    return f'<th class="col-{key}">{stage_badge}{html.escape(label)}{desc_html}</th>'


def write_html_report(summary, rows, headers, output_dir: Path, markdown_path: Path, csv_path: Path, json_path: Path) -> Path:
    html_path = output_dir / "QUADRO-PIL-PAVIMENTO.html"
    current_cards = _level_cards_html(summary["levels"], g2_lote=str(summary["g2_lote"]))
    head = "".join(_header_cell_html(key, label) for key, label in headers)
    legend_rows = "".join(
        f'<tr><td>{html.escape(stage)}</td><td>{html.escape(STAGE_DEFINITIONS[stage])}</td></tr>'
        for stage in sorted(STAGE_DEFINITIONS)
    )
    column_legend_rows = "".join(
        f'<tr><td>{html.escape(label)}</td><td>{html.escape(COLUMN_META.get(key, (None, ""))[0] or "—")}</td>'
        f'<td>{html.escape(COLUMN_META.get(key, (None, ""))[1] or "—")}</td></tr>'
        for key, label in headers
    )
    column_widths = {
        "etapa_proxima": 300, "item": 90, "n2_ficha": 220, "n2_campos": 260,
        "n4_g2_g2v_para": 220, "n4_g2_g2v_passa": 300, "n1_geometria": 260, "n1_campos_vinculos": 460,
        "n1_visual_cli": 240, "n1_n2_ficha": 300, "n3_smoke_para": 240, "n3_smoke_passa": 240,
        "n3_n4_ficha_para": 200, "n3_n4_ficha_passa": 200, "n3_n2_ficha_para": 200, "n3_n2_ficha_passa": 200,
        "selos_n1": 240, "selos_n3": 240, "rag_html": 320,
    }
    columns = "".join(f'<col style="width:{column_widths.get(key, 220)}px">' for key, _ in headers)
    body_rows = []
    for row in rows:
        cells = []
        for key, _ in headers:
            value = row[key]
            classes = ["col-" + key, _status_class(value)]
            if key == "etapa_proxima":
                classes.append("stage-" + row.get("_stage_col", "item"))
            cells.append(f'<td class="{" ".join(classes)}">{_html_cell(value)}</td>')
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    table_body = "\n".join(body_rows)
    diagnostic = html.escape(str(summary.get("diagnostic_path") or "não encontrado"))
    refresh = html.escape(
        "python scripts/arete/qa_pil_quadro_pavimento.py "
        f"--project-id {summary['project_id']} --obra {summary['obra']} --pav {summary['pavimento']} "
        "--output-dir <diretório>"
    )
    html_path.write_text(
        f'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quadro QA PIL — {html.escape(summary['obra'])} / {html.escape(summary['pavimento'])}</title>
  <style>
    :root {{ color-scheme: dark; --bg:#10151d; --panel:#182231; --line:#30445c; --text:#eaf2fc; --muted:#a8b8ca; --pass:#166534; --fail:#991b1b; --pending:#854d0e; --neutral:#253548; --accent:#22d3ee; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--text); font:14px/1.45 Inter,Segoe UI,Arial,sans-serif; }}
    main {{ max-width:100%; padding:24px; }} h1 {{ margin:0 0 4px; font-size:26px; }} h2 {{ margin:28px 0 12px; font-size:19px; }}
    .meta {{ color:var(--muted); margin:0; }} .meta code {{ color:var(--accent); }}
    .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:12px; margin-top:22px; }}
    .card {{ min-height:152px; padding:14px; border:1px solid var(--line); border-radius:10px; background:var(--panel); }}
    .card span,.card small {{ display:block; color:var(--muted); }} .card strong {{ display:block; margin:8px 0; color:var(--accent); font-size:21px; }}
    .seals {{ display:flex; flex-wrap:wrap; gap:6px; margin:0 0 10px; }} .seal {{ display:inline-block; padding:2px 7px; border-radius:999px; font-size:12px; font-weight:700; }}
    .seal.blue {{ background:#153f70; color:#9ed7ff; }} .seal.orange {{ background:#663d0b; color:#ffd08a; }} .seal.green {{ background:#164b32; color:#9cf0bb; }} .seal.pink {{ background:#6c245b; color:#ffc4ec; }} .g2 {{ margin-top:9px; color:#d6e5f6 !important; }}
    .table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:10px; background:var(--panel); }}
    table {{ border-collapse:collapse; table-layout:fixed; min-width:3200px; width:3200px; }} th,td {{ padding:10px; border-right:1px solid var(--line); border-bottom:1px solid var(--line); text-align:left; vertical-align:top; white-space:normal; overflow-wrap:anywhere; word-break:normal; line-height:1.5; }}
    th {{ position:sticky; top:0; z-index:2; background:#223047; color:#f7fbff; font-size:12px; }} tr:hover td {{ outline:1px solid #3d648a; }} td:first-child {{ position:sticky; left:0; z-index:1; font-weight:700; background:#223047; }}
    td.pass {{ background:color-mix(in srgb,var(--pass) 38%,var(--panel)); }} td.fail {{ background:color-mix(in srgb,var(--fail) 31%,var(--panel)); }} td.pending {{ background:color-mix(in srgb,var(--pending) 33%,var(--panel)); }} td.neutral {{ background:var(--neutral); }}
    .col-etapa_proxima {{ --column:#94a3b8; }} .col-item {{ --column:#64748b; }} .col-n2_ficha {{ --column:#0ea5e9; }} .col-n2_campos {{ --column:#14b8a6; }} .col-n4_g2_g2v_para {{ --column:#6d28d9; }} .col-n4_g2_g2v_passa {{ --column:#8b5cf6; }} .col-n1_geometria {{ --column:#f43f5e; }} .col-n1_campos_vinculos {{ --column:#f59e0b; }} .col-n1_visual_cli {{ --column:#eab308; }} .col-n1_n2_ficha {{ --column:#38bdf8; }} .col-n3_smoke_para {{ --column:#15803d; }} .col-n3_smoke_passa {{ --column:#22c55e; }} .col-n3_n4_ficha_para {{ --column:#7c3aed; }} .col-n3_n4_ficha_passa {{ --column:#a855f7; }} .col-n3_n2_ficha_para {{ --column:#db2777; }} .col-n3_n2_ficha_passa {{ --column:#ec4899; }} .col-selos_n1 {{ --column:#6366f1; }} .col-selos_n3 {{ --column:#0d9488; }} .col-rag_html {{ --column:#0f766e; }}
    th[class*="col-"] {{ background:color-mix(in srgb,var(--column) 36%,#182231); }} td[class*="col-"] {{ background:color-mix(in srgb,var(--column) 18%,var(--panel)); box-shadow:inset 3px 0 var(--column); }} td[class*="col-"].pass {{ background:color-mix(in srgb,var(--pass) 48%,var(--column)) !important; }} td[class*="col-"].fail {{ background:color-mix(in srgb,var(--fail) 48%,var(--column)) !important; }} td[class*="col-"].pending {{ background:color-mix(in srgb,var(--pending) 48%,var(--column)) !important; }} td[class*="col-"].neutral {{ background:color-mix(in srgb,var(--column) 22%,var(--panel)) !important; }} td.col-etapa_proxima {{ font-weight:700; }}
    td.stage-item {{ --column:#64748b; }} td.stage-n1_geometria {{ --column:#f43f5e; }} td.stage-n1_campos_vinculos {{ --column:#f59e0b; }} td.stage-n1_visual_cli {{ --column:#eab308; }} td.stage-n3_smoke_para {{ --column:#15803d; }}
    td.col-etapa_proxima[class*="stage-"] {{ background:color-mix(in srgb,var(--column) 42%,var(--panel)) !important; box-shadow:inset 4px 0 #f8fafc; }}
    details {{ margin-top:20px; padding:14px; border:1px solid var(--line); border-radius:10px; background:var(--panel); }} summary {{ cursor:pointer; color:var(--accent); font-weight:700; }} .links a {{ color:var(--accent); margin-right:16px; }} pre {{ white-space:pre-wrap; color:#d6e5f6; }}
    .stage-tag {{ display:inline-block; padding:1px 6px; border-radius:999px; background:#0f2942; color:#7dd3fc; font-size:11px; font-weight:800; }}
    small.col-desc {{ display:block; margin-top:4px; color:#c7d4e3; font-size:11px; font-weight:400; white-space:normal; }}
    .legend-table {{ width:100%; border-collapse:collapse; margin-top:8px; }} .legend-table th, .legend-table td {{ border:1px solid var(--line); padding:6px 10px; text-align:left; font-size:13px; vertical-align:top; }} .legend-table th {{ background:#223047; }}
  </style>
</head>
<body><main>
  <h1>Quadro QA — Pilares</h1>
  <p class="meta">Escopo: <code>{html.escape(summary['obra'])}/{html.escape(summary['pavimento'])}/PIL</code> · project-id <code>{html.escape(summary['project_id'])}</code> · pavimento técnico <code>{html.escape(summary['pavimento_tecnico'])}</code> · modo <code>read_only</code> · gerado em <code>{html.escape(summary['generated_at'])}</code></p>
  <h2>Pavimento atual em treino/análise — {html.escape(summary['obra'])} / {html.escape(summary['pavimento'])}</h2>
  <p class="meta">Este é o escopo ativo do relatório e do próximo ciclo de trabalho. {summary['items_sealed']}/{summary['items_n1']} pilares selados; {summary['items_geometria_confirmada']}/{summary['items_n1']} com geometria (polígono) já confirmada pelo adaptador.</p>
  <section class="cards">{current_cards}</section>
  <details open><summary>Legenda — estágios S0–S8/R1 e o que cada coluna contém</summary>
    <p class="meta">✅ = confirmado/N-A já persistido com alguma origem (azul/laranja/rosa — qualquer uma conta como validado) · 🕗 = confirmado pelo adaptador mas o <code>apply</code> ainda não rodou · ⚠ = REVISAR_HUMANO (motor e persistido divergem) · ⏳ = PENDENTE/ainda sem evidência · ➖ = N/A ou fora de escopo · ❔ = sem decisão do adaptador.</p>
    <table class="legend-table"><thead><tr><th>Estágio</th><th>Definição</th></tr></thead><tbody>{legend_rows}</tbody></table>
    <table class="legend-table"><thead><tr><th>Coluna</th><th>Estágio</th><th>O que ela mostra</th></tr></thead><tbody>{column_legend_rows}</tbody></table>
  </details>
  <h2>Itens do pavimento atual de trabalho — {html.escape(summary['obra'])} / {html.escape(summary['pavimento'])} / PIL ({summary['items_n1']} linhas)</h2>
  <div class="table-wrap"><table><colgroup>{columns}</colgroup><thead><tr>{head}</tr></thead><tbody>{table_body}</tbody></table></div>
  <details><summary>Proveniência, limites e atualização</summary>
    <p>Diagnóstico canônico lido: <code>{diagnostic}</code></p>
    <ul>{''.join(f'<li>{html.escape(limit)}</li>' for limit in summary['limits'])}</ul>
    <p>G2-V, N1-V e G5-V são vereditos visuais via <code>g2v_harness.py --backend cli</code>, lidos pelo modelo/agente CLI nos SVGs (PIL ainda em captura PNG legada — ver limites acima).</p>
    <p class="links"><a href="{markdown_path.name}">Markdown</a><a href="{csv_path.name}">CSV</a><a href="{json_path.name}">JSON de proveniência</a></p>
    <pre>{refresh}</pre>
  </details>
</main></body></html>\n''',
        encoding="utf-8",
    )
    return html_path


def write_report(summary: dict[str, Any], rows: list[dict[str, str]], output_dir: Path) -> tuple[Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "QUADRO-PIL-PAVIMENTO.md"
    csv_path = output_dir / "QUADRO-PIL-PAVIMENTO.csv"
    json_path = output_dir / "QUADRO-PIL-PAVIMENTO.json"
    headers = [
        ("etapa_proxima", "Etapa atual / próximo passo"),
        ("item", "Item"),
        ("n2_ficha", "N2 — ficha (validação/estado técnico)"),
        ("n2_campos", "Ficha N2 — seção/faces (comparação)"),
        ("n4_g2_g2v_para", "N4-PARA deste item — validação / G2 / G2-V CLI"),
        ("n4_g2_g2v_passa", "N4-PASSA deste item — validação / G2 / G2-V CLI"),
        ("n1_geometria", "N1 — geometria/polígono (aprovada = travada)"),
        ("n1_campos_vinculos", "N1 — campos/vínculos (cobertura de selo Azul/Laranja/Rosa)"),
        ("n1_visual_cli", "N1-V CLI — validação visual da interpretação N1"),
        ("n1_n2_ficha", "Ficha N1×N2 (comparada / QA)"),
        ("n3_smoke_para", "N3-PARA — smoke"),
        ("n3_smoke_passa", "N3-PASSA — smoke"),
        ("n3_n4_ficha_para", "Ficha N3-PARA×N4 (comparada / QA)"),
        ("n3_n4_ficha_passa", "Ficha N3-PASSA×N4 (comparada / QA)"),
        ("n3_n2_ficha_para", "Ficha N3-PARA×N2 (comparada / QA)"),
        ("n3_n2_ficha_passa", "Ficha N3-PASSA×N2 (comparada / QA)"),
        ("selos_n1", "Selos N1 do item"),
        ("selos_n3", "Selos N3 do item"),
        ("rag_html", "R1 — RAG multimodal: HTML pós-QA, hash e ingestão registrada"),
    ]
    # Sufixo de estágio só para MD/CSV (texto plano); o HTML já mostra o
    # estágio como badge visual separado do rótulo (ver _header_cell_html).
    text_headers = [
        (key, f"{label} [{COLUMN_META[key][0]}]" if COLUMN_META.get(key, (None, ""))[0] else label)
        for key, label in headers
    ]
    rows_for_output = [{key: row[key] for key, _ in text_headers} for row in rows]

    def markdown_seals(levels: dict[str, dict[str, Any]], level: str) -> str:
        order = ("azul", "laranja") if level == "n4" else SEAL_ORDER
        return "; ".join(f"{seal}={levels[level]['seals'][seal]}" for seal in order)

    mini_rows = [
        ("N2 — Fichas PIL", f"total={summary['levels']['n2']['total']}; {markdown_seals(summary['levels'], 'n2')}", "azul/laranja herdados read-only da política N4 correspondente"),
        ("N4 — Pilares", f"total={summary['levels']['n4']['total']}; {markdown_seals(summary['levels'], 'n4')}", f"G2 (paridade canônica): {summary['g2_lote']}; N4 só azul/laranja; n4_policy_rows={summary['n4_policy_rows']}"),
        ("N1 / SA — Pilares", f"total={summary['levels']['n1']['total']}; {markdown_seals(summary['levels'], 'n1')}", f"selados={summary['items_sealed']}; geometria confirmada={summary['items_geometria_confirmada']}"),
        ("N3 — Pilares", f"total={summary['levels']['n3']['total']}; {markdown_seals(summary['levels'], 'n3')}", "somente N3 com smoke persistido"),
    ]
    lines = [
        "# Quadro QA — Pilares por pavimento", "",
        f"- Escopo: `{summary['obra']}/{summary['pavimento']}/PIL`", f"- Project ID: `{summary['project_id']}`",
        f"- Pavimento técnico: `{summary['pavimento_tecnico']}`",
        f"- Modo: `{summary['mode']}`; gerado em `{summary['generated_at']}`", "",
        "## Legenda — estágios S0–S8 e R1", "",
        "✅ = confirmado/N-A já persistido com alguma origem (azul/laranja/rosa — qualquer uma conta como validado) · "
        "🕗 = confirmado pelo adaptador mas o `apply` ainda não rodou · ⚠ = REVISAR_HUMANO (motor e persistido divergem) · "
        "⏳ = PENDENTE/sem evidência ainda · ➖ = N/A ou fora de escopo · ❔ = sem decisão do adaptador.", "",
        "| Estágio | Definição |", "|---|---|",
    ]
    lines.extend(f"| {stage} | {_cell(STAGE_DEFINITIONS[stage])} |" for stage in sorted(STAGE_DEFINITIONS))
    lines.extend(["", "## Legenda — o que cada coluna contém", "", "| Coluna | Estágio | Conteúdo |", "|---|---|---|"])
    lines.extend(
        f"| {_cell(label)} | {COLUMN_META.get(key, (None, ''))[0] or '—'} | {_cell(COLUMN_META.get(key, (None, ''))[1] or '—')} |"
        for key, label in headers
    )
    lines.extend(["", "## Pavimento atual em treino/análise", "", "| Métrica | Valor | Fonte/limite |", "|---|---:|---|"])
    lines.extend(f"| {_cell(metric)} | {_cell(value)} | {_cell(source)} |" for metric, value, source in mini_rows)
    lines.extend(["", f"## Itens do pavimento atual de trabalho — {summary['obra']} / {summary['pavimento']} / PIL", "",
                  "| " + " | ".join(label for _, label in text_headers) + " |", "|" + "|".join("---" for _ in text_headers) + "|"])
    for row in rows_for_output:
        lines.append("| " + " | ".join(_cell(row[key]) for key, _ in text_headers) + " |")
    lines.extend([
        "", "## Limites de evidência", "",
        *[f"- {limit}" for limit in summary["limits"]], "",
        "G2-V, N1-V e G5-V são vereditos visuais via `g2v_harness.py --backend cli`, lidos pelo modelo/agente CLI nos SVGs.",
    ])
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[key for key, _ in headers])
        writer.writeheader()
        writer.writerows(rows_for_output)
    json_path.write_text(json.dumps({"summary": summary, "items": rows_for_output}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path = write_html_report(summary, rows, headers, output_dir, markdown_path, csv_path, json_path)
    return markdown_path, csv_path, json_path, html_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--obra", required=True)
    parser.add_argument("--pav", required=True)
    parser.add_argument("--db", type=Path, default=Path(r"D:\Agente-cad-PYSIDE\project_data.vision"))
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary, rows = build_report(args.project_id, args.obra, args.pav, args.db, args.repo_root)
    markdown_path, csv_path, json_path, html_path = write_report(summary, rows, args.output_dir)
    print(json.dumps({"summary": summary, "reports": [str(html_path), str(markdown_path), str(csv_path), str(json_path)]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
