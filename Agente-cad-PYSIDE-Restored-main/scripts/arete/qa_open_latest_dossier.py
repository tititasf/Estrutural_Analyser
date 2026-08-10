#!/usr/bin/env python3
"""Localiza e opcionalmente abre o dossiê QA / run de loop mais recente.

Não muta DB nem artefatos de obra. Serve a harmonização app↔agente: a UI/CLI
só aponta para a prova (dossiê), sem tratar HTML como gate.
"""
from __future__ import annotations

import argparse
import json
import os
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE = Path(__file__).resolve().parent / "relatorios" / "qa_evidencias"
DEFAULT_LOOPS = Path(__file__).resolve().parent / "relatorios" / "qa_loop_runs"


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def find_latest_evidence_dossier(
    root: Path = DEFAULT_EVIDENCE,
    *,
    project_id: str | None = None,
) -> Path | None:
    if not root.is_dir():
        return None
    candidates: list[Path] = []
    for path in root.rglob("manifesto.json"):
        if project_id:
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if str(manifest.get("project_id") or "") != project_id:
                continue
        candidates.append(path.parent)
    if not candidates:
        return None
    return max(candidates, key=_mtime)


def find_latest_loop_run(
    root: Path = DEFAULT_LOOPS,
    *,
    project_id: str | None = None,
    classe: str | None = None,
    item: str | None = None,
) -> Path | None:
    if not root.is_dir():
        return None
    best: Path | None = None
    best_m = -1.0
    for state_path in root.glob("*/state.json"):
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        scope = state.get("scope") or {}
        if project_id and scope.get("project_id") != project_id:
            continue
        if classe and scope.get("class") != classe.upper():
            continue
        if item and item not in (scope.get("items") or []):
            continue
        m = _mtime(state_path)
        if m > best_m:
            best_m = m
            best = state_path.parent
    return best


def open_path(path: Path) -> None:
    path = path.resolve()
    if path.is_dir():
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    if path.suffix.lower() in {".html", ".htm"}:
        webbrowser.open(path.as_uri())
        return
    os.startfile(str(path))  # type: ignore[attr-defined]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id")
    parser.add_argument("--classe", choices=("PIL", "LAJ", "FV", "LV"))
    parser.add_argument("--item")
    parser.add_argument("--kind", choices=("evidence", "loop", "any"), default="any")
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    evidence = (
        find_latest_evidence_dossier(project_id=args.project_id)
        if args.kind in {"evidence", "any"}
        else None
    )
    loop = (
        find_latest_loop_run(
            project_id=args.project_id, classe=args.classe, item=args.item,
        )
        if args.kind in {"loop", "any"}
        else None
    )
    chosen = None
    if args.kind == "evidence":
        chosen = evidence
    elif args.kind == "loop":
        chosen = loop
    else:
        candidates = [p for p in (evidence, loop) if p is not None]
        chosen = max(candidates, key=_mtime) if candidates else None

    payload = {
        "dossier": str(chosen) if chosen else None,
        "evidence_latest": str(evidence) if evidence else None,
        "loop_latest": str(loop) if loop else None,
        "notice": "Apresentação HTML ≠ prova; abra o dossiê para hashes/decisões.",
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload["dossier"] or "NONE")
    if args.open and chosen:
        open_path(chosen)
    return 0 if chosen else 1


if __name__ == "__main__":
    raise SystemExit(main())
