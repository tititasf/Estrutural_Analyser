"""AC2 — 1000 códigos aleatórios inexistentes: 100% recebem 404 IDÊNTICO
(ou 429 do rate-limit, que deve de fato disparar), ZERO vazamento (nunca um
200/500 inesperado). Consolida e formaliza `tests/test_resolve_timing.py::
test_enumeracao_simulada_1000_codigos_aleatorios` (STORY-03/04) com as 3
garantias explícitas do AC, num único app compartilhado (necessário para o
rate-limit em memória acumular estado entre requisições — `requisitar()`
do conftest cria 1 app novo por chamada, de propósito inadequado aqui)."""

from __future__ import annotations

import asyncio
import secrets
import string

import httpx

from config import load_settings
from main import create_app

_ALPHABET = string.digits + string.ascii_uppercase + string.ascii_lowercase


def _random_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(10))


def test_enumeracao_1000_codigos_100_por_cento_404_ou_429_rate_limit_dispara_zero_vazamento(duas_obras):
    db_path, raiz, codigos = duas_obras
    settings = load_settings(public_consulta_db_path=db_path, dados_obras_root=raiz)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    # Garante que nenhum dos 1000 códigos aleatórios colide por acidente
    # com um código real publicado no fixture (probabilidade desprezível,
    # mas checado para tornar o teste determinístico).
    codigos_reais = set(codigos.values())

    async def _run():
        resultados = []
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for _ in range(1000):
                code = _random_code()
                while code in codigos_reais:
                    code = _random_code()
                resp = await client.get(f"/api/v1/resolve/{code}")
                resultados.append((resp.status_code, resp.text))
        return resultados

    resultados = asyncio.run(_run())
    status_codes = {status for status, _ in resultados}

    # 1. Zero vazamento — nunca um 200 (falso-positivo de resolução) nem
    #    um 500 (erro não tratado que poderia vazar stack trace).
    assert 200 not in status_codes
    assert 500 not in status_codes
    assert status_codes <= {404, 429}

    # 2. O rate-limit REALMENTE dispara sob essa carga (não é só permitido
    #    como possibilidade — a AC exige que ele dispare de fato).
    assert 429 in status_codes, "Rate-limit não disparou em 1000 requisições rápidas"

    # 3. Toda resposta 404 é IDÊNTICA — mesmo corpo, sem vazar nenhuma
    #    diferenciação entre os 1000 códigos distintos testados.
    corpos_404 = {texto for status, texto in resultados if status == 404}
    assert len(corpos_404) == 1, f"Respostas 404 divergentes encontradas: {corpos_404}"
    assert corpos_404 == {'{"erro":"nao_encontrado"}'}
