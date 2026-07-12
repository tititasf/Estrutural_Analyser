"""Testes de tempo constante e anti-enumeração do /resolve (STORY-03, AC 3, 7).

Reexecutado formalmente e com mais rigor na suíte de segurança (STORY-15) —
aqui garantimos que o endpoint já nasce correto.
"""

from __future__ import annotations

import asyncio
import secrets
import sqlite3
import statistics
import string
import sys
import time
from pathlib import Path

import httpx
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import load_settings  # noqa: E402
from main import create_app  # noqa: E402

_ALPHABET = string.digits + string.ascii_uppercase + string.ascii_lowercase


@pytest.fixture
def public_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "public_consulta_timing.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, item_id, revoked) "
        "VALUES ('VALIDOCODE', 'item', 'obra-1', '/fake', 'P1', 0)"
    )
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, item_id, revoked) "
        "VALUES ('REVOKEDCOD', 'item', 'obra-1', '/fake', 'P2', 1)"
    )
    conn.commit()
    conn.close()
    return db_path


def _random_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(10))


def test_timing_valido_vs_invalido_dentro_da_margem(public_db: Path):
    """AC 3 — tempo médio de resposta pra código válido vs inválido não deve
    divergir de forma grosseira (margem generosa: ambiente de teste tem
    ruído alto; o objetivo é pegar um timing oracle ÓBVIO, não medir
    precisão de nanosegundo — isso é papel da STORY-15 com ferramenta
    dedicada)."""
    settings = load_settings(public_consulta_db_path=public_db)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async def _medir(path: str, n: int) -> list[float]:
        tempos = []
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for _ in range(n):
                inicio = time.perf_counter()
                await client.get(path)
                tempos.append(time.perf_counter() - inicio)
        return tempos

    n = 30
    tempos_validos = asyncio.run(_medir("/api/v1/resolve/VALIDOCODE", n))
    tempos_invalidos = asyncio.run(_medir("/api/v1/resolve/NAOEXISTE1", n))

    media_valido = statistics.mean(tempos_validos)
    media_invalido = statistics.mean(tempos_invalidos)

    # Margem generosa (50ms) — ambiente de teste local, sem isolamento de
    # rede real. O objetivo é falhar só se houver um short-circuit óbvio
    # (ex.: early-return por regex antes do SQL), não medir side-channel real.
    assert abs(media_valido - media_invalido) < 0.05, (
        f"Diferença de timing suspeita: válido={media_valido:.4f}s "
        f"inválido={media_invalido:.4f}s"
    )


def test_enumeracao_simulada_1000_codigos_aleatorios(public_db: Path):
    """AC 7 — 1000 códigos aleatórios inexistentes → nunca um 200 (nenhum
    falso-positivo de resolução). Nota (pós-STORY-04): com rate limit +
    detecção de rajada de 404 ativos, uma rajada de 1000 reqs passa a
    receber 429 depois do limite — resultado esperado e desejado (defesa
    em profundidade), não uma regressão desta story. A suíte formal de
    segurança (STORY-15) valida rate limit isoladamente."""
    settings = load_settings(public_consulta_db_path=public_db)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async def _run():
        status_codes = set()
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for _ in range(1000):
                resp = await client.get(f"/api/v1/resolve/{_random_code()}")
                status_codes.add(resp.status_code)
        return status_codes

    status_codes = asyncio.run(_run())
    assert status_codes <= {404, 429}
    assert 200 not in status_codes
