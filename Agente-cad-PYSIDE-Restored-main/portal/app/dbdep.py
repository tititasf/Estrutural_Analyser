"""Dependencia FastAPI: conexao SQLite por request.

[FIX 2026-07-05] main.py guardava UMA conexao sqlite3 em app.state.db, aberta na
thread do lifespan, e todos os routers + auth.exige_login reusavam esse mesmo
objeto. FastAPI roda handlers sincronos em threads do threadpool (uma por
request) e sqlite3.Connection recusa uso fora da thread onde foi criada
(`sqlite3.ProgrammingError: SQLite objects created in a thread can only be
used in that same thread`) — confirmado rodando o servidor de verdade (POST
/login quebrava com 500 nesse erro). Corrigido abrindo uma conexao NOVA por
request via este Depends, fechada no fim da request. `get_connection()' e'
barata (SQLite + WAL ja habilitado por connection.py), entao o custo por
request e' desprezivel para 3-5 usuarios concorrentes.
"""

from __future__ import annotations

import sqlite3
from typing import Iterator

from fastapi import Request

from ..db import connection as db_conn


def get_db_conn(request: Request) -> Iterator[sqlite3.Connection]:
    settings = request.app.state.settings
    conn = db_conn.get_connection(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()
