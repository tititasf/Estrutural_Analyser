#!/usr/bin/env python3
"""Quadro QA read-only de estado LAJ por pavimento.

Este módulo projeta somente evidências já persistidas no DB real e em relatórios
canônicos. Ele não executa headless, não gera DXF, não roda gates e não grava
selos. N2/N4 são exibidos exclusivamente como comparação: nunca completam N1
ou N3.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = Path(r"D:\Agente-cad-PYSIDE\project_data.vision")
SEALS = ("azul", "laranja", "verde", "rosa")
N4_SEALS = ("azul", "laranja")
ORIGIN_SEAL = {
    "human_ui": "azul", "legacy_human_ui": "azul", "humano_app": "azul",
    "qa_agente": "laranja", "qa_agent": "laranja", "humano_portal": "rosa",
}
REQUIRED_N1 = (
    "name", "laje_dim", "laje_nivel", "laje_outline_segs", "laje_islands",
    "laje_visao_corte", "laje_pilares_apoio", "laje_vizinhas_niveis",
)


def _json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return default


def _item_key(value: str) -> tuple[int, str]:
    match = re.search(r"(\d+)", value)
    return (int(match.group(1)) if match else 10**9, value)


def _pav_key(value: Any) -> str:
    raw = str(value or "").upper().strip()
    match = re.search(r"(?<!\d)(\d{1,2})\s*(?:_?PAV|P)(?![A-Z])", raw)
    return f"{int(match.group(1))}_PAV" if match else raw


def _seal_from_origin(origin: Any) -> str | None:
    return ORIGIN_SEAL.get(str(origin or "").lower().strip())


def _field_origins(raw: Any) -> dict[str, set[str]]:
    """Normaliza schema legado e acumulativo sem inferir origem ausente."""
    value = _json(raw, raw)
    if isinstance(value, list):
        return {str(field): {"humano_app"} for field in value}
    if not isinstance(value, dict):
        return {}
    result: dict[str, set[str]] = {}
    for field, entries in value.items():
        if not isinstance(entries, list):
            continue
        result[str(field)] = {
            str(entry.get("origem")) for entry in entries
            if isinstance(entry, dict) and _seal_from_origin(entry.get("origem"))
        }
    return result


def _n1_seals(row: sqlite3.Row, origins: dict[str, set[str]]) -> set[str]:
    seals: set[str] = set()
    if bool(row["is_validated"]):
        seals.add("verde")
    all_origins = set().union(*origins.values()) if origins else set()
    for origin in all_origins:
        seal = _seal_from_origin(origin)
        if seal:
            seals.add(seal)
    # Azul de cobertura completa é humano-app, nunca deriva de N2/N4.
    if set(REQUIRED_N1).issubset(origins) and all("humano_app" in origins.get(field, set()) for field in REQUIRED_N1):
        seals.add("azul")
    return seals


def _item_seal_line(seals: set[str], *, n4: bool = False) -> str:
    order = N4_SEALS if n4 else SEALS
    labels = {"azul": "🔵 Azul", "laranja": "🟠 Laranja", "verde": "🟢 Verde", "rosa": "🌸 Rosa"}
    return " · ".join(
        f"✅ {labels[seal]}" if seal in seals else f"○ {labels[seal]}"
        for seal in order
    )


def _count_seals(mapping: dict[Any, set[str]], *, n4: bool = False) -> dict[str, int]:
    order = N4_SEALS if n4 else SEALS
    return {seal: sum(seal in values for values in mapping.values()) for seal in order}


def _origin_line(field_ids: list[str], origins: dict[str, set[str]]) -> str:
    counts = {seal: 0 for seal in ("azul", "laranja", "rosa")}
    for field in field_ids:
        for origin in origins.get(field, set()):
            seal = _seal_from_origin(origin)
            if seal in counts:
                counts[seal] += 1
    return f"🔵 SA {counts['azul']} · 🟠 QA {counts['laranja']} · 🌸 Portal {counts['rosa']}"


def _n1_fields_summary(origins: dict[str, set[str]], points: list[tuple[float, float]], links: dict[str, Any]) -> str:
    """Resume a cobertura dos campos obrigatórios LAJ por origem persistida."""
    total = len(REQUIRED_N1)
    counts = {"azul": 0, "laranja": 0, "rosa": 0}
    for field in REQUIRED_N1:
        for origin in origins.get(field, set()):
            seal = _seal_from_origin(origin)
            if seal in counts:
                counts[seal] += 1
    evidence = [
        f"contorno={'sim' if points and links.get('laje_outline_segs') else 'não'}",
        f"apoios={'sim' if _count_evidence(links.get('laje_pilares_apoio')) else 'não'}",
        f"corte={'sim' if _count_evidence(links.get('laje_visao_corte')) else 'não'}",
    ]
    return (
        f"{'✅' if counts['azul'] == total else '⏳'} Campos obrigatórios LAJ: {total}\n"
        f"{'✅' if counts['azul'] == total else '○'} 🔵 Azul: {counts['azul']}/{total}\n"
        f"{'✅' if counts['laranja'] == total else '○'} 🟠 Laranja: {counts['laranja']}/{total}\n"
        f"{'✅' if counts['rosa'] == total else '○'} 🌸 Rosa: {counts['rosa']}/{total}\n"
        f"Evidência N1: {' · '.join(evidence)}\n"
        "Detalhe por família permanece no JSON/SVG; relações não substituem o contorno."
    )


def _points(raw: Any) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for point in _json(raw, []):
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            try:
                result.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError):
                pass
    return result


def _bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float] | None:
    if not points:
        return None
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def _distinct_vertices(points: list[tuple[float, float]]) -> int:
    """Remove somente repetição consecutiva/fechamento, preservando degraus reais."""
    compact: list[tuple[float, float]] = []
    for point in points:
        if not compact or compact[-1] != point:
            compact.append(point)
    if len(compact) > 1 and compact[0] == compact[-1]:
        compact.pop()
    return len(compact)


def _list_at(links: dict[str, Any], *keys: str) -> list[Any]:
    value: Any = links
    for key in keys:
        if not isinstance(value, dict):
            return []
        value = value.get(key)
    return value if isinstance(value, list) else []


def _family_geometry(points: list[tuple[float, float]], links: dict[str, Any], origins: dict[str, set[str]]) -> str:
    contour = links.get("laje_outline_segs")
    closed = len(points) >= 4 and points[0] == points[-1]
    state = "CONFIRMAR" if points and contour else "PENDENTE"
    return f"{'✅' if state == 'CONFIRMAR' else '⏳'} {state}: pontos={len(points)}; fechado={closed}; contorno={'sim' if contour else 'não'}\n{_origin_line(['laje_outline_segs', 'laje_islands'], origins)}"


def _family_dimension(links: dict[str, Any], origins: dict[str, set[str]]) -> str:
    dim = _list_at(links, "laje_dim", "label")
    text = next((str(item.get("text")) for item in dim if isinstance(item, dict) and item.get("text")), None)
    return f"{'✅ CONFIRMAR' if text else '⏳ PENDENTE'}: espessura={text or 'não persistida'}\n{_origin_line(['laje_dim'], origins)}"


def _family_levels(links: dict[str, Any], origins: dict[str, set[str]]) -> str:
    labels = _list_at(links, "laje_nivel", "label")
    text = next((str(item.get("text")) for item in labels if isinstance(item, dict) and item.get("text")), None)
    inferred = any(bool(item.get("is_inferred")) for item in labels if isinstance(item, dict))
    note = " (inferido: confirmar fonte)" if inferred else ""
    return f"{'👁️ TRILHA_N1_OBSERVADA' if text else '⏳ PENDENTE'}: nível={text or 'não persistido'}{note}\n{_origin_line(['laje_nivel', 'laje_vizinhas_niveis'], origins)}"


def _count_evidence(value: Any) -> int:
    """Conta somente entradas persistidas; um dict é uma família, não uma lista vazia."""
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return sum(1 for entry in value.values() if entry not in (None, [], {}, ""))
    return 0


def _family_holes(points: list[tuple[float, float]], links: dict[str, Any], origins: dict[str, set[str]]) -> str:
    obstacles = links.get("obstaculos") or links.get("laje_obstaculos") or []
    islands = links.get("laje_islands") or []
    count = _count_evidence(obstacles)
    islands_count = _count_evidence(islands)
    irregular = _distinct_vertices(points) > 4
    state = "TRILHA_N1_OBSERVADA" if count or islands_count or irregular else "N/A (nenhum persistido)"
    contour_note = "; recorte no contorno=sim" if irregular else ""
    icon = '👁️' if state == 'TRILHA_N1_OBSERVADA' else '—'
    return f"{icon} {state}: obstáculos={count}; ilhas/recortes={islands_count}{contour_note}\n{_origin_line(['laje_islands'], origins)}"


def _family_cut(links: dict[str, Any], origins: dict[str, set[str]]) -> str:
    cut = links.get("laje_visao_corte") or links.get("_laje_complex", {}).get("cut_view") or []
    count = _count_evidence(cut)
    return f"{'👁️ TRILHA_N1_OBSERVADA' if count else '— N/A (sem corte persistido)'}: evidências={count}\n{_origin_line(['laje_visao_corte'], origins)}"


def _family_supports(points: list[tuple[float, float]], links: dict[str, Any], origins: dict[str, set[str]]) -> str:
    support = links.get("laje_pilares_apoio") or {}
    pillars = support.get("pillar_geom") if isinstance(support, dict) else []
    pillars = pillars if isinstance(pillars, list) else []
    contacts = sum(1 for p in pillars if isinstance(p, dict) and (p.get("touch_face") or p.get("pillar_side")))
    state = "TRILHA_N1_OBSERVADA" if pillars else "N/A (sem apoio persistido)"
    icon = '👁️' if pillars else '—'
    return f"{icon} {state}: pilares={len(pillars)}; face/contato declarado={contacts}\nProximidade não substitui interseção geométrica.\n{_origin_line(['laje_pilares_apoio'], origins)}"


def _family_context(links: dict[str, Any], origins: dict[str, set[str]]) -> str:
    neighbors = links.get("laje_vizinhas_niveis") or []
    unions = links.get("unioes_nos_bordes") or []
    n_count = _count_evidence(neighbors)
    u_count = _count_evidence(unions)
    state = "TRILHA_N1_OBSERVADA" if n_count or u_count else "N/A (sem relação persistida)"
    icon = '👁️' if state == 'TRILHA_N1_OBSERVADA' else '—'
    return f"{icon} {state}: vizinhas={n_count}; uniões_bordo={u_count}\nRelação próxima não prova geometria.\n{_origin_line(['laje_vizinhas_niveis'], origins)}"


def _family_interference(links: dict[str, Any], origins: dict[str, set[str]]) -> str:
    obstacles = links.get("obstaculos") or []
    unions = links.get("unioes_nos_bordes") or []
    count = _count_evidence(obstacles) + _count_evidence(unions)
    return f"{'👁️ TRILHA_N1_OBSERVADA' if count else '— N/A (nenhuma exceção persistida)'}: exceções={count}\n{_origin_line(['laje_islands'], origins)}"


def _policy_seals(rows: list[sqlite3.Row], items: set[str], scope: str) -> dict[str, set[str]]:
    result = {item: set() for item in items}
    for row in rows:
        if str(row["scope"]).upper() != scope or not bool(row["locked"]):
            continue
        seal = _seal_from_origin(row["validation_origin"])
        if not seal or (scope == "N4" and seal not in N4_SEALS):
            continue
        # LAJ identities are individual; do not expand an unknown grouped policy.
        item = str(row["item_id"] or "").upper()
        if item in result:
            result[item].add(seal)
    return result


def _latest_diagnostic(repo_root: Path, obra: str, pav: str) -> tuple[Path | None, dict[str, Any]]:
    root = repo_root / "scripts" / "arete" / "relatorios" / "diagnosticos_laj" / obra / pav
    paths = sorted(root.glob("**/diagnostico_laj_n1_n2.json"), key=lambda path: path.stat().st_mtime) if root.exists() else []
    if not paths:
        return None, {}
    return paths[-1], _json(paths[-1].read_text(encoding="utf-8"), {})


def _g2_status(repo_root: Path, pav: str) -> tuple[str, str]:
    path = repo_root / "docs" / "STATUS.md"
    if not path.exists():
        return "não consultado", "STATUS.md ausente"
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in line.split("|") if part.strip()]
        if len(parts) >= 8 and parts[0] in {"LAJ", "LJ"} and parts[1] == pav:
            try:
                passed, failed, blocked = map(int, parts[3:6])
                return ("PASS" if failed == 0 and blocked == 0 else "FAIL") + f" {passed}/{passed + failed + blocked}", str(path)
            except ValueError:
                pass
    return "não consultado", str(path)


def _g2v(repo_root: Path, pav: str, par: str, gate: str) -> dict[str, str]:
    result: dict[str, tuple[float, str]] = {}
    root = repo_root / "scripts" / "arete" / "relatorios" / "g2v"
    for path in root.glob("**/relatorio.json") if root.exists() else []:
        report = _json(path.read_text(encoding="utf-8"), {})
        if not isinstance(report, dict) or report.get("classe") not in {"LAJ", "LJ"}:
            continue
        if report.get("pavimento") != pav or report.get("par") != par or report.get("gate") != gate:
            continue
        for item in report.get("itens") or []:
            if not isinstance(item, dict) or item.get("fonte_imagem") != "html_svg_vetorial":
                continue
            cli = (item.get("vereditos") or {}).get("cli") or {}
            verdict = str(cli.get("veredito") or "").upper()
            if cli.get("aguardando_agente") or verdict not in {"PASS", "FAIL", "SUSPEITO"}:
                continue
            key = str(item.get("elemento_id") or "").upper()
            if key and (key not in result or path.stat().st_mtime > result[key][0]):
                result[key] = (path.stat().st_mtime, verdict)
    return {key: value for key, (_, value) in result.items()}


def _n3_smokes(repo_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in (repo_root / "scripts" / "arete" / "relatorios").glob("**/qa_n3_smoke*.json"):
        report = _json(path.read_text(encoding="utf-8"), {})
        match = re.search(r"(?:LAJ|LJ):(L\d+)", str(report.get("question") or ""), re.I)
        if match:
            result[match.group(1).upper()] = str(report.get("overall") or "N/A").upper()
    return result


def _n2_by_item(connection: sqlite3.Connection, obra: str, pav: str) -> dict[str, sqlite3.Row]:
    # Fichas N2 são legadas e podem não ter projeto_id; escopo explícito obra+pav+classe
    # evita tanto perda de prova quanto mistura entre pavimentos.
    rows = connection.execute(
        "SELECT elemento_id, campos_json, status, aprovado_at, confianca, recorte_path, updated_at "
        "FROM reverse_eng_fichas WHERE obra_name=? AND pavimento=? AND upper(classe) IN ('LAJ','LJ') "
        "ORDER BY updated_at DESC, id DESC", (obra, pav)
    ).fetchall()
    result: dict[str, sqlite3.Row] = {}
    for row in rows:
        result.setdefault(str(row["elemento_id"] or "").upper(), row)
    return result


def _rag_t1_by_item(connection: sqlite3.Connection, project_id: str) -> dict[str, list[dict[str, str]]]:
    """Lê somente T1 curado e aprovado, sem confundir candidato com ingestão.

    Uma linha só é considerada ingerida quando a regra T1 em ``semantic_rag_kb``
    tem o mesmo ``candidate_id`` de um evento humano ``APPROVED``. O payload do
    candidato contém os itens e campos; portanto um evento agregado ``MULTI``
    continua rastreável até cada laje sem inventar uma aprovação individual.
    """
    approvals: dict[str, str] = {}
    for row in connection.execute(
        "SELECT estado_novo_json, approved_at FROM human_event_logs "
        "WHERE obra_id=? AND upper(classe) IN ('LAJ','LJ') "
        "AND event_kind='approval' AND status='APPROVED' AND tier='T1'",
        (project_id,),
    ):
        event = _json(row["estado_novo_json"], {})
        candidate_id = str(event.get("candidate_id") or "") if isinstance(event, dict) else ""
        if candidate_id:
            approvals[candidate_id] = str(row["approved_at"] or "")

    result: dict[str, list[dict[str, str]]] = {}
    for row in connection.execute(
        "SELECT regra_semantica FROM semantic_rag_kb "
        "WHERE upper(classe) IN ('LAJ','LJ') AND obra_contexto=?",
        (f"qa_groundtruth_t1:{project_id}",),
    ):
        rule = _json(row["regra_semantica"], {})
        if not isinstance(rule, dict) or rule.get("tier") != "T1":
            continue
        candidate_id = str(rule.get("candidate_id") or "")
        if not candidate_id or candidate_id not in approvals:
            continue
        field_id = str(rule.get("field_id") or "")
        for item in rule.get("items") or []:
            key = str(item or "").upper()
            if key:
                result.setdefault(key, []).append({
                    "field_id": field_id,
                    "candidate_id": candidate_id,
                    "approved_at": approvals[candidate_id],
                })
    return result


def _rag_ingestion_cell(entries: list[dict[str, str]]) -> str:
    """Estado read-only da curadoria T1 já ingerida para a laje desta linha."""
    if not entries:
        return (
            "⏳ RAG T1 não registrado para este item\n"
            "Exige entrada semantic_rag_kb + evento humano APPROVED do mesmo candidate_id.\n"
            "Candidato/materialização isolado não conta como ingestão."
        )
    fields = sorted({entry["field_id"] for entry in entries if entry["field_id"]})
    covered = len(set(fields) & set(REQUIRED_N1))
    candidates = sorted({entry["candidate_id"] for entry in entries})
    approved_at = max((entry["approved_at"] for entry in entries if entry["approved_at"]), default="data não registrada")
    return (
        f"✅ RAG T1 ingerido após QA: {covered}/{len(REQUIRED_N1)} campos N1\n"
        f"Campos: {', '.join(fields) or 'sem campo declarado'}\n"
        f"Curadoria humana: {len(candidates)} candidato(s); última aprovação {approved_at}\n"
        "Registro consultivo: nunca substitui a prova local deste item."
    )


def _svg(item: str, points: list[tuple[float, float]], output: Path, title: str) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    if not points:
        body = '<text x="12" y="24">Sem points_json persistido; SVG não prova geometria.</text>'
    else:
        box = _bbox(points)
        assert box
        xmin, ymin, xmax, ymax = box
        dx, dy = max(xmax - xmin, 1.0), max(ymax - ymin, 1.0)
        scale = min(500 / dx, 300 / dy)
        mapped = [(40 + (x - xmin) * scale, 340 - (y - ymin) * scale) for x, y in points]
        polygon = " ".join(f"{x:.2f},{y:.2f}" for x, y in mapped)
        body = (
            '<rect x="1" y="1" width="598" height="378" fill="#101827" stroke="#334155"/>'
            f'<polyline points="{polygon}" fill="rgba(6,182,212,.12)" stroke="#22d3ee" stroke-width="2"/>'
            f'<circle cx="{mapped[0][0]:.2f}" cy="{mapped[0][1]:.2f}" r="4" fill="#facc15"/>'
            '<text x="12" y="24" fill="#e2e8f0">points_json N1: contorno bruto persistido</text>'
        )
    document = f'''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="380" viewBox="0 0 600 380" role="img" aria-label="{html.escape(title)}"><title>{html.escape(title)}</title>{body}</svg>'''
    output.write_text(document, encoding="utf-8")
    return output


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def _readonly_connection(db_path: Path) -> sqlite3.Connection:
    """Impede por contrato que uma regeneração do quadro abra caminho de escrita."""
    resolved = db_path.resolve().as_posix()
    return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)


def _next(n2_exists: bool, n4: set[str], points: list[tuple[float, float]], origins: dict[str, set[str]], diagnostic: dict[str, Any] | None, n3: set[str]) -> tuple[str, str]:
    if not n2_exists:
        return "S1 — N2", "materializar/decidir recorte N2; sem ficha comparadora persistida"
    if not n4:
        return "S2 — N4", "executar G2/G2-V CLI e registrar decisão persistida"
    if not points:
        return "S3 — N1/SA", "materializar N1 do DXF original pelo headless canônico"
    if not set(REQUIRED_N1).issubset(origins):
        return "S4 — N1/SA", "probe/review das famílias N1 ainda sem origem permitida"
    if not diagnostic:
        return "S5 — N1×N2", "diagnóstico comparativo; N2 só denuncia, nunca preenche N1"
    if not n3:
        return "S6 — N3", "gerar apenas de N1 e executar smoke"
    return "S7 — N3×N4", "comparar N3×N4 e N3×N2; registrar veredito visual CLI"


def build_report(project_id: str, obra: str, pav: str, db_path: Path, repo_root: Path, output_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    connection = _readonly_connection(db_path)
    connection.row_factory = sqlite3.Row
    try:
        project = connection.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise ValueError(f"project_id inexistente: {project_id}")
        technical_pav = str(project["pavement_name"] or pav)
        slabs = connection.execute(
            "SELECT name, area, points_json, links_json, validated_fields_json, is_validated, extra_data_json "
            "FROM slabs WHERE project_id=? ORDER BY name", (project_id,)
        ).fetchall()
        # Pavimento sem N1 ainda é um estado operacional válido: o quadro precisa
        # expor que S3 está bloqueada, não desaparecer nem fingir uma linha LAJ.
        # Nenhum item é inventado a partir do N2 para preencher esta lacuna.
        items = {str(row["name"]).upper() for row in slabs}
        policy_rows = connection.execute(
            "SELECT item_id, scope, locked, validation_origin FROM artifact_validation_policies "
            "WHERE obra_name=? AND pavimento=? AND upper(classe) IN ('LAJ','LJ') AND scope IN ('N3','N4')",
            (obra, technical_pav),
        ).fetchall()
        n2_rows = _n2_by_item(connection, obra, pav)
        global_slabs = connection.execute("SELECT name, validated_fields_json, is_validated FROM slabs").fetchall()
        global_n2_rows = connection.execute(
            "SELECT obra_name, pavimento, elemento_id FROM reverse_eng_fichas WHERE upper(classe) IN ('LAJ','LJ')"
        ).fetchall()
        global_policies = connection.execute(
            "SELECT obra_name,pavimento,item_id,scope,locked,validation_origin FROM artifact_validation_policies "
            "WHERE upper(classe) IN ('LAJ','LJ') AND scope IN ('N3','N4')"
        ).fetchall()
        rag_t1 = _rag_t1_by_item(connection, project_id)
    finally:
        connection.close()

    n4 = _policy_seals(policy_rows, items, "N4")
    n3 = _policy_seals(policy_rows, items, "N3")
    diag_path, diagnostic = _latest_diagnostic(repo_root, obra, pav)
    diag_items = {str(row.get("item") or "").upper(): row for row in diagnostic.get("itens", []) if isinstance(row, dict)}
    # O par legado ``n1xn2`` mistura N2 e, portanto, não satisfaz o contrato
    # N1-V deste quadro: leitura N1 próximo + N1 distante contra o DXF original.
    # Ele permanece na coluna diagnóstica N1×N2 e não pode acender este campo.
    n1v: dict[str, str] = {}
    g2v = _g2v(repo_root, pav, "n2xn4", "G2-V")
    smokes = _n3_smokes(repo_root)
    g2, g2_source = _g2_status(repo_root, pav)

    rows: list[dict[str, Any]] = []
    for slab in slabs:
        item = str(slab["name"]).upper()
        points = _points(slab["points_json"])
        links = _json(slab["links_json"], {})
        origins = _field_origins(slab["validated_fields_json"])
        n1_seal = _n1_seals(slab, origins)
        n2_seal = n4.get(item, set())
        n3_seal = n3.get(item, set())
        n2row = n2_rows.get(item)
        stage, next_step = _next(n2row is not None, n4.get(item, set()), points, origins, diag_items.get(item), set(smokes) | {key for key, v in n3.items() if v})
        svg_path = _svg(item, points, output_dir / "svg" / f"{item}_N1_contorno.svg", f"{item}: evidência N1 local")
        diag = diag_items.get(item)
        evidence = (diag or {}).get("evidencia") or {}
        geo = evidence.get("geometria") or {}
        n1_n2 = "⏳ não comparada / QA pendente" if not diag else (
            f"👁️ auto {evidence.get('classificacao', 'N/A')}; IoU={geo.get('iou', 'N/A')} / QA pendente"
        )
        technical = str(n2row["status"] or "sem ficha") if n2row else "sem ficha"
        n2cell = (f"✅ Validação N2: SIM ({_item_seal_line(n2_seal, n4=True)})\n" if n2_seal else "⏳ Validação N2: NÃO\n") + f"Estado técnico: {technical}"
        n4cell = (
            (f"Selos N4: {_item_seal_line(n4.get(item, set()), n4=True)}\n")
            + f"{'✅' if str(g2).startswith('PASS') else '⏳'} G2 lote: {g2}\n"
            + (f"✅ G2-V CLI: {g2v[item]}" if item in g2v else "⏳ G2-V CLI: não registrado")
        )
        smoke = smokes.get(item, 'não evidenciado')
        n3cell = f"{'✅' if smoke == 'PASS' else '⏳'} smoke: {smoke}\nSelos N3: {_item_seal_line(n3_seal)}"
        rows.append({
            "etapa_proxima": f"{stage} — {next_step}", "item": item,
            "n2": n2cell, "n4": n4cell,
            "n1_sa": f"{_item_seal_line(n1_seal)}\npoints_json={len(points)}; área={slab['area'] if slab['area'] is not None else 'não persistida'}\nOrigens permitidas LAJ: payload/geometry N1; N2/N4 bloqueados.",
            "campos_n1": _n1_fields_summary(origins, points, links),
            "n1_v_cli": (
                f"✅ {n1v[item]}" if item in n1v else
                "⏳ não emitido: exige SVG N1 próximo + distante e leitura contra o DXF original; N2 é proibido neste veredito"
            ),
            "n1_n2": n1_n2,
            "n3": n3cell,
            "n3_visual_paineis": "⏳ não emitido: inspeção visual CLI N3-only de cotas, linhas verticais/horizontais, recortes, uniões e distribuição de painéis; N2/N4 não são entrada",
            "n3_n4": "⏳ não comparada / QA pendente", "n3_n2": "⏳ não comparada / QA pendente",
            "rag_html_t1": _rag_ingestion_cell(rag_t1.get(item, [])),
            "poligono_contorno": _family_geometry(points, links, origins),
            "dimensoes_espessura": _family_dimension(links, origins),
            "niveis": _family_levels(links, origins),
            "furos_recortes": _family_holes(points, links, origins),
            "visao_corte": _family_cut(links, origins),
            "pilares_vigas_apoio": _family_supports(points, links, origins),
            "interferencias_continuidade": _family_interference(links, origins),
            "evidencia_svg": str(svg_path), "_stage": stage,
        })
    rows.sort(key=lambda row: _item_key(row["item"]))

    # Consolidação histórica separada do pavimento atual, com a mesma semântica de selos.
    global_n1 = {
        f"{index}:{row['name']}": _n1_seals(row, _field_origins(row["validated_fields_json"]))
        for index, row in enumerate(global_slabs)
    }
    global_n2_keys = {(str(row["obra_name"]), _pav_key(row["pavimento"]), str(row["elemento_id"]).upper()) for row in global_n2_rows}
    global_n4 = {key: set() for key in global_n2_keys}
    global_n3 = {key: set() for key in global_n2_keys}
    for policy in global_policies:
        key = (str(policy["obra_name"]), _pav_key(policy["pavimento"]), str(policy["item_id"] or "").upper())
        if key not in global_n4 or not bool(policy["locked"]):
            continue
        seal = _seal_from_origin(policy["validation_origin"])
        if not seal:
            continue
        if str(policy["scope"]).upper() == "N4" and seal in N4_SEALS:
            global_n4[key].add(seal)
        if str(policy["scope"]).upper() == "N3":
            global_n3[key].add(seal)
    levels = {
        "n1": {"total": len(items), "seals": _count_seals({str(row["name"]): _n1_seals(row, _field_origins(row["validated_fields_json"])) for row in slabs})},
        "n2": {"total": len(n2_rows), "seals": _count_seals({key: n4.get(key, set()) for key in n2_rows}, n4=False)},
        "n3": {"total": len(set(smokes) | {key for key, seals in n3.items() if seals}), "seals": _count_seals(n3)},
        "n4": {"total": len(n2_rows), "seals": _count_seals({key: n4.get(key, set()) for key in n2_rows}, n4=True)},
    }
    all_time = {
        "n1": {"total": len(global_n1), "seals": _count_seals(global_n1)},
        "n2": {"total": len(global_n2_keys), "seals": _count_seals(global_n4)},
        "n3": {"total": len(global_n3), "seals": _count_seals(global_n3)},
        "n4": {"total": len(global_n4), "seals": _count_seals(global_n4, n4=True)},
    }
    summary = {
        "schema": "arete.qa_laj_quadro_pavimento/v1", "mode": "read_only",
        "generated_at": datetime.now(timezone.utc).isoformat(), "project_id": project_id,
        "obra": obra, "pavimento": pav, "pavimento_tecnico": technical_pav,
        "items": len(rows), "levels": levels, "all_time_levels": all_time,
        "source_db_sha256": _sha(db_path),
        "g2_lote": g2, "g2_source": g2_source, "diagnostic_path": str(diag_path) if diag_path else None,
        "diagnostic_items": len(diag_items),
        "predicate": f"{len(rows)} linhas N1; N4 só azul/laranja; N1/N3 quatro selos; oito famílias LAJ independentes; SVG de points_json e ingestão RAG T1 rastreável por item.",
        "limits": [
            "Read-only: não grava DB, selos, N2/N4, DXFs ou JSONs Fase-4.",
            "Sem N1 persistido, o quadro mantém zero linhas e evidencia S3 pendente; nunca cria linha LAJ a partir de N2.",
            "N2/N4 são comparadores e não completam geometria, campos ou relações N1/N3.",
            "Apoio próximo nunca prova contato: exige identidade e interseção/face no payload e SVG local.",
            "G2 é evidência de lote dentro de N4; G2-V/N1-V são apenas vereditos CLI SVG persistidos.",
            "SVG mostra points_json N1 persistido; não é aprovação visual nem substitui g2v_harness --backend cli.",
            "RAG só fica ingerido quando semantic_rag_kb T1 e human_event_logs APPROVED apontam ao mesmo candidate_id; candidato solto não conta.",
            "Fichas N2 históricas sem projeto_id são associadas somente por obra+pavimento+classe e identificadas como comparadores.",
        ],
    }
    return summary, rows


HEADERS = [
    ("etapa_proxima", "Etapa atual / próximo passo\nA cor replica a coluna que deve ser atacada agora.\nNão é selo: é a menor ação que move a laje."),
    ("item", "Identidade\nNome da laje N1 no projeto selecionado.\nToda prova desta linha pertence a este item."),
    ("n2", "S1 — N2: recorte/ficha comparadora\nMostra se há ficha reversa e se o aceite N4 é projetado em leitura.\nNunca fornece geometria ou campo para N1/N3."),
    ("n4", "S2 — N4: geração reversa aceita\nSomente selo humano azul ou QA laranja. G2 é paridade do lote; G2-V é veredito visual CLI.\nNão cria campos N1/N3."),
    ("n1_sa", "S3 — N1/SA: interpretação do DXF original\nPoints, área e quatro selos persistidos do Structural Analyzer.\nOrigem permitida: geometry/payload N1, nunca N2/N4."),
    ("n1_v_cli", "S5 — N1-V / G4-V: veredito visual CLI do N1\nAgente lê SVG N1 próximo/local e SVG N1 distante/contextual contra o DXF original.\nNão abre, consulta ou usa N2; registra PASS/FAIL/SUSPEITO sem reescrever N1."),
    ("n1_n2", "S5 — N1×N2: diagnóstico comparativo\nIoU, área e dimensões localizam divergência para o QA.\nResultado automático não é selo nem verdade geométrica completa."),
    ("n3", "S6 — N3: desenho nascido de N1\nSmoke do contrato/variantes e quatro selos N3 já persistidos.\nSmoke não substitui equivalência visual."),
    ("n3_n4", "S7 — N3×N4: paridade final\nG5/G5-V confrontam o desenho N3 com N4 por CLI e decisão QA.\nN4 é comparador; jamais gabarito de N3."),
    ("n3_n2", "S7 — N3×N2: diagnóstico auxiliar\nComparação de ficha para localizar causa entre interpretação e geração.\nNunca é entrada do motor N3."),
    ("poligono_contorno", "S4 — Polígono / contorno\nFechamento, vértices, área e segmentos persistidos do próprio N1.\nÉ a prova geométrica isolada, anterior a relações."),
    ("dimensoes_espessura", "S4 — Dimensões / espessura\nLê apenas laje_dim do payload N1 e sua origem de validação.\nValor ausente ou inferido não recebe aprovação automática."),
    ("niveis", "S4 — Níveis\nExpõe nível N1, fonte e se foi inferido.\nVizinhança pode explicar; nunca copia o nível da outra laje."),
    ("furos_recortes", "S4 — Furos / recortes\nSepara exceção estruturada de simples vértice irregular do contorno.\nIrregularidade observada não prova semântica de furo."),
    ("visao_corte", "S4 — Visão de corte\nEvidência contextual de transição, cota ou topologia local.\nNunca substitui o contorno N1."),
    ("pilares_vigas_apoio", "S4 — Pilares/vigas de apoio\nExige identidade, geometria e face/contato declarados.\nProximidade de bbox não é apoio validado."),
    ("interferencias_continuidade", "S4 — Interferência/continuidade\nVizinhas, uniões e obstáculos são relações/exceções rastreáveis.\nRelação próxima nunca prova a geometria da laje."),
    ("evidencia_svg", "Evidência SVG N1 local\nVisualização vetorial do points_json persistido desta linha.\nServe à inspeção; não é sozinho um veredito visual."),
]

# A tabela é compacta: detalhes das famílias S4 seguem preservados na linha
# interna/JSON, mas são condensados em uma cobertura de campos por selo.
VISIBLE_HEADERS = [
    ("etapa_proxima", "Etapa atual / próximo passo\nA cor replica a coluna-alvo; não é selo."),
    ("item", "Identidade\nItem LAJ N1 do projeto selecionado."),
    ("n2", "S1 — N2: recorte/ficha comparadora\nExiste ficha e aceite N4 projetado em leitura? Nunca alimenta N1/N3."),
    ("n4", "S2 — N4: geração reversa aceita\nSelos azul/laranja, G2 do lote e G2-V CLI; não cria N1/N3."),
    ("n1_sa", "S3 — Validação N1/SA\nPoints, área e quatro selos persistidos do Structural Analyzer."),
    ("campos_n1", "S4 — Campos N1: cobertura por selo\nConta os 8 campos obrigatórios LAJ por azul/laranja/rosa. Detalhes ficam no JSON/SVG."),
    ("n1_v_cli", "S5 — N1-V / G4-V: visual N1-only\nSVG próximo+distante contra DXF original; N2 é proibido."),
    ("n1_n2", "S5 — N1×N2: diagnóstico comparativo\nLocaliza divergência; nunca é selo ou fonte de N1."),
    ("n3", "S6 — N3: contrato e selos\nSmoke e quatro selos persistidos; N3 nasce somente de N1."),
    ("n3_visual_paineis", "S6 — N3-V: cotas e painelização\nRevisão visual CLI de cotas, linhas verticais/horizontais, recortes, uniões e distribuição."),
    ("n3_n4", "S7 — N3×N4: paridade final\nG5/G5-V e QA; N4 compara, nunca é gabarito do N3."),
    ("n3_n2", "S7 — N3×N2: diagnóstico auxiliar\nLocaliza causa; nunca alimenta o motor N3."),
    ("rag_html_t1", "S8 — RAG T1 por item: ingestão pós-QA\nSó acende com entrada T1 em semantic_rag_kb e evento humano APPROVED do mesmo candidato. Mostra campos realmente alimentados."),
    ("evidencia_svg", "Evidência SVG N1 local\nVisualização do points_json; serve à inspeção, não é veredito isolado."),
]

# Cor é semântica de etapa, não veredito. O estado PASS/PENDENTE/FAIL continua
# explícito no conteúdo e acrescenta somente uma borda; assim a cor nunca finge
# aprovação nem disputa com o próximo passo.
COLUMN_COLORS = {
    "etapa_proxima": "stage", "item": "identity", "n2": "n2", "n4": "n4",
    "n1_sa": "n1", "campos_n1": "fields", "n1_v_cli": "n1v", "n1_n2": "n1n2", "n3": "n3",
    "n3_visual_paineis": "n3v",
    "n3_n4": "n3n4", "n3_n2": "n3n2", "rag_html_t1": "rag", "poligono_contorno": "geometry",
    "dimensoes_espessura": "dimension", "niveis": "levels", "furos_recortes": "cuts",
    "visao_corte": "section", "pilares_vigas_apoio": "supports",
    "interferencias_continuidade": "context", "evidencia_svg": "svg",
}
STAGE_TARGET = {
    "S1": "n2", "S2": "n4", "S3": "n1", "S4": "fields", "S5": "n1v",
    "S6": "n3", "S7": "n3n4", "S8": "n3n2",
}


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _status(value: str) -> str:
    lowered = value.lower()
    if "fail" in lowered or "revisar_humano" in lowered:
        return "fail"
    if any(token in lowered for token in ("pendente", "não evidenciado", "não comparada", "não registrado", "n/a")):
        return "pending"
    return "pass"


def _cards(title: str, levels: dict[str, Any], g2: str | None = None) -> str:
    labels = {"n1": "N1 / SA — Lajes", "n2": "N2 — Fichas LAJ", "n3": "N3 — Lajes", "n4": "N4 — Lajes"}
    cards = []
    for level in ("n1", "n2", "n3", "n4"):
        data = levels[level]
        order = N4_SEALS if level == "n4" else SEALS
        seals = " · ".join(f"{seal}={data['seals'].get(seal, 0)}" for seal in order)
        suffix = f"<br><small>G2 lote: {html.escape(g2)}</small>" if level == "n4" and g2 else ""
        cards.append(f"<section class='card'><b>{labels[level]}</b><strong>{data['total']}</strong><span>{seals}</span>{suffix}</section>")
    return f"<h2>{html.escape(title)}</h2><div class='cards'>{''.join(cards)}</div>"


def write_report(summary: dict[str, Any], rows: list[dict[str, Any]], output_dir: Path) -> tuple[Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    md = output_dir / "QUADRO-LAJ-PAVIMENTO.md"
    csv_path = output_dir / "QUADRO-LAJ-PAVIMENTO.csv"
    json_path = output_dir / "QUADRO-LAJ-PAVIMENTO.json"
    html_path = output_dir / "QUADRO-LAJ-PAVIMENTO.html"
    visible = [{key: row[key] for key, _ in VISIBLE_HEADERS} for row in rows]
    detail_keys = (
        "poligono_contorno", "dimensoes_espessura", "niveis", "furos_recortes",
        "visao_corte", "pilares_vigas_apoio", "interferencias_continuidade",
    )
    n1_field_details = [
        {"item": row["item"], **{key: row[key] for key in detail_keys}}
        for row in rows
    ]
    json_path.write_text(
        json.dumps(
            {"summary": summary, "items": visible, "detalhe_campos_n1": n1_field_details},
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[key for key, _ in VISIBLE_HEADERS])
        writer.writeheader(); writer.writerows(visible)
    lines = ["# Quadro QA — Lajes por pavimento", "", f"- Escopo: `{summary['obra']}/{summary['pavimento']}/LAJ`", f"- Project ID: `{summary['project_id']}`", f"- Modo: `{summary['mode']}`", f"- Predicado: {summary['predicate']}", "", "## Todos os tempos", "", "| Nível | Total | Selos |", "|---|---:|---|"]
    for level in ("n1", "n2", "n3", "n4"):
        data = summary["all_time_levels"][level]; order = N4_SEALS if level == "n4" else SEALS
        lines.append(f"| {level.upper()} | {data['total']} | " + "; ".join(f"{seal}={data['seals'].get(seal,0)}" for seal in order) + " |")
    lines.extend(["", "## Pavimento atual", "", "| Nível | Total | Selos |", "|---|---:|---|"])
    for level in ("n1", "n2", "n3", "n4"):
        data = summary["levels"][level]; order = N4_SEALS if level == "n4" else SEALS
        suffix = f"; G2={summary['g2_lote']}" if level == "n4" else ""
        lines.append(f"| {level.upper()} | {data['total']} | " + "; ".join(f"{seal}={data['seals'].get(seal,0)}" for seal in order) + suffix + " |")
    lines.extend(["", "## Linhas por laje", "", "| " + " | ".join(label for _, label in VISIBLE_HEADERS) + " |", "|" + "|".join("---" for _ in VISIBLE_HEADERS) + "|"])
    lines.extend("| " + " | ".join(_cell(row[key]) for key, _ in VISIBLE_HEADERS) + " |" for row in visible)
    lines.extend(["", "## Limites", "", *[f"- {item}" for item in summary["limits"]], "", "Regenerar este quadro após todo microciclo que leia ou produza nova evidência persistida. A regeneração é somente leitura."])
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    table_head = "".join(f"<th class='col-{COLUMN_COLORS[key]}'>{html.escape(label).replace(chr(10), '<br>')}</th>" for key, label in VISIBLE_HEADERS)
    stage_by_item = {str(row["item"]): str(row.get("_stage") or "") for row in rows}
    table_rows = []
    for row in visible:
        values = []
        for key, _ in VISIBLE_HEADERS:
            value = str(row[key]); content = html.escape(value).replace("\n", "<br>")
            if key == "evidencia_svg":
                content = f"<a href='{html.escape(Path(value).relative_to(output_dir).as_posix() if Path(value).is_relative_to(output_dir) else value)}'>abrir SVG</a>"
            color = COLUMN_COLORS[key]
            if key == "etapa_proxima":
                stage_code = stage_by_item.get(str(row["item"]), "").split(" ", 1)[0]
                color = STAGE_TARGET.get(stage_code, "stage")
            values.append(f"<td class='col-{color} {_status(value)}'>{content}</td>")
        table_rows.append("<tr>" + "".join(values) + "</tr>")
    document = f"""<!doctype html><html lang='pt-BR'><meta charset='utf-8'><title>Quadro LAJ — {html.escape(summary['obra'])}/{html.escape(summary['pavimento'])}</title><style>
