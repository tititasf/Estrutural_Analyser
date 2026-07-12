"""AC5 — nenhuma resposta pública contém campo da blacklist comercial/
pessoal, em NENHUM endpoint que retorna JSON. Lista exata copiada de
`publisher/schema.sql` (comentário de topo) e architecture.md §5.4."""

from __future__ import annotations

from conftest import requisitar

_BLACKLIST = (
    "cliente", "criterios_cliente", "data_solicitacao", "data_entrega",
    "observacoes", "membro_id", "login", "nome", "email", "senha_hash",
    "descricao", "local_path",
)


def _assert_sem_blacklist(resp, contexto: str):
    corpo = resp.json()

    def _varrer(valor, caminho):
        if isinstance(valor, dict):
            for chave, sub in valor.items():
                assert chave not in _BLACKLIST, f"{contexto}: campo proibido '{chave}' em {caminho}"
                _varrer(sub, f"{caminho}.{chave}")
        elif isinstance(valor, list):
            for i, item in enumerate(valor):
                _varrer(item, f"{caminho}[{i}]")

    _varrer(corpo, "$")


def test_resolve_sem_campos_da_blacklist(duas_obras):
    db_path, raiz, codigos = duas_obras
    resp = requisitar(db_path, raiz, "GET", f"/api/v1/resolve/{codigos['pilar_a']}")
    _assert_sem_blacklist(resp, "/resolve")


def test_ficha_sem_campos_da_blacklist(duas_obras):
    db_path, raiz, codigos = duas_obras
    resp = requisitar(db_path, raiz, "GET", f"/api/v1/ficha/{codigos['pilar_a']}")
    _assert_sem_blacklist(resp, "/ficha")


def test_obra_sem_campos_da_blacklist(duas_obras):
    db_path, raiz, codigos = duas_obras
    resp = requisitar(db_path, raiz, "GET", f"/api/v1/obra/{codigos['obra_a']}")
    _assert_sem_blacklist(resp, "/obra")


def test_pavimento_sem_campos_da_blacklist(duas_obras):
    db_path, raiz, codigos = duas_obras
    resp = requisitar(db_path, raiz, "GET", f"/api/v1/pavimento/{codigos['pavimento_a']}")
    _assert_sem_blacklist(resp, "/pavimento")


def test_paineis_lv_sem_campos_da_blacklist(duas_obras):
    db_path, raiz, codigos = duas_obras
    resp = requisitar(db_path, raiz, "GET", f"/api/v1/ficha/{codigos['viga_a']}/paineis-lv")
    _assert_sem_blacklist(resp, "/paineis-lv")


def test_ficha_nunca_expoe_item_id_ou_pavimento_cru(duas_obras):
    """Reforço específico — `item_id`/`pavimento` internos não são
    blacklist per se, mas a Architecture exige que só os RÓTULOS públicos
    (`pavimento_label`) apareçam, nunca a chave interna crua."""
    db_path, raiz, codigos = duas_obras
    resp = requisitar(db_path, raiz, "GET", f"/api/v1/ficha/{codigos['pilar_a']}")
    corpo = resp.json()
    assert "item_id" not in corpo
    assert "pavimento" not in corpo
    assert "obra_dir" not in corpo
    assert "obra_id" not in corpo


def test_obra_nunca_expoe_item_id_ou_pavimento_cru(duas_obras):
    db_path, raiz, codigos = duas_obras
    resp = requisitar(db_path, raiz, "GET", f"/api/v1/obra/{codigos['obra_a']}")
    corpo = resp.json()
    for pav in corpo["pavimentos"]:
        for item in pav["itens"]:
            assert set(item.keys()) == {"code", "titulo", "tipo"}
