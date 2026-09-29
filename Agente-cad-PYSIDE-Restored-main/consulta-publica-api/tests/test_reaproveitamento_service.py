"""Regras de reaproveitamento entre pavimentos (D-70..D-73, MATERIAIS §12)."""
from services.reaproveitamento_service import alocar_pavimento, chave_item, encaixe, numero_pavimento


def _p(pid, w, h, *, item="V301", pontas=(False, False), tipo="sarrafeado", reap=True):
    return {"id": pid, "numero": 1, "grupo": "G", "item": item, "chave": chave_item(item), "titulo": item,
            "largura_cm": w, "altura_cm": h, "partes": None, "pontas": list(pontas), "tipo": tipo,
            "reaproveitavel": reap, "sarrafos": [], "montagem": []}


def test_chave_item_troca_digito_do_pavimento():
    assert chave_item("V309A.PARA") == chave_item("V409A.PARA") == "V09A.PARA"
    assert chave_item("L319") == chave_item("L419")
    assert chave_item("P10.PARA") == "P10.PARA"
    assert numero_pavimento("TERREO") == 0 and numero_pavimento("14_PAV") == 14


def test_lateral_comprimento_igual_pontas_iguais_corta_embaixo():
    dst = _p("d", 244, 55, pontas=(True, False))
    assert encaixe("viga_lateral", _p("s", 244, 55, pontas=(True, False)), dst, False)
    assert encaixe("viga_lateral", _p("s", 250, 55, pontas=(True, False)), dst, True) is None  # mais comprido
    assert encaixe("viga_lateral", _p("s", 244, 60, pontas=(False, True)), dst, True) is None  # ponta errada
    assert encaixe("viga_lateral", _p("s", 244, 60, pontas=(True, False), tipo="gradeado"), dst, True) is None
    corte = encaixe("viga_lateral", _p("s", 244, 60, pontas=(True, False)), dst, True)
    assert "embaixo" in corte["corte"] and corte["retalhos"] == [(244, 4.0)]
    assert encaixe("viga_lateral", _p("s", 244, 50, pontas=(True, False)), dst, True) is None  # mais baixo


def test_pilar_so_altura_corta_em_cima():
    dst = _p("d", 82, 75, item="P10")
    assert "em cima" in encaixe("pilar", _p("s", 82, 122, item="P10"), dst, True)["corte"]
    assert encaixe("pilar", _p("s", 90, 122, item="P10"), dst, True) is None


def test_fundo_so_comprimento_e_ponta_cortada_fica_sem_sarrafo():
    src = _p("s", 244, 19, pontas=(True, True))
    assert encaixe("viga_fundo", src, _p("d", 200, 19, pontas=(True, False)), True)["corte"].endswith("direita")
    assert encaixe("viga_fundo", src, _p("d", 200, 19, pontas=(True, True)), True) is None
    assert encaixe("viga_fundo", src, _p("d", 200, 15, pontas=(True, False)), True) is None  # largura


def test_laje_qualquer_direcao_e_tira_nao_volta():
    assert encaixe("laje", _p("s", 122, 244), _p("d", 244, 36), True)
    assert encaixe("laje", _p("s", 122, 244, reap=False), _p("d", 100, 36), True) is None


def test_etapas_proprio_item_antes_dos_outros_e_novo_so_o_que_falta():
    itens = [{"code": c, "item": n, "chave": chave_item(n), "titulo": n, "tipo": "pilar",
              "paineis": [_p(f"{n}-P01", 82, 122, item=n)],
              "grupos": [{"titulo": "G", "disponivel": True, "sarrafos": [],
                          "paineis": [{"id": f"{n}-P01", "numero": 1, "largura_cm": 82, "altura_cm": 122,
                                       "sarrafos": []}]}]}
             for c, n in (("a", "P1"), ("b", "P2"), ("c", "P3"))]
    anterior = {"montados": [_p("13-P2-P01", 82, 122, item="P2"), _p("13-P9-P01", 82, 130, item="P9")],
                "chapas": [], "barras": []}
    r = alocar_pavimento("pilar", itens, anterior, {"montados": [], "chapas": [], "barras": []})
    a = r["alocacao"]
    # P2 pega o próprio mesmo sendo o segundo da lista; P1 recebe o do P9 cortado; P3 compra.
    assert a["P2-P01"]["etapa"] == "1" and a["P2-P01"]["fonte_id"] == "13-P2-P01"
    assert a["P1-P01"]["etapa"] == "2.5" and a["P1-P01"]["fonte_id"] == "13-P9-P01"
    assert a["P3-P01"]["etapa"] == "novo"
    assert r["compras"]["c"]["chapas"] and not r["compras"]["a"].get("chapas")