body{{background:#0f172a;color:#e2e8f0;font:14px system-ui;margin:24px}} h1{{color:#22d3ee}} .cards{{display:grid;grid-template-columns:repeat(4,minmax(180px,1fr));gap:12px}}.card{{background:#172554;border:1px solid #334155;border-radius:9px;padding:14px}}.card strong{{display:block;font-size:28px;color:#f8fafc}}.card span{{font-size:12px}}.table-wrap{{width:100%;overflow-x:auto;border:1px solid #334155}}table{{border-collapse:collapse;table-layout:fixed;width:max-content;min-width:100%;margin:0}}th{{position:sticky;top:0;background:#172554;z-index:1}}th,td{{box-sizing:border-box;width:300px;min-width:300px;max-width:300px;border:1px solid #334155;padding:10px;vertical-align:top;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.38}}td.pending{{box-shadow:inset 4px 0 #f59e0b}}td.fail{{box-shadow:inset 4px 0 #fb7185}}td.pass{{box-shadow:inset 4px 0 #4ade80}}.col-stage{{background:#1e293b}}.col-identity{{background:#172554}}.col-n2{{background:#3a2b0b}}.col-n4{{background:#2e1b4f}}.col-n1{{background:#0c314c}}.col-fields{{background:#1f3b45}}.col-n1v{{background:#073b4c}}.col-n1n2{{background:#0d3c39}}.col-n3{{background:#123c25}}.col-n3v{{background:#1c4031}}.col-n3n4{{background:#342054}}.col-n3n2{{background:#4a1638}}.col-rag{{background:#3a2d10}}.col-geometry{{background:#233044}}.col-dimension{{background:#3b2c1d}}.col-levels{{background:#1c3b3a}}.col-cuts{{background:#472027}}.col-section{{background:#2a294c}}.col-supports{{background:#263b1a}}.col-context{{background:#3a2637}}.col-svg{{background:#12384a}}a{{color:#67e8f9}}small{{color:#94a3b8}}@media(max-width:1000px){{.cards{{grid-template-columns:repeat(2,1fr)}}body{{margin:12px}}}}</style>
<h1>QUADRO-LAJ-PAVIMENTO — read-only</h1><p>Escopo: <b>{html.escape(summary['obra'])}/{html.escape(summary['pavimento'])}/LAJ</b> · project_id <code>{html.escape(summary['project_id'])}</code></p>
{_cards('Todos os tempos', summary['all_time_levels'])}{_cards('Pavimento atual', summary['levels'], summary['g2_lote'])}
<p><b>Contrato:</b> N2/N4 apenas comparam; contorno isolado antecede relações; apoio requer identidade e contato/interseção. G2/G2-V permanecem dentro de N4.</p>
<p><a href='{md.name}'>Markdown</a> · <a href='{csv_path.name}'>CSV</a> · <a href='{json_path.name}'>JSON</a></p><div class='table-wrap'><table><thead><tr>{table_head}</tr></thead><tbody>{''.join(table_rows)}</tbody></table></div>
<h2>Limites</h2><ul>{''.join('<li>'+html.escape(value)+'</li>' for value in summary['limits'])}</ul></html>"""
    html_path.write_text(document, encoding="utf-8")
    return html_path, json_path, csv_path, md


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True); parser.add_argument("--obra", required=True); parser.add_argument("--pav", required=True)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB); parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary, rows = build_report(args.project_id, args.obra, args.pav, args.db, args.repo_root, args.output_dir)
    reports = write_report(summary, rows, args.output_dir)
    # Arquivo de integridade da geração: prova os outputs, sem registrar nada no DB.
    manifest = args.output_dir / "MANIFEST-READ-ONLY.json"
    manifest_payload = {"mode": "read_only", "source_db_sha256": summary["source_db_sha256"], "reports": {path.name: _sha(path) for path in reports}, "svg_count": len(rows)}
    manifest.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Este é log do relatório, não log de decisão: nenhum selo ou campo é escrito.
    registry = args.output_dir.parent / "REGISTRO-REGENERACOES.jsonl"
    with registry.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"generated_at": summary["generated_at"], "mode": "read_only", "project_id": args.project_id, "obra": args.obra, "pavimento": args.pav, "db_sha256": summary["source_db_sha256"], "output_dir": str(args.output_dir), "manifest": str(manifest)}, ensure_ascii=False) + "\n")
    print(json.dumps({"summary": summary, "reports": [str(path) for path in reports], "manifest": str(manifest)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
