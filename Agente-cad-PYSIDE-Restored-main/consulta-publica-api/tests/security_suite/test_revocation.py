"""AC8 — item/obra revogado (`revoked=1`) responde EXATAMENTE como "nunca
existiu" em todo endpoint — nenhuma diferença observável de comportamento,
timing, ou corpo de resposta entre revogado e inexistente."""

from __future__ import annotations

from conftest import requisitar


def test_item_revogado_retorna_404_identico_a_inexistente_em_resolve(duas_obras):
    db_path, raiz, codigos = duas_obras

    resp_revogado = requisitar(db_path, raiz, "GET", f"/api/v1/resolve/{codigos['revogado']}")
    resp_inexistente = requisitar(db_path, raiz, "GET", "/api/v1/resolve/NAOEXISTE01")

    assert resp_revogado.status_code == resp_inexistente.status_code == 404
    assert resp_revogado.json() == resp_inexistente.json() == {"erro": "nao_encontrado"}


def test_item_revogado_retorna_404_identico_em_ficha(duas_obras):
    db_path, raiz, codigos = duas_obras

    resp_revogado = requisitar(db_path, raiz, "GET", f"/api/v1/ficha/{codigos['revogado']}")
    resp_inexistente = requisitar(db_path, raiz, "GET", "/api/v1/ficha/NAOEXISTE02")

    assert resp_revogado.status_code == resp_inexistente.status_code == 404
    assert resp_revogado.json() == resp_inexistente.json()


def test_item_revogado_retorna_404_identico_em_svg(duas_obras):
    db_path, raiz, codigos = duas_obras

    resp_revogado = requisitar(db_path, raiz, "GET", f"/api/v1/ficha/{codigos['revogado']}/svg/n1")
    resp_inexistente = requisitar(db_path, raiz, "GET", "/api/v1/ficha/NAOEXISTE03/svg/n1")

    assert resp_revogado.status_code == resp_inexistente.status_code == 404
    assert resp_revogado.json() == resp_inexistente.json()


def test_obra_revogada_retorna_404_identico_em_obra_index(duas_obras):
    """Revoga a obra A inteira (simulando `publisher.publish.revogar`) e
    confirma que `/obra/{code}` passa a se comportar como inexistente."""
    import sqlite3

    db_path, raiz, codigos = duas_obras
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE public_codes SET revoked = 1 WHERE code = ?", (codigos["obra_a"],))
    conn.commit()
    conn.close()

    resp_revogada = requisitar(db_path, raiz, "GET", f"/api/v1/obra/{codigos['obra_a']}")
    resp_inexistente = requisitar(db_path, raiz, "GET", "/api/v1/obra/NAOEXISTE04")

    assert resp_revogada.status_code == resp_inexistente.status_code == 404
    assert resp_revogada.json() == resp_inexistente.json()


def test_revogar_um_item_nao_afeta_outros_itens_da_mesma_obra(duas_obras):
    """Efeito colateral indevido seria um bug grave — revogar 1 item nunca
    pode derrubar acesso a itens irmãos ativos da mesma obra."""
    db_path, raiz, codigos = duas_obras

    resp_pilar_ativo = requisitar(db_path, raiz, "GET", f"/api/v1/ficha/{codigos['pilar_a']}")
    assert resp_pilar_ativo.status_code == 200

    resp_revogado = requisitar(db_path, raiz, "GET", f"/api/v1/ficha/{codigos['revogado']}")
    assert resp_revogado.status_code == 404
