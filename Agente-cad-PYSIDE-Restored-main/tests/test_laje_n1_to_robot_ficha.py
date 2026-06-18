from src.core.laje_n1_to_robot_ficha import n1_laje_to_robot_ficha


def test_converts_rectangular_n1_laje_to_robot_ficha():
    ficha = n1_laje_to_robot_ficha(
        {
            "name": "L327",
            "points": [[0, 0], [200, 0], [200, 100], [0, 100], [0, 0]],
            "laje_linhas_v_count": "1",
            "laje_linhas_h_count": "2",
            "unioes_nos_bordes": "sim",
            "observacoes": "validado no N1",
        },
        modo_selecionado=0,
    )

    assert ficha["nome"] == "L327"
    assert ficha["numero"] == 327
    assert ficha["comprimento"] == 200
    assert ficha["largura"] == 100
    assert ficha["area_cm2"] == 20000
    assert ficha["linhas_verticais"] == [{"value": 100.0, "is_union": False}]
    assert ficha["linhas_horizontais"] == [
        {"value": 33.3, "is_union": False},
        {"value": 66.7, "is_union": False},
    ]


def test_deformed_laje_keeps_polygon_and_area():
    ficha = n1_laje_to_robot_ficha(
        {
            "id_item": "L308",
            "coordenadas": [[0, 0], [200, 0], [200, 80], [160, 100], [0, 100]],
            "linhas_verticais": [{"value": 90}],
            "linhas_horizontais": [50],
        }
    )

    assert ficha["comprimento"] == 200
    assert ficha["largura"] == 100
    assert len(ficha["coordenadas"]) == 5
    assert ficha["area_cm2"] == 19600
    assert ficha["linhas_verticais"] == [{"value": 90.0, "is_union": False}]
    assert ficha["linhas_horizontais"] == [{"value": 50.0, "is_union": False}]
