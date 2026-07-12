"""Testes de isolamento estrutural da API pública (STORY-02, AC 4, AC 5).

Estes testes alimentam diretamente a suíte de segurança da STORY-15 — devem
continuar existindo e passando em todo commit futuro, não são descartáveis.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_FORBIDDEN_IMPORTS = (
    "portal.app.auth",
    "portal.app.access",
    "portal.app.repository",
    "portal.db.connection",
)

_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+([\w.]+)", re.MULTILINE
)


def _python_files_under_consulta_publica():
    """Todo .py sob consulta-publica-api/, exceto este próprio arquivo de
    teste (que cita os módulos proibidos como STRINGS de comparação, não
    como import de verdade — não pode se auto-flagar)."""
    self_path = Path(__file__).resolve()
    for path in _PROJECT_ROOT.rglob("*.py"):
        if path.resolve() == self_path:
            continue
        yield path


def test_no_forbidden_imports():
    """AC 4 — nenhum arquivo da API pública importa auth/access/repository/
    connection do portal interno."""
    violacoes: list[str] = []
    for path in _python_files_under_consulta_publica():
        texto = path.read_text(encoding="utf-8", errors="replace")
        for match in _IMPORT_RE.finditer(texto):
            modulo = match.group(1)
            for proibido in _FORBIDDEN_IMPORTS:
                if modulo == proibido or modulo.startswith(proibido + "."):
                    violacoes.append(f"{path.relative_to(_PROJECT_ROOT)}: import {modulo}")
    assert not violacoes, "Imports proibidos encontrados:\n" + "\n".join(violacoes)


def test_no_write_verbs_registered():
    """AC 5 — nenhuma rota registrada aceita POST/PUT/DELETE/PATCH."""
    from main import app

    proibidos = {"POST", "PUT", "DELETE", "PATCH"}
    violacoes = []
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        achados = methods & proibidos
        if achados:
            violacoes.append(f"{getattr(route, 'path', route)}: {achados}")
    assert not violacoes, "Rotas com verbo de escrita registradas:\n" + "\n".join(violacoes)


def test_post_health_retorna_405():
    """AC 5 — comprovação end-to-end via requisição HTTP real, não só
    introspecção. `httpx.ASGITransport` usado em vez de
    `starlette.testclient.TestClient` (incompatível com httpx>=0.28 deste
    ambiente — ver test_health.py)."""
    import asyncio

    import httpx
    from main import app

    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/v1/health")

    resp = asyncio.run(_run())
    assert resp.status_code == 405
