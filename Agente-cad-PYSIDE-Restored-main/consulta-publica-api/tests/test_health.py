"""Teste do endpoint /api/v1/health (STORY-02, AC 2)."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def test_health_returns_200_no_store():
    # `starlette.testclient.TestClient` é incompatível com httpx>=0.28
    # instalado neste ambiente (`Client.__init__() got an unexpected keyword
    # argument 'app'`) — usamos httpx.ASGITransport diretamente, API moderna
    # equivalente, sem downgrade de dependência compartilhada.
    import asyncio

    import httpx
    from main import app

    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/v1/health")

    resp = asyncio.run(_run())
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert resp.headers.get("cache-control") == "no-store"
