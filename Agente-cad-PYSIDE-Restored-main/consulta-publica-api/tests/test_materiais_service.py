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
    assert por_bitola["Sarrafo de pressão"]["cortes"] == [{"comprimento_cm": 122.0, "quantidade": 1}]


def test_plano_de_corte_barras_e_chapas():
    from services.plano_de_corte import barras_necessarias, chapas_necessarias

    # 150+150 cabem numa barra de 300; 120 abre a 2ª; 350 = emenda (300 + 50).
    b = barras_necessarias([150, 150, 120, 350])
    assert (b["barras"], b["emendas"]) == (3, 1)
    # 2 painéis 122x122 = 1 chapa; 88x122 x3 = 2 chapas (sobra 68 não cabe 88).
    assert chapas_necessarias([(122, 122)] * 2)["chapas"] == 1
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
    rotulos = sorted(p["rotulo"] for ch in c["layout"] for p in ch["pecas"])
    assert rotulos == ["1", "2", "3", "4a", "4b"]
    for ch in c["layout"]:
        r = [(p["x"], p["y"], p["x"] + p["largura_cm"], p["y"] + p["altura_cm"]) for p in ch["pecas"]]
        assert all(x1 <= 244.05 and y1 <= 122.05 for _, _, x1, y1 in r)
        for i, a in enumerate(r):
            for b in r[i + 1:]:
                assert min(a[2], b[2]) - max(a[0], b[0]) <= 0.05 or min(a[3], b[3]) - max(a[1], b[1]) <= 0.05
