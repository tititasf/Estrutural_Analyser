#!/usr/bin/env python3
"""Quadro read-only de progresso FV por pavimento.

Não é comparador, gerador, headless ou scorer: apenas consolida o que já está
persistido no DB e nos relatórios canônicos. Estados sem prova permanecem
``PENDENTE``/``não persistido`` para impedir que N2/N4 completem N1 por tabela.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FV_SEGMENT_RE = re.compile(r"^viga_fundo_seg_(\d+)_exists$")
FV_DIM_RE = re.compile(r"^viga_fundo_seg_(\d+)_dim$")
FV_AREA_RE = re.compile(r"^viga_fundo_seg_(\d+)_area_segs$")
POLICY_ITEM_RE = re.compile(r"(?:VF|V)\d+[A-Z]?")
SEAL_ORDER = ("azul", "laranja", "verde", "rosa")
FIELD_ORIGIN_TO_SEAL = {
    "humano_app": "azul",
    "qa_agente": "laranja",
    "qa_agent": "laranja",
    "humano_portal": "rosa",
}


def _empty_seals() -> dict[str, int]:
    return {seal: 0 for seal in SEAL_ORDER}


def _seal_from_origin(origin: Any) -> str | None:
    """Traduz a origem persistida para o selo que ela pode provar.

    As polÃ­ticas N4 sÃ£o registradas pela UI como ``human_ui`` (ou pelo dado
    anterior como ``legacy_human_ui``); ambas sÃ£o confirmaÃ§Ãµes humanas da app e
    portanto azul. A regra Ã© deliberadamente fechada: uma origem desconhecida
    nÃ£o recebe cor por inferÃªncia.
    """
    value = str(origin or "").strip().lower()
    if value in {"human_ui", "legacy_human_ui", "humano_app"}:
        return "azul"
    if value in {"qa_agente", "qa_agent"}:
        return "laranja"
    if value == "humano_portal":
        return "rosa"
    return None


def _policy_items(item_id: Any, known_items: set[str]) -> set[str]:
    """Expande somente agrupamentos N4 persistidos para identidades jÃ¡ conhecidas.

    Ex.: ``V313-V315V-V317`` representa trÃªs fichas; a expansÃ£o nÃ£o inventa
    itens, pois cada token ainda precisa existir no inventÃ¡rio N2/N1 recebido.
    """
    raw = str(item_id or "").upper()
    return {token for token in POLICY_ITEM_RE.findall(raw) if token in known_items}


def _policy_seals_by_item(
    policy_rows: list[sqlite3.Row], known_items: set[str], allowed_seals: set[str] | None = None
) -> dict[str, set[str]]:
    seals = {item: set() for item in known_items}
    for policy in policy_rows:
        seal = _seal_from_origin(policy["validation_origin"])
        if not seal or (allowed_seals is not None and seal not in allowed_seals):
            continue
        for item in _policy_items(policy["item_id"], known_items):
            seals[item].add(seal)
    return seals


def _pavimento_key(value: Any) -> str:
    """Chave estável para aproximar ``13_PAV`` e o nome técnico que contém ``13P``."""
    raw = str(value or "").upper().strip()
    if "TERREO" in raw or "TER" == raw:
        return "TERREO"
    if "FUN" in raw:
        return "FUNDACAO"
    if "TIP" in raw:
        return "TIPO"
    match = re.search(r"(?<!\d)(\d{1,2})\s*(?:_?PAV|P)(?![A-Z])", raw)
    return f"{int(match.group(1))}_PAV" if match else raw


def _policy_seals_by_context(
    policy_rows: list[sqlite3.Row], known_items: set[tuple[str, str, str]], allowed_seals: set[str] | None = None
) -> dict[tuple[str, str, str], set[str]]:
    """Aplica uma política N4/N3 ao item da mesma obra+pavimento+identidade."""
    seals = {item: set() for item in known_items}
    for policy in policy_rows:
        seal = _seal_from_origin(policy["validation_origin"])
        if not seal or (allowed_seals is not None and seal not in allowed_seals):
            continue
        obra = str(policy["obra_name"] or "").upper()
        pavimento = _pavimento_key(policy["pavimento"])
        for item in POLICY_ITEM_RE.findall(str(policy["item_id"] or "").upper()):
            key = (obra, pavimento, item)
            if key in seals:
                seals[key].add(seal)
    return seals


def _seal_counts(items: set[str], seals_by_item: dict[str, set[str]]) -> dict[str, int]:
    return {
        seal: sum(seal in seals_by_item.get(item, set()) for item in items)
        for seal in SEAL_ORDER
    }


def _seal_counts_for_sets(seals_by_item: dict[Any, set[str]]) -> dict[str, int]:
    return {seal: sum(seal in seals for seals in seals_by_item.values()) for seal in SEAL_ORDER}


def _n1_item_seals(beam: dict[str, Any], is_validated: Any) -> set[str]:
    """LÃª apenas selos jÃ¡ persistidos; nunca deduz cobertura por valor de campo."""
    seals: set[str] = set()
    if bool(is_validated) or bool(beam.get("is_validated")):
        seals.add("verde")
    if bool(beam.get("selo_azul")) or bool(beam.get("is_fully_validated")):
        seals.add("azul")
    if bool(beam.get("selo_laranja")):
        seals.add("laranja")
    if bool(beam.get("selo_rosa")):
        seals.add("rosa")
    return seals


def _qa_fv_scope_counts(repo_root: Path, projects_by_id: dict[str, tuple[str, str]]) -> dict[str, Any]:
    """Conta onde o QA-Evidências FV foi realmente executado, pelo log append-only."""
    path = repo_root / "scripts" / "arete" / "relatorios" / "qa_evidencias" / "registro_sessoes.jsonl"
    scopes: set[tuple[str, str]] = set()
    runs = 0
    if not path.exists():
        return {"obras": 0, "pavimentos": 0, "runs": 0, "source": str(path)}
    for raw in path.read_text(encoding="utf-8").splitlines():
        entry = _json(raw, {})
        classes = {value.strip().upper() for value in str(entry.get("classe") or "").split(",")}
        if "FV" not in classes:
            continue
        project = projects_by_id.get(str(entry.get("project_id") or ""))
        if not project:
            continue
        runs += 1
        scopes.add(project)
    return {
        "obras": len({obra for obra, _ in scopes}),
        "pavimentos": len(scopes),
        "runs": runs,
        "source": str(path),
    }


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


def _find_latest_diagnostic(repo_root: Path, obra: str, pavimento: str) -> tuple[Path | None, dict[str, Any]]:
    candidates = list(
        (repo_root / "scripts" / "arete" / "relatorios" / "diagnosticos_fv" / obra / pavimento).glob("**/diagnostico_fv_n1_n2.json")
    )
    if not candidates:
        return None, {}

    # Um diagn\u00f3stico executado diretamente sobre um ``estado_*`` parcial pode
    # listar todos os N2, mas conter N1 apenas para o lote materializado. Isso
    # \u00e9 \u00fatil para depura\u00e7\u00e3o, por\u00e9m n\u00e3o pode substituir a proje\u00e7\u00e3o do
    # quadro e fazer os demais itens parecerem ``N1 ausente``. O headless
    # can\u00f4nico filtra seu relat\u00f3rio parcial e torna os tr\u00eas contadores
    # coerentes. Preferimos sempre esse contrato; s\u00f3 ca\u00edmos no artefato mais
    # novo quando n\u00e3o h\u00e1 nenhum diagn\u00f3stico can\u00f4nico dispon\u00edvel.
    parsed: list[tuple[Path, dict[str, Any], bool]] = []
    for path in candidates:
        report = _json(path.read_text(encoding="utf-8"), {})
        summary = report.get("resumo") if isinstance(report, dict) else {}
        summary = summary if isinstance(summary, dict) else {}
        try:
            scoped = (
                int(summary.get("itens")) == int(summary.get("n1_itens"))
                == int(summary.get("n2_itens"))
            )
        except (TypeError, ValueError):
            scoped = False
        parsed.append((path, report if isinstance(report, dict) else {}, scoped))
    compatible = [entry for entry in parsed if entry[2]] or parsed
    path, report, _ = max(compatible, key=lambda entry: entry[0].stat().st_mtime)
    return path, report


def _g2_lote_from_status(repo_root: Path, pavimento: str) -> tuple[str, str]:
    """Obtém o G2 FV do snapshot canônico, sem recalcular ou selar nada."""
    status_path = repo_root / "docs" / "STATUS.md"
    if not status_path.exists():
        return "não consultado", "STATUS.md ausente"
    for line in status_path.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in line.strip().split("|") if part.strip()]
        if len(parts) < 8 or parts[0] != "FV" or parts[1] != pavimento:
            continue
        try:
            passed, failed, blocked = (int(parts[3]), int(parts[4]), int(parts[5]))
            golden = int(parts[7])
        except ValueError:
            continue
        verdict = "PASS" if failed == 0 and blocked == 0 else "FAIL"
        return f"{verdict} {passed}/{passed + failed + blocked}; golden {golden}", str(status_path)
    return "não consultado", f"FV/{pavimento} não encontrado em {status_path.name}"


def _n2_multiplier_notes(ficha_row: sqlite3.Row | None) -> list[str]:
    """Lê anotações ``Nx`` do recorte N2 sem atribuí-las por suposição.

    A ficha estruturada pode guardar dois segmentos enquanto o desenho declara,
    por exemplo, ``5x``. O relatório expõe essa evidência, mas não multiplica um
    painel até que o vínculo espacial painel↔cota exista no motor N2.
    """
    if ficha_row is None or not ficha_row["recorte_path"]:
        return []
    try:
        import ezdxf

        document = ezdxf.readfile(Path(ficha_row["recorte_path"]))
        texts: list[str] = []
        for entity in document.modelspace():
            if entity.dxftype() == "MTEXT":
                text = str(entity.text)
            elif entity.dxftype() in {"TEXT", "ATTRIB", "ATTDEF"}:
                text = str(entity.dxf.text)
            else:
                continue
            texts.extend(re.findall(r"\b\d+\s*[xX]\b", text))
        return sorted(set(text.replace(" ", "") for text in texts))
    except Exception:
        return []


def _n2_segments(ficha: dict[str, Any] | None, multipliers: list[str]) -> str:
    if not ficha:
        return "Ficha N2: não emitida"
    largura = ficha.get("total_width")
    segmentos = ficha.get("segments_rich") or []
    if not isinstance(segmentos, list) or not segmentos:
        return "Ficha N2: emitida\nsegmentos não estruturados"
    partes: list[str] = []
    for index, segment in enumerate(segmentos, start=1):
        comprimento = segment.get("total_width")
        paineis = segment.get("panels") or []
        suffix = f"; painéis={len(paineis)}" if isinstance(paineis, list) else ""
        partes.append(f"S{index} {_number(comprimento)}×{_number(largura)}{suffix}")
    multiplier_note = f"\nmultiplicador visual {', '.join(multipliers)} (associação pendente)" if multipliers else ""
    return f"Ficha N2: emitida\n{len(segmentos)} seg\n" + "\n".join(partes) + multiplier_note


def _fv_contour_measurement(beam: dict[str, Any], segment_index: int) -> tuple[Any, Any] | None:
    """Obtém C×L apenas do contorno FV N1 já persistido.

    ``fv_measure_length`` é a medida geométrica produzida pelo interpretador;
    quando ausente, ``ficha`` continua sendo metadado emitido pelo próprio
    contorno N1. Não consulta N2/N4 nem usa bbox como substituto da geometria.
    """
    links = beam.get("links") if isinstance(beam.get("links"), dict) else {}
    payload = links.get(f"viga_fundo_seg_{segment_index}_area_segs")
    contours = payload.get("contour") if isinstance(payload, dict) else []
    if not isinstance(contours, list):
        return None
    for contour in contours:
        if not isinstance(contour, dict):
            continue
        points = contour.get("points") or []
        if not isinstance(points, list) or len(points) < 3:
            continue
        fiche = contour.get("ficha") if isinstance(contour.get("ficha"), dict) else {}
        length = contour.get("fv_measure_length")
        if length in (None, ""):
            length = contour.get("len")
        if length in (None, ""):
            length = fiche.get("comprimento_total_fundo")
        width = fiche.get("largura_total_fundo")
        if length not in (None, "") and width not in (None, ""):
            return length, width
    return None


def _n1_segments(beam: dict[str, Any], diagnostic_item: dict[str, Any] | None) -> tuple[int, str]:
    # O estado legado persiste campos FV no topo; o estado novo pode colocá-los
    # em ``fields``. Unir os dois evita transformar um segmento real em vazio
    # apenas por haver um dicionário auxiliar ``fields``.
    fields = dict(beam)
    if isinstance(beam.get("fields"), dict):
        fields.update(beam["fields"])
    indexes = sorted(
        int(match.group(1))
        for key, value in fields.items()
        if (match := FV_SEGMENT_RE.match(str(key))) and value is True
    )
    if not indexes:
        return 0, "N1/SA: segmentos não persistidos"
    evidence = (diagnostic_item or {}).get("evidencia") or {}
    n1 = evidence.get("n1") or {}
    lengths = n1.get("comprimentos") if isinstance(n1.get("comprimentos"), list) else []
    widths = n1.get("larguras") if isinstance(n1.get("larguras"), list) else []
    # Um microciclo headless read-only não regrava o SA. Caso ele produza uma
    # topologia mais nova, o quadro precisa expor as duas verdades: o snapshot
    # persistido da UI/DB e a evidência N1 ainda não promovida pelo QA.
    persisted_parts: list[str] = []
    for segment_index in indexes:
        measure = _fv_contour_measurement(beam, segment_index)
        if measure:
            persisted_parts.append(f"S{segment_index} {_number(measure[0])}×{_number(measure[1])}")
        else:
            dim = fields.get(f"viga_fundo_seg_{segment_index}_dim") or "dimensão não persistida"
            persisted_parts.append(f"S{segment_index} C não persistido × {dim}")

    snapshot_parts: list[str] = []
    for position, length in enumerate(lengths, start=1):
        width = widths[position - 1] if position <= len(widths) else None
        if width is None:
            snapshot_parts.append(f"S{position} {_number(length)}×largura não emitida")
        else:
            snapshot_parts.append(f"S{position} {_number(length)}×{_number(width)}")

    if snapshot_parts and len(lengths) != len(indexes):
        return (
            len(indexes),
            f"N1/SA: segmentos persistidos ({len(indexes)})\n"
            + "\n".join(persisted_parts)
            + f"\nSnapshot N1 read-only: {len(lengths)} seg\n"
            + "\n".join(snapshot_parts),
        )
    if snapshot_parts:
        return len(indexes), f"N1/SA: segmentos persistidos ({len(indexes)})\n" + "\n".join(snapshot_parts)
    return len(indexes), f"N1/SA: segmentos persistidos ({len(indexes)})\n" + "\n".join(persisted_parts)


def _field_origins(validated_fields: Any) -> dict[str, set[str]]:
    """Normaliza lista legada e formato novo de validações por origem."""
    if isinstance(validated_fields, (list, tuple, set)):
        return {str(field): {"humano_app"} for field in validated_fields}
    if not isinstance(validated_fields, dict):
        return {}
    result: dict[str, set[str]] = {}
    for field, entries in validated_fields.items():
        if not isinstance(entries, list):
            continue
        result[str(field)] = {
            str(entry.get("origem"))
            for entry in entries
            if isinstance(entry, dict) and entry.get("origem") in FIELD_ORIGIN_TO_SEAL
        }
    return result


def _origin_counts(field_ids: list[str], origins_by_field: dict[str, set[str]]) -> dict[str, int]:
    counts = {"azul": 0, "laranja": 0, "rosa": 0}
    for field_id in field_ids:
        seals = {FIELD_ORIGIN_TO_SEAL[origin] for origin in origins_by_field.get(str(field_id), set())}
        for seal in seals:
            counts[seal] += 1
    return counts


def _field_seals(origins_by_field: dict[str, set[str]], field_id: str) -> set[str]:
    """Selos que realmente constam no campo, sem promover por cobertura parcial."""
    return {
        FIELD_ORIGIN_TO_SEAL[origin]
        for origin in origins_by_field.get(str(field_id), set())
        if origin in FIELD_ORIGIN_TO_SEAL
    }


def _seal_triplet(seals: set[str]) -> str:
    """Mostra as três origens de campo, inclusive quando ainda não há validação."""
    return " · ".join(
        f"{icon}{'✓' if seal in seals else '—'}"
        for seal, icon in (("azul", "🔵"), ("laranja", "🟠"), ("rosa", "🌸"))
    )


def _fv_stage_validation(
    beam: dict[str, Any],
    total_segments: int,
    *,
    stage: str,
    suffixes: tuple[tuple[str, str], ...],
    global_fields: tuple[tuple[str, str], ...] = (),
) -> tuple[bool, str]:
    """Cobertura FV por etapa, baseada apenas no estado de campo persistido.

    S3 exige contorno e dimensão de cada segmento. S4 fecha o item FV com
    identidade/quantidade e os apoios local inicial/final. Cada origem (azul,
    laranja, rosa) é calculada isoladamente: nunca se mistura cobertura de
    pessoas/agente diferentes para fabricar um selo.
    """
    if total_segments <= 0:
        return False, f"Validação {stage}: PENDENTE (N1/SA sem segmentos persistidos)"

    origins_by_field = _field_origins(beam.get("validated_fields"))
    required_by_segment = [
        (index, [(f"viga_fundo_seg_{index}_{suffix}", label) for suffix, label in suffixes])
        for index in range(1, total_segments + 1)
    ]
    all_field_ids = [field_id for _, fields in required_by_segment for field_id, _ in fields]
    all_field_ids.extend(field_id for field_id, _ in global_fields)

    complete_by_any = 0
    complete_by_seal = {"azul": 0, "laranja": 0, "rosa": 0}
    segment_lines: list[str] = []
    requires_contour_measure = any(suffix == "area_segs" for suffix, _ in suffixes)
    for index, fields in required_by_segment:
        seals_by_field = {field_id: _field_seals(origins_by_field, field_id) for field_id, _ in fields}
        measurement = _fv_contour_measurement(beam, index) if requires_contour_measure else None
        measure_ok = measurement is not None if requires_contour_measure else True
        complete_any = all(seals_by_field[field_id] for field_id, _ in fields) and measure_ok
        complete_by_any += int(complete_any)
        for seal in complete_by_seal:
            complete_by_seal[seal] += int(
                all(seal in seals_by_field[field_id] for field_id, _ in fields) and measure_ok
            )
        detail = " · ".join(f"{label} {_seal_triplet(seals_by_field[field_id])}" for field_id, label in fields)
        if requires_contour_measure:
            detail += f" · C×L {_number(measurement[0])}×{_number(measurement[1])}" if measurement else " · C×L não rastreável"
        segment_lines.append(f"S{index} {'✓' if complete_any else '○'} {detail}")

    globals_ok_any = all(_field_seals(origins_by_field, field_id) for field_id, _ in global_fields)
    globals_by_seal = {
        seal: all(seal in _field_seals(origins_by_field, field_id) for field_id, _ in global_fields)
        for seal in ("azul", "laranja", "rosa")
    }
    column_complete = complete_by_any == total_segments and globals_ok_any
    source_coverage = " · ".join(
        f"{icon}{'✓' if complete_by_seal[seal] == total_segments and globals_by_seal[seal] else '—'} {complete_by_seal[seal]}/{total_segments}"
        for seal, icon in (("azul", "🔵"), ("laranja", "🟠"), ("rosa", "🌸"))
    )
    global_line = ""
    if global_fields:
        global_line = "\nGlobais: " + " · ".join(
            f"{label} {_seal_triplet(_field_seals(origins_by_field, field_id))}"
            for field_id, label in global_fields
        )
    status = "SIM" if column_complete else "PENDENTE"
    return (
        column_complete,
        f"Validação {stage}: {status} ({complete_by_any}/{total_segments} segmentos completos)"
        f"{global_line}\nSelos completos por origem: {source_coverage}\n"
        + "\n".join(segment_lines),
    )


def _origin_line(counts: dict[str, int]) -> str:
    def mark(count: int) -> str:
        return "✓" if count else "—"
    return (
        f"🔵 SA {mark(counts['azul'])} {counts['azul']} · "
        f"🟠 QA {mark(counts['laranja'])} {counts['laranja']} · "
        f"🌸 Portal {mark(counts['rosa'])} {counts['rosa']}"
    )


def _item_seal_line(seals: set[str]) -> str:
    def mark(seal: str) -> str:
        return "✓" if seal in seals else "—"
    return (
        f"🔵 {mark('azul')} Azul · 🟠 {mark('laranja')} Laranja · "
        f"🟢 {mark('verde')} Verde · 🌸 {mark('rosa')} Rosa"
    )


def _validated_topology(beam: dict[str, Any], total_segments: int, item_seals: set[str]) -> str:
    topologies = beam.get("validated_segment_topologies_v1") or {}
    fv = topologies.get("FV") if isinstance(topologies, dict) else []
    fv = fv if isinstance(fv, list) else []
    origins_by_field = _field_origins(beam.get("validated_fields"))
    topology_origins = _origin_counts([str(field) for field in fv], origins_by_field)
    field_origins = _origin_counts(list(origins_by_field), origins_by_field)
    field_count = len(origins_by_field)
    if not fv:
        topology_line = f"Topologia 0/{total_segments}"
    else:
        topology_line = f"Topologia {len(fv)}/{total_segments}"
    return (
        f"Selos N1 / SA do item\n{_item_seal_line(item_seals)}\n"
        f"{topology_line}\n{_origin_line(topology_origins)}\n"
        f"Campos N1\n{_origin_line(field_origins)}"
    )


def _diagnostic_status(diagnostic_item: dict[str, Any] | None) -> str:
    if not diagnostic_item:
        return "não comparada / QA pendente"
    evidence = diagnostic_item.get("evidencia") or {}
    seg = "PASS" if evidence.get("segmentos_match") else "FAIL"
    med = "PASS" if evidence.get("medidas_segmentos_match") else "FAIL"
    return f"auto {evidence.get('classificacao', 'N/A')}: seg {seg}, medidas {med} / QA pendente"


def _geometry_qa_reference(
    diagnostic_item: dict[str, Any] | None,
    n1v_verdict: str | None,
    has_n2: bool,
) -> str:
    """Evidência necessária para selo QA laranja da geometria FV.

    Não grava selo: o relatório só explica quais provas ainda precisam ser
    persistidas por ``qa_agente``. N2 participa exclusivamente como referência
    comparativa e o N1-V CLI lê os SVGs local/contextual pelo modelo CLI.
    """
    if not has_n2:
        return "QA laranja geométrico: N/A (não há ficha N2 para comparação)"
    evidence = (diagnostic_item or {}).get("evidencia") or {}
    if diagnostic_item:
        match = "PASS" if evidence.get("segmentos_match") and evidence.get("medidas_segmentos_match") else "FAIL"
        comparison = f"N1×N2 contagem+medidas (0,05 cm): {match}"
    else:
        comparison = "N1×N2 contagem+medidas (0,05 cm): PENDENTE"
    visual = f"N1-V CLI SVG local+contextual: {n1v_verdict}" if n1v_verdict else "N1-V CLI SVG local+contextual: PENDENTE"
    return (
        f"{comparison}\n{visual}\n"
        "Laranja QA: só após PASS acima + checklist contorno_posicao_sobre_estrutural "
        "(cada área N1 alinhada/posicionada sobre linhas DXF — tamanho certo flutuando = FAIL) "
        "e contorno+dim de cada segmento persistidos por qa_agente"
    )


def _n1_svg_items(repo_root: Path) -> set[str]:
    g2v_root = repo_root / "scripts" / "arete" / "relatorios" / "g2v"
    if not g2v_root.exists():
        return set()
    return {
        match.group(1)
        for path in g2v_root.glob("**/FV_*_n1xn2*.svg")
        if (match := re.search(r"FV_(V[^_]+)_n1xn2", path.name, flags=re.IGNORECASE))
    }


def _cli_svg_verdicts_by_item(repo_root: Path, pavimento: str, par: str, gate: str) -> dict[str, str]:
    """Lê um veredito CLI SVG válido por item, sempre do par/gate solicitado.

    Relatórios antigos baseados em PNG não são reaproveitados: a política atual
    exige SVG+manifesto e veredito CLI registrado. Um item sem veredito completo
    permanece ausente e será exibido como ``NÃO registrado``.
    """
    root = repo_root / "scripts" / "arete" / "relatorios" / "g2v"
    verdicts: dict[str, tuple[float, str]] = {}
    for path in root.glob("**/relatorio.json"):
        report = _json(path.read_text(encoding="utf-8"), {})
        if not isinstance(report, dict) or report.get("classe") != "FV":
            continue
        if report.get("pavimento") != pavimento or report.get("par") != par or report.get("gate") != gate:
            continue
        for item in report.get("itens") or []:
            if not isinstance(item, dict) or item.get("fonte_imagem") != "html_svg_vetorial":
                continue
            if not item.get("svg_paths") or not item.get("svg_manifest_path"):
                continue
            cli = (item.get("vereditos") or {}).get("cli") or {}
            verdict = str(cli.get("veredito") or "").upper()
            if cli.get("aguardando_agente") or verdict not in {"PASS", "FAIL", "SUSPEITO"}:
                continue
            checklist = cli.get("checklist_visual")
            if verdict == "PASS" and isinstance(checklist, dict) and any(value is not True for value in checklist.values()):
                continue
            item_id = str(item.get("elemento_id") or "").upper()
            if not item_id:
                continue
            stamp = path.stat().st_mtime
            if item_id not in verdicts or stamp > verdicts[item_id][0]:
                verdicts[item_id] = (stamp, verdict)
    return {item: verdict for item, (_, verdict) in verdicts.items()}


def _g2v_cli_by_item(repo_root: Path, pavimento: str) -> dict[str, str]:
    """G2-V (veredito visual CLI N2×N4) por item FV."""
    return _cli_svg_verdicts_by_item(repo_root, pavimento, "n2xn4", "G2-V")


def _n1v_cli_by_item(repo_root: Path, pavimento: str) -> dict[str, str]:
    """N1-V (veredito visual CLI N1×N2) por item FV."""
    return _cli_svg_verdicts_by_item(repo_root, pavimento, "n1xn2", "N1-V")


def _g5v_cli_by_item(repo_root: Path, pavimento: str) -> dict[str, str]:
    """G5-V (veredito visual CLI N3×N4) por item FV."""
    return _cli_svg_verdicts_by_item(repo_root, pavimento, "n3xn4", "G5-V")


def _n3_smokes(repo_root: Path) -> dict[str, str]:
    base = repo_root / "scripts" / "arete" / "relatorios"
    result: dict[str, str] = {}
    for path in base.glob("**/qa_n3_smoke*.json"):
        report = _json(path.read_text(encoding="utf-8"), {})
        question = str(report.get("question") or "")
        match = re.search(r"FV:(V[\w.-]+)", question)
        if match:
            result[match.group(1)] = f"smoke {report.get('overall', 'N/A')}; visual pendente"
    return result


def _rag_html_ingestion_by_item(
    repo_root: Path,
    *,
    project_id: str,
    obra: str,
    pavimento: str,
) -> dict[str, dict[str, Any]]:
    """Lê o registro append-only de ingestão multimodal por item.

    R1 registra somente que um pacote HTML, seu hash e o run QA foram enviados
    ao contexto RAG local. Não é promoção T1, não cria selo N1/N3 e não torna
    N2/N4 fonte de interpretação. Entradas sem HTML+hash são rejeitadas na
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
        if row.get("project_id") != project_id or row.get("classe") != "FV":
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
        return "RAG HTML: NÃO registrado / ingestão pendente"
    status = str(entry.get("status") or "INGESTED_T0").upper()
    if status not in {"INGESTED_T0", "T1_PROMOTED"}:
        return f"RAG HTML: NÃO ({status})"
    tier = "T1 curado" if status == "T1_PROMOTED" else "T0 contextual"
    return (
        f"RAG HTML: SIM ({tier})\n"
        f"HTML: {entry['html_path']}\n"
        f"SHA-256: {entry['html_sha256']}\n"
        f"Run QA: {entry.get('qa_run_id') or 'não informado'}"
    )


