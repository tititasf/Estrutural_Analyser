#!/usr/bin/env python3
"""Rubrica de eficiência do ciclo treino × validação (QA Global).

Schema: arete.qa_cycle_efficiency/v1

Mede se o microciclo do item foi enxuto e honesto — NÃO emite selo 🟠, Arete
nem autoriza apply. Ver docs/QA-CICLO-EFICIENCIA-E-AUTORIDADE.md.
"""
from __future__ import annotations

from collections import Counter
from typing import Any


SCHEMA = "arete.qa_cycle_efficiency/v1"
PHASES = ("train", "validate", "visual", "fix", "regen")


def _phase_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    """Conta fases.

    Prefere eventos ``cycle_phase`` (auto ou manuais). Fallback para
    ``manual_record``/teach só em runs antigos sem ``cycle_phase``, para não
    dupla-contar quando o executor já emite phase automaticamente.
    """
    counts: dict[str, int] = {p: 0 for p in PHASES}
    has_explicit = False
    for event in events:
        kind = str(event.get("kind") or "")
        phase = str(event.get("phase") or event.get("cycle_phase") or "").lower()
        if kind == "cycle_phase" and phase in counts:
            counts[phase] += 1
            has_explicit = True
    if has_explicit:
        return counts
    for event in events:
        kind = str(event.get("kind") or "")
        if kind == "manual_record":
            rk = str(event.get("record_kind") or "").lower()
            if rk == "visual":
                counts["visual"] += 1
            elif rk == "fix":
                counts["fix"] += 1
            elif rk == "test":
                counts["validate"] += 1
        elif kind in {"human_teaching", "structured_question"}:
            counts["train"] += 1
    return counts


def _closed_loop_score(phases: dict[str, int], status: str | None) -> tuple[float, str]:
    """train→regen→visual→validate (ou subset honesto se não houve bug)."""
    train = phases.get("train", 0)
    regen = phases.get("regen", 0)
    visual = phases.get("visual", 0)
    validate = phases.get("validate", 0)
    fix = phases.get("fix", 0)

    # Ciclo de exploração sem bug: só validate (+ opcional visual) ainda é fechado.
    if train == 0 and fix == 0 and regen == 0:
        if validate > 0:
            note = "loop de validação pura (sem treino/fix) — ok se item já saudável"
            return (90.0 if visual > 0 else 75.0), note
        return 20.0, "sem fases train/validate registradas"

    score = 0.0
    parts = []
    if train > 0 or fix > 0:
        score += 25.0
        parts.append("train/fix")
    if regen > 0 or (fix == 0 and train == 0):
        score += 25.0
        parts.append("regen" if regen else "sem-regen-necessário")
    else:
        parts.append("faltou regen após fix/train")
    if visual > 0:
        score += 25.0
        parts.append("visual")
    else:
        parts.append("sem visual registrado")
    if validate > 0:
        score += 25.0
        parts.append("validate")
    else:
        parts.append("sem validate")

    # penalidade se visual repetido sem fix
    if visual >= 3 and fix == 0 and train == 0:
        score = max(0.0, score - 20.0)
        parts.append("visual_rounds sem fix")

    return score, " + ".join(parts)


def _budget_score(cycle: int | None, max_cycles: int | None) -> float:
    if not max_cycles or max_cycles <= 0:
        return 70.0
    used = max(0, int(cycle or 0))
    ratio = min(1.0, used / float(max_cycles))
    return round(100.0 * (1.0 - ratio), 1)


def _routing_score(routing: dict[str, Any], event_kinds: dict[str, int]) -> float:
    score = 80.0
    if routing.get("used_review"):
        score += 10.0
    # headless excessivo costuma aparecer como muitos automatic_step sem fecho
    auto = int(event_kinds.get("automatic_step") or 0)
    if auto > 6:
        score -= 15.0
    if auto > 12:
        score -= 15.0
    if routing.get("structured_questions", 0) > 3:
        score -= 10.0
    return max(0.0, min(100.0, score))


def _visual_discipline(phases: dict[str, int], tasks: dict[str, Any]) -> float:
    visual = phases.get("visual", 0)
    fix = phases.get("fix", 0)
    task_visual = str((tasks.get("visual") or {}) if isinstance(tasks.get("visual"), dict) else tasks.get("visual") or "")
    if isinstance(tasks.get("visual"), dict):
        task_visual = str(tasks["visual"].get("status") or "")
    score = 50.0
    if visual >= 1:
        score = 85.0
    if task_visual.upper() in {"PASS", "COMPLETE", "OK"}:
        score = max(score, 90.0)
    if task_visual.upper() == "FAIL" and fix == 0:
        score = min(score, 40.0)
    if visual >= 4 and fix == 0:
        score = min(score, 35.0)
    if visual == 0 and fix > 0:
        score = min(score, 45.0)  # fix sem reabrir visual
    return score


def _outcome_honesty(status: str | None, tasks: dict[str, Any], phases: dict[str, int]) -> float:
    st = (status or "").upper()
    if st in {"WAITING_HUMAN_VISUAL", "WAITING_HUMAN_QG7", "WAITING_HUMAN_RULE", "NEEDS_IMPLEMENTATION", "ACTIVE"}:
        # honesto: não fingiu COMPLETE
        return 85.0
    if st == "COMPLETE":
        visual_ok = phases.get("visual", 0) > 0 or str(
            (tasks.get("visual") or {}).get("status") if isinstance(tasks.get("visual"), dict) else ""
        ).upper() in {"PASS", "OK", "COMPLETE"}
        if not visual_ok and phases.get("fix", 0) > 0:
            return 40.0  # complete após fix sem visual
        return 90.0
    if st in {"FAILED", "BLOCKED"}:
        return 70.0
    return 60.0


