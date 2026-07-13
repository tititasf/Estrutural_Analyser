#!/usr/bin/env python3
"""Materializa candidatos RAG a partir de uma sessão QA, sem promover memória."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_candidates(manifest: dict, decisions: list[dict]) -> list[dict]:
    """Agrupa decisões QA confiáveis sem transformá-las em memória ativa.

    A saída é deliberadamente uma proposta T1: quem aprova é o dono.  Isso evita
    que uma sessão de auditoria local passe a contaminar a recuperação semântica.
    """
    # CORRIGIR é evidência para o backlog de engenharia, não para a memória que
    # ajudará a confirmar casos futuros.  Uma regra só se torna candidata T1 se
    # o próprio campo foi confirmado; mesmo assim a promoção humana continua
    # obrigatória.
    eligible = [
        row for row in decisions
        if (
            row.get("confidence") == "high"
            and row.get("decision") in {"CONFIRMAR", "N/A_CONFIRMADO"}
            and not row.get("operations")
        )
    ]
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in eligible:
        groups[(row["classe"], row["field_id"])].append(row)
    candidates: list[dict] = []
    for (classe, field_id), rows in sorted(groups.items()):
        evidence = []
        for row in rows:
            for entry in row.get("evidence") or []:
                if isinstance(entry, dict):
                    evidence.append(entry)
        decision_ids = "|".join(sorted(x["decision_id"] for x in rows))
        key = f"{manifest['run_id']}|{classe}|{field_id}|{decision_ids}"
        candidates.append({
            "candidate_id": "qa-rag-" + hashlib.sha256(key.encode()).hexdigest()[:16],
            "status": "T1_CANDIDATE_REQUIRES_HUMAN_APPROVAL",
            "tier_candidate": "T1",
            "classe": classe,
            "field_id": field_id,
            "project_id": manifest.get("project_id"),
            "source_run": manifest["run_id"],
            "items": sorted({row["item"] for row in rows}),
            "decisions": sorted({row["decision"] for row in rows}),
            "decision_ids": [row["decision_id"] for row in rows],
            "evidence": evidence[:32],
            "rule": "Registro de evidência confirmada por item/campo; não é regra universal do campo. Exige confirmação humana e artefato/hash antes de entrar no RAG consultável T1.",
        })
    return candidates


def write_candidate_pack(run_dir: Path, manifest: dict, candidates: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "candidatos_t1.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Candidatos RAG T1 — revisão humana obrigatória", "", f"- Run QA: `{manifest['run_id']}`", f"- Candidatos: {len(candidates)}", ""]
    for candidate in candidates:
        lines.append(f"- `{candidate['candidate_id']}` — {candidate['classe']}/{candidate['field_id']} — itens: {', '.join(candidate['items'])}")
    (out_dir / "resumo.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def promote_candidates(
    db_path: Path,
    candidates_path: Path,
    *,
    approved_by: str,
    approved_ids: set[str] | None = None,
) -> dict:
    """Promove candidatos já aprovados para T1 de forma idempotente.

    A tabela legada ``semantic_rag_kb`` não possui colunas de tier. Por isso a
    proveniência, o tier e o candidato são preservados dentro do JSON da regra e
    no evento humano correspondente.  O consumidor continua consultivo até
    possuir um schema de ranking próprio.
    """
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    selected = [
        candidate for candidate in candidates
        if approved_ids is None or candidate["candidate_id"] in approved_ids
    ]
    if not selected:
        raise ValueError("nenhum candidato corresponde à seleção de aprovação")

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    inserted = 0
    existing = 0
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT regra_semantica FROM semantic_rag_kb WHERE obra_contexto LIKE 'qa_groundtruth_t1:%'"
        ).fetchall()
        known = set()
        for (raw,) in rows:
            try:
                known.add(json.loads(raw).get("candidate_id"))
            except (TypeError, json.JSONDecodeError):
                continue
        for candidate in selected:
            candidate_id = candidate["candidate_id"]
            if candidate_id in known:
                existing += 1
                continue
            rule = {
                "candidate_id": candidate_id,
                "tier": "T1",
                "kind": "qa_groundtruth_item_field",
                "field_id": candidate["field_id"],
                "items": candidate["items"],
                "source_run": candidate["source_run"],
                "decision_ids": candidate["decision_ids"],
                "evidence": candidate["evidence"],
                "approved_by": approved_by,
                "approved_at": now,
                "authority": "human_approved; consultative_only_without_local_evidence",
            }
            context = f"qa_groundtruth_t1:{candidate['project_id']}"
            conn.execute(
                "INSERT INTO semantic_rag_kb (classe, regra_semantica, obra_contexto, confianca) VALUES (?, ?, ?, ?)",
                (candidate["classe"], json.dumps(rule, ensure_ascii=False, sort_keys=True), context, 1.0),
            )
            event = {
                "candidate_id": candidate_id,
                "tier": "T1",
                "field_id": candidate["field_id"],
                "items": candidate["items"],
                "source_run": candidate["source_run"],
            }
            conn.execute(
                """
                INSERT INTO human_event_logs (
                    log_id, timestamp, obra_id, classe, item_id, fase_editada,
                    ui_context, estado_anterior_json, estado_novo_json,
                    campos_alterados, processado_por_rag, event_kind, status,
                    tier, validation_origin, user_reason, source_agent,
                    actor_id, session_id, idempotency_key, approved_at,
                    approved_by, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'approval', 'APPROVED', 'T1',
                    'human_approved_qa_curation', ?, 'qa_evidence_auditor', ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"qa-rag-approval-{candidate_id}", now, candidate["project_id"], candidate["classe"],
                    "MULTI", "QA_RAG_CURATOR", "qa_rag_curation.py", "{}", json.dumps(event, ensure_ascii=False),
                    candidate["field_id"], "Aprovação humana do pacote QA ground truth", approved_by,
                    candidate["source_run"], candidate_id, now, approved_by, now,
                ),
            )
            inserted += 1
        conn.commit()
    finally:
        conn.close()
    return {"selected": len(selected), "inserted": inserted, "already_promoted": existing}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    materialize = sub.add_parser("materialize", help="gera candidatos T1 sem escrever no banco")
    materialize.add_argument("--run", required=True, help="dossiê produzido por qa_evidence_auditor")
    materialize.add_argument("--out-dir")
    promote = sub.add_parser("promote", help="promove candidatos T1 já aprovados")
    promote.add_argument("--db", required=True)
    promote.add_argument("--candidates", required=True)
    promote.add_argument("--approved-by", required=True)
    promote.add_argument("--candidate", action="append", dest="candidate_ids")
    promote.add_argument("--approve-all", action="store_true")
    args = parser.parse_args()
    if args.command == "promote":
        if not args.approve_all and not args.candidate_ids:
            parser.error("promote requer --approve-all ou ao menos um --candidate")
        outcome = promote_candidates(
            Path(args.db), Path(args.candidates), approved_by=args.approved_by,
            approved_ids=None if args.approve_all else set(args.candidate_ids),
        )
        print(json.dumps(outcome, ensure_ascii=False))
        return 0
    run_dir = Path(args.run)
    manifest = json.loads((run_dir / "manifesto.json").read_text(encoding="utf-8"))
    decisions = read_jsonl(run_dir / "decisoes.jsonl")
    candidates = build_candidates(manifest, decisions)
    out_dir = Path(args.out_dir) if args.out_dir else run_dir / "rag_candidatos"
    write_candidate_pack(run_dir, manifest, candidates, out_dir)
    print(json.dumps({"out_dir": str(out_dir), "candidates": len(candidates)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
