"""Testes do módulo de conexão read-only (STORY-02, AC 3)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from db.connection import get_ro_connection  # noqa: E402


@pytest.fixture
def db_with_schema(tmp_path: Path) -> Path:
    db_path = tmp_path / "public_consulta_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE public_codes (code TEXT PRIMARY KEY, kind TEXT)")
    conn.execute("INSERT INTO public_codes (code, kind) VALUES ('ABC1234567', 'obra')")
    conn.commit()
    conn.close()
    return db_path


def test_ro_connection_le_dados(db_with_schema: Path):
    conn = get_ro_connection(db_with_schema)
    try:
        row = conn.execute("SELECT code FROM public_codes").fetchone()
        assert row["code"] == "ABC1234567"
    finally:
        conn.close()


def test_ro_connection_rejects_write(db_with_schema: Path):
    """AC 3 — tentativa de escrita através desta conexão DEVE falhar."""
    conn = get_ro_connection(db_with_schema)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                "INSERT INTO public_codes (code, kind) VALUES ('ZZZ9999999', 'item')"
            )
    finally:
        conn.close()


def test_ro_connection_arquivo_inexistente_falha(tmp_path: Path):
    """Nunca cria o arquivo — só o Publisher tem permissão de escrita/criação.
    `mode=ro` falha já na abertura da conexão (mais estrito que exigido)."""
    inexistente = tmp_path / "nao_existe.db"
    with pytest.raises(sqlite3.OperationalError):
        get_ro_connection(inexistente)
    assert not inexistente.exists()
