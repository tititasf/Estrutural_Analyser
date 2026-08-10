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


def test_existing_inferred_pillar_without_face_is_pruned_but_human_is_preserved():
    window = _window([])
    target = _slab()
    target["links"] = {
        "laje_pilares_apoio": {
            "pillar_geom": [
                {
                    "points": [[190, 20], [210, 20], [210, 70], [190, 70], [190, 20]],
                    "is_inferred": True,
                    "validated": True,
                    "ficha": {"pillar_name": "P1", "pillar_side": "NULO", "touch_face": "NULO"},
                },
                {
                    "points": [[190, 20], [210, 20], [210, 70], [190, 70], [190, 20]],
                    "validated": True,
                    "source": "human_ui",
                },
            ]
        }
    }

    window._auto_link_slab_cut_views([target])

    linked = target["links"]["laje_pilares_apoio"]["pillar_geom"]
    assert len(linked) == 1
    assert linked[0]["source"] == "human_ui"


def test_layer7_l_pillar_links_by_edge_overlap_not_global_polygon_distance():
    """Pilar L real (14P/L409): face encosta na laje mas bbox global fica distante."""
    slab_pts = [
        [5360.798623, 2553.025], [5350.798623, 2553.025], [5264.09, 2553.025],
        [5065.09, 2553.025], [5010.474794, 2553.025], [5010.474794, 2652.025],
        [5360.798623, 2652.025], [5360.798623, 2553.025],
    ]
    p26 = [
        [4856.59, 2335.025], [5021.59, 2335.025], [5021.59, 2354.025],
        [4875.59, 2354.025], [4875.59, 2553.025], [4856.59, 2553.025],
        [4856.59, 2335.025],
    ]
    p27 = [
        [5472.59, 2335.025], [5472.59, 2553.025], [5453.59, 2553.025],
        [5453.59, 2354.025], [5307.59, 2354.025], [5307.59, 2335.025],
        [5472.59, 2335.025],
    ]

    def _fill(_slab, link):
        pts = link.get("points") or []
        if pts and abs(float(pts[0][0]) - 4856.59) < 1.0:
            link["ficha"] = {"pillar_name": "P26", "pillar_side": "C", "touch_face": "CIMA"}
        else:
            link["ficha"] = {"pillar_name": "P27", "pillar_side": "C", "touch_face": "CIMA"}

    window = _window([
        {"points": p26, "layer": "7"},
        {"points": p27, "layer": "7"},
    ])
    window._auto_fill_pillar_ficha = _fill
    target = {"id": "s409", "name": "L409", "points": slab_pts, "links": {}}

    cuts, pillars = window._auto_link_slab_cut_views([target])

    assert cuts == 0
    assert pillars == 2
    names = {
        g["ficha"]["pillar_name"]
        for g in target["links"]["laje_pilares_apoio"]["pillar_geom"]
    }
    assert names == {"P26", "P27"}


def test_layer7_l_pillar_larger_than_compact_marker_window_is_linked_by_real_contact():
    """An L-shaped support may exceed 180 DXF units but must still prove face/name."""
    l_pillar = [
        [10, -230], [35, -230], [35, -20], [175, -20],
        [175, 0], [10, 0], [10, -230],
    ]
    window = _window([{"points": l_pillar, "layer": "7"}])
    window._auto_fill_pillar_ficha = lambda _slab, link: link.update({
        "ficha": {"pillar_name": "P26", "pillar_side": "B", "touch_face": "CIMA"}
    })
    target = _slab()

    cuts, pillars = window._auto_link_slab_cut_views([target])

    assert cuts == 0
    assert pillars == 1
    support = target["links"]["laje_pilares_apoio"]["pillar_geom"]
    assert len(support) == 1
    assert support[0]["ficha"]["pillar_name"] == "P26"


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