def _n2_formal(row: sqlite3.Row | None) -> str:
    if row is None:
        return "não há ficha N2"
    if row["aprovado_at"] or str(row["status"] or "").lower() in {"approved", "validated", "valid"}:
        return "SIM"
    return f"NÃO ({row['status'] or 'sem status'})"


def _n2_item_validation_status(ficha_row: sqlite3.Row | None, n4_seals: set[str]) -> str:
    """N2 é validado pelo aceite do N4 correspondente; status da ficha é metadado."""
    origins = []
    if "azul" in n4_seals:
        origins.append("azul/humano")
    if "laranja" in n4_seals:
        origins.append("laranja/QA")
    technical = str(ficha_row["status"] or "sem status") if ficha_row else "sem ficha"
    if origins:
        return f"Validação N2: SIM ({', '.join(origins)})\nEstado técnico da ficha: {technical}"
    return f"Validação N2: NÃO\nEstado técnico da ficha: {technical}"


def _n4_item_validation_status(seals: set[str], g2v_verdict: str | None) -> str:
    """Estado granular do item; o G2 de lote pertence somente ao card N4."""
    origins = []
    if "azul" in seals:
        origins.append("azul/humano")
    if "laranja" in seals:
        origins.append("laranja/QA")
    validation = f"Validação N4 deste item: SIM ({', '.join(origins)})" if origins else "Validação N4 deste item: NÃO"
    g2v = f"G2-V CLI deste item: SIM ({g2v_verdict})" if g2v_verdict else "G2-V CLI deste item: NÃO registrado"
    return f"{validation}\n{g2v}"


