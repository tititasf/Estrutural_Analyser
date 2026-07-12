"""Testes do endpoint GET /api/v1/resolve/{code} (STORY-03, AC 1-6)."""

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
    db_path = tmp_path / "public_consulta_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, obra_rotulo, revoked) "
        "VALUES ('OBRA000001', 'obra', 'obra-1', '/fake/obra1', 'Obra Teste', 0)"
    )
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "('ITEM000001', 'item', 'obra-1', '/fake/obra1', 'TERREO', 'pilares', 'P1', 'pilar', 'P1', 0)"
    )
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "('REVOKED001', 'item', 'obra-1', '/fake/obra1', 'TERREO', 'pilares', 'P2', 'pilar', 'P2', 1)"
    )
    conn.commit()
    conn.close()
    return db_path


def _client(public_db: Path) -> httpx.AsyncClient:
    settings = load_settings(public_consulta_db_path=public_db)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _get(public_db: Path, path: str) -> httpx.Response:
    async def _run():
        async with _client(public_db) as client:
            return await client.get(path)

    return asyncio.run(_run())


def test_resolve_item_valido(public_db: Path):
    resp = _get(public_db, "/api/v1/resolve/ITEM000001")
    assert resp.status_code == 200
    assert resp.json() == {"kind": "item", "code": "ITEM000001"}
    assert resp.headers.get("cache-control") == "private, no-store"


def test_resolve_obra_valida(public_db: Path):
    resp = _get(public_db, "/api/v1/resolve/OBRA000001")
    assert resp.status_code == 200
    assert resp.json() == {"kind": "obra", "code": "OBRA000001"}


@pytest.mark.parametrize(
    "code",
    [
        "NAOEXISTE1",       # inexistente, mas formato plausível
        "x",                # malformado — comprimento errado (curto)
        "AAAAAAAAAAAAAAAA",  # malformado — comprimento errado (longo)
        "REVOKED001",       # existe mas revogado
        "",                 # vazio
    ],
)
def test_resolve_404_generico_para_todos_os_casos_negativos(public_db: Path, code: str):
    resp = _get(public_db, f"/api/v1/resolve/{code}" if code else "/api/v1/resolve/")
    if code == "":
        # path vazio nem bate na rota — FastAPI trata como 404 nativo do
        # roteador (comportamento aceitável, não é o "nao_encontrado" do
        # nosso handler, mas ainda assim nunca revela nada).
        assert resp.status_code == 404
        return
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}
    assert resp.headers.get("cache-control") == "private, no-store"


def test_resolve_trim_espacos(public_db: Path):
    """AC 5 — trim de espaços acidentais, mas sem alterar case."""
    resp = _get(public_db, "/api/v1/resolve/%20ITEM000001%20")
    assert resp.status_code == 200
    assert resp.json()["code"] == "ITEM000001"


def test_resolve_case_sensitive(public_db: Path):
    """AC 5 — base62 é case-sensitive, não normaliza."""
    resp = _get(public_db, "/api/v1/resolve/item000001")
    assert resp.status_code == 404
