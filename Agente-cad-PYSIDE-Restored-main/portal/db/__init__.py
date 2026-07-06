"""Camada de dados do portal (portal_data.db) — HANDOFF-DATAENGINEER-PORTAL.md.

Banco SQLite fisicamente separado de project_data.vision (regra de fronteira §3).
"""

from .connection import DEFAULT_DB_PATH, get_connection, init_db, migrate

__all__ = ["get_connection", "init_db", "migrate", "DEFAULT_DB_PATH"]
