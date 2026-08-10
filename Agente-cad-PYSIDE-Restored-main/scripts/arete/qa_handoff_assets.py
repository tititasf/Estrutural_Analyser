#!/usr/bin/env python3
"""Resolve assets de handoff multi-classe: quadro pavimento + KPIs treino/validação."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
RELATORIOS = Path(__file__).resolve().parent / "relatorios"

QUADRO_GLOBS = {
    "PIL": ["**/qa_pil_quadro*/**/*", "**/quadro*pil*", "**/*pil*quadro*"],
    "LAJ": ["**/qa_laj_quadro*/**/*", "**/quadro*laj*", "**/*laj*quadro*"],
    "FV": ["**/qa_fv_quadro*/**/*", "**/quadro*fv*", "**/*fv*quadro*"],
    "LV": ["**/qa_lv_quadro*/**/*", "**/quadro*lv*", "**/*lv*quadro*"],
}


def find_latest_quadro(
    *,
    classe: str,
    project_id: str | None = None,
    root: Path = RELATORIOS,
) -> Path | None:
    """Melhor esforço: HTML/JSON/MD de quadro mais recente para a classe."""
    if not root.is_dir():
        return None
    classe = classe.upper()
    patterns = {
        "PIL": [
            "*pil*quadro*", "*quadro*pil*", "qa_pil_quadro*",
            "qa_quadros/PIL*", "QUADRO-PIL*",
        ],
        "LAJ": [
            "*laj*quadro*", "*quadro*laj*", "qa_laj_quadro*",
            "qa_laj_quadro_pavimento*", "QUADRO-LAJ*",
        ],
        "FV": [
            "*fv*quadro*", "*quadro*fv*", "qa_fv_quadro*",
            "qa_quadros/FV*", "QUADRO-FV*",
        ],
        "LV": [
            "*lv*quadro*", "*quadro*lv*", "qa_lv_quadro*",
            "qa_quadro_lv*", "QUADRO-LV*",
        ],
    }.get(classe, [])
    candidates: list[Path] = []
    for pat in patterns:
        candidates.extend(root.rglob(pat))
    # também pastas de output com index/quadro
    files: list[Path] = []
    preferred_names = (
        f"QUADRO-{classe}-PAVIMENTO.md",
        f"QUADRO-{classe}-PAVIMENTO.html",
        "index.html",
        "quadro.html",
        "quadro.md",
        "resumo.md",
        "summary.json",
    )
    for c in candidates:
        if c.is_file() and c.suffix.lower() in {".html", ".md", ".json", ".csv"}:
            files.append(c)
        elif c.is_dir():
            for name in preferred_names:
                p = c / name
                if p.is_file():
                    files.append(p)
    if project_id:
        filtered = [
            f for f in files
            if project_id in str(f) or project_id[:8] in str(f)
        ]
        if filtered:
            files = filtered
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def kpis_treino_validacao(
    decisions: list[Any],
    findings: list[Any],
    questions: list[Any],
) -> dict[str, Any]:
    """Separa sinais de treino (organização) vs validação (certificação local)."""
    def _get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    totals: dict[str, int] = {}
    for d in decisions:
        dec = _get(d, "decision")
        totals[dec] = totals.get(dec, 0) + 1
    confirm = int(totals.get("CONFIRMAR") or 0) + int(totals.get("N/A_CONFIRMADO") or 0)
    pending = int(totals.get("PENDENTE") or 0) + int(totals.get("REVISAR_HUMANO") or 0)
    corrigir = int(totals.get("CORRIGIR") or 0)
    codes = []
    for f in findings:
        codes.append(str(_get(f, "code") or _get(f, "kind") or "unknown"))
    return {
        "schema": "arete.qa_kpis_treino_validacao/v1",
        "validacao": {
            "decisions_total": len(decisions),
            "confirm_or_na": confirm,
            "pending_or_human": pending,
            "corrigir": corrigir,
            "decision_totals": totals,
            "fields_with_ops": sum(
                1 for d in decisions
                if (_get(d, "operations") or [])
            ),
        },
        "treino": {
            "findings": len(findings),
            "finding_codes": sorted(set(codes)),
            "questions_human": len(questions),
            "error_memory_ingest_recommended": len(findings) > 0,
            "rag_candidate_eligible_confirm": confirm,
        },
        "ratio_confirm_vs_pending": (
            round(confirm / max(1, confirm + pending), 3)
        ),
    }


def handoff_extra_lines(
    *,
    classe: str | None,
    project_id: str | None,
    decisions: list[Any],
    findings: list[Any],
    questions: list[Any],
) -> list[str]:
    lines: list[str] = ["## KPIs treino vs validação", ""]
    kpis = kpis_treino_validacao(decisions, findings, questions)
    v = kpis["validacao"]
    t = kpis["treino"]
    lines += [
        f"- Validação: decisões={v['decisions_total']}, CONFIRMAR/NA={v['confirm_or_na']}, "
        f"PENDENTE/HUMANO={v['pending_or_human']}, CORRIGIR={v['corrigir']}",
        f"- Treino: achados={t['findings']}, perguntas={t['questions_human']}, "
        f"códigos={', '.join(t['finding_codes'][:8]) or '—'}",
        f"- Razão confirm/(confirm+pending)={kpis['ratio_confirm_vs_pending']}",
        "",
    ]
    if classe and classe not in {"ALL", None}:
        quadro = find_latest_quadro(classe=str(classe), project_id=project_id)
        lines += ["## Quadro de estado (se existir)", ""]
        if quadro:
            lines.append(f"- Quadro {classe}: `{quadro.resolve()}`")
        else:
            lines.append(
                f"- Quadro {classe}: não encontrado sob `scripts/arete/relatorios/` "
                f"(gere com `qa_{classe.lower()}_quadro_pavimento.py`)."
            )
        lines.append("")
    return lines
