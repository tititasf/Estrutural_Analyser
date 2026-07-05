from scripts.arete.conversao_n1_diff import compare_outline, diagnose_item


def test_outline_accepts_translation_and_quarter_turn():
    n1 = [[10, 20], [10, 120], [50, 120], [50, 20]]
    n2 = [[0, 0], [100, 0], [100, 40], [0, 40]]
    result = compare_outline(n1, n2)
    assert result["pass"] is True
    assert result["rotation"] in {90, 270}


def test_outline_rejects_different_shape_with_same_bbox():
    rectangle = [[0, 0], [100, 0], [100, 40], [0, 40]]
    notched = [[0, 0], [100, 0], [100, 40], [50, 40], [50, 20], [0, 20]]
    assert compare_outline(rectangle, notched)["pass"] is False


def test_g4_does_not_treat_missing_algorithmic_grid_as_success():
    raw_n1 = {
        "name": "L1",
        "points": [[0, 0], [100, 0], [100, 40], [0, 40]],
        "area_cm2": 4000,
    }
    n2 = {
        "nome": "L1",
        "numero": 1,
        "coordenadas": [[0, 0], [100, 0], [100, 40], [0, 40]],
        "comprimento": 100,
        "largura": 40,
        "area_cm2": 4000,
        "linhas_verticais": [{"value": 40, "is_union": False}],
        "linhas_horizontais": [],
        "obstaculos": [],
        "modo_selecionado": 0,
        "unioes_nos_bordes": [],
        "pontaletes": {},
        "cotas_paineis": [],
        "observacoes": "",
    }
    result = diagnose_item("L1", raw_n1, n2)
    assert result["resultado"] == "FAIL"
    vertical = next(field for field in result["campos"] if field["campo"] == "linhas_verticais")
    assert vertical["categoria"] == "b"
    assert vertical["pass"] is False
