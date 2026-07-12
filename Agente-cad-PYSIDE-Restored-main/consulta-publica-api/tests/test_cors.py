"""Testes de CORS travado (STORY-04, AC 3, 4)."""

from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path

import httpx
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import load_settings  # noqa: E402
from main import create_app  # noqa: E402

_ALLOWED_ORIGIN = "https://consulta.suaempresa.app"


@pytest.fixture
def public_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "public_consulta_cors.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def app(public_db: Path, tmp_path: Path):
    settings = load_settings(
        public_consulta_db_path=public_db,
        audit_log_path=tmp_path / "public_audit.log",
        allowed_origin=_ALLOWED_ORIGIN,
    )
    return create_app(settings)


def test_cors_origem_permitida_recebe_header_exato(app):
    """AC 3 — Access-Control-Allow-Origin é exatamente o domínio configurado,
    nunca '*'."""
    transport = httpx.ASGITransport(app=app)

    async def _run():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(
                "/api/v1/health", headers={"Origin": _ALLOWED_ORIGIN}
            )

    resp = asyncio.run(_run())
    assert resp.headers.get("access-control-allow-origin") == _ALLOWED_ORIGIN
    assert resp.headers.get("access-control-allow-origin") != "*"


def test_cors_preflight_origem_nao_autorizada_sem_header(app):
    """AC 4 — preflight OPTIONS de origem diferente não recebe
    Access-Control-Allow-Origin correspondente."""
    transport = httpx.ASGITransport(app=app)

    async def _run():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.options(
                "/api/v1/health",
                headers={
                    "Origin": "https://site-hostil.exemplo.com",
                    "Access-Control-Request-Method": "GET",
                },
            )

    resp = asyncio.run(_run())
    allow_origin = resp.headers.get("access-control-allow-origin")
    assert allow_origin != "https://site-hostil.exemplo.com"
    assert allow_origin is None or allow_origin == _ALLOWED_ORIGIN
