"""Consulta (SÓ LEITURA) de `public_consulta.db` a partir do portal
[2026-07-12] — pedido do dono: mostrar o código público (obra/pavimento/
item) direto nas telas do portal, sem precisar de outra ferramenta.

Único módulo do portal autorizado a abrir `public_consulta.db` — sempre em
`mode=ro` (o Publisher, em `consulta-publica-api/publisher/db.py`, é quem
tem permissão de escrita). Falha graciosamente (retorna `None`) se o
arquivo ainda não existe ou a tabela ainda não foi criada — no MVP local
antes do 1º ciclo de auto-publicação isso é esperado, não um erro.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


def _conectar_ro(db_path: Path) -> Optional[sqlite3.Connection]:
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError:
        return None


def buscar_code_obra(db_path: Path, obra_id: str) -> Optional[str]:
    conn = _conectar_ro(db_path)
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT code FROM public_codes WHERE obra_id = ? AND kind = 'obra' AND revoked = 0",
            (obra_id,),
        ).fetchone()
        return row["code"] if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def buscar_code_pavimento(db_path: Path, obra_id: str, pavimento: str) -> Optional[str]:
    conn = _conectar_ro(db_path)
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT code FROM public_codes WHERE obra_id = ? AND pavimento = ? "
            "AND kind = 'pavimento' AND revoked = 0",
            (obra_id, pavimento),
        ).fetchone()
        return row["code"] if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def buscar_code_item(
    db_path: Path, obra_id: str, pavimento: str, classe: str, item_id: str,
) -> Optional[str]:
    conn = _conectar_ro(db_path)
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT code FROM public_codes WHERE obra_id = ? AND pavimento = ? AND classe = ? "
            "AND item_id = ? AND kind = 'item' AND revoked = 0",
            (obra_id, pavimento, classe, item_id),
        ).fetchone()
        return row["code"] if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
