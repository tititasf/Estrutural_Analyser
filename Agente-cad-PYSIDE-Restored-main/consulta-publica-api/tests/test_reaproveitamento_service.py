"""Regras de reaproveitamento entre pavimentos (D-70..D-73, MATERIAIS §12)."""
from pathlib import Path

from services import reaproveitamento_service as reap
from services.reaproveitamento_service import (alocar_pavimento, cenarios_da_classe, chave_item, encaixe,
                                                numero_pavimento, vazio)


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
    anterior = vazio(["pil"])
    anterior["montados"]["pil"] = [_p("13-P2-P01", 82, 122, item="P2"), _p("13-P9-P01", 82, 130, item="P9")]
    r = alocar_pavimento({"pil": itens}, anterior, vazio(["pil"]))
    a = r["alocacao"]
    # P2 pega o próprio mesmo sendo o segundo da lista; P1 recebe o do P9 cortado; P3 compra.
    assert a["P2-P01"]["etapa"] == "1" and a["P2-P01"]["fonte_id"] == "13-P2-P01"
    assert a["P1-P01"]["etapa"] == "2.5" and a["P1-P01"]["fonte_id"] == "13-P9-P01"
    assert a["P3-P01"]["etapa"] == "novo"
    assert r["compras"]["c"]["chapas"] and not r["compras"]["a"].get("chapas")


def _item(code, nome, tipo, w, h):
    return {"code": code, "item": nome, "chave": chave_item(nome), "titulo": nome, "tipo": tipo,
            "paineis": [_p(f"{nome}-P01", w, h, item=nome)],
            "grupos": [{"titulo": "G", "disponivel": True, "sarrafos": [],
                        "paineis": [{"id": f"{nome}-P01", "numero": 1, "largura_cm": w, "altura_cm": h,
                                     "sarrafos": []}]}]}


def test_sobra_limpa_circula_entre_classes_maior_painel_primeiro():
    """D-75: sobra limpa de chapa serve a qualquer classe; D-77: o maior painel
    pendente escolhe primeiro, sem ordem de classes; retalho de montado fica na classe."""
    classes = {"fundo": [_item("f", "V301", "viga_fundo", 100, 19)],
               "lajes": [_item("l", "L301", "laje", 120, 100)]}
    anterior = vazio(classes)
    anterior["limpas"] = [{"id": "S1", "tipo": "chapa", "material": "Compensado", "classe": "fundo",
                           "largura_cm": 122, "altura_cm": 110, "pavimento": "13_PAV"}]
    anterior["da_classe"]["fundo"] = [{"id": "13-X-R1", "tipo": "chapa", "largura_cm": 101, "altura_cm": 20}]
    a = alocar_pavimento(classes, anterior, vazio(classes))["alocacao"]
    assert a["L301-P01"]["etapa"] == "3.5" and a["L301-P01"]["fonte_id"] == "S1"  # laje usa sobra do fundo
    assert a["V301-P01"]["fonte_id"] == "13-X-R1"  # retalho de montado: só a própria classe


def test_cenarios_fundo_e_laje_nos_dois():
    assert cenarios_da_classe("pilares_n3_para") == ["para"]
    assert cenarios_da_classe("lateral_a_passa") == ["passa"]
    assert cenarios_da_classe("fundo") == cenarios_da_classe("lajes") == ["para", "passa"]


def test_tipo_repetido_alimenta_a_si_mesmo_e_o_proximo(monkeypatch):
    """O cadastro é único; cada concretagem usa o estoque da anterior."""
    pavimentos = [
        {"pavimento": "1_PAV", "tipo": None},
        {"pavimento": "TIPO", "tipo": {"de": 2, "ate": 4}},
        {"pavimento": "5_PAV", "tipo": None},
    ]
    monkeypatch.setattr(reap, "pavimentos_ordenados", lambda _obra: pavimentos)
    monkeypatch.setattr(reap, "classes_do_cenario", lambda *_: ["fundo"])
    chamadas = []

    def inventario(_conn, _obra, pav, _classe, _root):
        chamadas.append(pav)
        if pav == "1_PAV":
            return []
        return [_item(pav, "V301", "viga_fundo", 100, 19)]

    monkeypatch.setattr(reap, "inventario", inventario)
    tipo = reap.calcular_cenario(None, "obra-tipo-repetido", "TIPO", "para", Path("."))
    assert tipo["pavimentos"] == ["1_PAV", "TIPO (2º)", "TIPO (3º)", "TIPO (4º)"]
    assert tipo["alocacao"]["V301-P01"]["etapa"] == "1"
    assert tipo["alocacao"]["V301-P01"]["fonte_pavimento"] == "TIPO (3º)"

    seguinte = reap.calcular_cenario(None, "obra-tipo-repetido", "5_PAV", "para", Path("."))
    assert seguinte["alocacao"]["V301-P01"]["etapa"] == "1"
    assert seguinte["alocacao"]["V301-P01"]["fonte_pavimento"] == "TIPO (4º)"
    assert chamadas.count("TIPO") == 2  # um inventário por cadastro, não por repetição
    estoque = seguinte["disponivel"]
    ids_montados = [p["id"] for e in estoque.values()
                    for pecas in e["montados"].values() for p in pecas]
    assert len(ids_montados) == len(set(ids_montados))
    assert all("TIPO@" in pid for pid in ids_montados)
