#!/usr/bin/env python3
"""Materializa candidatos RAG a partir de uma sessão QA, sem promover memória."""
from __future__ import annotations

import argparse
import hashlib
import json
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="dossiê produzido por qa_evidence_auditor")
    parser.add_argument("--out-dir")
    args = parser.parse_args()
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
