"""AC1 — POST/PUT/DELETE/PATCH em QUALQUER rota registrada -> 405, sem
exceção. Expande `tests/test_isolation.py::test_post_health_retorna_405`
(que só testava 1 rota) para TODAS as rotas reais do app, via requisição
HTTP de verdade (não introspecção)."""

from __future__ import annotations

from conftest import requisitar

_VERBOS_ESCRITA = ("POST", "PUT", "DELETE", "PATCH")


def _rotas_reais() -> list[str]:
    """Rotas de API reais (exclui /docs, /openapi.json, /redoc — não são
    endpoints de dado)."""
    from main import app

    rotas = []
    for route in app.routes:
        path = getattr(route, "path", None)
        if path and path.startswith("/api/v1"):
            rotas.append(path)
    return rotas


def test_todas_as_rotas_reais_existem_e_sao_testaveis():
    """Sanity — garante que a lista de rotas não está vazia (se ficar,
    os testes abaixo passariam vazios silenciosamente, mascarando um
    problema de configuração)."""
    assert len(_rotas_reais()) >= 5


def test_todos_verbos_de_escrita_retornam_405_em_todas_as_rotas(duas_obras):
    db_path, raiz, codigos = duas_obras

    rotas_concretas = [
        "/api/v1/health",
        f"/api/v1/resolve/{codigos['pilar_a']}",
        f"/api/v1/ficha/{codigos['pilar_a']}",
        f"/api/v1/ficha/{codigos['pilar_a']}/svg/n1",
        f"/api/v1/ficha/{codigos['viga_a']}/paineis-lv",
        f"/api/v1/obra/{codigos['obra_a']}",
        f"/api/v1/pavimento/{codigos['pavimento_a']}",
    ]

    violacoes = []
    for rota in rotas_concretas:
        for verbo in _VERBOS_ESCRITA:
            resp = requisitar(db_path, raiz, verbo, rota)
            if resp.status_code != 405:
                violacoes.append(f"{verbo} {rota} -> {resp.status_code} (esperado 405)")

    assert not violacoes, "Verbos de escrita aceitos:\n" + "\n".join(violacoes)
