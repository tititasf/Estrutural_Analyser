"""Conexão READ-ONLY a `public_consulta.db` (STORY-02, AC 3).

Único módulo de banco da API pública. Abre exclusivamente em `mode=ro` via URI
SQLite — qualquer INSERT/UPDATE/DELETE tentado através desta conexão falha com
`sqlite3.OperationalError` ("attempt to write a readonly database"), garantia
estrutural comprovada em teste (`tests/test_connection.py`), não apenas
convenção de code review.

Este módulo NUNCA importa nada de `portal/` — é o próprio critério estrutural
da STORY-02 (AC 4), comprovado por `tests/test_isolation.py`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def get_ro_connection(db_path: Path | str) -> sqlite3.Connection:
    """Abre `public_consulta.db` em modo somente-leitura. Levanta
    `sqlite3.OperationalError` se o arquivo não existir (nunca cria — só o
    Publisher, em `consulta-publica-api/publisher/db.py`, tem permissão de
    escrita/criação)."""
    db_path = Path(db_path)
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn
