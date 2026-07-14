#!/usr/bin/env python3
"""Executor persistente dos microciclos do QA Global de Evidências.

O executor coordena CLIs canônicos, conserva estado entre sessões e sempre
devolve uma próxima ação concreta. Ele não edita código, não promove RAG, não
aplica validações e não substitui o veredito visual humano/agente.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = Path(r"D:\Agente-cad-PYSIDE\project_data.vision")
DEFAULT_ROOT = Path(__file__).resolve().parent / "relatorios" / "qa_loop_runs"
SCHEMA = "arete.qa_loop_state/v1"
EVENT_SCHEMA = "arete.qa_loop_event/v1"
CLASSES = ("PIL", "LAJ", "FV", "LV")
LEVELS = ("N1", "N3", "N4")
HUMAN_KINDS = {"visual", "rule", "qg7", "rag_promotion"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _run_dir(root: Path, run_id: str) -> Path:
    return root / run_id


def _state_path(root: Path, run_id: str) -> Path:
    return _run_dir(root, run_id) / "state.json"


def load_state(root: Path, run_id: str) -> dict[str, Any]:
    path = _state_path(root, run_id)
    if not path.is_file():
        raise ValueError(f"run inexistente: {run_id}")
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("schema") != SCHEMA:
        raise ValueError(f"schema de run inválido: {path}")
    return state


def list_states(
    root: Path,
    *,
    project_id: str | None = None,
    classe: str | None = None,
    item: str | None = None,
    level: str | None = None,
    include_complete: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not root.is_dir():
        return rows
    for path in root.glob("*/state.json"):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if state.get("schema") != SCHEMA:
            continue
        scope = state.get("scope") or {}
        if project_id and scope.get("project_id") != project_id:
            continue
        if classe and scope.get("class") != classe.upper():
            continue
        if item and item not in (scope.get("items") or []):
            continue
        if level and scope.get("level") != level.upper():
            continue
        if not include_complete and state.get("status") == "COMPLETE":
            continue
        rows.append(state)
    return sorted(rows, key=lambda row: row.get("updated_at") or "", reverse=True)


def compatible_state(
    root: Path,
    *,
    project_id: str,
    classe: str,
    items: list[str],
    level: str,
) -> dict[str, Any] | None:
    wanted = set(items)
    for state in list_states(
        root,
        project_id=project_id,
        classe=classe,
        level=level,
        include_complete=False,
    ):
        if set((state.get("scope") or {}).get("items") or []) == wanted:
            return state
    return None


def _persist(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    run_dir = _run_dir(root, state["run_id"])
    _atomic_json(run_dir / "state.json", state)
    (run_dir / "RESUME.md").write_text(_resume_markdown(state), encoding="utf-8")


def _append_event(root: Path, state: dict[str, Any], kind: str, **payload: Any) -> dict[str, Any]:
    event = {
        "schema": EVENT_SCHEMA,
        "event_id": str(uuid.uuid4()),
        "at": utc_now(),
        "run_id": state["run_id"],
        "cycle": state["cycle"],
        "kind": kind,
        **payload,
    }
    state.setdefault("events", []).append(event)
    ledger = _run_dir(root, state["run_id"]) / "events.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def _resume_markdown(state: dict[str, Any]) -> str:
    scope = state["scope"]
    lines = [
        "# Retomada — QA Global de Evidências",
        "",
        f"- Run: `{state['run_id']}`",
        f"- Estado: **{state['status']}**",
        f"- Ciclo: {state['cycle']}/{state['max_cycles']}",
        f"- Escopo: `{scope['class']}` / `{scope['level']}` / `{', '.join(scope['items'])}`",
        f"- Projeto: `{scope['project_id']}`",
        "",
        "## Próxima ação",
        "",
        state.get("next_action") or "executar resume",
        "",
        "## Limites humanos preservados",
        "",
        "- regra estrutural ambígua ou lacuna do manual;",
        "- veredito visual;",
        "- promoção QG7 e promoção RAG T1/T2.",
        "",
    ]
    return "\n".join(lines)


def create_state(
    *,
    project_id: str,
    classe: str,
    items: list[str],
    level: str,
    pav: str | None,
    part: str | None,
    variant: str | None,
    max_cycles: int,
    root: Path,
) -> dict[str, Any]:
    classe = classe.upper()
    level = level.upper()
    if classe not in CLASSES:
        raise ValueError(f"classe inválida: {classe}")
    if level not in LEVELS:
        raise ValueError(f"nível inválido: {level}")
    normalized_items = list(dict.fromkeys(item.strip() for item in items if item.strip()))
    if not normalized_items:
        raise ValueError("informe ao menos um item")
    if max_cycles < 1:
        raise ValueError("max_cycles deve ser positivo")
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    state = {
        "schema": SCHEMA,
        "run_id": run_id,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "scope": {
            "project_id": project_id,
            "class": classe,
            "items": normalized_items,
            "level": level,
            "pav": pav,
            "part": part,
            "variant": variant,
        },
        "status": "ACTIVE",
        "cycle": 0,
        "max_cycles": max_cycles,
        "tasks": {
            "evidence_review": {"status": "PENDING"},
            "class_coverage": {"status": "PENDING" if classe == "PIL" else "NOT_APPLICABLE"},
            "visual": {"status": "PENDING"},
            "qg7": {"status": "PENDING" if classe in {"PIL", "FV", "LV"} else "NOT_REQUIRED"},
            "rag_candidate": {"status": "PENDING"},
        },
        "item_results": {},
        "teachings": [],
        "events": [],
        "next_action": "executar o primeiro ciclo automático",
        "authority": "diagnostic_only" if classe in {"PIL", "FV", "LV"} else "validation_ready",
    }
    _append_event(root, state, "run_created", scope=state["scope"])
    _persist(root, state)
    return state


def _execute(command: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(completed.stdout or "", encoding="utf-8")
    stderr_path.write_text(completed.stderr or "", encoding="utf-8")
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": str(stdout_path.resolve()),
        "stderr": str(stderr_path.resolve()),
    }


def _run_review(root: Path, state: dict[str, Any], db: Path) -> None:
    task = state["tasks"]["evidence_review"]
    if task["status"] == "COMPLETE":
        return
    run_dir = _run_dir(root, state["run_id"])
    scope = state["scope"]
    # O auditor grava um dossie imutavel e recusa sobrescrever. Cada ciclo
    # precisa portanto de seu proprio artefato; assim a correção preserva o
    # antes/depois e uma retomada nunca vira falha de infraestrutura.
    cycle_tag = f"cycle_{int(state.get('cycle') or 0):02d}"
    out_dir = run_dir / "evidence_review" / cycle_tag
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "arete" / "qa_evidence_auditor.py"),
        "review",
        "--db", str(db),
        "--project-id", scope["project_id"],
        "--classe", scope["class"],
        "--item", *scope["items"],
        "--include-sealed",
        "--rag-evidence", "auto",
        "--run-id", f"{state['run_id']}_review_{cycle_tag}",
        "--out-dir", str(out_dir),
    ]
    result = _execute(command, cwd=REPO_ROOT, stdout_path=run_dir / "logs" / "review.out", stderr_path=run_dir / "logs" / "review.err")
    task.update({"status": "COMPLETE" if result["returncode"] == 0 else "FAILED", "result": result, "out_dir": str(out_dir.resolve())})
    _append_event(root, state, "automatic_step", step="evidence_review", result=result)


def _run_pil_coverage(root: Path, state: dict[str, Any], db: Path) -> None:
    task = state["tasks"]["class_coverage"]
    if task["status"] == "COMPLETE":
        return
    run_dir = _run_dir(root, state["run_id"])
    scope = state["scope"]
    rows: dict[str, Any] = {}
    failed = False
    for item in scope["items"]:
        out = run_dir / "coverage" / f"{item}.json"
        command = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "arete" / "qa_pil_coverage.py"),
            "--project-id", scope["project_id"],
            "--item", item,
            "--db", str(db),
            "--run-probes",
            "--out", str(out),
        ]
        result = _execute(
            command,
            cwd=REPO_ROOT,
            stdout_path=run_dir / "logs" / f"coverage_{item}.out",
            stderr_path=run_dir / "logs" / f"coverage_{item}.err",
        )
        if out.is_file():
            coverage = json.loads(out.read_text(encoding="utf-8"))
            rows[item] = {
                "artifact": str(out.resolve()),
                "structural_complete": coverage.get("structural_complete"),
                "probes_complete": coverage.get("probes_complete"),
                "ready_for_visual": coverage.get("ready_for_visual"),
                "findings": coverage.get("findings", []),
                "next_actions": coverage.get("next_actions", []),
            }
        else:
            rows[item] = {"artifact": str(out.resolve()), "error": "relatório não materializado"}
        failed = failed or result["returncode"] not in (0, 1)
        _append_event(root, state, "automatic_step", step="pil_coverage", item=item, result=result)
    state["item_results"] = rows
    task.update({"status": "FAILED" if failed else "COMPLETE", "items": rows})


def _derive_status(state: dict[str, Any]) -> None:
    tasks = state["tasks"]
    if any(task.get("status") == "FAILED" for task in tasks.values()):
        state["status"] = "NEEDS_STRATEGY"
        state["next_action"] = "ler os logs do passo automático que falhou, corrigir a infraestrutura e retomar"
        return
    if state["scope"]["class"] == "PIL":
        rows = state.get("item_results") or {}
        findings = [(item, finding) for item, row in rows.items() for finding in row.get("findings", [])]
        if findings:
            item, finding = findings[0]
            state["status"] = "NEEDS_IMPLEMENTATION"
            state["next_action"] = (
                f"{item}: investigar e corrigir causa geral {finding.get('code')} ({finding.get('message')}); "
                "depois registrar kind=fix para invalidar e repetir as probes"
            )
            return
        if rows and not all(row.get("probes_complete") for row in rows.values()):
            state["status"] = "NEEDS_EVIDENCE"
            state["next_action"] = "resolver as probes cross-classe PENDENTE/FAIL antes da validação visual"
            return
    visual = tasks["visual"].get("status")
    if visual != "PASS":
        state["status"] = "WAITING_HUMAN_VISUAL"
        state["next_action"] = "abrir as fichas/PNGs canônicos e registrar record --kind visual --result PASS|FAIL com evidência"
        return
    if tasks["qg7"].get("status") == "PENDING":
        state["status"] = "WAITING_HUMAN_QG7"
        state["next_action"] = "revisar a promoção QG7 do adaptador; não habilitar apply PIL por score ou por cobertura apenas"
        return
    if tasks["qg7"].get("status") == "PASS" and state["authority"] == "diagnostic_only":
        state["status"] = "READY_FOR_PROMOTION"
        state["next_action"] = "implementar/revisar a mudança explícita de authority e seu teste; só então registrar promotion"
        return
    if tasks["rag_candidate"].get("status") == "PENDING":
        state["status"] = "READY_FOR_RAG_CANDIDATE"
        state["next_action"] = "materializar candidato RAG; promoção T1/T2 continua humana"
        return
    state["status"] = "COMPLETE"
    state["next_action"] = "item concluído dentro do contrato registrado; avançar ao próximo item"


def advance(root: Path, state: dict[str, Any], *, db: Path, force: bool = False) -> dict[str, Any]:
    if state["status"] == "COMPLETE" and not force:
        return state
    paused = {
        "NEEDS_IMPLEMENTATION", "NEEDS_EVIDENCE", "NEEDS_STRATEGY",
        "WAITING_HUMAN_RULE", "WAITING_HUMAN_VISUAL", "WAITING_HUMAN_QG7",
        "READY_FOR_PROMOTION", "READY_FOR_RAG_CANDIDATE",
    }
    if state["status"] in paused and not force:
        # Retomada sem nova evidência não deve gastar budget nem repetir a mesma
        # probe. O next_action explica qual evento precisa destravar o ciclo.
        _persist(root, state)
        return state
    if force:
        state["tasks"]["evidence_review"] = {"status": "PENDING"}
        if state["scope"]["class"] == "PIL":
            state["tasks"]["class_coverage"] = {"status": "PENDING"}
        state["status"] = "ACTIVE"
    if state["cycle"] >= state["max_cycles"] and not force:
        state["status"] = "NEEDS_STRATEGY"
        state["next_action"] = "orçamento de ciclos esgotado; revisar hipóteses e estender conscientemente o budget"
        _append_event(root, state, "cycle_budget_exhausted")
        _persist(root, state)
        return state
    state["cycle"] += 1
    _append_event(root, state, "cycle_started")
    _run_review(root, state, db)
    if state["scope"]["class"] == "PIL":
        _run_pil_coverage(root, state, db)
    _derive_status(state)
    _append_event(root, state, "cycle_finished", status=state["status"], next_action=state["next_action"])
    _persist(root, state)
    return state


def record(
    root: Path,
    state: dict[str, Any],
    *,
    kind: str,
    result: str,
    message: str,
    evidence: list[str],
) -> dict[str, Any]:
    normalized = result.upper()
    _append_event(root, state, "manual_record", record_kind=kind, result=normalized, message=message, evidence=evidence)
    if kind == "fix":
        state["tasks"]["evidence_review"] = {"status": "PENDING"}
        if state["scope"]["class"] == "PIL":
            state["tasks"]["class_coverage"] = {"status": "PENDING"}
        state["status"] = "ACTIVE"
        state["next_action"] = "retomar o ciclo para reverificar snapshot, cobertura e probes"
    elif kind == "visual":
        state["tasks"]["visual"] = {"status": normalized, "message": message, "evidence": evidence}
        if normalized == "FAIL":
            state["status"] = "NEEDS_IMPLEMENTATION"
            state["next_action"] = "triangular o achado visual, corrigir por fórmula geral e registrar fix"
        else:
            _derive_status(state)
    elif kind == "qg7":
        state["tasks"]["qg7"] = {"status": normalized, "message": message, "evidence": evidence}
        _derive_status(state)
    elif kind == "promotion":
        if normalized != "PASS" or not evidence:
            raise ValueError("promotion exige PASS e evidência explícita da alteração/revisão")
        state["authority"] = "validation_ready"
        state["tasks"]["qg7"]["status"] = "PASS"
        _derive_status(state)
    elif kind == "rag_candidate":
        state["tasks"]["rag_candidate"] = {"status": normalized, "message": message, "evidence": evidence}
        _derive_status(state)
    else:
        state["next_action"] = "usar a evidência registrada para executar o próximo passo técnico"
    _persist(root, state)
    return state


def teach(
    root: Path,
    state: dict[str, Any],
    *,
    family: str,
    field: str,
    rule: str,
    examples: list[str],
    exceptions: list[str],
    evidence: list[str],
) -> dict[str, Any]:
    if not rule.strip() or not examples:
        raise ValueError("ensino exige regra reutilizável e ao menos um exemplo")
    teaching = {
        "schema": "arete.qa_human_teaching/v1",
        "teaching_id": str(uuid.uuid4()),
        "at": utc_now(),
        "scope": state["scope"],
        "family": family,
        "field": field,
        "rule": rule.strip(),
        "examples": examples,
        "exceptions": exceptions,
        "evidence": evidence,
        "candidate_tier": "T1",
        "requires_human_approval": True,
        "authority": "human teaching; must still be encoded/tested as a universal motor rule",
    }
    path = _run_dir(root, state["run_id"]) / "teachings" / f"{teaching['teaching_id']}.json"
    _atomic_json(path, teaching)
    state.setdefault("teachings", []).append(str(path.resolve()))
    _append_event(root, state, "human_teaching", teaching=str(path.resolve()), family=family, field=field)
    state["status"] = "NEEDS_IMPLEMENTATION"
    state["next_action"] = (
        f"traduzir o ensino {family}/{field} em fórmula geral + teste positivo/negativo; "
        "depois registrar fix e retomar. Não promover o candidato RAG automaticamente"
    )
    _persist(root, state)
    return state


def ask_question(
    root: Path,
    state: dict[str, Any],
    *,
    gate: str,
    observation: str,
    attempts: list[str],
    rejected: list[str],
    alternatives: list[str],
    needed: str,
    evidence: list[str],
) -> dict[str, Any]:
    if not observation.strip() or not attempts or not alternatives or not needed.strip():
        raise ValueError("pergunta exige observação, tentativas, alternativas e resposta necessária")
    question = {
        "schema": "arete.qa_structured_question/v1",
        "question_id": str(uuid.uuid4()),
        "at": utc_now(),
        "scope": state["scope"],
        "gate": gate,
        "observation": observation.strip(),
        "evidence": evidence,
        "attempts": attempts,
        "rejected_hypotheses": rejected,
        "plausible_alternatives": alternatives,
        "answer_needed": needed.strip(),
        "how_to_teach": {
            "rule": "descreva a regra no vocabulário da ficha",
            "positive_example": "informe um caso que deve seguir a regra",
            "counterexample_or_exception": "informe quando a regra não se aplica",
            "scope": "delimite classe, família, modo e faces afetadas",
            "expected_drawing_effect": "diga o efeito esperado no N3/N4",
        },
        "status": "PENDENTE",
    }
    path = _run_dir(root, state["run_id"]) / "questions" / f"{question['question_id']}.json"
    _atomic_json(path, question)
    _append_event(root, state, "structured_question", question=str(path.resolve()), gate=gate)
    state["status"] = "WAITING_HUMAN_RULE"
    state["next_action"] = (
        f"responder a pergunta estruturada em {path.resolve()} e registrar com `teach`; "
        "o dono fornece a regra, não diagnostica o código"
    )
    _persist(root, state)
    return state


def _print_state(state: dict[str, Any], root: Path) -> None:
    print(json.dumps({
        "run_id": state["run_id"],
        "status": state["status"],
        "cycle": state["cycle"],
        "max_cycles": state["max_cycles"],
        "authority": state["authority"],
        "next_action": state["next_action"],
        "state": str(_state_path(root, state["run_id"]).resolve()),
        "resume": str((_run_dir(root, state["run_id"]) / "RESUME.md").resolve()),
    }, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Estado persistente e retomável do QA Global.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--project-id", required=True)
    start.add_argument("--classe", choices=CLASSES, required=True)
    start.add_argument("--item", action="append", required=True)
    start.add_argument("--nivel", choices=LEVELS, required=True)
    start.add_argument("--pav")
    start.add_argument("--parte")
    start.add_argument("--variante")
    start.add_argument("--max-cycles", type=int, default=8)
    start.add_argument("--db", type=Path, default=DEFAULT_DB)
    start.add_argument("--no-advance", action="store_true")
    start.add_argument("--new-run", action="store_true", help="ignora run ativo compatível")

    resume = sub.add_parser("resume")
    resume.add_argument("--run", required=True)
    resume.add_argument("--db", type=Path, default=DEFAULT_DB)
    resume.add_argument("--force", action="store_true")
    resume.add_argument("--extend-cycles", type=int, default=0)

    status = sub.add_parser("status")
    status.add_argument("--run", required=True)

    listing = sub.add_parser("list")
    listing.add_argument("--project-id")
    listing.add_argument("--classe", choices=CLASSES)
    listing.add_argument("--item")
    listing.add_argument("--nivel", choices=LEVELS)
    listing.add_argument("--include-complete", action="store_true")

    rec = sub.add_parser("record")
    rec.add_argument("--run", required=True)
    rec.add_argument("--kind", required=True, choices=("fix", "test", "visual", "qg7", "promotion", "rag_candidate", "note"))
    rec.add_argument("--result", required=True)
    rec.add_argument("--message", default="")
    rec.add_argument("--evidence", action="append", default=[])

    teaching = sub.add_parser("teach")
    teaching.add_argument("--run", required=True)
    teaching.add_argument("--family", required=True)
    teaching.add_argument("--field", required=True)
    teaching.add_argument("--rule", required=True)
    teaching.add_argument("--example", action="append", required=True)
    teaching.add_argument("--exception", action="append", default=[])
    teaching.add_argument("--evidence", action="append", default=[])

    question = sub.add_parser("question")
    question.add_argument("--run", required=True)
    question.add_argument("--gate", required=True)
    question.add_argument("--observation", required=True)
    question.add_argument("--attempt", action="append", required=True)
    question.add_argument("--rejected", action="append", default=[])
    question.add_argument("--alternative", action="append", required=True)
    question.add_argument("--needed", required=True)
    question.add_argument("--evidence", action="append", default=[])

    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == "start":
        state = None if args.new_run else compatible_state(
            root,
            project_id=args.project_id,
            classe=args.classe,
            items=args.item,
            level=args.nivel,
        )
        if state is None:
            state = create_state(
                project_id=args.project_id,
                classe=args.classe,
                items=args.item,
                level=args.nivel,
                pav=args.pav,
                part=args.parte,
                variant=args.variante,
                max_cycles=args.max_cycles,
                root=root,
            )
        else:
            _append_event(root, state, "compatible_run_reused")
            _persist(root, state)
        if not args.no_advance:
            state = advance(root, state, db=args.db)
    elif args.command == "resume":
        state = load_state(root, args.run)
        if args.extend_cycles:
            if args.extend_cycles < 0:
                parser.error("--extend-cycles deve ser positivo")
            state["max_cycles"] += args.extend_cycles
            _append_event(root, state, "cycle_budget_extended", amount=args.extend_cycles)
            if state["status"] == "NEEDS_STRATEGY":
                state["status"] = "ACTIVE"
        state = advance(root, state, db=args.db, force=args.force)
    elif args.command == "status":
        state = load_state(root, args.run)
    elif args.command == "list":
        rows = list_states(
            root,
            project_id=args.project_id,
            classe=args.classe,
            item=args.item,
            level=args.nivel,
            include_complete=args.include_complete,
        )
        print(json.dumps([
            {
                "run_id": row["run_id"],
                "status": row["status"],
                "updated_at": row["updated_at"],
                "scope": row["scope"],
                "next_action": row["next_action"],
            }
            for row in rows
        ], ensure_ascii=False, indent=2))
        return 0
    elif args.command == "record":
        state = record(root, load_state(root, args.run), kind=args.kind, result=args.result, message=args.message, evidence=args.evidence)
    elif args.command == "teach":
        state = teach(
            root,
            load_state(root, args.run),
            family=args.family,
            field=args.field,
            rule=args.rule,
            examples=args.example,
            exceptions=args.exception,
            evidence=args.evidence,
        )
    else:
        state = ask_question(
            root,
            load_state(root, args.run),
            gate=args.gate,
            observation=args.observation,
            attempts=args.attempt,
            rejected=args.rejected,
            alternatives=args.alternative,
            needed=args.needed,
            evidence=args.evidence,
        )
    _print_state(state, root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