def _n3_item_validation_status(smoke: str, seals: set[str], g5v_verdict: str | None) -> str:
    """Separa prova de geração (smoke) de validações acumuláveis do N3."""
    g5v = f"G5-V CLI N3×N4: {g5v_verdict}" if g5v_verdict else "G5-V CLI N3×N4: não registrado"
    return (
        f"{smoke}\n"
        f"{g5v}\n"
        "Selos N3 do item\n"
        f"{_item_seal_line(seals)}"
    )


def _g5v_item_status(g5v_verdict: str | None) -> str:
    if g5v_verdict == "PASS":
        return "✓ G5-V CLI N3×N4: PASS"
    if g5v_verdict == "FAIL":
        return "× G5-V CLI N3×N4: FAIL"
    if g5v_verdict == "SUSPEITO":
        return "○ G5-V CLI N3×N4: SUSPEITO"
    return "não comparada / QA pendente"


def _next_step(
    n2_validated: bool,
    n1_count: int,
    geometry_complete: bool,
    item_complete: bool,
    diagnostic: dict[str, Any] | None,
    n3: str,
    g5v_verdict: str | None,
) -> str:
    if not n2_validated:
        return "S1 — registrar decisão humana do recorte/ficha N2"
    if not n1_count:
        return "S3 — interpretar N1 do DXF original"
    if not geometry_complete:
        return "S3 — validar contorno + dimensão de cada segmento N1"
    if not item_complete:
        return "S4 — validar continuidade, apoio inicial/final e item FV"
    if not diagnostic:
        return "S5 — diagnóstico e QA N1×N2 campo a campo"
    if n3 == "não evidenciado":
        return "S6 — gerar N3 somente de N1 + smoke"
    if g5v_verdict == "FAIL":
        return "S5 — reconciliar campo divergente N1×N2 antes de regenerar N3"
    if not g5v_verdict:
        return "S7 — comparar N3×N4 via G5-V CLI"
    return "S7 — comparar ficha N3×N2 sem alimentar o N3"