def _cost_score(llm: dict[str, Any] | None) -> float:
    if not llm:
        return 70.0  # neutro
    total = int(llm.get("total_tokens") or 0)
    calls = int(llm.get("calls_count") or 0)
    if calls == 0 and total == 0:
        return 80.0  # sem LLM registrado — ok se ciclo CAD-only
    # faixas grosseiras: eficiência relativa, não orçamento absoluto
    if total <= 50_000:
        return 90.0
    if total <= 200_000:
        return 75.0
    if total <= 500_000:
        return 55.0
    return 35.0


def grade_for(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def build_cycle_efficiency(
    state: dict[str, Any],
    *,
    llm_usage: dict[str, Any] | None = None,
    routing_signals: dict[str, Any] | None = None,
    event_kinds: dict[str, int] | None = None,
) -> dict[str, Any]:
    events = list(state.get("events") or [])
    phases = _phase_counts(events)
    # contagem explícita em state.cycle_phases se o executor grava
    for phase, n in (state.get("cycle_phases") or {}).items():
        key = str(phase).lower()
        if key in phases:
            phases[key] = max(phases[key], int(n or 0))

    tasks = state.get("tasks") or {}
    status = state.get("status")
    cycle = state.get("cycle")
    max_cycles = state.get("max_cycles")
    routing = routing_signals or {}
    kinds = event_kinds or dict(Counter(str(e.get("kind") or "unknown") for e in events))
    llm = llm_usage or state.get("llm_usage") or {}

    closed, closed_note = _closed_loop_score(phases, status)
    budget = _budget_score(cycle if isinstance(cycle, int) else None, max_cycles if isinstance(max_cycles, int) else None)
    routing_s = _routing_score(routing, kinds)
    visual_s = _visual_discipline(phases, tasks)
    outcome_s = _outcome_honesty(status, tasks, phases)
    cost_s = _cost_score(llm if isinstance(llm, dict) else None)

    score = round(
        0.25 * closed
        + 0.20 * budget
        + 0.15 * routing_s
        + 0.15 * visual_s
        + 0.15 * outcome_s
        + 0.10 * cost_s,
        1,
    )
    grade = grade_for(score)

    recommendations: list[str] = []
    if phases["validate"] == 0:
        recommendations.append("registrar phase=validate antes de apply/selo 🟠")
    if phases["fix"] > 0 and phases["visual"] == 0:
        recommendations.append("após fix, regerar e reabrir G2-V (phase=visual)")
    if phases["visual"] >= 3 and phases["fix"] == 0:
        recommendations.append("muitos rounds visuais sem fix — triangular causa no motor")
    if isinstance(max_cycles, int) and isinstance(cycle, int) and max_cycles and cycle >= max_cycles:
        recommendations.append("budget esgotado — estender ciclos só com hipótese nova")
    if not recommendations:
        recommendations.append("manter rota mínima; registrar phases para a próxima comparação")

    return {
        "schema": SCHEMA,
        "score": score,
        "grade": grade,
        "weights": {
            "closed_loop": 0.25,
            "budget": 0.20,
            "routing": 0.15,
            "visual_discipline": 0.15,
            "outcome_honesty": 0.15,
            "cost": 0.10,
        },
        "components": {
            "closed_loop": {"score": closed, "note": closed_note},
            "budget": {"score": budget, "cycle": cycle, "max_cycles": max_cycles},
            "routing": {"score": routing_s},
            "visual_discipline": {"score": visual_s},
            "outcome_honesty": {"score": outcome_s, "status": status},
            "cost": {"score": cost_s, "llm_tokens": llm.get("total_tokens") if isinstance(llm, dict) else None},
        },
        "phases": phases,
        "closed_loop": closed >= 75.0,
        "recommendations": recommendations,
        "anti_superselo": (
            "Esta nota mede eficiência do processo, não qualidade Arete da fôrma. "
            "Não emite selo 🟠 (qa_agente); 🟠 exige CONFIRMAR com prova no adaptador."
        ),
        "doc": "docs/QA-CICLO-EFICIENCIA-E-AUTORIDADE.md",
    }


def efficiency_markdown_lines(eff: dict[str, Any]) -> list[str]:
    phases = eff.get("phases") or {}
    lines = [
        "## Eficiência do ciclo (treino × validação)",
        "",
        f"- Nota: **{eff.get('score')}/{eff.get('grade')}** "
        f"(closed_loop={'sim' if eff.get('closed_loop') else 'não'})",
        f"- Fases: train={phases.get('train', 0)} validate={phases.get('validate', 0)} "
        f"visual={phases.get('visual', 0)} fix={phases.get('fix', 0)} regen={phases.get('regen', 0)}",
        f"- Doc: `{eff.get('doc')}`",
        "",
        "### Recomendações de processo",
        "",
    ]
    for rec in eff.get("recommendations") or []:
        lines.append(f"- {rec}")
    lines += ["", f"> {eff.get('anti_superselo')}", ""]
    return lines
