from src.core.laje_n1_to_robot_ficha import n1_laje_to_robot_ficha


def test_mode_is_derived_from_algorithmic_grid_when_absent():
    ficha = n1_laje_to_robot_ficha(
        {
            "name": "L1",
            "points": [[0, 0], [405.5, 0], [405.5, 183], [0, 183]],
        }
    )
    assert len(ficha["linhas_horizontais"]) > len(ficha["linhas_verticais"])
    assert ficha["modo_selecionado"] == 1


def test_explicit_mode_is_preserved():
    ficha = n1_laje_to_robot_ficha(
        {
            "name": "L1",
            "points": [[0, 0], [405.5, 0], [405.5, 183], [0, 183]],
            "modo_selecionado": 0,
        }
    )
    assert ficha["modo_selecionado"] == 0
