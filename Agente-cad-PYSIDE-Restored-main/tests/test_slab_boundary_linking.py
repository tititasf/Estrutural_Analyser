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
