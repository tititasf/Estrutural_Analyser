#!/usr/bin/env python3
"""Cobertura estrutural do adaptador QA de pilares.

Este módulo não valida o pilar e não grava o banco. Ele verifica se o grafo
necessário para o looping PIL está materializado e coerente o bastante para o
próximo microciclo: identidade/geometria, faces, contratos PARA/PASSA,
montagem e proveniência. A autoridade continua ``diagnostic_only`` até QG7.
"""

from __future__ import annotations

import argparse
import hashlib
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

from scripts.arete.qa_content_cache import ContentAddressedCache
from scripts.arete.qa_n1_field_probe import DEFAULT_CACHE, DEFAULT_DB
from scripts.arete.qa_profile_probe import load_profile, run_profile_probe


SCHEMA = "arete.qa_pil_coverage/v1"
DEFAULT_REPORTS = Path(__file__).resolve().parent / "relatorios" / "qa_pil_coverage"
FACES = ("A", "B", "C", "D")
BEAM_SLOTS = ("passa_esq", "passa_dir", "ch1", "ch2", "ch3")
PASS_SLOTS = ("passa_esq", "passa_dir")
ARRIVAL_SLOTS = ("ch1", "ch2", "ch3")
DIMENSION_RE = re.compile(r"^\s*\d+(?:[.,]\d+)?\s*[/xX]\s*\d+(?:[.,]\d+)?\s*$")
BEAM_RE = re.compile(r"^V[A-Z]*\d+[A-Z0-9._-]*$", re.IGNORECASE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(raw: Any, default: Any) -> Any:
    if raw in (None, ""):
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _label_text(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    labels = value.get("label") or []
    if not labels or not isinstance(labels[0], dict):
        return None
    text = str(labels[0].get("text") or "").strip()
    return text or None


def _explicit_null(value: Any) -> bool:
    text = (_label_text(value) or "").upper()
    return text in {"SEM LAJE", "NULO", "VAZIO (X)"} or "VAZIO" in text


def _row(con: sqlite3.Connection, project_id: str, item: str) -> dict[str, Any]:
    con.row_factory = sqlite3.Row
    row = con.execute(
        """
        SELECT id, project_id, name, links_json, points_json, sides_data_json,
               extra_data_json, conf_map_json
          FROM pillars WHERE project_id=? AND name=?
        """,
        (project_id, item),
    ).fetchone()
    if row is None:
        raise ValueError(f"pilar ausente: project_id={project_id!r} item={item!r}")
    return dict(row)


def _finding(code: str, family: str, message: str, **evidence: Any) -> dict[str, Any]:
    return {"code": code, "family": family, "message": message, "evidence": evidence}


def _analyze_identity(name: str, links: dict, points: list, extra: dict) -> tuple[dict, list[dict]]:
    findings: list[dict] = []
    label = _label_text(links.get("name"))
    dimension = str(((extra.get("fields") or {}).get("Dimensão (b x h)") or "")).strip()
    segments = ((links.get("pilar_segs") or {}).get("segments") or [])
    if not label or label.upper() != name.upper():
        findings.append(_finding("identity_label", "identity_geometry", "rótulo do pilar ausente ou divergente", expected=name, observed=label))
    if not DIMENSION_RE.match(dimension):
        findings.append(_finding("pillar_dimension", "identity_geometry", "dimensão b/h ausente ou inválida", observed=dimension))
    if len(points) < 4 and not segments:
        findings.append(_finding("pillar_geometry", "identity_geometry", "geometria do pilar ausente", point_count=len(points)))
    return {
        "name": name,
        "label": label,
        "dimension": dimension or None,
        "point_count": len(points),
        "segment_count": len(segments),
        "status": "COMPLETE" if not findings else "CONFLICT",
    }, findings


def _analyze_faces(links: dict) -> tuple[dict[str, Any], list[dict], list[dict]]:
    faces: dict[str, Any] = {}
    findings: list[dict] = []
    probe_targets: list[dict] = []
    for face in FACES:
        laje_value = links.get(f"p_s{face}_l1_n")
        laje = _label_text(laje_value)
        face_findings: list[dict] = []
        if laje is None:
            face_findings.append(_finding("face_laje_state", "faces", f"face {face} sem estado explícito de laje", face=face))
        beams: list[dict] = []
        for slot in BEAM_SLOTS:
            name_link = links.get(f"p_s{face}_v_{slot}_n")
            dim_link = links.get(f"p_s{face}_v_{slot}_d")
            beam_name = _label_text(name_link)
            beam_dim = _label_text(dim_link)
            if beam_name is None and beam_dim is None:
                continue
            row = {
                "slot": slot,
                "kind": "passa" if slot in PASS_SLOTS else "chega",
                "name": beam_name,
                "dimension": beam_dim,
            }
            beams.append(row)
            if beam_name is None or not BEAM_RE.match(beam_name):
                face_findings.append(_finding(
                    "beam_identity", "faces", f"face {face}/{slot} sem identidade de viga válida",
                    face=face, slot=slot, observed=beam_name,
                ))
            if beam_dim is None or not DIMENSION_RE.match(beam_dim):
                face_findings.append(_finding(
                    "beam_dimension", "faces", f"face {face}/{slot} sem dimensão largura/profundidade válida",
                    face=face, slot=slot, beam=beam_name, observed=beam_dim,
                ))
            if beam_name and BEAM_RE.match(beam_name) and beam_dim and DIMENSION_RE.match(beam_dim):
                probe_targets.append({"face": face, "slot": slot, "beam": beam_name, "dimension": beam_dim})
        faces[face] = {
            "laje": None if _explicit_null(laje_value) else laje,
            "laje_state": "explicit_null" if _explicit_null(laje_value) else "linked" if laje else "missing",
            "beams": beams,
            "status": "COMPLETE" if not face_findings else "CONFLICT",
        }
        findings.extend(face_findings)
    return faces, findings, probe_targets


def _analyze_mode_contract(mode: str, variant: Any) -> tuple[dict[str, Any], list[dict]]:
    family = mode.lower()
    findings: list[dict] = []
    if not isinstance(variant, dict):
        return {"status": "MISSING", "mode": mode}, [
            _finding("mode_contract", family, f"contrato {mode} ausente")
        ]
    contract = variant.get("contract") or variant.get("payload", {}).get("_sa_mode_contract")
    payload = variant.get("payload") or {}
    if not isinstance(contract, dict):
        return {"status": "MISSING", "mode": mode}, [
            _finding("mode_contract", family, f"contrato semântico {mode} ausente")
        ]
    if str(contract.get("modo_semantico") or "").upper() != mode:
        findings.append(_finding("mode_identity", family, f"modo do contrato diverge de {mode}", observed=contract.get("modo_semantico")))
    height = contract.get("altura_pilar") or {}
    for key in ("nivel_saida", "nivel_chegada", "altura"):
        if not isinstance(height.get(key), (int, float)):
            findings.append(_finding("pillar_height", family, f"{mode} sem {key} numérico", field=key, observed=height.get(key)))
    faces = contract.get("faces") or {}
    face_rows: dict[str, Any] = {}
    for face in FACES:
        data = faces.get(face)
        if not isinstance(data, dict):
            findings.append(_finding("contract_face", family, f"{mode} sem contrato da face {face}", face=face))
            continue
        required = {
            "vazio_topo", "viga_passante_referencia", "aberturas_vigas_que_param",
            "aberturas_vigas_que_passam", "aberturas_vigas_que_chegam", "fontes_n1",
        }
        missing = sorted(required - set(data))
        if missing:
            findings.append(_finding("contract_face_fields", family, f"{mode}/{face} incompleto", face=face, missing=missing))
        void = data.get("vazio_topo") or {}
        if not isinstance(void.get("valor_cm"), (int, float)) or not void.get("fonte"):
            findings.append(_finding("top_void", family, f"{mode}/{face} sem vazio de topo rastreável", face=face, observed=void))
        sources = data.get("fontes_n1") or {}
        missing_sources = sorted({"lajes", "passa", "chega", "interior"} - set(sources))
        if missing_sources:
            findings.append(_finding("n1_sources", family, f"{mode}/{face} sem famílias N1", face=face, missing=missing_sources))
        face_rows[face] = {
            "vazio_topo": void,
            "passante": data.get("viga_passante_referencia"),
            "param": len(data.get("aberturas_vigas_que_param") or []),
            "passam": len(data.get("aberturas_vigas_que_passam") or []),
            "chegam": len(data.get("aberturas_vigas_que_chegam") or []),
            "fontes_n1": sources,
        }
    required_payload = {"nome", "comprimento", "largura", "altura", "nivel_saida", "nivel_chegada", "_sa_meta", "_sa_mode_contract", "_sa_mode_variant"}
    missing_payload = sorted(required_payload - set(payload))
    if missing_payload:
        findings.append(_finding("n3_payload", family, f"payload {mode} incompleto", missing=missing_payload))
    artifacts = variant.get("artifacts") or {}
    artifact_rows = {}
    for key in ("json", "abcd", "grades"):
        raw_path = artifacts.get(key)
        exists = bool(raw_path and Path(raw_path).is_file())
        artifact_rows[key] = {"path": raw_path, "exists": exists}
        if not exists:
            findings.append(_finding("artifact", family, f"artefato {mode}/{key} ausente", artifact=key, path=raw_path))
    return {
        "mode": mode,
        "status": "COMPLETE" if not findings else "CONFLICT",
        "height": height,
        "faces": face_rows,
        "payload_keys": sorted(payload),
        "artifacts": artifact_rows,
    }, findings


def _analyze_assembly(variants: dict) -> tuple[dict[str, Any], list[dict]]:
    findings: list[dict] = []
    payload = {}
    for mode in ("para", "passa"):
        candidate = (variants.get(mode) or {}).get("payload") or {}
        if candidate:
            payload = candidate
            break
    grade_keys = [f"grade_{index}" for index in range(1, 4)]
    distance_keys = ["distancia_1", "distancia_2"]
    screw_keys = [f"par_{index}_{index + 1}" for index in range(1, 9)]
    missing = [key for key in (*grade_keys, *distance_keys, *screw_keys) if key not in payload]
    if missing:
        findings.append(_finding("assembly_payload", "assembly", "campos de montagem/grades incompletos", missing=missing))
    return {
        "status": "COMPLETE" if not findings else "CONFLICT",
        "grades": {key: payload.get(key) for key in grade_keys},
        "distances": {key: payload.get(key) for key in distance_keys},
        "screws": {key: payload.get(key) for key in screw_keys},
    }, findings


def _run_probes(
    con: sqlite3.Connection,
    *,
    project_id: str,
    item: str,
    targets: list[dict],
    cache: ContentAddressedCache,
) -> list[dict[str, Any]]:
    profile = load_profile("PIL")
    probe_id = "face_slot_identity_dimension_contact"
    if probe_id not in ((profile.get("n1") or {}).get("probes") or {}):
        probe_id = "face_pass_slot_identity_dimension_contact"
    rows = []
    for target in targets:
        try:
            result = run_profile_probe(
                con,
                profile,
                probe_id=probe_id,
                item=item,
                variables={"face": target["face"], "slot": target["slot"]},
                project_id=project_id,
                cache=cache,
            )
            rows.append({"target": target, "overall": result.get("overall"), "result": result})
        except Exception as exc:  # probe é evidência auxiliar; erro fica explícito
            rows.append({"target": target, "overall": "PENDENTE", "error": f"{type(exc).__name__}: {exc}"})
    return rows


def build_pil_coverage(
    con: sqlite3.Connection,
    *,
    project_id: str,
    item: str,
    run_probes: bool = False,
    cache: ContentAddressedCache | None = None,
) -> dict[str, Any]:
    row = _row(con, project_id, item)
    links = _load_json(row.get("links_json"), {})
    points = _load_json(row.get("points_json"), [])
    sides = _load_json(row.get("sides_data_json"), {})
    extra = _load_json(row.get("extra_data_json"), {})
    variants = extra.get("pl_n3_variants") or {}

    identity, f_identity = _analyze_identity(item, links, points, extra)
    faces, f_faces, targets = _analyze_faces(links)
    para, f_para = _analyze_mode_contract("PARA", variants.get("para"))
    passa, f_passa = _analyze_mode_contract("PASSA", variants.get("passa"))
    assembly, f_assembly = _analyze_assembly(variants)
    findings = [*f_identity, *f_faces, *f_para, *f_passa, *f_assembly]
    probes = _run_probes(
        con,
        project_id=project_id,
        item=item,
        targets=targets,
        cache=cache or ContentAddressedCache(DEFAULT_CACHE),
    ) if run_probes else []
    probe_summary = {
        status: sum(1 for row in probes if row.get("overall") == status)
        for status in ("PASS", "FAIL", "PENDENTE")
    }
    structural_complete = not findings
    probes_complete = bool(probes) and all(row.get("overall") == "PASS" for row in probes)
    next_actions = []
    if findings:
        next_actions.append("corrigir a primeira causa geral listada em findings e regenerar somente o escopo afetado")
    if run_probes and not probes_complete:
        next_actions.append("resolver FAIL/PENDENTE das probes cross-classe antes de confiar em nome, dimensão ou contato")
    if structural_complete and (not run_probes or probes_complete):
        next_actions.append("executar leitura visual N1/N3 e registrar veredito; cobertura estrutural não substitui visão")
    result = {
        "schema": SCHEMA,
        "generated_at": _now(),
        "authority": "diagnostic_only; QG7 and human visual ground truth are required before validation_ready/apply",
        "scope": {"project_id": project_id, "class": "PIL", "item": item},
        "source": {
            "table": "pillars",
            "row_id": row["id"],
            "snapshot_hash": _canonical_hash({key: row.get(key) for key in sorted(row)}),
            "sides_hash": _canonical_hash(sides),
        },
        "families": {
            "identity_geometry": identity,
            "faces": {"status": "COMPLETE" if not f_faces else "CONFLICT", "items": faces},
            "para": para,
            "passa": passa,
            "assembly": assembly,
        },
        "probe_targets": targets,
        "profile_probes": probes,
        "profile_probe_summary": probe_summary,
        "findings": findings,
        "structural_complete": structural_complete,
        "probes_complete": probes_complete if run_probes else None,
        "ready_for_visual": structural_complete and (not run_probes or probes_complete),
        "human_checkpoints": [
            "regra estrutural ambígua ou lacuna do manual",
            "veredito visual do N1 próximo/distante e dos desenhos N3",
            "promoção QG7 do adaptador PIL para validation_ready",
            "promoção de candidato RAG T1/T2",
        ],
        "next_actions": next_actions,
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mede cobertura do adaptador PIL sem validar/gravar N1.")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--item", required=True)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--run-probes", action="store_true")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    with sqlite3.connect(args.db) as con:
        result = build_pil_coverage(
            con,
            project_id=args.project_id,
            item=args.item,
            run_probes=args.run_probes,
            cache=ContentAddressedCache(args.cache_dir),
        )
    out = args.out or DEFAULT_REPORTS / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_PIL_{args.item}.json"
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "item": args.item,
        "structural_complete": result["structural_complete"],
        "ready_for_visual": result["ready_for_visual"],
        "findings": len(result["findings"]),
        "out": str(out),
    }, ensure_ascii=False))
    return 0 if result["ready_for_visual"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
