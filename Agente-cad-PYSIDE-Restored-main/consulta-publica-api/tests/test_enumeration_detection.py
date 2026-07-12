"""Testes de detecção de rajada de enumeração + log de auditoria (STORY-04,
AC 2, 5)."""

from __future__ import annotations

import asyncio
import json
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
    db_path = tmp_path / "public_consulta_enum.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def audit_log(tmp_path: Path) -> Path:
    return tmp_path / "public_audit.log"


def _app(public_db: Path, audit_log: Path):
    settings = load_settings(public_consulta_db_path=public_db, audit_log_path=audit_log)
    return create_app(settings)


def test_rajada_de_404_dispara_bloqueio(public_db: Path, audit_log: Path):
    """AC 2 — mais de 20 404s em 60s bloqueia requisições subsequentes,
    mesmo antes de bater no limite geral de 60/min."""
    app = _app(public_db, audit_log)
    transport = httpx.ASGITransport(app=app)

    async def _run():
        status_codes = []
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for i in range(25):
                resp = await client.get(f"/api/v1/resolve/naoexiste{i:02d}")
                status_codes.append(resp.status_code)
        return status_codes

    status_codes = asyncio.run(_run())
    # As primeiras ~20 são 404 normais; depois do threshold, vira 429
    # (bloqueio por rajada), mesmo sem ter batido no limite de 60/min.
    assert 429 in status_codes
    assert status_codes.count(404) <= 21  # threshold é > 20


def test_rajada_de_404_registra_evento_de_auditoria(public_db: Path, audit_log: Path):
    """AC 2, 5 — evento 'enumeracao_detectada' vai pro log de auditoria,
    arquivo fisicamente distinto de public_consulta.db."""
    app = _app(public_db, audit_log)
    transport = httpx.ASGITransport(app=app)

    async def _run():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for i in range(25):
                await client.get(f"/api/v1/resolve/naoexiste{i:02d}")

    asyncio.run(_run())

    assert audit_log.exists()
    assert audit_log.resolve() != public_db.resolve()

    linhas = [json.loads(l) for l in audit_log.read_text(encoding="utf-8").splitlines() if l]
    tipos = {linha["tipo"] for linha in linhas}
    assert "enumeracao_detectada" in tipos
    assert "acesso" in tipos

    # Nenhuma linha de acesso grava o código em texto puro.
    acessos = [l for l in linhas if l["tipo"] == "acesso"]
    for acesso in acessos:
        assert "naoexiste" not in json.dumps(acesso)
        if acesso.get("code_hash"):
            assert len(acesso["code_hash"]) == 12
