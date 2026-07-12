"""Testes de rate limiting (STORY-04, AC 1, 6, 7)."""

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


@pytest.fixture
def public_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "public_consulta_rl.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, item_id, revoked) "
        "VALUES ('VALIDOCODE', 'item', 'obra-1', '/fake', 'P1', 0)"
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def audit_log(tmp_path: Path) -> Path:
    return tmp_path / "public_audit.log"


def _app(public_db: Path, audit_log: Path):
    settings = load_settings(public_consulta_db_path=public_db, audit_log_path=audit_log)
    return create_app(settings)


def test_rate_limit_60_ok_61a_bloqueada(public_db: Path, audit_log: Path):
    """AC 1, 7 — primeiras 60 reqs/min OK, a 61ª recebe 429 determinístico."""
    app = _app(public_db, audit_log)
    transport = httpx.ASGITransport(app=app)

    async def _run():
        status_codes = []
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for _ in range(61):
                resp = await client.get("/api/v1/resolve/VALIDOCODE")
                status_codes.append(resp.status_code)
        return status_codes

    status_codes = asyncio.run(_run())
    assert status_codes[:60] == [200] * 60
    assert status_codes[60] == 429


def test_rate_limit_resposta_429_tem_retry_after(public_db: Path, audit_log: Path):
    app = _app(public_db, audit_log)
    transport = httpx.ASGITransport(app=app)

    async def _run():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for _ in range(60):
                await client.get("/api/v1/resolve/VALIDOCODE")
            return await client.get("/api/v1/resolve/VALIDOCODE")

    resp = asyncio.run(_run())
    assert resp.status_code == 429
    body = resp.json()
    assert body["erro"] == "muitas_tentativas"
    assert isinstance(body["retry_after_seconds"], int)
    assert body["retry_after_seconds"] > 0
    assert "Retry-After" in resp.headers


def test_health_isento_do_rate_limit_agressivo(public_db: Path, audit_log: Path):
    """AC 6 — /health não é afetado pelo limite de 60/min."""
    app = _app(public_db, audit_log)
    transport = httpx.ASGITransport(app=app)

    async def _run():
        status_codes = []
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for _ in range(100):
                resp = await client.get("/api/v1/health")
                status_codes.append(resp.status_code)
        return status_codes

    status_codes = asyncio.run(_run())
    assert status_codes == [200] * 100
