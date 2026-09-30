"""Contexto SA opcional, fixado por projeto, torre e revisão antes do processo.

Traduz a legenda e entrega níveis coletados no mesmo DXF. Contexto rejeitado
é consultivo; a recepção da entrada não comprova seu consumo pelo motor.
"""
from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path

from .freshness import changed_sources
from .runner import RunnerError, _revision, _write_atomic
from .service import digest, read_floor, read_tower
from .sa_levels import item_level_input


def convention_input(package):
    """Não escolhe primeiro candidato, nem trata texto solto como símbolo vazio."""
    conventions = package.get("pillar_conventions", {})
    if len(conventions) != 1 or package.get("status") not in {"complete", "partial"}:
        return {}, "missing_or_ambiguous_convention"
    source_id, extracted = next(iter(conventions.items()))
    if extracted.get("conflicts"):
        return {}, "conflicting_convention"
    entries = extracted.get("entries", [])
    result = {}
    signatures = set()
    for entry in entries:
        signature = entry.get("signature")
        label = str(entry.get("label") or "").strip()
        # No SA atual NASCE também muda ignore_in_beams e a topologia de FV.
        # A/B real do 14_PAV mostrou alterações não limitadas à classificação;
        # até a certificação N3/N5, manter a evidência no pacote e não aplicar.
        if label.upper() == 'NASCE':
            continue
        # EMPTY exige evidência de símbolo, e não apenas ausência de linhas.
        if not label or not entry.get("label_handle") or not entry.get("line_handles"):
            continue
        if signature == "EMPTY" and entry.get("line_count", 0) < 4:
            continue
        if signature in signatures or label.upper() in result:
            return {}, "ambiguous_signature_or_term"
        signatures.add(signature)
        result[label.upper()] = {"label": label, "sig": signature,
                                 "label_pos": entry["label_position"],
                                 "line_count": entry["line_count"],
                                 "source_id": source_id,
                                 "source_entity_handles": [entry["label_handle"], *entry["line_handles"]]}
    return result, "accepted" if result else "no_supported_evidence"


def level_reference_input(package):
    """Aceita somente a altura direta, local e coerente do pavimento fixado."""
    reference = (package.get("level_inventory") or {}).get("reference") or {}
    if reference.get("status") != "direct_local_reference" or reference.get("unit") != "m":
        return None
    source_id = reference.get("source_id")
    if not source_id or source_id not in {source.get("source_id") for source in package.get("sources", [])}:
        return None
    if reference.get("datum_id") != f"source-local:{source_id}":
        return None
    try:
        base, top, height = (float(reference[key]) for key in ("base", "top", "height"))
    except (ValueError, TypeError, KeyError):
        return None
    if not (0 < top - base <= 6 and abs(top - base - height) < 1e-3):
        return None
    return {"base": base, "top": top, "height": height, "unit": "m",
            "source_id": source_id, "evidence_handles": list(reference.get("evidence_handles") or [])}


def pin_context(*, obra_dir, obra_id, pavimento, project_id, dxf_path):
    """Retorna manifesto fixo ou motivo de não consumo; nunca procura por P1."""
    obra_dir = Path(obra_dir).resolve()
    floor = read_floor(obra_dir, pavimento)
    if not floor or floor["obra_id"] != obra_id:
        return None, "context_absent"
    matching = [s for s in floor["sources"] if s["kind"] == "tower" and
                (obra_dir / s["relative_path"]).resolve() == Path(dxf_path).resolve()]
    if len(matching) != 1:
        return None, "source_not_exactly_bound"
    package = read_tower(obra_dir, floor, matching[0]["source_id"])
    if changed_sources(obra_dir, package["sources"]):
        return None, "stale_context"
    convention, reason = convention_input(package)
    if not convention and not item_level_input(package):
        return None, reason
    reason = 'accepted' if convention else 'accepted_item_levels'
    payload = {"schema": "cad.sa.context/v1", "context_run_id": floor["run_id"],
               "scope": package["scope"], "project_id": project_id,
               "obra_dir": str(obra_dir), "source_dxf": str(Path(dxf_path).resolve()),
               "package_hash": digest(package), "package": package,
               "convention": convention, "reason": reason}
    payload["context_hash"] = digest(payload)
    path = obra_dir / "preprocessamento/v1/sa_inputs" / f"{uuid.uuid4().hex}.json"
    _write_atomic(path, payload)
    return path, reason


