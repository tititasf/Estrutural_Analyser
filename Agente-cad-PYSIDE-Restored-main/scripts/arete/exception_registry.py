# -*- coding: utf-8 -*-
"""
exception_registry.py — API de consulta sobre G2_EXCECOES (arete_config.py)
para uso pelo frontend (Diagnostic Hub / Diagnostic Reverse Hub).

Objetivo: durante a INTERPRETACAO de um item (P18, P26, P27, ...), o
frontend pode chamar `get_item_exceptions(classe, elemento_id, pavimento)`
para descobrir se aquele item especifico tem uma exceção G2 PENDENTE
documentada (gate canonico FAIL com causa raiz ja investigada) e exibir um
aviso visual ("EXCECAO") — ver
scripts/arete/relatorios/AR-1prime-canonico/EXCECOES-FRONTEND.md para a
arquitetura completa e o roadmap do classificador de exceções.

Nao depende de Qt — modulo puro, seguro para chamar de qualquer thread.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from arete_config import G2_EXCECOES  # noqa: E402


def get_item_exceptions(classe: str, elemento_id: str,
                         pavimento: str | None = None) -> list[dict]:
    """Exceções ITEM-ESPECIFICAS (`itens` contem `elemento_id`) que afetam
    (classe, elemento_id[, pavimento]).

    Estas sao as exceções relevantes para o flag "EXCECAO" no frontend: o
    item tem gate G2 FAIL com causa raiz documentada e `status=PENDENTE`
    (ainda nao resolvida / nao classificada).
    """
    classe = (classe or "").upper()
    out = []
    for exc in G2_EXCECOES:
        if str(exc.get("classe", "")).upper() != classe:
            continue
        itens = exc.get("itens")
        if not itens or elemento_id not in itens:
            continue
        exc_pav = exc.get("pavimento")
        if pavimento and exc_pav and exc_pav != pavimento:
            continue
        out.append(exc)
    return out


def get_class_exceptions(classe: str, parte: str | None = None) -> list[dict]:
    """Exceções de CLASSE (sem `itens` — aplicam a categorias diagnostico
    como `paineis`/`cotas` para TODOS os itens de uma classe/parte, ex.:
    EXC-PIL-ABCD-FORMA, EXC-PIL-CIMA-FORMA).

    Uteis para uma nota informativa de escopo (nao um flag de FAIL por
    item), ex.: "paineis/cotas desta vista sao diagnostico, nao bloqueiam
    o gate — ver EXC-PIL-CIMA-FORMA".
    """
    classe = (classe or "").upper()
    out = []
    for exc in G2_EXCECOES:
        if str(exc.get("classe", "")).upper() != classe:
            continue
        if exc.get("itens"):
            continue
        if parte and parte not in exc.get("partes", []):
            continue
        out.append(exc)
    return out


def has_pending_exception(classe: str, elemento_id: str,
                           pavimento: str | None = None) -> bool:
    """True se (classe, elemento_id[, pavimento]) tem >=1 exceção
    item-especifica com status=PENDENTE."""
    return any(
        exc.get("status") == "PENDENTE"
        for exc in get_item_exceptions(classe, elemento_id, pavimento)
    )


def summarize_item_exceptions(classe: str, elemento_id: str,
                               pavimento: str | None = None) -> str:
    """Resumo curto (1 linha por exceção) para tooltip/label no frontend."""
    excs = get_item_exceptions(classe, elemento_id, pavimento)
    if not excs:
        return ""
    linhas = []
    for exc in excs:
        cats = ", ".join(exc.get("categorias_afetadas", []))
        linhas.append(f"{exc['id']} [{exc.get('status')}] ({cats})")
    return "\n".join(linhas)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Consulta G2_EXCECOES")
    p.add_argument("classe")
    p.add_argument("elemento_id")
    p.add_argument("--pav", default=None)
    args = p.parse_args()

    excs = get_item_exceptions(args.classe, args.elemento_id, args.pav)
    if not excs:
        print(f"{args.classe}/{args.elemento_id}: sem exceção registrada.")
    else:
        print(f"{args.classe}/{args.elemento_id}: {len(excs)} exceção(ões)")
        for exc in excs:
            print(f"  - {exc['id']} [{exc.get('status')}]")
            print(f"    partes: {exc.get('partes')}")
            print(f"    categorias_afetadas: {exc.get('categorias_afetadas')}")
            print(f"    motivo: {exc['motivo'][:200]}...")
