from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from main import MainWindow


def _t_shape(y_offset: float = 0.0) -> list[list[float]]:
    return [
        [20, 0 + y_offset], [20, -12 + y_offset], [50, -12 + y_offset],
        [50, -55 + y_offset], [70, -55 + y_offset], [70, -12 + y_offset],
        [100, -12 + y_offset], [100, 0 + y_offset], [20, 0 + y_offset],
    ]


def _window(polylines: list[dict]) -> MainWindow:
    window = MainWindow.__new__(MainWindow)
    window.dxf_data = {"polylines": polylines}
    window._auto_fill_cut_view_ficha = lambda *args, **kwargs: None
    window._auto_fill_pillar_ficha = lambda *args, **kwargs: None
    window._find_cut_view_web_extension = lambda *args, **kwargs: None
    return window


def _slab() -> dict:
    return {
        "id": "s1", "name": "L1",
        "points": [[0, 0], [200, 0], [200, 100], [0, 100], [0, 0]],
        "links": {},
    }


def test_auto_link_cut_view_requires_scaled_boundary_contact():
    window = _window([
        {"points": _t_shape(0), "layer": "8"},
        {"points": _t_shape(-30), "layer": "8"},
    ])
    target = _slab()
    cuts, pillars = window._auto_link_slab_cut_views([target])
    linked = target["links"]["laje_visao_corte"]["cut_view_geom"]
    assert cuts == 1
    assert pillars == 0
    assert len(linked) == 1
    assert linked[0]["distance_to_slab"] == 0.0


def test_existing_unvalidated_distant_cut_is_pruned_but_human_link_is_preserved():
    window = _window([])
    target = _slab()
    target["links"] = {
        "laje_visao_corte": {
            "cut_view_geom": [
                {
                    "points": _t_shape(-30), "is_inferred": True,
                    "source": "geometry_near_slab_boundary", "distance_to_slab": 30.0,
                },
                {
                    "points": _t_shape(-30), "validated": True,
                    "source": "human_ui", "distance_to_slab": 30.0,
                },
            ]
        }
    }
    window._auto_link_slab_cut_views([target])
    linked = target["links"]["laje_visao_corte"]["cut_view_geom"]
    assert len(linked) == 1
    assert linked[0]["validated"] is True


def test_existing_validated_inference_is_pruned_but_validated_human_link_is_preserved():
    window = _window([])
    target = _slab()
    target["links"] = {
        "laje_visao_corte": {
            "cut_view_geom": [
                {
                    "points": _t_shape(-30), "is_inferred": True,
                    "validated": True, "source": "geometry_near_slab_boundary",
                },
                {
                    "points": _t_shape(-30), "validated": True,
                    "source": "human_ui",
                },
            ]
        }
    }

    window._auto_link_slab_cut_views([target])

    linked = target["links"]["laje_visao_corte"]["cut_view_geom"]
    assert len(linked) == 1
    assert linked[0]["source"] == "human_ui"


def test_prune_neighbor_level_removes_stale_inference_even_when_slab_is_sealed():
    window = MainWindow.__new__(MainWindow)
    source = {
        "id": "s2", "name": "L2", "fields": {"laje_nivel": "855.12"},
        "links": {"laje_nivel": {"label": [{"text": "855.12", "role": "Nivel CAD"}]}},
    }
    target = {
        "id": "s1", "name": "L1", "is_validated": True,
        "validated_fields": ["laje_vizinhas_niveis"],
        "links": {"laje_vizinhas_niveis": {"neighbor_east": [{
            "text": "206.5", "source": "orthogonal_neighbor_level",
            "source_slab": "L2", "is_inferred": True,
        }]}},
    }

    removed = window._prune_stale_neighbor_level_links([target, source])

    assert removed == 1
    assert target["links"]["laje_vizinhas_niveis"]["neighbor_east"] == []
