#!/usr/bin/env python
"""Rollup de concordância entre diagnóstico automático e triagem humana.

Item 4 do checklist §6 de `docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md` — métrica
objetiva descrita em §4.2: por classe/causa_raiz, quantos achados automáticos
existem, quantos têm par humano no mesmo item, e qual a taxa de concordância
entre os dois (mesma causa_raiz apontada pelos dois lados). É o dado que, ao
longo do tempo, justifica dar mais ou menos autonomia ao diagnóstico
automático por tipo de causa — não decide nada sozinho.

Fontes:
- Log humano (append-only, mantido por `qa_error_review.py` + interpretação
  do agente): `scripts/arete/relatorios/triagem_erros/*.jsonl`.
- Log automático (gerado a cada rodada de `diagnostico_{classe}_n1_n2.py`,
  um por run): `scripts/arete/relatorios/diagnosticos_{classe}/{obra}/{pav}/
  {run_id}/triagem_auto_{classe}.jsonl` — só o run MAIS RECENTE de cada
  classe entra no rollup (runs antigos são histórico, não duplicam contagem).

Uso:
    python scripts/arete/triagem_concordancia.py
    python scripts/arete/triagem_concordancia.py --json   # saída máquina
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
_TRIAGEM_HUMANA_DIR = SCRIPT_DIR / "relatorios" / "triagem_erros"
_RELATORIOS_DIR = SCRIPT_DIR / "relatorios"


def _read_jsonl(path: Path) -> list[dict]:
    entries = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def load_human_entries() -> list[dict]:
    """Lê todos os `triagem_erros/*.jsonl` — cada linha já tem `classe`."""
    entries: list[dict] = []
    if not _TRIAGEM_HUMANA_DIR.is_dir():
        return entries
    for path in sorted(_TRIAGEM_HUMANA_DIR.glob("*.jsonl")):
        for entry in _read_jsonl(path):
            entry.setdefault("marcado_por", "humano")
            entry["_fonte"] = path.name
            entries.append(entry)
    return entries


def load_latest_auto_entries() -> list[dict]:
    """Lê o run mais recente de `triagem_auto_{classe}.jsonl` por classe,
    varrendo `diagnosticos_{classe}/{obra}/{pav}/{run_id}/`. Runs antigos
    (mesma classe, run_id menor) são ignorados para não duplicar achados já
    superados por uma rodada mais nova do mesmo diagnóstico."""
    latest_by_classe: dict[str, tuple[str, Path]] = {}
    if not _RELATORIOS_DIR.is_dir():
        return []
    for diag_dir in sorted(_RELATORIOS_DIR.glob("diagnosticos_*")):
        classe = diag_dir.name.removeprefix("diagnosticos_").upper()
        for jsonl_path in diag_dir.glob("*/*/*/triagem_auto_*.jsonl"):
            run_id = jsonl_path.parent.name
            current = latest_by_classe.get(classe)
            if current is None or run_id > current[0]:
                latest_by_classe[classe] = (run_id, jsonl_path)

    entries: list[dict] = []
    for classe, (run_id, path) in latest_by_classe.items():
        for entry in _read_jsonl(path):
            entry["_fonte"] = f"{path.name} (run {run_id})"
            entries.append(entry)
    return entries


def build_rollup(human: list[dict], auto: list[dict]) -> dict[str, dict]:
    """Agrupa por classe -> causa_raiz -> métricas.

    `taxa_concordancia` só é calculável quando existe pelo menos 1 item com
    par humano+auto simultâneo; sem isso, fica `None` (não é zero — zero
    significaria "sempre discorda", `None` significa "sem dado ainda").
    """
    human_by_classe_item: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for entry in human:
        classe = str(entry.get("classe") or "").upper()
        item = str(entry.get("item") or "")
        if classe and item:
            human_by_classe_item[(classe, item)].append(entry)

    rollup: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(lambda: {
            "n_auto": 0,
            "n_com_par_humano": 0,
            "n_concorda": 0,
            "n_diverge": 0,
            "n_abertos_reais": 0,
            "itens_abertos": [],
        })
    )

    for entry in auto:
        classe = str(entry.get("classe") or "").upper()
        causa = str(entry.get("causa_raiz") or "sem_causa")
        item = str(entry.get("item") or "")
        bucket = rollup[classe][causa]
        bucket["n_auto"] += 1

        pares_humanos = human_by_classe_item.get((classe, item)) or []
        if pares_humanos:
            bucket["n_com_par_humano"] += 1
            # Concorda se QUALQUER marcação humana do item citar a mesma causa.
            if any(str(h.get("causa_raiz") or "") == causa for h in pares_humanos):
                bucket["n_concorda"] += 1
            else:
                bucket["n_diverge"] += 1

        if str(entry.get("status") or "") == "aberto":
            bucket["n_abertos_reais"] += 1
            bucket["itens_abertos"].append(item)

    # Achados só-humanos (sem par automático) — contam para completude do
    # rollup ainda que não tenham `n_auto`; ficam com causa própria.
    for (classe, item), entries in human_by_classe_item.items():
        for entry in entries:
            causa = str(entry.get("causa_raiz") or "sem_causa")
            bucket = rollup[classe][causa]
            # já contado acima se tinha par; aqui só garante que a causa
            # apareça no rollup mesmo quando NENHUM auto a identificou ainda.
            _ = bucket

    result: dict[str, dict] = {}
    for classe, causas in rollup.items():
        result[classe] = {}
        for causa, metrics in causas.items():
            n_par = metrics["n_com_par_humano"]
            taxa = (metrics["n_concorda"] / n_par) if n_par else None
            result[classe][causa] = {
                "n_auto": metrics["n_auto"],
                "n_com_par_humano": n_par,
                "n_concorda": metrics["n_concorda"],
                "n_diverge": metrics["n_diverge"],
                "taxa_concordancia": taxa,
                "n_abertos_reais": metrics["n_abertos_reais"],
                "itens_abertos": metrics["itens_abertos"],
            }
    return result


def format_text(rollup: dict[str, dict]) -> str:
    lines = []
    for classe in sorted(rollup):
        lines.append(f"=== {classe} ===")
        for causa in sorted(rollup[classe]):
            m = rollup[classe][causa]
            taxa = (
                f"{m['taxa_concordancia']:.0%}"
                if m["taxa_concordancia"] is not None
                else "sem dado (nenhum par humano ainda)"
            )
            lines.append(
                f"  {causa}: {m['n_auto']} auto | {m['n_com_par_humano']} c/ par humano "
                f"| concordância {taxa} | {m['n_abertos_reais']} aberto(s) real(is)"
            )
            if m["itens_abertos"]:
                lines.append(f"    itens abertos: {', '.join(m['itens_abertos'])}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rollup de concordância auto x humano por classe/causa_raiz"
    )
    parser.add_argument("--json", action="store_true", help="Saída em JSON puro")
    args = parser.parse_args()

    human = load_human_entries()
    auto = load_latest_auto_entries()
    rollup = build_rollup(human, auto)

    if args.json:
        print(json.dumps(rollup, ensure_ascii=False, indent=2))
    else:
        print(format_text(rollup))


if __name__ == "__main__":
    main()