def build_report(project_id: str, obra: str, pavimento: str, db_path: Path, repo_root: Path, g2_lote: str, g2_source: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        project = connection.execute(
            "SELECT pavement_name FROM projects WHERE id=?", (project_id,)
        ).fetchone()
        beams = connection.execute(
            "SELECT name, data_json, validated_fields_json, is_validated FROM beams WHERE project_id=? ORDER BY name",
            (project_id,),
        ).fetchall()
        fichas = connection.execute(
            "SELECT elemento_id, campos_json, status, aprovado_at, recorte_path FROM reverse_eng_fichas "
            "WHERE obra_name=? AND pavimento=? AND classe='FV' ORDER BY id DESC",
            (obra, pavimento),
        ).fetchall()
        policy_rows = connection.execute(
            "SELECT obra_name, pavimento, item_id, scope, validation_origin FROM artifact_validation_policies "
            "WHERE obra_name=? AND pavimento=? AND classe='FV' "
            "AND scope IN ('N3', 'N4') AND locked=1",
            (obra, project["pavement_name"] if project else pavimento),
        ).fetchall()
        global_beams = connection.execute(
            "SELECT data_json, is_validated FROM beams "
            "WHERE data_json LIKE '%viga_fundo_%'"
        ).fetchall()
        global_fichas = connection.execute(
            "SELECT obra_name, pavimento, elemento_id FROM reverse_eng_fichas "
            "WHERE classe='FV' ORDER BY id DESC"
        ).fetchall()
        global_policy_rows = connection.execute(
            "SELECT obra_name, pavimento, item_id, scope, validation_origin FROM artifact_validation_policies "
            "WHERE classe='FV' AND scope IN ('N3', 'N4') AND locked=1"
        ).fetchall()
        project_rows = connection.execute(
            "SELECT id, work_name, pavement_name FROM projects"
        ).fetchall()
    finally:
        connection.close()

    n2_by_item: dict[str, sqlite3.Row] = {}
    for ficha in fichas:
        n2_by_item.setdefault(str(ficha["elemento_id"]), ficha)
    diagnostic_path, diagnostic = _find_latest_diagnostic(repo_root, obra, pavimento)
    diagnostic_by_item = {str(row.get("item")): row for row in diagnostic.get("itens", []) if isinstance(row, dict)}
    n1_svg_items = _n1_svg_items(repo_root)
    g2v_cli_by_item = _g2v_cli_by_item(repo_root, pavimento)
    n1v_cli_by_item = _n1v_cli_by_item(repo_root, pavimento)
    g5v_cli_by_item = _g5v_cli_by_item(repo_root, pavimento)
    n3_smoke_by_item = _n3_smokes(repo_root)
    rag_html_by_item = _rag_html_ingestion_by_item(
        repo_root, project_id=project_id, obra=obra, pavimento=pavimento,
    )
    n1_items = {str(row["name"]) for row in beams}
    n2_items = set(n2_by_item)
    n4_policy_rows = [row for row in policy_rows if row["scope"] == "N4"]
    n3_policy_rows = [row for row in policy_rows if row["scope"] == "N3"]
    # N4 e N2 usam a identidade da ficha N2. Cada selo N4 Ã© projetado na ficha
    # N2 correspondente, como definido pelo dono; isto Ã© uma leitura, nunca uma
    # escrita que altere a proveniÃªncia N1/N3 ou a ficha de engenharia reversa.
    n4_allowed_seals = {"azul", "laranja"}
    n4_seals_by_n2 = _policy_seals_by_item(n4_policy_rows, n2_items, n4_allowed_seals)
    n4_seals_by_n1 = _policy_seals_by_item(n4_policy_rows, n1_items, n4_allowed_seals)
    n3_seals_by_item = _policy_seals_by_item(n3_policy_rows, n1_items)
    n3_generated_items = set(n3_smoke_by_item) | {
        item for item, seals in n3_seals_by_item.items() if seals
    }
    rows: list[dict[str, str]] = []
    partial_topology = 0
    sa_item_validated = 0
    for row in beams:
        item = str(row["name"])
        beam = _json(row["data_json"], {})
        beam["validated_fields"] = _json(row["validated_fields_json"], [])
        diag_item = diagnostic_by_item.get(item)
        n1_count, n1_segments = _n1_segments(beam, diag_item)
        item_seals = _n1_item_seals(beam, row["is_validated"])
        geometry_complete, geometry_validation = _fv_stage_validation(
            beam,
            n1_count,
            stage="S3 geometria",
            suffixes=(("area_segs", "contorno"), ("dim", "dimensão C×L")),
        )
        item_complete, topology = _fv_stage_validation(
            beam,
            n1_count,
            stage="S4 item FV",
            suffixes=(("local_ini", "apoio inicial"), ("local_fim", "apoio final")),
            global_fields=(("name", "nome"), ("viga_count_c", "quantidade de segmentos")),
        )
        if item_complete:
            partial_topology += 1
        sa_item_validated += int("verde" in item_seals)
        ficha_row = n2_by_item.get(item)
        ficha = _json(ficha_row["campos_json"], {}) if ficha_row else None
        n2_seals = n4_seals_by_n1.get(item, set())
        n2_validation = _n2_item_validation_status(ficha_row, n2_seals)
        n3 = n3_smoke_by_item.get(item, "não evidenciado")
        g5v_verdict = g5v_cli_by_item.get(item)
        n3_status = _n3_item_validation_status(n3, n3_seals_by_item.get(item, set()), g5v_verdict)
        rows.append({
            "item": item,
            "n2_recorte_formal": n2_validation,
            "n2_segmentos": _n2_segments(ficha, _n2_multiplier_notes(ficha_row)),
            "n4_g2_g2v": _n4_item_validation_status(n4_seals_by_n1.get(item, set()), g2v_cli_by_item.get(item)),
            "n1_segmentos": (
                f"{geometry_validation}\n{n1_segments}\n"
                f"{_geometry_qa_reference(diag_item, n1v_cli_by_item.get(item), bool(ficha_row))}"
            ),
            "n1_topologia_campos": topology,
            "n1_visual_cli": (
                (
                    f"N1-V CLI deste item: {n1v_cli_by_item[item]}\n"
                    "🟠 exige contorno_posicao_sobre_estrutural (alinhado no DXF, não só C×L)"
                )
                if item in n1v_cli_by_item
                else (
                    "SVG emitido; QA pendente — 🟠 exige posição sobre linhas estruturais"
                    if item in n1_svg_items
                    else "não emitido / QA pendente"
                )
            ),
            "n1_n2_ficha": _diagnostic_status(diag_item),
            "n3_smoke": n3_status,
            "n3_n4_ficha": _g5v_item_status(g5v_verdict),
            "n3_n2_ficha": "não comparada / QA pendente",
            "rag_html": _rag_html_status(rag_html_by_item.get(item)),
            "etapa_proxima": _next_step(
                bool(n2_seals), n1_count, geometry_complete, item_complete, diag_item, n3, g5v_verdict,
            ),
        })
    rows.sort(key=lambda value: _item_key(value["item"]))
    n1_seals_by_item = {
        str(row["name"]): _n1_item_seals(_json(row["data_json"], {}), row["is_validated"])
        for row in beams
    }
    n1_card = {"total": len(n1_items), "seals": _seal_counts(n1_items, n1_seals_by_item)}
    n2_card = {"total": len(n2_items), "seals": _seal_counts(n2_items, n4_seals_by_n2)}
    n3_card = {"total": len(n3_generated_items), "seals": _seal_counts(n3_generated_items, n3_seals_by_item)}
    n4_card = {"total": len(n2_items), "seals": _seal_counts(n2_items, n4_seals_by_n2)}

    # Consolidado temporal: N1 só entra quando o schema FV é reconhecível no
    # próprio registro (`viga_fundo_*`). Isso evita somar laterais/legados sem
    # identidade FV ao total histórico.
    global_n1_seals = {
        index: _n1_item_seals(_json(row["data_json"], {}), row["is_validated"])
        for index, row in enumerate(global_beams)
    }
    global_n2_by_context: dict[tuple[str, str, str], sqlite3.Row] = {}
    for ficha in global_fichas:
        key = (
            str(ficha["obra_name"] or "").upper(),
            _pavimento_key(ficha["pavimento"]),
            str(ficha["elemento_id"] or "").upper(),
        )
        global_n2_by_context.setdefault(key, ficha)
    global_n2_items = set(global_n2_by_context)
    global_n4_policies = [row for row in global_policy_rows if row["scope"] == "N4"]
    global_n3_policies = [row for row in global_policy_rows if row["scope"] == "N3"]
    global_n4_seals = _policy_seals_by_context(global_n4_policies, global_n2_items, n4_allowed_seals)
    global_n3_policy_items = {
        (str(row["obra_name"] or "").upper(), _pavimento_key(row["pavimento"]), item)
        for row in global_n3_policies
        for item in POLICY_ITEM_RE.findall(str(row["item_id"] or "").upper())
    }
    global_n3_seals = _policy_seals_by_context(global_n3_policies, global_n3_policy_items)
    global_n3_total = len(set(_n3_smokes(repo_root))) + len(global_n3_policy_items)
    global_levels = {
        "n1": {"total": len(global_n1_seals), "seals": _seal_counts_for_sets(global_n1_seals)},
        "n2": {"total": len(global_n2_items), "seals": _seal_counts_for_sets(global_n4_seals)},
        "n3": {"total": global_n3_total, "seals": _seal_counts_for_sets(global_n3_seals)},
        "n4": {"total": len(global_n2_items), "seals": _seal_counts_for_sets(global_n4_seals)},
    }
    projects_by_id = {
        str(row["id"]): (str(row["work_name"] or "sem obra"), str(row["pavement_name"] or "sem pavimento"))
        for row in project_rows
    }
    qa_fv_coverage = _qa_fv_scope_counts(repo_root, projects_by_id)
    summary = {
        "schema": "arete.qa_fv_quadro_pavimento/v3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only",
        "project_id": project_id,
        "obra": obra,
        "pavimento": pavimento,
        "items_n1": len(rows),
        "items_n2": len(n2_by_item),
        # Não existe ainda um índice item-a-item de S8/Arete FV no DB. Logo, a
        # ausência de uma prova S8 é reportada como zero, enquanto is_validated
        # aparece em métrica separada de UI/SA.
        "items_arete_proven": 0,
        "items_sa_validated": sa_item_validated,
        "items_with_human_topology": partial_topology,
        "n2_formally_approved": n2_card["seals"]["azul"] + n2_card["seals"]["laranja"],
        "n4_humanly_validated": n4_card["seals"]["azul"] + n4_card["seals"]["laranja"],
        "levels": {
            "n1": n1_card,
            "n2": n2_card,
            "n3": n3_card,
            "n4": n4_card,
        },
        "global_levels": global_levels,
        "qa_fv_coverage": qa_fv_coverage,
        "diagnostic_path": str(diagnostic_path) if diagnostic_path else None,
        "diagnostic_items": len(diagnostic_by_item),
        "g2_lote": g2_lote,
        "g2_source": g2_source,
        "limits": [
            "N2/N4 never feed N1/N3.",
            "N2 blue/orange in the summary is inherited read-only from the matching locked N4 policy; it does not rewrite the N2 fiche.",
            "N4 uses only human-app blue and QA-agent orange; green/pink do not apply to N4.",
            "Historical N1 counts include only records with a persisted viga_fundo_* identity; the detailed table remains the current pavement only.",
            "G2 numeric lot status is not an item-level visual verdict.",
            "N1 lengths remain 'não persistido' without N1 contour/points/evidence_segments.",
            "QA pending is not inferred from smoke or automatic diagnostics.",
        ],
    }
    return summary, rows


def _status_class(value: str) -> str:
    normalized = value.lower()
    first_line = normalized.splitlines()[0] if normalized.splitlines() else normalized
    if "validação s3 geometria: sim" in first_line or "validação s4 item fv: sim" in first_line:
        return "pass"
    if "validação s3 geometria: pendente" in first_line or "validação s4 item fv: pendente" in first_line:
        return "pending"
    if "ficha n2: emitida" in first_line:
        return "pass"
    if "pendente" in normalized or "não evidenciado" in normalized or "não comparada" in normalized:
        return "pending"
    if "fail" in normalized or "ruim" in normalized or "não (" in normalized:
        return "fail"
    if "sim" in normalized or "pass" in normalized or "excelente" in normalized:
        return "pass"
    return "neutral"


def _stage_target_column(value: str) -> str:
    """A etapa S0…S8 aponta para a coluna que guia visualmente a linha."""
    stage = str(value).strip().split(" ", 1)[0]
    return {
        "S0": "item", "S1": "n2_recorte_formal", "S2": "n4_g2_g2v",
        "S3": "n1_segmentos", "S4": "n1_topologia_campos",
        "S5": "n1_n2_ficha", "S6": "n3_smoke",
        "S7": "n3_n4_ficha", "S8": "n3_n4_ficha",
    }.get(stage, "item")


def _html_cell(value: str) -> str:
    """Apresenta conclusão por célula sem inferir ou criar selo algum."""
    rendered: list[str] = []
    for raw_line in str(value).splitlines() or [""]:
        normalized = raw_line.casefold()
        status_line = any(token in normalized for token in (
            "validação", " cli", "smoke", "auto excelente", "não emitido",
            "não comparada", "não evidenciado", "qa pendente",
        ))
        is_ok = (
            "validação n2: sim" in normalized
            or "validação n4 deste item: sim" in normalized
            or "ficha n2: emitida" in normalized
            or "validação s3 geometria: sim" in normalized
            or "validação s4 item fv: sim" in normalized
            or "g2-v cli deste item: sim (pass)" in normalized
            or "n1-v cli deste item: pass" in normalized
            or "n1-v cli svg local+contextual: pass" in normalized
            or "n1×n2 contagem+medidas (0,05 cm): pass" in normalized
            or "g5-v cli deste item: sim (pass)" in normalized
            or "rag html: sim" in normalized
            or "smoke: pass" in normalized
            or "auto excelente" in normalized and "medidas pass" in normalized
        )
        # "NÃO registrado" descreve ausência de evidência (pendente), não uma
        # reprovação.  A distinção é importante nas colunas granulares G2-V,
        # N1-V e G5-V: só uma divergência/FAIL efetivamente registrado recebe ×.
        is_pending = any(token in normalized for token in (
            "não registrado", "qa pendente", "não emitido", "não comparada",
            "não evidenciado", "svg emitido", "n1/sa: segmentos não persistidos",
            "rag html: não registrado", "ingestão pendente",
        ))
        is_fail = not is_pending and (
            " fail" in normalized
            or "diverg" in normalized
            or "validação n2: não" in normalized
            or "validação n4 deste item: não" in normalized
        )
        marker = ""
        if is_ok:
            marker = '<span class="state-mark ok" title="evidência concluída">✓</span>'
        elif is_fail:
            marker = '<span class="state-mark fail" title="divergência registrada">×</span>'
        elif is_pending or status_line:
            marker = '<span class="state-mark pending" title="ainda não concluído">○</span>'
        rendered.append(marker + html.escape(raw_line))
    return "<br>".join(rendered)


def _level_card_html(level: str, card: dict[str, Any], note: str, *, g2_lote: str | None = None) -> str:
    """Card único por nível; cada selo é uma contagem de itens, não um score."""
    seal_order = ("azul", "laranja") if level == "n4" else SEAL_ORDER
    colors = {
        "azul": ("Azul", "blue"),
        "laranja": ("Laranja", "orange"),
        "verde": ("Verde", "green"),
        "rosa": ("Rosa", "pink"),
    }
    badges = "".join(
        f'<span class="seal {css}">{label}: {card["seals"][seal]}</span>'
        for seal in seal_order
        for label, css in [colors[seal]]
    )
    g2 = f'<small class="g2">G2 (paridade canônica): {html.escape(g2_lote)}</small>' if g2_lote else ""
    return (
        f'<article class="card level-card {level}"><span>{"N1 / SA" if level == "n1" else level.upper()} — Fundos de Viga</span>'
        f'<strong>Total: {card["total"]}</strong><div class="seals">{badges}</div>'
        f'<small>{html.escape(note)}</small>{g2}</article>'
    )


def _level_cards_html(levels: dict[str, dict[str, Any]], *, g2_lote: str | None = None) -> str:
    return "\n".join([
        _level_card_html("n2", levels["n2"], "Azul/laranja herdados da validação humana/QA do N4 correspondente; não regrava a ficha N2."),
        _level_card_html("n4", levels["n4"], "N4 só admite azul (humano) e laranja (QA); total pareado às fichas N2.", g2_lote=g2_lote),
        _level_card_html("n1", levels["n1"], "Selos N1 lidos exclusivamente do estado persistido do SA."),
        _level_card_html("n3", levels["n3"], "Total somente de N3 com smoke ou política de validação persistida."),
    ])


def _qa_coverage_card_html(coverage: dict[str, Any]) -> str:
    return (
        '<article class="card coverage-card"><span>QA FV — cobertura de execução</span>'
        f'<strong>Obras: {coverage["obras"]}</strong>'
        f'<div class="coverage-counts"><span>Pavimentos: {coverage["pavimentos"]}</span></div>'
        f'<small>{coverage["runs"]} execução(ões) QA FV registradas no log append-only.</small></article>'
    )


def write_html_report(
    summary: dict[str, Any],
    rows: list[dict[str, str]],
    headers: list[tuple[str, str]],
    output_dir: Path,
    markdown_path: Path,
    csv_path: Path,
    json_path: Path,
) -> Path:
    """Renderiza o mesmo estado read-only em HTML local, sem dependência externa."""
    html_path = output_dir / "QUADRO-FV-PAVIMENTO.html"
    global_cards = _qa_coverage_card_html(summary["qa_fv_coverage"]) + "\n" + _level_cards_html(summary["global_levels"])
    current_cards = _level_cards_html(summary["levels"], g2_lote=str(summary["g2_lote"]))
    head = "".join(f'<th class="col-{key}">{html.escape(label)}</th>' for key, label in headers)
    column_widths = {
        "etapa_proxima": 290, "item": 125, "n2_recorte_formal": 180, "n2_segmentos": 310,
        "n4_g2_g2v": 280, "n1_segmentos": 310, "n1_topologia_campos": 285,
        "n1_visual_cli": 190, "n1_n2_ficha": 285, "n3_smoke": 280,
        "n3_n4_ficha": 230, "n3_n2_ficha": 230, "rag_html": 310, "etapa_proxima": 270,
    }
    columns = "".join(f'<col style="width:{column_widths.get(key, 220)}px">' for key, _ in headers)
    body_rows: list[str] = []
    for row in rows:
        cells = []
        for key, _ in headers:
            value = row[key]
            classes = ["col-" + key, _status_class(value)]
            if key == "etapa_proxima":
                classes.append("stage-" + _stage_target_column(value))
            rendered = html.escape(str(value)) if key == "item" else _html_cell(value)
            cells.append(f'<td class="{" ".join(classes)}">{rendered}</td>')
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    table_body = "\n".join(body_rows)
    diagnostic = html.escape(str(summary.get("diagnostic_path") or "não encontrado"))
    refresh = html.escape(
        "python scripts/arete/qa_fv_quadro_pavimento.py "
        f"--project-id {summary['project_id']} --obra {summary['obra']} --pav {summary['pavimento']} "
        "--output-dir <diretório>"
    )
    html_path.write_text(
        f'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quadro QA FV — {html.escape(summary['obra'])} / {html.escape(summary['pavimento'])}</title>
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
    .coverage-card strong {{ color:#f4d35e; }} .coverage-counts {{ margin:0 0 10px; }} .coverage-counts span {{ display:inline-block; padding:2px 7px; border-radius:999px; background:#3b315d; color:#ded0ff; font-size:12px; font-weight:700; }}
    .table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:10px; background:var(--panel); }}
    table {{ border-collapse:collapse; table-layout:fixed; min-width:3310px; width:3310px; }} th,td {{ padding:10px; border-right:1px solid var(--line); border-bottom:1px solid var(--line); text-align:left; vertical-align:top; white-space:normal; overflow-wrap:anywhere; word-break:normal; line-height:1.5; }}
    th {{ position:sticky; top:0; z-index:2; background:#223047; color:#f7fbff; font-size:12px; line-height:1.35; }} tr:hover td {{ outline:1px solid #3d648a; }} td:first-child {{ position:sticky; left:0; z-index:1; font-weight:700; background:#223047; }}
    td.pass {{ background:color-mix(in srgb,var(--pass) 38%,var(--panel)); }} td.fail {{ background:color-mix(in srgb,var(--fail) 31%,var(--panel)); }} td.pending {{ background:color-mix(in srgb,var(--pending) 33%,var(--panel)); }} td.neutral {{ background:var(--neutral); }}
    .col-etapa_proxima {{ --column:#94a3b8; }} .col-item {{ --column:#64748b; }} .col-n2_recorte_formal {{ --column:#0ea5e9; }} .col-n2_segmentos {{ --column:#14b8a6; }} .col-n4_g2_g2v {{ --column:#8b5cf6; }} .col-n1_segmentos {{ --column:#6366f1; }} .col-n1_topologia_campos {{ --column:#f59e0b; }} .col-n1_visual_cli {{ --column:#eab308; }} .col-n1_n2_ficha {{ --column:#38bdf8; }} .col-n3_smoke {{ --column:#22c55e; }} .col-n3_n4_ficha {{ --column:#a855f7; }} .col-n3_n2_ficha {{ --column:#ec4899; }} .col-rag_html {{ --column:#0f766e; }}
    th[class*="col-"] {{ background:color-mix(in srgb,var(--column) 36%,#182231); }} td[class*="col-"] {{ background:color-mix(in srgb,var(--column) 18%,var(--panel)); box-shadow:inset 3px 0 var(--column); }} td[class*="col-"].pass {{ background:color-mix(in srgb,var(--pass) 48%,var(--column)) !important; }} td[class*="col-"].fail {{ background:color-mix(in srgb,var(--fail) 48%,var(--column)) !important; }} td[class*="col-"].pending {{ background:color-mix(in srgb,var(--pending) 48%,var(--column)) !important; }} td[class*="col-"].neutral {{ background:color-mix(in srgb,var(--column) 22%,var(--panel)) !important; }} td.col-etapa_proxima {{ font-weight:700; }}
    td.stage-item {{ --column:#64748b; }} td.stage-n2_recorte_formal {{ --column:#0ea5e9; }} td.stage-n4_g2_g2v {{ --column:#8b5cf6; }} td.stage-n1_segmentos {{ --column:#6366f1; }} td.stage-n1_topologia_campos {{ --column:#f59e0b; }} td.stage-n1_n2_ficha {{ --column:#38bdf8; }} td.stage-n3_smoke {{ --column:#22c55e; }} td.stage-n3_n4_ficha {{ --column:#a855f7; }}
    td.col-etapa_proxima[class*="stage-"] {{ background:color-mix(in srgb,var(--column) 42%,var(--panel)) !important; box-shadow:inset 4px 0 #f8fafc; }}
    .state-mark {{ display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px; margin:0 6px 2px 0; border-radius:50%; font-weight:900; vertical-align:middle; }} .state-mark.ok {{ color:#c7f9d9; background:#166534; }} .state-mark.fail {{ color:#ffd1d1; background:#991b1b; }} .state-mark.pending {{ color:#ffe4a3; background:#854d0e; }}
    details {{ margin-top:20px; padding:14px; border:1px solid var(--line); border-radius:10px; background:var(--panel); }} summary {{ cursor:pointer; color:var(--accent); }} .links a {{ color:var(--accent); margin-right:16px; }} pre {{ white-space:pre-wrap; color:#d6e5f6; }}
  </style>
</head>
<body><main>
  <h1>Quadro QA — Fundos de Viga</h1>
  <p class="meta">Escopo: <code>{html.escape(summary['obra'])}/{html.escape(summary['pavimento'])}/FV</code> · project-id <code>{html.escape(summary['project_id'])}</code> · modo <code>read_only</code> · gerado em <code>{html.escape(summary['generated_at'])}</code></p>
  <h2>Consolidado — todos os tempos</h2>
  <p class="meta">Somente evidência FV persistida no histórico disponível; não é mistura de níveis.</p>
  <section class="cards">{global_cards}</section>
  <h2>Pavimento atual em treino/análise — {html.escape(summary['obra'])} / {html.escape(summary['pavimento'])}</h2>
  <p class="meta">Este é o escopo ativo do relatório e do próximo ciclo de trabalho.</p>
  <section class="cards">{current_cards}</section>
  <h2>Itens do pavimento atual de trabalho — {html.escape(summary['obra'])} / {html.escape(summary['pavimento'])} / FV ({summary['items_n1']} linhas)</h2>
  <div class="table-wrap"><table><colgroup>{columns}</colgroup><thead><tr>{head}</tr></thead><tbody>{table_body}</tbody></table></div>
  <details><summary>Proveniência, limites e atualização</summary>
    <p>Diagnóstico canônico lido: <code>{diagnostic}</code></p>
    <ul>{''.join(f'<li>{html.escape(limit)}</li>' for limit in summary['limits'])}</ul>
    <p>G2-V, N1-V e G5-V são vereditos visuais via <code>g2v_harness.py --backend cli</code>, lidos pelo modelo/agente CLI nos SVGs.</p>
    <p class="links"><a href="{markdown_path.name}">Markdown</a><a href="{csv_path.name}">CSV</a><a href="{json_path.name}">JSON de proveniência</a></p>
    <pre>{refresh}</pre>
  </details>
</main></body></html>\n''',
        encoding="utf-8",
    )
    return html_path


def write_report(summary: dict[str, Any], rows: list[dict[str, str]], output_dir: Path) -> tuple[Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "QUADRO-FV-PAVIMENTO.md"
    csv_path = output_dir / "QUADRO-FV-PAVIMENTO.csv"
    json_path = output_dir / "QUADRO-FV-PAVIMENTO.json"
    headers = [
        ("etapa_proxima", "Etapa atual — próximo passo executável (S1–S8)"),
        ("item", "Identidade FV — item"),
        ("n2_recorte_formal", "S1 — N2: decisão humana do recorte/ficha (gabarito)"),
        ("n2_segmentos", "S1 — N2: ficha emitida + segmentos/painéis de referência (C×L cm)"),
        ("n4_g2_g2v", "S2 / G2 (paridade N2×N4) — N4 do item + G2-V CLI"),
        ("n1_segmentos", "S3 — N1 / SA: geometria por segmento — contorno + dimensão (C×L cm), N1×N2 e N1-V CLI"),
        ("n1_topologia_campos", "S4 — N1 / SA: item completo — quantidade, continuidade e apoio inicial/final por segmento"),
        ("n1_visual_cli", "S4-V / G4-V (interpretação visual N1×N2) — veredito CLI"),
        ("n1_n2_ficha", "S5 / G4 (convergência N1) — ficha N1×N2 e QA campo a campo"),
        ("n3_smoke", "S6 — N3 somente de N1: geração, smoke e selos"),
        ("n3_n4_ficha", "S7 / G5 (paridade final N3×N4) — ficha e QA visual CLI"),
        ("n3_n2_ficha", "S7 — N3×N2: referência adicional de ficha, sem alimentar N3"),
        ("rag_html", "R1 — RAG multimodal: HTML pós-QA, hash e ingestão registrada"),
    ]
    def markdown_seals(levels: dict[str, dict[str, Any]], level: str) -> str:
        order = ("azul", "laranja") if level == "n4" else SEAL_ORDER
        return "; ".join(f"{seal}={levels[level]['seals'][seal]}" for seal in order)
    def mini_rows(levels: dict[str, dict[str, Any]], *, include_g2: bool) -> list[tuple[str, str, str]]:
        return [
            ("N2 — Fichas FV", f"total={levels['n2']['total']}; {markdown_seals(levels, 'n2')}", "azul/laranja herdados read-only da política N4 correspondente"),
            ("N4 — Fundos de Viga", f"total={levels['n4']['total']}; {markdown_seals(levels, 'n4')}", f"G2 (paridade canônica): {summary['g2_lote']}; N4 só azul/laranja" if include_g2 else "N4 só azul/laranja; G2 pertence ao lote atual"),
            ("N1 / SA — Fundos de Viga", f"total={levels['n1']['total']}; {markdown_seals(levels, 'n1')}", "somente selos persistidos no Structural Analyzer (SA)"),
            ("N3 — Fundos de Viga", f"total={levels['n3']['total']}; {markdown_seals(levels, 'n3')}", "somente N3 com smoke ou política persistida"),
        ]
    global_mini = mini_rows(summary["global_levels"], include_g2=False)
    global_mini.insert(
        0,
        (
            "QA FV — cobertura de execução",
            f"obras={summary['qa_fv_coverage']['obras']}; pavimentos={summary['qa_fv_coverage']['pavimentos']}",
            f"{summary['qa_fv_coverage']['runs']} execução(ões) no registro append-only",
        ),
    )
    current_mini = mini_rows(summary["levels"], include_g2=True)
    lines = [
        "# Quadro QA — Fundo de Viga por pavimento", "",
        f"- Escopo: `{summary['obra']}/{summary['pavimento']}/FV`", f"- Project ID: `{summary['project_id']}`",
        f"- Modo: `{summary['mode']}`; gerado em `{summary['generated_at']}`", "",
        "## Consolidado — todos os tempos", "", "| Métrica | Valor | Fonte/limite |", "|---|---:|---|",
    ]
    lines.extend(f"| {_cell(metric)} | {_cell(value)} | {_cell(source)} |" for metric, value, source in global_mini)
    lines.extend(["", f"## Pavimento atual em treino/análise — {summary['obra']} / {summary['pavimento']}", "", "| Métrica | Valor | Fonte/limite |", "|---|---:|---|"])
    lines.extend(f"| {_cell(metric)} | {_cell(value)} | {_cell(source)} |" for metric, value, source in current_mini)
    lines.extend(["", f"## Itens do pavimento atual de trabalho — {summary['obra']} / {summary['pavimento']} / FV", "", "| " + " | ".join(label for _, label in headers) + " |", "|" + "|".join("---" for _ in headers) + "|"])
    for row in rows:
        lines.append("| " + " | ".join(_cell(row[key]) for key, _ in headers) + " |")
    lines.extend([
        "", "## Limites de evidência", "",
        *[f"- {limit}" for limit in summary["limits"]], "",
        "G2-V, N1-V e G5-V são vereditos visuais via `g2v_harness.py --backend cli`, lidos pelo modelo/agente CLI nos SVGs.",
    ])
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[key for key, _ in headers])
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps({"summary": summary, "items": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path = write_html_report(summary, rows, headers, output_dir, markdown_path, csv_path, json_path)
    return markdown_path, csv_path, json_path, html_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--obra", required=True)
    parser.add_argument("--pav", required=True)
    parser.add_argument("--db", type=Path, default=Path(r"D:\Agente-cad-PYSIDE\project_data.vision"))
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--g2-lote", help="sobrescreve STATUS.md somente para auditoria histórica")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    detected_g2, g2_source = _g2_lote_from_status(args.repo_root, args.pav)
    g2_lote = args.g2_lote or detected_g2
    if args.g2_lote:
        g2_source = "--g2-lote (sobrescrita explícita)"
    summary, rows = build_report(args.project_id, args.obra, args.pav, args.db, args.repo_root, g2_lote, g2_source)
    markdown_path, csv_path, json_path, html_path = write_report(summary, rows, args.output_dir)
    print(json.dumps({"summary": summary, "reports": [str(html_path), str(markdown_path), str(csv_path), str(json_path)]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
