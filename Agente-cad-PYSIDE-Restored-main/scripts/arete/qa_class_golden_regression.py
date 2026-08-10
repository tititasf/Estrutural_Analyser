#!/usr/bin/env python3
"""Golden/regressão N1 multi-item unificado — PIL, LAJ, FV, LV.

Mesmo schema e critérios de regressão para as quatro classes. Roda adaptadores
canônicos em paralelo por classe (conexões SQLite isoladas) para performance.

Exemplos:
  python scripts/arete/qa_class_golden_regression.py --project-id <id> --write-baseline
  python scripts/arete/qa_class_golden_regression.py --project-id <id>
  python scripts/arete/qa_class_golden_regression.py --project-id <id> --classe PIL --classe LAJ
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DEFAULT_DB = Path(r"D:\Agente-cad-PYSIDE\project_data.vision")
DEFAULT_BASELINE = (
    REPO / "scripts" / "arete" / "qa_requests" / "golden" / "classes_13pav_baseline.json"
)
CLASSES = ("PIL", "LAJ", "FV", "LV")
# Itens representativos por classe (amostra de robustez do agente, não campanha).
DEFAULT_ITEMS: dict[str, list[str]] = {
    "PIL": ["P1", "P3", "P11", "P35"],
    "LAJ": ["L301", "L318", "L319", "L320"],
    "FV": ["V301", "V303", "V305", "V306", "V307", "V312", "V327", "V328"],
    "LV": ["V301", "V303", "V305", "V312", "V327"],
}
SCHEMA = "arete.qa_class_golden/v2"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _summarize_decisions(decisions: list[Any], findings: list[Any], classe: str, items: list[str]) -> dict:
    by_item: dict[str, Counter] = {}
    fields_by_item: dict[str, dict[str, str]] = {}
    for decision in decisions:
        item = getattr(decision, "item", None) or decision.get("item")
        field_id = getattr(decision, "field_id", None) or decision.get("field_id")
        dec = getattr(decision, "decision", None) or decision.get("decision")
        by_item.setdefault(item, Counter())[dec] += 1
        fields_by_item.setdefault(item, {})[field_id] = dec
    return {
        "classe": classe,
        "items_requested": items,
        "items_seen": sorted(by_item),
        "decision_totals": dict(Counter(
            (getattr(d, "decision", None) or d.get("decision")) for d in decisions
        )),
        "per_item": {item: dict(counter) for item, counter in sorted(by_item.items())},
        "fields": fields_by_item,
        "n_decisions": len(decisions),
        "n_findings": len(findings),
    }


def run_class(
    *,
    db: Path,
    project_id: str,
    classe: str,
    items: list[str],
    run_id: str,
) -> dict:
    """Executa o adaptador da classe em conexão própria (thread-safe)."""
    t0 = time.perf_counter()
    con = sqlite3.connect(str(db))
    try:
        selected = set(items)
        classe = classe.upper()
        if classe == "LAJ":
            from scripts.arete.qa_evidence_auditor import LajEvidenceAuditor, load_slabs
            slabs = load_slabs(con, project_id)
            auditor = LajEvidenceAuditor(slabs, run_id)
            decisions = auditor.audit(selected=selected, include_sealed=True)
            findings = auditor.findings
        elif classe == "PIL":
            from scripts.arete.qa_evidence_auditor import (
                PilEvidenceAuditor,
                load_beams_for_project,
                load_pillars,
                load_slabs,
            )
            pillars = load_pillars(con, project_id)
            beams = load_beams_for_project(con, project_id)
            slabs = load_slabs(con, project_id)
            auditor = PilEvidenceAuditor(pillars, beams, slabs, run_id)
            decisions = auditor.audit(selected=selected, include_sealed=True)
            findings = auditor.findings
        elif classe in {"FV", "LV"}:
            from scripts.arete.qa_fv_lv_adapters import (
                FvEvidenceAuditor,
                LvEvidenceAuditor,
                load_beam_records,
                load_name_index,
            )
            beams = load_beam_records(con, project_id)
            names = load_name_index(con, project_id)
            auditor = (
                FvEvidenceAuditor(beams, names, run_id)
                if classe == "FV"
                else LvEvidenceAuditor(beams, names, run_id)
            )
            decisions = auditor.audit(selected=selected, include_sealed=True)
            findings = auditor.findings
        else:
            raise ValueError(f"classe desconhecida: {classe}")
        out = _summarize_decisions(decisions, findings, classe, items)
        out["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        out["adapter"] = type(auditor).__name__
        return out
    finally:
        con.close()


def compare(baseline: dict, current: dict, classes: list[str]) -> list[str]:
    """Regressões: queda de CONFIRMAR, PENDENTE demais, item sumindo, demote de campo."""
    issues: list[str] = []
    for classe in classes:
        base = (baseline.get("classes") or {}).get(classe) or {}
        cur = (current.get("classes") or {}).get(classe) or {}
        if not base:
            continue
        base_tot = base.get("decision_totals") or {}
        cur_tot = cur.get("decision_totals") or {}
        base_conf = int(base_tot.get("CONFIRMAR") or 0)
        cur_conf = int(cur_tot.get("CONFIRMAR") or 0)
        if cur_conf < base_conf:
            issues.append(f"{classe}: CONFIRMAR regrediu {base_conf} → {cur_conf}")
        base_pend = int(base_tot.get("PENDENTE") or 0)
        cur_pend = int(cur_tot.get("PENDENTE") or 0)
        if cur_pend > max(base_pend + 3, int(base_pend * 1.15) + 1):
            issues.append(f"{classe}: PENDENTE aumentou demais {base_pend} → {cur_pend}")
        base_items = set(base.get("items_seen") or [])
        cur_items = set(cur.get("items_seen") or [])
        missing = sorted(base_items - cur_items)
        if missing:
            issues.append(f"{classe}: itens sumiram da auditoria: {missing}")
        base_fields = base.get("fields") or {}
        cur_fields = cur.get("fields") or {}
        demoted = []
        for item, fmap in base_fields.items():
            for field_id, decision in (fmap or {}).items():
                if decision != "CONFIRMAR":
                    continue
                now = (cur_fields.get(item) or {}).get(field_id)
                if now and now not in {"CONFIRMAR", "N/A_CONFIRMADO"}:
                    demoted.append(f"{item}.{field_id}:{decision}→{now}")
        if demoted:
            issues.append(f"{classe}: campos despromovidos ({len(demoted)}): {demoted[:12]}")
    return issues


def run_report(
    *,
    db: Path,
    project_id: str,
    classes: list[str],
    items_by_class: dict[str, list[str]],
    workers: int = 4,
) -> dict:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_class_golden"
    t0 = time.perf_counter()
    results: dict[str, dict] = {}
    workers = max(1, min(workers, len(classes)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(
                run_class,
                db=db,
                project_id=project_id,
                classe=classe,
                items=items_by_class.get(classe) or DEFAULT_ITEMS[classe],
                run_id=f"{run_id}_{classe}",
            ): classe
            for classe in classes
        }
        for fut in as_completed(futs):
            classe = futs[fut]
            results[classe] = fut.result()
    return {
        "schema": SCHEMA,
        "run_id": run_id,
        "created_at": utc_now(),
        "project_id": project_id,
        "db": str(db.resolve()),
        "classes": {c: results[c] for c in classes},
        "elapsed_ms_total": int((time.perf_counter() - t0) * 1000),
        "workers": workers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--classe", action="append", choices=CLASSES, dest="classes")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--pil-item", action="append", dest="pil_items")
    parser.add_argument("--laj-item", action="append", dest="laj_items")
    parser.add_argument("--fv-item", action="append", dest="fv_items")
    parser.add_argument("--lv-item", action="append", dest="lv_items")
    args = parser.parse_args(argv)

    classes = list(args.classes) if args.classes else list(CLASSES)
    items_by_class = {
        "PIL": args.pil_items or DEFAULT_ITEMS["PIL"],
        "LAJ": args.laj_items or DEFAULT_ITEMS["LAJ"],
        "FV": args.fv_items or DEFAULT_ITEMS["FV"],
        "LV": args.lv_items or DEFAULT_ITEMS["LV"],
    }
    report = run_report(
        db=args.db,
        project_id=args.project_id,
        classes=classes,
        items_by_class=items_by_class,
        workers=args.workers,
    )
    out = args.out or (
        REPO / "scripts" / "arete" / "relatorios" / "qa_golden" / f"{report['run_id']}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.write_baseline:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        # merge with existing baseline classes not re-run
        if args.baseline.is_file() and args.classes:
            prev = json.loads(args.baseline.read_text(encoding="utf-8"))
            merged = dict(prev)
            merged_classes = dict(prev.get("classes") or {})
            merged_classes.update(report["classes"])
            merged["classes"] = merged_classes
            merged["run_id"] = report["run_id"]
            merged["created_at"] = report["created_at"]
            merged["schema"] = SCHEMA
            args.baseline.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            args.baseline.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({
            "baseline_written": str(args.baseline),
            "report": str(out),
            "elapsed_ms_total": report["elapsed_ms_total"],
            "totals": {c: report["classes"][c]["decision_totals"] for c in classes},
        }, ensure_ascii=False, indent=2))
        return 0

    if not args.baseline.is_file():
        print(json.dumps({
            "error": "baseline ausente; rode com --write-baseline",
            "report": str(out),
            "hint": f"python scripts/arete/qa_class_golden_regression.py --project-id {args.project_id} --write-baseline",
        }, ensure_ascii=False, indent=2))
        return 2

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    issues = compare(baseline, report, classes)
    payload = {
        "report": str(out),
        "baseline": str(args.baseline),
        "ok": not issues,
        "issues": issues,
        "elapsed_ms_total": report["elapsed_ms_total"],
        "totals": {c: report["classes"][c]["decision_totals"] for c in classes},
        "per_class_ms": {c: report["classes"][c].get("elapsed_ms") for c in classes},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
