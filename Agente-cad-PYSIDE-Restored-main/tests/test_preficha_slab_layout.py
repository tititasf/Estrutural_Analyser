from src.ui.widgets.pre_validation_dialog import (
    _slab_details_text,
    _slab_outline_points,
)


def _slab():
    return {
        "name": "L301",
        "area": 74206.5,
        "points": [[0, 0], [10, 0], [10, 8], [0, 8], [0, 0]],
        "fields": {"laje_dim": "h=12", "laje_nivel": "852.12"},
        "origin": "motor_geom",
        "method": "n2_axes",
        "confidence_score": 0.5,
        "is_validated": False,
        "links": {
            "laje_pilares_apoio": {
                "pillar_geom": [
                    {"ficha": {"pillar_name": "P1"}},
                    {"ficha": {"pillar_name": "P2"}},
                ]
            },
            "laje_vizinhas_niveis": {
                "neighbor_north": [],
                "neighbor_east": [{"source_slab": "L302"}],
                "neighbor_south": [{"source_slab": "L309"}],
                "neighbor_west": [],
            },
            "laje_visao_corte": {"cut_view_geom": [{}, {}]},
        },
    }


def test_slab_details_group_existing_information_without_vh_inference():
    text = _slab_details_text(_slab())

    assert "DIMENSÕES E NÍVEL\nAltura: h=12\nNível: 852.12" in text
    assert "Área geométrica: 74206.5 u²" in text
    assert "Vértices do contorno: 4" in text
    assert "APOIOS\nPilares: P1, P2" in text
    assert "Leste: L302" in text
    assert "Sul: L309" in text
    assert "Confiança: 50%" in text
    assert "Cortes vinculados: 2" in text
    assert "Verticais" not in text
    assert "Horizontais" not in text


def test_slab_outline_falls_back_to_sa_link():
    slab = {
        "links": {
            "laje_outline_segs": {
                "contour": [{"points": [[1, 2], [3, 2], [3, 4], [1, 2]]}]
            }
        }
    }

    assert _slab_outline_points(slab) == [[1, 2], [3, 2], [3, 4], [1, 2]]