def load_context(path, *, expected_hash, obra_dir, pavimento, project_id, dxf_path):
    """Verifica novamente no filho; ausência/erro mantém caminho anterior."""
    rejected = {"status": "not_consumed", "reason": "context_absent"}
    if path is None:
        return {}, rejected
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        supplied_hash = payload.pop("context_hash")
        if not expected_hash or supplied_hash != expected_hash or digest(payload) != expected_hash:
            raise RunnerError("context_hash_mismatch")
        if payload["schema"] != "cad.sa.context/v1":
            raise RunnerError("context_schema_mismatch")
        scope = payload["scope"]
        if (Path(payload["obra_dir"]).resolve() != Path(obra_dir).resolve()
                or scope["pavimento_id"] != pavimento or payload["project_id"] != project_id
                or Path(payload["source_dxf"]).resolve() != Path(dxf_path).resolve()):
            raise RunnerError("context_scope_mismatch")
        package = payload["package"]
        if package["scope"] != scope or digest(package) != payload["package_hash"]:
            raise RunnerError("context_package_mismatch")
        if package["run_id"] != payload["context_run_id"]:
            raise RunnerError("context_run_mismatch")
        if _revision(Path(dxf_path)) != scope["source_revision"] or changed_sources(Path(obra_dir), package["sources"]):
            raise RunnerError("stale_context")
        convention, reason = convention_input(package)
        if (not convention and not item_level_input(package)) or convention != payload["convention"]:
            raise RunnerError(reason if not convention else "context_translation_mismatch")
        return copy.deepcopy(convention), {
            "status": "accepted", "context_run_id": payload["context_run_id"],
            "context_hash": expected_hash, "package_hash": payload["package_hash"],
            "scope": scope, "sources": package["sources"], "convention": convention,
            "level_reference": level_reference_input(package),
            "item_levels": item_level_input(package),
            "cache": "disabled", "reason": "validated_source_signature_to_raw_term",
        }
    except (OSError, ValueError, KeyError, TypeError, RunnerError) as exc:
        rejected["reason"] = str(exc)
        return {}, rejected


def consumption_evidence(runner, receipt):
    """Relata campo produzido pelo consumidor real; não confunde entrada com uso."""
    result = copy.deepcopy(receipt)
    if result.get("status") != "accepted":
        return result
    calls = [call for call in getattr(runner, '_sa_context_calls', [])
             if call.get('used_external_convention')]
    result['consumer_calls'] = calls
    result['level_consumer_calls'] = copy.deepcopy(getattr(runner, '_sa_level_consumer_calls', []))
    evidence = []
    for key, item in (getattr(runner, "pavimento_pillar_report", {}) or {}).items():
        points = item.get("points") or []
        signature = runner._pillar_geom_sig(points) if points else None
        matches = [v for v in result["convention"].values() if v["sig"] == signature]
        if len(matches) == 1 and any(call['signature'] == signature and
                                     call['result'] == matches[0]['label'] for call in calls):
            actual = item.get("classification")
            evidence.append({"report_key": key, "item_name": item.get("name", key),
                             "field": "classification", "value": actual,
                             "expected_raw_term": matches[0]["label"],
                             "matches": actual == matches[0]["label"],
                             "source_id": matches[0]["source_id"],
                             "source_entity_handles": matches[0]["source_entity_handles"]})
    result["items"] = evidence
    result["status"] = "consumed" if any(e["matches"] for e in evidence) or result['level_consumer_calls'] else "accepted_no_item_effect"
    return result
