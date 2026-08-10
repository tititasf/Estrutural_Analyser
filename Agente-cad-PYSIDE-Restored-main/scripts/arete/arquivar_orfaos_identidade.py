#!/usr/bin/env python3
"""Arquiva linhas órfãs de pillars/beams/slabs — decisão do dono em 2026-07-30.

CONTEXTO. `projects` foi repovoada em 2026-07-10 (32 linhas, todas da obra de
teste do Drive) e deixou ~17.9k linhas de N1 apontando para `project_id`
inexistente. Medido antes de decidir (`qa_identity_integrity.py`):

  - is_validated=0 e validated_fields_json VAZIO em 100% das órfãs
    -> nenhum trabalho humano é arquivado
  - zero fichas de `reverse_eng_fichas` referenciam project_id órfão
    -> desconectadas do caminho N2/Arete em uso
  - carregam geometria de motor, regenerável a partir do DXF

POR QUE TABELA NOVA E NÃO `*_backup_legacy`. As tabelas `_backup_legacy` que já
existem são MAIS ESTREITAS que as vivas (`beams_backup_legacy` tem 5 colunas
contra 19 em `beams`). Mover para lá descartaria 14 colunas, inclusive a
geometria — o oposto de arquivar. Este script cria `<tabela>_orfaos_<data>` com
o schema COMPLETO, via `CREATE TABLE ... AS SELECT *`.

SEGURANÇA. Dry-run é o padrão; `--executar` é explícito. Só apaga da tabela viva
depois de conferir que a cópia tem exatamente a mesma contagem. Faça backup do
.vision antes (o script exige `--backup-confirmado`).

Uso:
    python scripts/arete/arquivar_orfaos_identidade.py                 # dry-run
    python scripts/arete/arquivar_orfaos_identidade.py --executar --backup-confirmado
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date

DB_PADRAO = "D:/Agente-cad-PYSIDE/project_data.vision"
TABELAS = ("pillars", "beams", "slabs")

# Linha órfã = project_id que não existe em projects. NULL também é órfão:
# sem projeto, a linha não é alcançável por nenhum caminho da app.
_ONDE_ORFA = (
    "project_id IS NULL OR project_id NOT IN (SELECT id FROM projects)"
)


def _contar(con: sqlite3.Connection, tabela: str) -> tuple[int, int]:
    total = con.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]
    orfas = con.execute(
        f'SELECT COUNT(*) FROM "{tabela}" WHERE {_ONDE_ORFA}'
    ).fetchone()[0]
    return total, orfas


def _condicao_humana(con: sqlite3.Connection, tabela: str) -> str | None:
    """SQL que identifica linha com marca de validação humana, ou None."""
    colunas = {r[1] for r in con.execute(f'PRAGMA table_info("{tabela}")')}
    condicoes = []
    if "is_validated" in colunas:
        condicoes.append("is_validated = 1")
    if "validated_fields_json" in colunas:
        condicoes.append(
            "(validated_fields_json IS NOT NULL AND "
            "TRIM(validated_fields_json) NOT IN ('', '[]', '{}', 'null'))"
        )
    return " OR ".join(condicoes) if condicoes else None


def _onde_arquivar(con: sqlite3.Connection, tabela: str) -> str:
    """Órfã E sem marca humana.

    A decisão do dono partiu de "nenhum trabalho humano é perdido". Em vez de
    abortar a tabela inteira quando aparece uma linha marcada, o script RETÉM
    essa linha na tabela viva e a reporta — arquivar o resto continua correto,
    e a exceção fica visível em vez de virar bloqueio silencioso.
    """
    humana = _condicao_humana(con, tabela)
    if not humana:
        return _ONDE_ORFA
    return f"({_ONDE_ORFA}) AND NOT ({humana})"


def _retidas(con: sqlite3.Connection, tabela: str) -> list[tuple]:
    """Órfãs com marca humana que ficam na tabela viva (para o dono revisar)."""
    humana = _condicao_humana(con, tabela)
    if not humana:
        return []
    return con.execute(
        f'SELECT id, project_id FROM "{tabela}" '
        f"WHERE ({_ONDE_ORFA}) AND ({humana}) LIMIT 20"
    ).fetchall()


def executar(db_path: str, *, aplicar: bool, sufixo: str) -> int:
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    problemas = 0
    try:
        print(f"DB: {db_path}")
        print(f"Modo: {'EXECUTAR (escreve)' if aplicar else 'DRY-RUN (nao escreve)'}")
        print()
        for tabela in TABELAS:
            total, orfas = _contar(con, tabela)
            onde = _onde_arquivar(con, tabela)
            a_arquivar = con.execute(
                f'SELECT COUNT(*) FROM "{tabela}" WHERE {onde}'
            ).fetchone()[0]
            retidas = _retidas(con, tabela)
            alvo = f"{tabela}_orfaos_{sufixo}"
            colunas = len(con.execute(f'PRAGMA table_info("{tabela}")').fetchall())

            print(f"-- {tabela}")
            print(f"   linhas={total}  orfas={orfas}  a arquivar={a_arquivar}  ficam={total - a_arquivar}")
            if retidas:
                print(f"   RETIDAS (orfas com marca humana, NAO arquivadas): {len(retidas)}")
                for ident, projeto in retidas:
                    print(f"     id={ident!r} project_id={projeto!r}")
            if not a_arquivar:
                print("   nada a arquivar.")
                continue
            print(f"   destino: {alvo} (schema completo, {colunas} colunas)")
            if not aplicar:
                continue

            with con:  # transação: cópia + verificação + delete, tudo ou nada
                con.execute(f'DROP TABLE IF EXISTS "{alvo}"')
                con.execute(
                    f'CREATE TABLE "{alvo}" AS SELECT * FROM "{tabela}" WHERE {onde}'
                )
                copiadas = con.execute(f'SELECT COUNT(*) FROM "{alvo}"').fetchone()[0]
                if copiadas != a_arquivar:
                    raise RuntimeError(
                        f"copia incompleta em {alvo}: {copiadas} != {a_arquivar} — rollback"
                    )
                con.execute(f'DELETE FROM "{tabela}" WHERE {onde}')
                restante = con.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]
                if restante != total - a_arquivar:
                    raise RuntimeError(
                        f"delete inesperado em {tabela}: {restante} != {total - a_arquivar} — rollback"
                    )
            print(f"   OK: {copiadas} arquivadas, {restante} mantidas.")
        return problemas
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=DB_PADRAO)
    parser.add_argument("--executar", action="store_true",
                        help="escreve de fato; sem isto e' dry-run")
    parser.add_argument("--backup-confirmado", action="store_true",
                        help="confirma que ha backup do .vision")
    parser.add_argument("--sufixo", default=date.today().strftime("%Y%m%d"))
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:  # pragma: no cover
        pass

    if args.executar and not args.backup_confirmado:
        print("RECUSADO: --executar exige --backup-confirmado.", file=sys.stderr)
        return 2
    return 1 if executar(args.db, aplicar=args.executar, sufixo=args.sufixo) else 0


if __name__ == "__main__":
    raise SystemExit(main())
