"""Conexão e inicialização de `public_consulta.db` (STORY-01).

Único módulo do projeto autorizado a ABRIR este arquivo em modo leitura+escrita
(o Publisher). A API pública (fora do escopo desta story) só abre em mode=ro.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

DEFAULT_DB_PATH = Path("D:/Agente-cad-PYSIDE/public_consulta.db")


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Abre (criando se necessário) `public_consulta.db` em modo leitura+escrita.

    Só o Publisher deve chamar esta função — a API pública usa uma conexão
    somente-leitura própria (STORY-02), nunca esta."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def assert_no_blacklisted_columns(conn: sqlite3.Connection) -> None:
    """Falha ruidosamente se `public_codes` ganhar alguma coluna proibida —
    usado pelo teste de schema (AC 2) e como salvaguarda em runtime."""
    blacklist = {
        "cliente", "criterios_cliente", "data_solicitacao", "data_entrega",
        "observacoes", "membro_id", "login", "nome", "email", "senha_hash",
        "descricao", "local_path",
    }
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(public_codes)")}
    leaked = columns & blacklist
    if leaked:
        raise AssertionError(
            f"public_codes contém coluna(s) da blacklist: {sorted(leaked)}"
        )
