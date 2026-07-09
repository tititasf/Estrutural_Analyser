"""Conexão e migrations do banco do portal (portal_data.db).

Regra de fronteira (HANDOFF §0/§3): este arquivo abre APENAS portal_data.db,
NUNCA project_data.vision. A separação física é proposital — um bug aqui jamais
pode segurar o lock nem corromper a curadoria Arete.

Config de conexão (HANDOFF §1):
- PRAGMA journal_mode=WAL   → N leitores + 1 escritor (web serve enquanto worker grava).
- PRAGMA foreign_keys=ON    → SQLite desliga FK por padrão; ligar por conexão.
- PRAGMA busy_timeout=5000  → espera o lock em vez de erro imediato.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# raiz do repo = pai de portal/db/ → portal/ → <repo>. portal_data.db fica na raiz do repo.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = _REPO_ROOT / "portal_data.db"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# Guarda absoluta contra reabrir o banco da curadoria em modo escrita (HANDOFF §3).
_ARETE_DB_NAME = "project_data.vision"


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Abre portal_data.db com os PRAGMAs do portal aplicados.

    db_path default = raiz do repo (portal_data.db). NUNCA project_data.vision.
    """
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    if path.name == _ARETE_DB_NAME:
        raise ValueError(
            "get_connection() nunca abre o banco da curadoria "
            f"({_ARETE_DB_NAME}) — regra de fronteira HANDOFF §3."
        )
    # [FIX 2026-07-07] check_same_thread=False: FastAPI resolve dependencias
    # `yield` sincronas e roda o corpo do endpoint em chamadas SEPARADAS de
    # run_in_threadpool — o anyio pode entregar threads DIFERENTES do pool pra
    # cada chamada dentro da MESMA request (nunca concorrentes entre si, so'
    # sequenciais: abre -> usa -> fecha). Sem essa flag, sqlite3 recusa com
    # "SQLite objects created in a thread can only be used in that same
    # thread" — confirmado ao vivo quando 3 fotos (bruto/limpo/detalhes) do
    # viewer de Recortes disparam requests concorrentes. Seguro aqui porque
    # cada request abre sua PRÓPRIA conexão (nunca compartilhada entre
    # requests), então não há acesso concorrente real ao mesmo objeto.
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _applied_version(conn: sqlite3.Connection) -> int:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS portal_schema_version(
            version INTEGER PRIMARY KEY,
            aplicada_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            descricao TEXT)"""
    )
    row = conn.execute(
        "SELECT COALESCE(MAX(version),0) FROM portal_schema_version"
    ).fetchone()
    return row[0]


def migrate(conn: sqlite3.Connection, migrations_dir: str | Path = MIGRATIONS_DIR) -> int:
    """Aplica migrations pendentes em ordem numérica. Idempotente (HANDOFF §6).

    Retorna a versão final do schema. Rodar 2x é seguro: versões já aplicadas
    são puladas e o DDL usa IF NOT EXISTS de qualquer forma.
    """
    migrations_dir = Path(migrations_dir)
    atual = _applied_version(conn)
    for path in sorted(migrations_dir.glob("*.sql")):
        ver = int(path.stem.split("_")[0])
        if ver <= atual:
            continue
        with conn:  # transação por migration
            conn.executescript(path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT OR IGNORE INTO portal_schema_version(version, descricao) VALUES(?,?)",
                (ver, path.stem),
            )
        atual = ver
    return atual


def init_db(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Abre o banco e roda as migrations pendentes. Idempotente.

    Retorna a conexão já migrada (o chamador é dono do ciclo de vida / close).
    """
    conn = get_connection(db_path)
    migrate(conn)
    return conn
