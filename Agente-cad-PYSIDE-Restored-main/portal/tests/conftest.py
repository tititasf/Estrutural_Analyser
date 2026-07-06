"""Fixtures e config compartilhadas dos testes do portal.

Decisões de ambiente (confirmadas nesta máquina, 2026-07-05):
- `fastapi.testclient.TestClient` NÃO funciona: starlette 0.27.0 + httpx 0.28.1 têm
  incompatibilidade real (`TypeError: Client.__init__() got an unexpected keyword
  argument 'app'`). Os testes HTTP usam `httpx.ASGITransport` + `AsyncClient`.
- `pytest-asyncio` 1.3.0 está instalado. Como não há `[tool.pytest.ini_options]` no
  pyproject e nenhum `asyncio_mode`, cada teste async é decorado explicitamente com
  `@pytest.mark.asyncio` e o marker é registrado aqui (evita warning de marker
  desconhecido). Idem para o marker `slow`.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

# raiz do repo = portal/tests/ -> portal/ -> <repo>. Garante import de `portal.*` e
# `scripts.*` mesmo quando o pytest é invocado de outro cwd.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: teste async (pytest-asyncio)")
    config.addinivalue_line("markers", "slow: teste pesado (pipeline real / subprocess uvicorn)")


@pytest.fixture()
def db_path(tmp_path) -> Path:
    """Path de um portal_data.db temporário e isolado (nunca toca project_data.vision)."""
    return tmp_path / "portal_data.db"


@pytest.fixture()
def conn(db_path):
    """Conexão já migrada para o db temporário (mesmo padrão do test_repository.py)."""
    from portal.db import connection

    c = connection.init_db(db_path)
    yield c
    c.close()


@pytest.fixture()
def settings(tmp_path, db_path):
    """Settings de teste: db em tmp, poller off, dados/logs em tmp, STATUS.md inexistente.

    poll_enabled=False é o default de produção também — o loop do poller não sobe.

    [FIX 2026-07-06] drive_oauth_json/drive_sa_json APONTADOS PARA TMP (inexistentes)
    de propósito: esta máquina TEM uma credencial OAuth real do Drive em
    portal/.secrets/gdrive-oauth.json (reautorizada em 2026-07-06). Sem este
    isolamento, qualquer teste que chame montar_drive_client() cairia no Drive
    REAL em vez de FakeDriveClient — mesma classe de bug já corrigida uma vez em
    test_lifespan_com_poller_habilitado_cria_task, agora fechada na fonte (a
    fixture compartilhada) para nenhum teste futuro repetir o erro.
    """
    from portal.app.config import load_settings

    return load_settings(
        db_path=db_path,
        poll_enabled=False,
        dados_obras_dir=tmp_path / "DADOS-OBRAS",
        logs_dir=tmp_path / "logs",
        status_md_path=tmp_path / "STATUS.md",  # não existe -> tudo vira 'beta' (fail-safe)
        drive_oauth_json=tmp_path / "sem-credencial-oauth.json",
        drive_sa_json=tmp_path / "sem-credencial-sa.json",
    )


@pytest.fixture()
def membro_id(conn) -> str:
    """Membro genérico com pasta de Drive — motor geral, nada hardcoded a um usuário."""
    from portal.db import repository as repo

    return repo.criar_membro(
        conn, login="ana", nome="Ana Silva", senha_hash="hash-fake",
        drive_folder_id="folder-ana",
    )
