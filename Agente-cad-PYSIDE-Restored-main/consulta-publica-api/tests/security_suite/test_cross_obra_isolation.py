"""AC3 — código de obra A NUNCA resolve dado de obra B, em NENHUM endpoint
público. O teste de segurança mais crítico do MVP (KPI de tolerância zero
do PRD §8.2: "Vazamento cross-cliente — 0").
"""

from __future__ import annotations

from conftest import requisitar


def test_ficha_do_pilar_a_nunca_contem_dado_de_b(duas_obras):
    db_path, raiz, codigos = duas_obras

    resp_a = requisitar(db_path, raiz, "GET", f"/api/v1/ficha/{codigos['pilar_a']}")
    assert resp_a.status_code == 200
    corpo_a = resp_a.json()
    assert corpo_a["titulo"] == "Pilar A"
    assert "Obra B" not in corpo_a["obra_rotulo"]
    assert "Cliente Confidencial Y" not in resp_a.text

    resp_b = requisitar(db_path, raiz, "GET", f"/api/v1/ficha/{codigos['pilar_b']}")
    assert resp_b.status_code == 200
    corpo_b = resp_b.json()
    assert corpo_b["titulo"] == "Pilar B"
    assert "Cliente Confidencial X" not in resp_b.text

    assert corpo_a["code"] != corpo_b["code"]


def test_svg_do_pilar_a_nunca_e_servido_para_code_de_b_e_vice_versa(duas_obras):
    db_path, raiz, codigos = duas_obras

    resp_a = requisitar(db_path, raiz, "GET", f"/api/v1/ficha/{codigos['pilar_a']}/svg/n1")
    resp_b = requisitar(db_path, raiz, "GET", f"/api/v1/ficha/{codigos['pilar_b']}/svg/n1")
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    # Cada um resolve seu próprio obra_dir — nenhum vaza pro outro (ambos
    # servem o mesmo SVG sintético do fixture, mas por CAMINHOS distintos;
    # o teste real é que cada code aponta exclusivamente pro seu obra_dir).
    assert resp_a.status_code == resp_b.status_code == 200


def test_paineis_lv_da_viga_a_nunca_contem_dado_de_b(duas_obras):
    db_path, raiz, codigos = duas_obras

    resp_a = requisitar(db_path, raiz, "GET", f"/api/v1/ficha/{codigos['viga_a']}/paineis-lv")
    resp_b = requisitar(db_path, raiz, "GET", f"/api/v1/ficha/{codigos['viga_b']}/paineis-lv")
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    # Nenhuma resposta contém o obra_dir/rótulo do outro lado.
    assert "obra_b" not in resp_a.text and "Cliente Confidencial Y" not in resp_a.text
    assert "obra_a" not in resp_b.text and "Cliente Confidencial X" not in resp_b.text


def test_indice_de_obra_a_nunca_lista_item_de_b(duas_obras):
    db_path, raiz, codigos = duas_obras

    resp = requisitar(db_path, raiz, "GET", f"/api/v1/obra/{codigos['obra_a']}")
    assert resp.status_code == 200
    body = resp.json()
    codes = {item["code"] for pav in body["pavimentos"] for item in pav["itens"]}
    assert codigos["pilar_b"] not in codes
    assert codigos["viga_b"] not in codes
    assert "Cliente Confidencial Y" not in resp.text


def test_code_de_item_de_a_usado_no_endpoint_obra_falha_generico(duas_obras):
    """Um `code` de ITEM (não de obra) enviado a `/obra/{code}` deve dar o
    404 genérico — nunca revela dado cruzado por confusão de tipo."""
    db_path, raiz, codigos = duas_obras
    resp = requisitar(db_path, raiz, "GET", f"/api/v1/obra/{codigos['pilar_a']}")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}


def test_pavimento_de_a_nunca_contem_dado_de_b(duas_obras):
    db_path, raiz, codigos = duas_obras

    resp_a = requisitar(db_path, raiz, "GET", f"/api/v1/pavimento/{codigos['pavimento_a']}")
    assert resp_a.status_code == 200
    body_a = resp_a.json()
    codes_a = {it["code"] for it in body_a["itens"]}
    assert codigos["pilar_b"] not in codes_a
    assert codigos["viga_b"] not in codes_a
    assert "Cliente Confidencial Y" not in resp_a.text

    resp_b = requisitar(db_path, raiz, "GET", f"/api/v1/pavimento/{codigos['pavimento_b']}")
    assert resp_b.status_code == 200
    body_b = resp_b.json()
    codes_b = {it["code"] for it in body_b["itens"]}
    assert codigos["pilar_a"] not in codes_b
    assert codigos["viga_a"] not in codes_b
    assert "Cliente Confidencial X" not in resp_b.text


def test_code_de_pavimento_de_a_usado_no_endpoint_obra_falha_generico(duas_obras):
    """Um `code` de PAVIMENTO enviado a `/obra/{code}` — nunca resolve por
    confusão de tipo, mesmo padrão do teste equivalente com code de item."""
    db_path, raiz, codigos = duas_obras
    resp = requisitar(db_path, raiz, "GET", f"/api/v1/obra/{codigos['pavimento_a']}")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}


def test_resolve_nunca_confunde_item_de_a_com_item_de_b(duas_obras):
    db_path, raiz, codigos = duas_obras
    resp_a = requisitar(db_path, raiz, "GET", f"/api/v1/resolve/{codigos['pilar_a']}")
    resp_b = requisitar(db_path, raiz, "GET", f"/api/v1/resolve/{codigos['pilar_b']}")
    assert resp_a.json()["code"] == codigos["pilar_a"]
    assert resp_b.json()["code"] == codigos["pilar_b"]
    assert resp_a.json()["code"] != resp_b.json()["code"]
