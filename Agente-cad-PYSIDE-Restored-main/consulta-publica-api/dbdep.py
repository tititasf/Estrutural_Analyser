"""Dependência FastAPI: conexão read-only por request (mesma disciplina do
portal — `sqlite3.Connection` não pode atravessar threads; abre nova conexão
por request, fecha no fim)."""

from __future__ import annotations

import sqlite3
from typing import Iterator

from fastapi import HTTPException, Request

from db.connection import get_ro_connection


def get_ro_conn(request: Request) -> Iterator[sqlite3.Connection]:
    settings = request.app.state.settings
    try:
        conn = get_ro_connection(settings.public_consulta_db_path)
    except sqlite3.OperationalError:
        # `public_consulta.db` ainda não existe (nenhuma obra publicada ainda
        # pelo Publisher, STORY-01) — distinto de "code não encontrado"
        # (404): é o serviço inteiro que ainda não está pronto, não vaza
        # nenhuma informação por código.
        raise HTTPException(status_code=503, detail="servico_indisponivel")
    try:
        yield conn
    finally:
        conn.close()
