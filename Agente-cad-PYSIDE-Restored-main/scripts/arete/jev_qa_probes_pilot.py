"""Compare Jev evidence triage with existing field-scoped QA probes for four classes.

No probe verdict, status or reason is sent to Jev. This measures triage, not CAD
interpretation quality or visual approval. Input probes are produced by the
canonical qa_profile_probe.py in read-only mode.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path


def chunks(checks: list[dict], max_chars: int = 5000) -> list[list[dict]]:
    out: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    for check in checks:
        compact = {k: check.get(k) for k in ("id", "op", "left", "right")}
        length = len(json.dumps(compact, ensure_ascii=False))
        if length > max_chars:
            raise ValueError(f"single check exceeds chunk budget: {compact['id']}")
        if current and size + length > max_chars:
            out.append(current)
            current, size = [], 0
        current.append(compact)
        size += length
    if current:
        out.append(current)
    return out


def evaluate(client, probe: dict) -> dict:
    from typesafe_sdk import Choice

    source = probe.get("preflight") or probe
    checks = source.get("checks") or []
    if not checks:
        return {"decision": "hold", "reason": "no_checks_in_probe", "chunks": []}
    all_chunks = chunks(checks)
    answers = []
    for index, part in enumerate(all_chunks, start=1):
        state = {
            "class": probe.get("profile", {}).get("class") or probe.get("scope", {}).get("classe"),
            "question": probe.get("question"),
            "part": index,
            "parts_total": len(all_chunks),
            "checks": part,
        }
        payload_chars = len(json.dumps(state, ensure_ascii=False))
        if payload_chars > 6500:
            raise ValueError("state exceeds local size guard")
        q = Choice(
            instructions=(
                "For this part only, are ALL listed field checks explicitly satisfied by "
                "the supplied values? A null, missing, mismatched, contradictory or "
                "untraceable value makes this part HOLD. Do not infer missing CAD facts. "
                "Return CONFIRM only when every listed check passes its stated operation."
            ),
            criteria={
                "CONFIRM": "Every listed check is explicitly satisfied; no missing evidence.",
                "HOLD": "At least one listed check fails or lacks enough evidence.",
            },
        )
        t0 = time.perf_counter()
        response = client.system_one(state=state, questions={"part_ready": q})
        answer = response.choices["part_ready"]
        answers.append({
            "part": index, "check_count": len(part), "state_chars": payload_chars,
            "choice": answer.choice, "confidence": answer.confidence,
            "probabilities": answer.probabilities,
            "model": response.model, "latency_s": round(time.perf_counter() - t0, 3),
            "input_tokens": response.usage.input_tokens if response.usage else None,
        })
    return {"decision": "confirm" if all(a["choice"] == "CONFIRM" for a in answers) else "hold",
            "chunks": answers}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from dotenv import load_dotenv
    from typesafe_sdk import TypeSafeClient

    repo = Path(__file__).resolve().parents[2]
    load_dotenv(repo / ".env")
    if not os.getenv("TYPESAFE_API_KEY"):
        parser.error("TYPESAFE_API_KEY absent")
    files = sorted(args.probe_dir.glob("probe_*.json"))
    if not files:
        parser.error("no profile probes found")
    rows = []
    with TypeSafeClient(model="jev-1.13.0") as client:
        for path in files:
            probe = json.loads(path.read_text(encoding="utf-8"))
            pieces = path.stem.split("_", 2)
            if len(pieces) != 3:
                continue
            _, cls, item = pieces
            try:
                model = evaluate(client, probe)
            except Exception as exc:
                model = {"decision": "technical_error", "error_type": type(exc).__name__, "error": str(exc)[:160]}
            rows.append({
                "class": cls, "item": item, "qa_probe_status": probe.get("overall"),
                "qa_probe_scope": probe.get("scope_authority"),
                "jev": model,
            })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema": "jev_qa_probe_pilot/1", "results": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"cases": len(rows), "by_class": {c: sum(r["class"] == c for r in rows) for c in ("PIL", "LV", "FV", "LAJ")},
               "qa_pass": sum(r["qa_probe_status"] == "PASS" for r in rows),
               "jev_confirm": sum(r["jev"]["decision"] == "confirm" for r in rows),
               "false_confirm_vs_qa": sum(r["qa_probe_status"] != "PASS" and r["jev"]["decision"] == "confirm" for r in rows),
               "false_hold_vs_qa": sum(r["qa_probe_status"] == "PASS" and r["jev"]["decision"] == "hold" for r in rows),
               "technical_errors": sum(r["jev"]["decision"] == "technical_error" for r in rows)}
    print(json.dumps(summary, ensure_ascii=False))
    print(args.output)
    return 0 if summary["technical_errors"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
