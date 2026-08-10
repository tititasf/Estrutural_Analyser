#!/usr/bin/env python3
"""Integridade de identidade obra/pavimento/item — diagnóstico READ-ONLY.

Auditoria 2026-07-30: o banco tem TRÊS chaves de obra concorrentes
(`project_id`, `obra_id`, `obra_name`), a tabela-ponte `reverse_eng_projetos`
está vazia, e as referências estão quebradas em massa. Isso produz a família de
bugs "falha de vínculo" — o recorte não acha a ficha, o gate lê zeros e reporta
"campo obrigatório ausente", indistinguível de erro do motor.

Este script NÃO escreve nada. Ele mede, para você decidir o que migrar:

  1. Referências órfãs por tabela (project_id que não existe em `projects`)
  2. Ambiguidade de `obra_id` (mesma coluna resolvendo contra tabelas diferentes)
  3. Cobertura da normalização de pavimento (src/core/obra_identity)
  4. Vínculo recorte -> ficha usando o pavimento normalizado

Uso:
    python scripts/arete/qa_identity_integrity.py
    python scripts/arete/qa_identity_integrity.py --json --out relatorio.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.obra_identity import pavimento_de_caminho  # noqa: E402

DB_PADRAO = "D:/Agente-cad-PYSIDE/project_data.vision"

# Tabelas que referenciam projects.id — a checar por órfãos.
TABELAS_PROJECT_ID = (
    "pillars", "beams", "slabs", "project_documents", "training_events",
    "pavimento_pi", "generated_scripts", "beam_elements", "slab_elements",
)
# Tabelas cujo obra_id pode resolver contra `projects` OU `obras` (ambíguo).
TABELAS_OBRA_ID = (
    "dxf_entidades", "fase3_fichas", "pavimentos", "pipeline_state",
    "human_event_logs",
)


def _conectar(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _existe(con: sqlite3.Connection, tabela: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabela,)
    ).fetchone()
    return row is not None


def orfaos_project_id(con: sqlite3.Connection) -> list[dict[str, Any]]:
    saida = []
    for tabela in TABELAS_PROJECT_ID:
        if not _existe(con, tabela):
            continue
        total = con.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]
        orfas = con.execute(
            f'SELECT COUNT(*) FROM "{tabela}" t '
            "LEFT JOIN projects p ON p.id = t.project_id WHERE p.id IS NULL"
        ).fetchone()[0]
        ids_orfaos = con.execute(
            f'SELECT COUNT(DISTINCT t.project_id) FROM "{tabela}" t '
            "LEFT JOIN projects p ON p.id = t.project_id WHERE p.id IS NULL"
        ).fetchone()[0]
        saida.append({
            "tabela": tabela, "linhas": total, "linhas_orfas": orfas,
            "project_ids_orfaos": ids_orfaos,
            "pct_orfas": round(orfas * 100 / total, 1) if total else 0.0,
        })
    return saida


def ambiguidade_obra_id(con: sqlite3.Connection) -> list[dict[str, Any]]:
    saida = []
    tem_obras = _existe(con, "obras")
    for tabela in TABELAS_OBRA_ID:
        if not _existe(con, tabela):
            continue
        distintos = con.execute(
            f'SELECT COUNT(DISTINCT obra_id) FROM "{tabela}"'
        ).fetchone()[0]
        via_projects = con.execute(
            f'SELECT COUNT(DISTINCT t.obra_id) FROM "{tabela}" t '
            "JOIN projects p ON p.id = t.obra_id"
        ).fetchone()[0]
        via_obras = con.execute(
            f'SELECT COUNT(DISTINCT t.obra_id) FROM "{tabela}" t '
            "JOIN obras o ON o.id = t.obra_id"
        ).fetchone()[0] if tem_obras else 0
        saida.append({
            "tabela": tabela, "obra_ids_distintos": distintos,
            "resolve_em_projects": via_projects, "resolve_em_obras": via_obras,
            "orfaos": distintos - via_projects - via_obras,
            # Ambíguo = a MESMA coluna aponta para tabelas diferentes conforme a linha.
            "ambiguo": via_projects > 0 and via_obras > 0,
        })
    return saida


def vinculo_recorte_ficha(con: sqlite3.Connection) -> dict[str, Any]:
    """Mede se o pavimento normalizado resolve recorte -> ficha."""
    rows = con.execute(
        "SELECT elemento_id, classe, recorte_path FROM reverse_eng_recortes "
        "WHERE recorte_path IS NOT NULL"
    ).fetchall()
    resolvidos = 0
    sem_pavimento = 0
    sem_ficha: list[dict[str, str]] = []
    for elemento_id, classe, caminho in rows:
        pavimento = pavimento_de_caminho(caminho)
        if pavimento is None:
            sem_pavimento += 1
            continue
        achou = con.execute(
            "SELECT 1 FROM reverse_eng_fichas "
            "WHERE classe=? AND pavimento=? AND elemento_id=?",
            (classe, pavimento, elemento_id),
        ).fetchone()
        if achou:
            resolvidos += 1
        elif len(sem_ficha) < 40:
            sem_ficha.append({
                "classe": classe, "elemento_id": elemento_id, "pavimento": pavimento,
            })
    total = len(rows)
    com_pavimento = total - sem_pavimento
    return {
        "recortes": total,
        "pavimento_inferido": com_pavimento,
        "pct_pavimento_inferido": round(com_pavimento * 100 / total, 1) if total else 0.0,
        "vinculo_resolvido": resolvidos,
        "pct_vinculo_resolvido": round(resolvidos * 100 / com_pavimento, 1) if com_pavimento else 0.0,
        "sem_pavimento": sem_pavimento,
        "sem_ficha_amostra": sem_ficha,
    }


def ambiguidade_elemento_id(con: sqlite3.Connection) -> dict[str, Any]:
    """Itens cujo elemento_id se repete entre pavimentos.

    Esses são exatamente os que uma busca sem `pavimento` resolve errado — e o
    erro é silencioso: devolve a ficha de OUTRO pavimento, com geometria plausível.
    """
    rows = con.execute(
        "SELECT classe, elemento_id, COUNT(DISTINCT pavimento) n "
        "FROM reverse_eng_fichas GROUP BY classe, elemento_id "
        "HAVING n > 1 ORDER BY n DESC"
    ).fetchall()
    return {
        "itens_ambiguos": len(rows),
        "pior_caso": [
            {"classe": c, "elemento_id": e, "pavimentos": n} for c, e, n in rows[:10]
        ],
    }


def coletar(db_path: str) -> dict[str, Any]:
    con = _conectar(db_path)
    try:
        ponte = con.execute("SELECT COUNT(*) FROM reverse_eng_projetos").fetchone()[0] \
            if _existe(con, "reverse_eng_projetos") else None
        return {
            "schema": "arete.identity_integrity/v1",
            "db": db_path,
            "tabela_ponte_reverse_eng_projetos": ponte,
            "orfaos_project_id": orfaos_project_id(con),
            "ambiguidade_obra_id": ambiguidade_obra_id(con),
            "ambiguidade_elemento_id": ambiguidade_elemento_id(con),
            "vinculo_recorte_ficha": vinculo_recorte_ficha(con),
        }
    finally:
        con.close()


def render(rel: dict[str, Any]) -> str:
    L: list[str] = []
    L.append("=== INTEGRIDADE DE IDENTIDADE (read-only) ===")
    L.append(f"DB: {rel['db']}")
    ponte = rel["tabela_ponte_reverse_eng_projetos"]
    L.append(f"Tabela-ponte reverse_eng_projetos: {ponte} linhas"
             + ("   <-- VAZIA: nada reconcilia as tres chaves" if ponte == 0 else ""))
    L.append("")
    L.append("-- Referencias orfas (project_id sem linha em projects) --")
    L.append(f"{'tabela':20}{'linhas':>9}{'orfas':>9}{'%':>7}{'ids orfaos':>12}")
    for r in rel["orfaos_project_id"]:
        L.append(f"{r['tabela']:20}{r['linhas']:>9}{r['linhas_orfas']:>9}"
                 f"{r['pct_orfas']:>7}{r['project_ids_orfaos']:>12}")
    L.append("")
    L.append("-- obra_id: resolve contra qual tabela? --")
    for r in rel["ambiguidade_obra_id"]:
        marca = "  <-- AMBIGUO" if r["ambiguo"] else ""
        L.append(f"  {r['tabela']:18} distintos={r['obra_ids_distintos']:3} "
                 f"projects={r['resolve_em_projects']:3} obras={r['resolve_em_obras']:3} "
                 f"orfaos={r['orfaos']:3}{marca}")
    L.append("")
    amb = rel["ambiguidade_elemento_id"]
    L.append(f"-- elemento_id repetido entre pavimentos: {amb['itens_ambiguos']} itens --")
    L.append("   (busca sem `pavimento` devolve a ficha de OUTRO pavimento, em silencio)")
    for r in amb["pior_caso"][:5]:
        L.append(f"   {r['classe']} {r['elemento_id']}: {r['pavimentos']} pavimentos")
    L.append("")
    v = rel["vinculo_recorte_ficha"]
    L.append("-- Vinculo recorte -> ficha via pavimento normalizado --")
    L.append(f"   recortes           : {v['recortes']}")
    L.append(f"   pavimento inferido : {v['pavimento_inferido']} ({v['pct_pavimento_inferido']}%)")
    L.append(f"   vinculo resolvido  : {v['vinculo_resolvido']} ({v['pct_vinculo_resolvido']}%)")
    if v["sem_ficha_amostra"]:
        L.append(f"   sem ficha no par (amostra de {len(v['sem_ficha_amostra'])}):")
        for r in v["sem_ficha_amostra"][:6]:
            L.append(f"     {r['classe']:4} {r['pavimento']:10} {r['elemento_id']}")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=DB_PADRAO)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:  # pragma: no cover - console exotico
        pass

    rel = coletar(args.db)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rel, ensure_ascii=False, indent=2) if args.json else render(rel))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
