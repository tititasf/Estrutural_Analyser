"""Optional Jev sidecars for a canonical N1 QA review.

The canonical decisions and scorecards are immutable. This module only joins a
prepared source-evidence question to the review snapshot and records advice.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.arete.jev_sa_second_read import run, validate_request, verify_source_dxf


def validate_packets(request_paths: list[Path], source_dxf: Path, manifest: dict,
                     decisions: list) -> list[tuple[Path, dict]]:
    if source_dxf.suffix.lower() != ".dxf" or not source_dxf.is_file():
        raise ValueError("--jev-source-dxf must identify the original N1 source DXF")
    if any(token in str(source_dxf).replace("\\", "/").lower()
           for token in ("fase-2", "recortes_reversos", "reverse_eng")):
        raise ValueError("N2/reverse-engineering DXF cannot be Jev N1 source")
    available = {(row.classe, row.item, row.field_id) for row in decisions}
    snapshots = manifest["snapshots"]
    prepared = []
    seen = set()
    for path in request_paths:
        request = json.loads(path.read_text(encoding="utf-8-sig"))
        validate_request(request)
        if request.get("use_context") not in {"QA_B1", "QA_B2", "QA_B3"}:
            raise ValueError(f"Jev request {path.name} requires a valid use_context")
        ident = request["identity"]
        key = (ident["classe"], ident["item"], ident["campo"])
        if ident["project_id"] != manifest["project_id"] or key not in available:
            raise ValueError(f"Jev request {path.name} is outside this QA project/item/field")
        snapshot = manifest.get("snapshots_by_class", {}).get(
            f"{ident['classe']}:{ident['item']}")
        if snapshot is None:
            snapshot = snapshots.get(ident["item"])
            if snapshot and snapshot.get("classe") != ident["classe"]:
                snapshot = None
        if not snapshot:
            raise ValueError(f"Jev request {path.name} has no matching N1 snapshot")
        if request.get("qa_snapshot_sha256") != snapshot["hash"]:
            raise ValueError(f"Jev request {path.name} has a stale/missing qa_snapshot_sha256")
        verify_source_dxf(source_dxf, ident["source_dxf_sha256"])
        if key in seen:
            raise ValueError(f"duplicate Jev question for {key}")
        seen.add(key)
        prepared.append((path, request))
    return prepared


def summarize_result(request: dict, result: dict) -> dict:
    full = next(x for x in result["results"] if x["variant"] == "full")
    controls = [x for x in result["results"] if x["variant"] != "full"]
    presence_id = request.get("presence_question_id")
    presence_yes = None
    if presence_id:
        presence_yes = full["companion_answers"][presence_id]["noul"]
    if any(x["control_matches_expectation"] is False for x in controls):
        status = "CONTROL_FAILED"
    elif presence_yes is not None and (
            (full["choice"] != "INSUFFICIENT" and presence_yes < 0.5) or
            (full["choice"] == "INSUFFICIENT" and presence_yes > 0.5)):
        status = "CONTRADICTORY_SIGNALS"
    elif full["choice"] == "INSUFFICIENT":
        status = "INSUFFICIENT"
    else:
        status = "SECOND_READING"
    return {"status": status, "choice": full["choice"],
            "presence_yes_probability": presence_yes,
            "control_statuses": [x["control_matches_expectation"] for x in controls]}


def write_advice(out_dir: Path, prepared: list[tuple[Path, dict]], *, execute: bool) -> list[dict]:
    """Persist one advisory record per question; API failure never changes QA decisions."""
    rows = []
    for index, (path, request) in enumerate(prepared, 1):
        identity = request["identity"]
        row = {
            "schema": "jev_qa_advice/1", "identity": identity,
            "qa_snapshot_sha256": request["qa_snapshot_sha256"],
            "request_path": str(path.resolve()),
            "mode": "executed" if execute else "validated_only",
            "status": "VALIDATED_ONLY", "changes_qa_score": False,
        }
        if execute:
            try:
                result = run(request)
                row.update(summarize_result(request, result),
                           result_file=f"jev_{index:02d}_result.json")
                (out_dir / row["result_file"]).write_text(
                    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as exc:
                row.update(status="TECHNICAL_ERROR", error_type=type(exc).__name__)
        rows.append(row)
    (out_dir / "jev_consultas.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (out_dir / "jev_resumo.md").write_text(
        "# Segunda leitura Jev — consultiva\n\n"
        "O score QA canônico e as decisões N1 não são alterados por este sidecar. "
        "Confira controles, DXF fonte e PNG antes do veredito.\n\n"
        + "\n".join(f"- {r['identity']['classe']}:{r['identity']['item']} "
                    f"{r['identity']['campo']}: {r['status']}"
                    + (f" ({r['choice']})" if r.get('choice') else "") for r in rows) + "\n",
        encoding="utf-8",
    )
    return rows
