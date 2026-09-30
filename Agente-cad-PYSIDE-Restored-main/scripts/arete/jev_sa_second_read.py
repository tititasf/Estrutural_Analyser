"""Optional, read-only Jev second reading of a prepared SA/N1 evidence packet.

This helper is not a QA gate or an N1 writer. It accepts compact source evidence,
keeps the SA baseline outside Jev's state, and records an evidence-removal control.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


MODEL = "jev-1.13.0"
MAX_STATE_BYTES = 16000
MAX_QUESTION_BYTES = 4000
MAX_CONTROLS = 4
MAX_COMPANIONS = 3


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def verify_source_dxf(path: Path, expected_sha256: str) -> None:
    if path.suffix.lower() != ".dxf" or not path.is_file():
        raise ValueError("source must be an existing N1 DXF")
    if any(token in str(path).replace("\\", "/").lower()
           for token in ("fase-2", "recortes_reversos", "reverse_eng")):
        raise ValueError("N2/reverse-engineering DXF cannot be N1 evidence")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected_sha256.lower():
        raise ValueError("source DXF hash does not match request identity")


def validate_request(request: dict) -> dict:
    if request.get("schema") != "jev_sa_second_read_request/1":
        raise ValueError("schema must be jev_sa_second_read_request/1")
    identity = request.get("identity")
    if not isinstance(identity, dict) or not all(identity.get(k) for k in
            ("project_id", "pavimento", "classe", "item", "campo", "source_dxf_sha256")):
        raise ValueError("identity requires project_id, pavimento, classe, item, campo, source_dxf_sha256")
    if identity["classe"] not in {"PIL", "FV", "LV", "LAJ"}:
        raise ValueError("classe must be PIL, FV, LV or LAJ")
    if request.get("use_context") is not None and request["use_context"] not in {
            "SA_POST_EXTRACT", "QA_B1", "QA_B2", "QA_B3"}:
        raise ValueError("use_context must be SA_POST_EXTRACT or QA_B1/B2/B3")
    sha = str(identity["source_dxf_sha256"])
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha.lower()):
        raise ValueError("source_dxf_sha256 must be a 64-digit SHA-256 hex digest")
    if "baseline_sa" not in request:
        raise ValueError("baseline_sa is required for comparison and stays outside Jev state")
    question = request.get("question")
    if not isinstance(question, dict) or not isinstance(question.get("instructions"), str):
        raise ValueError("question.instructions is required")
    criteria = question.get("criteria")
    if not isinstance(criteria, dict) or not 2 <= len(criteria) <= 8:
        raise ValueError("question.criteria must contain 2 to 8 choices")
    if "INSUFFICIENT" not in criteria or any(not isinstance(v, str) or not v.strip() for v in criteria.values()):
        raise ValueError("criteria require nonempty descriptions and INSUFFICIENT")
    if len(_canonical(question)) > MAX_QUESTION_BYTES:
        raise ValueError("question exceeds 4 KB; ask one focused question")
    companions = request.get("companion_questions", {})
    if not isinstance(companions, dict) or len(companions) > MAX_COMPANIONS:
        raise ValueError("companion_questions must have at most 3 independent questions")
    for name, spec in companions.items():
        if not isinstance(name, str) or not name.isidentifier() or name == "second_read":
            raise ValueError("companion question names must be unique identifiers")
        if not isinstance(spec, dict) or not isinstance(spec.get("instructions"), str) or not spec["instructions"].strip():
            raise ValueError("each companion requires instructions")
        if spec.get("type") == "noul":
            noul_criteria = spec.get("criteria")
            if not isinstance(noul_criteria, dict) or not noul_criteria or \
                    not set(noul_criteria) <= {"true", "false"} or \
                    any(not isinstance(value, (str, dict)) or not value for value in noul_criteria.values()):
                raise ValueError("noul criteria require nonempty true/false descriptions")
        elif spec.get("type") == "score":
            levels = spec.get("criteria")
            if not isinstance(levels, list) or not 2 <= len(levels) <= 5 or any(not isinstance(x, (str, dict)) or not x for x in levels):
                raise ValueError("score requires 2 to 5 ordered, described levels")
        else:
            raise ValueError("companion type must be noul or score")
        if len(_canonical(spec)) > MAX_QUESTION_BYTES:
            raise ValueError("companion question exceeds 4 KB")
    presence_id = request.get("presence_question_id")
    if presence_id is not None and (presence_id not in companions or
                                    companions[presence_id]["type"] != "noul"):
        raise ValueError("presence_question_id must name a companion noul")
    evidence = request.get("evidence")
    if not isinstance(evidence, dict) or not evidence:
        raise ValueError("evidence must be a nonempty JSON object")
    forbidden = {"baseline_sa", "sa_value", "sa_level", "ground_truth", "qa_verdict", "expected_choice"}
    if forbidden.intersection(evidence):
        raise ValueError("keep SA baseline, ground truth and expected answers outside Jev evidence")
    controls = request.get("controls")
    if not isinstance(controls, list) or not 1 <= len(controls) <= MAX_CONTROLS:
        raise ValueError("1 to 4 evidence-removal controls are required")
    seen = set()
    for control in controls:
        if not isinstance(control, dict) or not isinstance(control.get("id"), str) or not control["id"]:
            raise ValueError("each control needs a unique id")
        if control["id"] in seen:
            raise ValueError("control ids must be unique")
        seen.add(control["id"])
        if not isinstance(control.get("evidence"), dict):
            raise ValueError("each control needs its own evidence object")
        if forbidden.intersection(control["evidence"]):
            raise ValueError("keep SA baseline, ground truth and expected answers outside Jev evidence")
        if control["evidence"] == evidence:
            raise ValueError("control evidence must differ from full evidence")
        expected = control.get("expected_choice")
        if expected is not None and expected not in criteria:
            raise ValueError("control expected_choice must name a criterion")
    for state in [evidence, *(c["evidence"] for c in controls)]:
        if len(_canonical(state)) > MAX_STATE_BYTES:
            raise ValueError("one evidence state exceeds 16 KB; split by item/field/segment")
    return {"identity": identity, "choices": list(criteria), "controls": len(controls),
            "max_state_bytes": max(len(_canonical(s)) for s in [evidence, *(c["evidence"] for c in controls)]),
            "request_sha256": _sha(request), "companions": list(companions)}


def run(request: dict) -> dict:
    from dotenv import load_dotenv
    from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if not os.getenv("TYPESAFE_API_KEY"):
        raise RuntimeError("TYPESAFE_API_KEY absent from environment/.env")
    q = Choice(instructions=request["question"]["instructions"],
               criteria=request["question"]["criteria"])
    questions = {"second_read": q}
    for name, spec in request.get("companion_questions", {}).items():
        primitive = Noul if spec["type"] == "noul" else Score
        questions[name] = primitive(instructions=spec["instructions"], criteria=spec["criteria"])
    states = [("full", request["evidence"], None)] + [
        (c["id"], c["evidence"], c.get("expected_choice")) for c in request["controls"]
    ]
    results = []
    with TypeSafeClient(model=MODEL) as client:
        for label, state, expected in states:
            started = time.perf_counter()
            reply = client.system_one(state=state, questions=questions)
            answer = reply.choices["second_read"]
            companion_answers = {}
            for name, spec in request.get("companion_questions", {}).items():
                response = reply.nouls[name] if spec["type"] == "noul" else reply.scores[name]
                companion_answers[name] = response.model_dump(mode="json")
            results.append({"variant": label, "evidence_sha256": _sha(state),
                            "choice": answer.choice, "confidence": answer.confidence,
                            "probabilities": answer.probabilities,
                            "companion_answers": companion_answers,
                            "expected_choice": expected,
                            "control_matches_expectation": answer.choice == expected if expected else None,
                            "input_tokens": reply.usage.input_tokens if reply.usage else None,
                            "latency_s": round(time.perf_counter() - started, 3)})
    return {"schema": "jev_sa_second_read_result/1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "mode": "optional_read_only", "model": MODEL, "identity": request["identity"],
            "baseline_sa": request["baseline_sa"], "request_sha256": _sha(request),
            "results": results, "decision": "QA_REVIEW_ONLY",
            "note": "Jev adds a second reading; it neither approves a field nor writes N1."}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--request", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--source-dxf", type=Path, help="verify original N1 DXF SHA-256 before inference")
    ap.add_argument("--execute", action="store_true", help="call Jev after local validation; default only validates")
    args = ap.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8-sig"))
    summary = validate_request(request)
    if args.source_dxf:
        verify_source_dxf(args.source_dxf, request["identity"]["source_dxf_sha256"])
    if not args.execute:
        print(json.dumps({"status": "VALID", **summary}, ensure_ascii=False))
        return 0
    if not args.output:
        ap.error("--output is required with --execute")
    if args.output.exists():
        ap.error("output already exists; use a new file to preserve the evidence history")
    result = run(request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "RECORDED", "output": str(args.output), "choices":
                      [r["choice"] for r in result["results"]]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
