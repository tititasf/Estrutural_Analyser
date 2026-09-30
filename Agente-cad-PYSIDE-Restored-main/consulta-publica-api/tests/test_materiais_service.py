"""Medição de painéis/sarrafos no DXF N3 (services/materiais_service.py)."""

from __future__ import annotations

import ezdxf

from services.materiais_service import medir_dxf


def _dxf(tmp_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    # 2 painéis 244x19 + 138x19 (módulo 244), como o FV desenha.
    for x in (0, 244, 382):
        msp.add_line((x, 0), (x, 19), dxfattribs={"layer": "Painéis"})
    msp.add_line((0, 0), (382, 0), dxfattribs={"layer": "Painéis"})
    msp.add_line((0, 19), (382, 19), dxfattribs={"layer": "Painéis"})
    # Sarrafo horizontal desenhado 2x (defeito da LV): conta 1.
    for _ in range(2):
        msp.add_lwpolyline([(7, 7), (237, 7)], dxfattribs={"layer": "SARR_2.2x7"})
    msp.add_line((7, 0), (7, 19), dxfattribs={"layer": "SARR_2.2x7"})
    msp.add_lwpolyline([(0, 0), (122, 0), (122, 7), (0, 7)], close=True,
                       dxfattribs={"layer": "Sarrafo de Pressão"})
    path = tmp_path / "n3.dxf"
    doc.saveas(path)
    return path


def test_paineis_sao_as_celulas_fechadas_da_layer_paineis(tmp_path):
    m = medir_dxf(_dxf(tmp_path))
    assert m["paineis_total"] == 2
    assert {(p["largura_cm"], p["altura_cm"]) for p in m["paineis"]} == {(244.0, 19.0), (138.0, 19.0)}
    assert m["paineis_area_m2"] == round(382 * 19 / 1e4, 2)


def test_sarrafo_duplicado_conta_uma_vez_e_bitola_vem_da_layer(tmp_path):
    m = medir_dxf(_dxf(tmp_path))
    por_bitola = {s["bitola"]: s for s in m["sarrafos"]}
    assert m["sarrafos_duplicados_ignorados"] == 1
    assert por_bitola["Sarrafo 2.2 x 7 cm"]["pecas"] == 2
    assert por_bitola["Sarrafo 2.2 x 7 cm"]["total_m"] == round((230 + 19) / 100, 2)
    # Peça desenhada como retângulo mede o lado maior.
    assert por_bitola["Sarrafo de pressão 2.2 x 7 cm"]["cortes"] == [{"comprimento_cm": 122.0, "quantidade": 1}]


def test_plano_de_corte_barras_e_chapas():
    from services.plano_de_corte import barras_necessarias, chapas_necessarias

    # Perda de 1 cm por corte também na barra: 150 + 149 cabe em 300, 150 + 150 não.
    assert barras_necessarias([150, 149])["barras"] == 1
    assert barras_necessarias([150, 150])["barras"] == 2
    # Peça que ocupa a barra inteira não tem corte; 350 = emenda (300 + 50).
    b = barras_necessarias([300, 350])
    assert (b["barras"], b["emendas"]) == (3, 1)
    # 2 painéis 122x122: o corte entre eles come 1 cm → 2 chapas.
    assert chapas_necessarias([(122, 122)] * 2)["chapas"] == 2
    assert chapas_necessarias([(121.5, 122)] * 2)["chapas"] == 1
    # Perda de 1 cm por corte: 102 + 20 não cabe em 122; 102 + 19 cabe.
    assert chapas_necessarias([(194, 102), (194, 20)])["chapas"] == 2
    assert chapas_necessarias([(194, 102), (194, 19)])["chapas"] == 1
    assert chapas_necessarias([(88, 122)] * 3)["chapas"] == 2
    c = chapas_necessarias([(19, 255)])
    assert (c["chapas"], c["emendas"]) == (1, 1)


def test_layout_da_chapa_numera_pecas_e_nao_sobrepoe():
    from services.plano_de_corte import compra_de_grupos

    grupos = [{"titulo": "Lado A", "disponivel": True, "sarrafos": [],
               "paineis": [{"largura_cm": 88, "altura_cm": 122, "quantidade": 3, "recortado": False},
                           {"largura_cm": 19, "altura_cm": 255, "quantidade": 1, "recortado": False}]}]
    c = compra_de_grupos(grupos)["chapas"]
    assert grupos[0]["paineis"][0]["numeros"] == [1, 2, 3]
    # A otimização usa o mínimo: 3 x 88 x 122 + 19 x 255 cabem em 2 chapas.
    assert c["chapas"] == 2
    rotulos = sorted(p["rotulo"] for ch in c["layout"] for p in ch["pecas"])
    assert rotulos == ["1", "2", "3", "4a", "4b"]
    for ch in c["layout"]:
        r = [(p["x"], p["y"], p["x"] + p["largura_cm"], p["y"] + p["altura_cm"]) for p in ch["pecas"]]
        assert all(x1 <= 244.05 and y1 <= 122.05 for _, _, x1, y1 in r)
        for i, a in enumerate(r):
            for b in r[i + 1:]:
                assert min(a[2], b[2]) - max(a[0], b[0]) <= 0.05 or min(a[3], b[3]) - max(a[1], b[1]) <= 0.05


def test_otimizacao_acha_o_minimo_que_uma_ordem_so_perde():
    from services.plano_de_corte import chapas_necessarias

    # 4 x 120 x 60 + 4 x 120 x 60 = área de ~1,93 chapa; 2 chapas é o mínimo
    # (2 colunas de 120 + 1 cm de corte ≤ 244; 60 + 1 + 60 ≤ 122).
    assert chapas_necessarias([(120, 60)] * 8)["chapas"] == 2
    # Plano determinístico: mesma entrada, mesmo layout.
    pecas = [(194, 102), (161.5, 20), (50, 20), (244, 122), (80, 40), (30, 110)]
    assert chapas_necessarias(pecas) == chapas_necessarias(pecas)


def test_laje_tira_hachurada_nao_e_reaproveitavel_e_todo_painel_tem_id(tmp_path):
    from services.materiais_service import identificar_paineis, prefixo_id_painel

    doc = ezdxf.new()
    msp = doc.modelspace()
    # Painel 194 x 102 em cima de uma tira 194 x 20 hachurada.
    for y in (0, 20, 122):
        msp.add_line((0, y), (194, y), dxfattribs={"layer": "Painéis"})
    for x in (0, 194):
        msp.add_line((x, 0), (x, 122), dxfattribs={"layer": "Painéis"})
    h = msp.add_hatch(dxfattribs={"layer": "Hachura"})
    h.paths.add_polyline_path([(0, 0), (194, 0), (194, 20), (0, 20)], is_closed=True)
    path = tmp_path / "laje.dxf"
    doc.saveas(path)

    grupo = {"titulo": "Painéis", "disponivel": True, **medir_dxf(path)}
    row = {"obra_id": "obra_treino_1", "pavimento": "13_PAV", "tipo_elemento": "laje",
           "item_id": "L301", "classe": "lajes"}
    prefixo = prefixo_id_painel(row)
    assert prefixo == "TREINO_1-13PAV-LAJ-L301"
    identificar_paineis([grupo], prefixo, laje=True)
    p1, p2 = grupo["paineis"]  # ordem de leitura: de cima p/ baixo
    assert (p1["altura_cm"], p1["classe"], p1["reaproveitavel"]) == (102.0, "Painel comum", True)
    assert (p2["altura_cm"], p2["classe"], p2["reaproveitavel"]) == (20.0, "Tira de escoramento", False)
    assert [p["id"] for p in grupo["paineis"]] == ["TREINO_1-13PAV-LAJ-L301-P01", "TREINO_1-13PAV-LAJ-L301-P02"]


def test_id_do_pilar_carrega_o_modo():
    from services.materiais_service import prefixo_id_painel

    row = {"obra_id": "5aecf77e", "obra_rotulo": "Obra_TREINO_1", "pavimento": "13_PAV",
           "tipo_elemento": "pilar", "item_id": "P1_Passa", "classe": "pilares_n3_passa", "titulo_publico": "P1"}
    assert prefixo_id_painel(row) == "TREINO_1-13PAV-PIL-P1.PASSA"
    fundo = {"obra_rotulo": "Obra_TREINO_1", "pavimento": "13_PAV", "tipo_elemento": "viga_fundo",
             "item_id": "fundo|9d77|1|1", "classe": "fundo", "titulo_publico": "V309A (segmento 1)"}
    assert prefixo_id_painel(fundo) == "TREINO_1-13PAV-FV-V309A.S1"


def test_grade_peca_desenhada_com_4_linhas_e_uma_peca_e_vai_para_a_grade_do_rotulo(tmp_path):
    from services.materiais_service import separar_grades

    doc = ezdxf.new()
    msp = doc.modelspace()

    def ret(x0, y0, x1, y1, layer):
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            msp.add_line(a, b, dxfattribs={"layer": layer})

    for dx, rot in ((0, "P1.A"), (128, "P1.B")):
        msp.add_text(rot, dxfattribs={"layer": "NOMENCLATURA", "insert": (dx - 10, 0)})
        ret(dx, 0, dx + 88, 2, "SARR_2.2x7")        # travessa de base
        ret(dx, 2, dx + 7, 201, "SARR_2.2x7")       # montante (encosta na base)
        ret(dx + 27, 2, dx + 31, 201, "SARR_3.5x7")  # meio pontalete
    path = tmp_path / "grades.dxf"
    doc.saveas(path)

    g = {"titulo": "Grades", "disponivel": True, **medir_dxf(path)}
    por = {s["bitola"]: s for s in g["sarrafos"]}
    assert por["Sarrafo 2.2 x 7 cm"]["pecas"] == 4  # 2 por grade, não 16 linhas
    assert por["Sarrafo 3.5 x 7 cm"]["cortes"] == [{"comprimento_cm": 199.0, "quantidade": 2}]
    separar_grades(g)
    assert [gr["rotulo"] for gr in g["grades"]] == ["P1.A", "P1.B"]
    pecas_a = g["grades"][0]["pecas"]
    assert sum(c["quantidade"] for c in pecas_a) == 3
    # verticais antes das horizontais
    assert [c["sentido"] for c in pecas_a] == ["vertical", "vertical", "horizontal"]


def test_cada_sarrafo_vai_para_o_painel_onde_corre():
    from services.materiais_service import associar_sarrafos

    g = {"paineis": [{"_bbox": (0, 0, 88, 122)}, {"_bbox": (0, 122, 88, 244)}],
         "_pecas_sarrafo": [("Sarrafo de pressão", 122.0, (7, 0, 7, 122)),
                            ("Sarrafo de pressão", 122.0, (7, 122, 7, 244)),
                            ("Sarrafo 2.2 x 7 cm", 80.0, (4, 200, 84, 200)),
                            ("Sarrafo 2.2 x 7 cm", 30.0, (500, 0, 530, 0))]}
    associar_sarrafos(g)
    assert g["paineis"][0]["sarrafos"] == [{"bitola": "Sarrafo de pressão", "comprimento_cm": 122.0, "quantidade": 1}]
    assert len(g["paineis"][1]["sarrafos"]) == 2
    assert g["sarrafos_avulsos"] == [{"bitola": "Sarrafo 2.2 x 7 cm", "comprimento_cm": 30.0, "quantidade": 1}]
    # Montagem 3D: coordenadas locais ao painel; eixo sem largura ganha 7 cm
    # centrados; pressão entra por último.
    m = g["paineis"][1]["montagem"]
    assert [s["bitola"] for s in m] == ["Sarrafo 2.2 x 7 cm", "Sarrafo de pressão"]
    assert m[0] == {"bitola": "Sarrafo 2.2 x 7 cm", "comprimento_cm": 80.0, "espessura_cm": 2.2,
                    "face": "frente", "x": 4.0, "y": 74.5, "w": 80.0, "h": 7.0}
    # Pressão (HIDDEN em x=7) faz par com a borda x=0 e vai na face de trás.
    assert (m[1]["face"], m[1]["x"], m[1]["y"], m[1]["w"], m[1]["h"]) == ("tras", 0.0, 0.0, 7.0, 122.0)


def test_sarrafo_do_painel_e_o_par_de_linhas_ou_linha_e_borda():
    """LV V309A P01 (244 x 124): linhas em 7 · 27,5/34,5 · 58,5/65,5 ·
    89,5/96,5 · 117 + vertical em x=7 = 6 sarrafos, não 9. FV (244 x 19):
    linhas em 7 e 12 fazem par com as bordas (2 de 7 cm), não entre si (5 cm)."""
    from services.materiais_service import associar_sarrafos

    b = "Sarrafo 2.2 x 7 cm"
    lv = {"paineis": [{"_bbox": (0, 0, 244, 124)}],
          "_pecas_sarrafo": [(b, 236.2, (7, y, 243.2, y)) for y in (7, 27.5, 34.5, 58.5, 65.5, 89.5, 96.5, 117)]
          + [(b, 124.0, (7, 0, 7, 124))]}
    associar_sarrafos(lv)
    m = lv["paineis"][0]["montagem"]
    assert len(m) == 6 and all(min(s["w"], s["h"]) == 7.0 for s in m)
    assert sorted(s["y"] for s in m if s["h"] == 7.0) == [0.0, 27.5, 58.5, 89.5, 117.0]
    assert lv["sarrafos"][0]["pecas"] == 6

    fv = {"paineis": [{"_bbox": (0, 0, 244, 19)}],
          "_pecas_sarrafo": [(b, 237.0, (7, 7, 244, 7)), (b, 237.0, (7, 12, 244, 12)), (b, 19.0, (7, 0, 7, 19))]}
    associar_sarrafos(fv)
    assert sorted((s["y"], s["h"]) for s in fv["paineis"][0]["montagem"] if s["w"] > 7) == [(0.0, 7.0), (12.0, 7.0)]


def test_barras_paralelas_com_montantes_nao_viram_uma_peca(tmp_path):
    """FV V309A S1: duas barras a 5 cm, partidas na união (x=244), e os
    montantes das pontas fecham um "retângulo" 447 x 5 — são 6 peças."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    for y in (-12, -7):
        msp.add_line((7, y), (244, y), dxfattribs={"layer": "SARR_2.2x7"})
        msp.add_line((244, y), (454, y), dxfattribs={"layer": "SARR_2.2x7"})
    for x in (7, 454):
        msp.add_line((x, -19), (x, 0), dxfattribs={"layer": "SARR_2.2x7"})
    path = tmp_path / "fv.dxf"
    doc.saveas(path)
    s = medir_dxf(path)["sarrafos"][0]
    assert s["pecas"] == 6
    assert {c["comprimento_cm"] for c in s["cortes"]} == {237.0, 210.0, 19.0}


def test_sobras_de_chapa_e_barra_tem_id_rastreavel():
    """Sobra = estoque para o próximo pavimento: ID no formato do painel."""
    from services.plano_de_corte import compra_de_grupos

    g = {"disponivel": True, "titulo": "Lado A",
         "paineis": [{"numero": 1, "id": "X-P01", "largura_cm": 200.0, "altura_cm": 100.0}],
         "sarrafos": [{"bitola": "Sarrafo 2.2 x 7 cm", "cortes": [{"comprimento_cm": 250.0, "quantidade": 1}]},
                      {"bitola": "Sarrafo 3.5 x 7 cm", "cortes": [{"comprimento_cm": 100.0, "quantidade": 1}]}]}
    c = compra_de_grupos([g], "TREINO_1-13PAV-LV-V1.PARA")
    ids = {s["id"]: s for s in c["sobras"]}
    assert all(i.startswith("TREINO_1-13PAV-LV-V1.PARA-CH01-S") for i, s in ids.items() if s["tipo"] == "chapa")
    assert ids["TREINO_1-13PAV-LV-V1.PARA-S7-B01"]["comprimento_cm"] == 49.0  # 300 - 250 - 1 de corte
    assert ids["TREINO_1-13PAV-LV-V1.PARA-MP-B01"]["comprimento_cm"] == 199.0
    assert len(ids) == len(c["sobras"])


def test_painel_recortado_leva_o_contorno_real(tmp_path):
    """L319 P06: painel 122 x 244 com entalhe de pilar 81,4 x 65 no canto."""
    doc = ezdxf.new()
    pts = [(40.6, 179), (122, 179), (122, 0), (0, 0), (0, 244), (40.6, 244)]
    doc.modelspace().add_lwpolyline([(x + 500, y + 100) for x, y in pts], close=True, dxfattribs={"layer": "Painéis"})
    path = tmp_path / "laje.dxf"
    doc.saveas(path)
    p = medir_dxf(path)["paineis"][0]
    assert p["recortado"] and (p["largura_cm"], p["altura_cm"]) == (122.0, 244.0)
    parte, = p["partes"]
    assert sorted(map(tuple, parte["contorno"])) == sorted(pts) and parte["furos"] == []


def test_pilar_viga_chegando_recorta_o_painel(tmp_path):
    """ABCD: HATCH = viga que chega na face. Painel = pilha − viga; viga que
    cruza a face inteira parte o painel em 2 peças (P1 Para, face C)."""
    import json

    from services.materiais_service import _paineis_do_contrato_pilar

    doc = ezdxf.new()
    msp = doc.modelspace()
    for y in (0, 244, 278):
        msp.add_line((0, y), (19, y), dxfattribs={"layer": "Painéis"})
    h = msp.add_hatch()
    h.paths.add_polyline_path([(-8, 138), (19, 138), (19, 208), (-8, 208)], is_closed=True)
    dxf = tmp_path / "PL_ABCD_preview_P1.dxf"
    doc.saveas(dxf)
    (tmp_path / "P1.json").write_text(json.dumps({"paineis_intervals_A": [244, 34], "larg1_A": 19}))
    baixo, cima = _paineis_do_contrato_pilar(dxf)["paineis"]
    assert baixo["recortado"] and not cima["recortado"]
    partes = sorted(tuple(sorted(map(tuple, p["contorno"]))) for p in baixo["partes"])
    assert partes == [((0, 0), (0, 138), (19, 0), (19, 138)), ((0, 208), (0, 244), (19, 208), (19, 244))]


def test_recorte_vira_sobra_e_recebe_peca_de_outra_chapa():
    """Nada é descarte (D-68): o entalhe do painel é sobra com ID; uma peça que
    cabe nele sai de lá em vez de abrir outra chapa."""
    from services.plano_de_corte import chapas_necessarias

    entalhe = [{"contorno": [[40.6, 179], [122, 179], [122, 0], [0, 0], [0, 244], [40.6, 244]], "furos": []}]
    so = chapas_necessarias([(122, 244, 1, "Painéis", "X-P01", entalhe)], "X")
    (s,) = so["layout"][0]["sobras"]
    assert s["recorte_de"] == ["X-P01"] and s["id"] == "X-CH01-S1"
    assert sorted((s["largura_cm"], s["altura_cm"])) == [64.0, 80.4]  # 81,4 x 65 menos 1 cm de serra
    com = chapas_necessarias([(122, 244, 1, "Painéis", "X-P01", entalhe), (60, 50, 2, "Painéis", "X-P02")], "X")
    assert com["chapas"] == 1
    p2 = next(p for p in com["layout"][0]["pecas"] if p["id"] == "X-P02")
    assert p2["em_sobra"]
    (resto,) = com["layout"][0]["sobras"]
    assert resto["recorte_de"] == ["X-P01"] and "contorno" in resto and resto["util"]["largura_cm"] > 0


def test_pilar_viga_na_largura_toda_estreita_o_painel(tmp_path):
    """Face A 88 com viga de 11 descendo 64 no canto: o painel de cima (34)
    é 77 x 34 inteiro (não recortado de 88); o de baixo leva o entalhe 11 x 30."""
    import json

    from services.materiais_service import _paineis_do_contrato_pilar

    doc = ezdxf.new()
    msp = doc.modelspace()
    for y in (0, 244, 278):
        msp.add_line((0, y), (88, y), dxfattribs={"layer": "Painéis"})
    h = msp.add_hatch()
    h.paths.add_polyline_path([(77, 214), (88, 214), (88, 278), (77, 278)], is_closed=True)
    dxf = tmp_path / "PL_ABCD_preview_P1.dxf"
    doc.saveas(dxf)
    (tmp_path / "P1.json").write_text(json.dumps({"paineis_intervals_A": [244, 34], "larg1_A": 88}))
    baixo, cima = _paineis_do_contrato_pilar(dxf)["paineis"]
    assert (cima["largura_cm"], cima["altura_cm"], cima["recortado"]) == (77.0, 34.0, False)
    assert (baixo["largura_cm"], baixo["altura_cm"], baixo["recortado"]) == (88.0, 244.0, True)
