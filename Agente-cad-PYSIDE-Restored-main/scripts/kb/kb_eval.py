# -*- coding: utf-8 -*-
"""
kb_eval.py — mede a qualidade da busca da KB contra perguntas com resposta conhecida.

Para cada modo (texto, vetor, híbrido) calcula:
  hit@1  a fonte esperada é o 1º resultado
  hit@5  aparece entre os 5 primeiros
  MRR    média de 1/posição da primeira fonte esperada (0 se não aparece)

Perguntas: docs/CONHECIMENTO/kb_eval_perguntas.yaml. Rodar depois de cada rebuild ou
mudança de embedder; queda de hit@5 é regressão.

Uso:
    python scripts/kb/kb_eval.py
    python scripts/kb/kb_eval.py --detalhe     # lista as perguntas que falharam
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kb_comum import KB_DIR  # noqa: E402
from kb_query import buscar  # noqa: E402


def avaliar(modo: str, perguntas: list[dict], db=None) -> tuple[dict, list]:
    h1 = h5 = rr = 0.0
    falhas = []
    for p in perguntas:
        res = buscar(p["pergunta"], k=10, modo=modo, por_fonte=1, db_global=db)
        pos = next((i for i, r in enumerate(res, 1)
                    if any(e in r["path"] for e in p["esperado"])), None)
        h1 += pos == 1
        h5 += bool(pos and pos <= 5)
        rr += 1 / pos if pos else 0
        if not pos or pos > 5:
            falhas.append((p["pergunta"], pos, [r["path"].split("/")[-1] for r in res[:3]]))
    n = len(perguntas)
    return {"hit@1": h1 / n, "hit@5": h5 / n, "MRR": rr / n}, falhas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--detalhe", action="store_true")
    ap.add_argument("--modos", default="texto,vetor,hibrido")
    ap.add_argument("--db", type=Path, help="índice alternativo (comparação de embedder)")
    args = ap.parse_args()
    perguntas = yaml.safe_load((KB_DIR / "kb_eval_perguntas.yaml").read_text(encoding="utf-8"))
    print(f"{len(perguntas)} perguntas\n")
    print(f"{'modo':<9} {'hit@1':>6} {'hit@5':>6} {'MRR':>6}")
    for modo in args.modos.split(","):
        m, falhas = avaliar(modo, perguntas, args.db)
        print(f"{modo:<9} {m['hit@1']:>6.0%} {m['hit@5']:>6.0%} {m['MRR']:>6.2f}")
        if args.detalhe and falhas:
            for perg, pos, top in falhas:
                print(f"    ✗ {perg}  (pos={pos}) top3={top}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
