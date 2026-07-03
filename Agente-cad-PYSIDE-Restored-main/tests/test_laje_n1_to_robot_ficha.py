from src.core.laje_n1_to_robot_ficha import (
    apply_n1_outline_anchor,
    n1_laje_outline_points,
    n1_laje_to_robot_ficha,
)


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


def test_sa_outline_points_are_absolute_even_when_robot_geometry_is_local():
    laje = {
        "coordenadas": [[0, 0], [418, 0], [418, 122], [0, 122]],
        "links": {
            "laje_outline_segs": {
                "contour": [
                    {
                        "points": [
                            [2496.5, 2680.0],
                            [2914.5, 2680.0],
                            [2914.5, 2991.0],
                            [2496.5, 2991.0],
                        ]
                    }
                ]
            }
        },
    }

    assert n1_laje_outline_points(laje) == [
        [2496.5, 2680.0],
        [2914.5, 2680.0],
        [2914.5, 2991.0],
        [2496.5, 2991.0],
    ]

    positioned = apply_n1_outline_anchor(
        {
            "coordenadas": [[418, 122], [0, 122], [0, 0], [418, 0]],
            "_stog_pose": {"x": 4041.07, "y": 2280.94},
        },
        laje,
    )

    assert positioned["_stog_pose"] == {"x": 2496.5, "y": 2680.0}
    assert min(point[0] for point in positioned["coordenadas"]) == 0
    assert min(point[1] for point in positioned["coordenadas"]) == 0
    assert positioned["_sa_meta"]["n3_pose_source"] == "sa_outline_anchor"
