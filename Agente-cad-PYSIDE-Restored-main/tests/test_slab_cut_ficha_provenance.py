"""Regressões de proveniência dos cálculos internos da visão de corte LAJ."""

from main import MainWindow
from src.core.sa_db_persistence import merge_analysis_item


def test_cut_ficha_rejects_geometric_neighbor_height_that_creates_negative_clearance():
    window = MainWindow.__new__(MainWindow)
    window._points_bbox_tuple = lambda pts: (0, 0, 10, 10)
    window._bbox_center_tuple = lambda bbox: (5, 5)
    window._slab_cut_direction = lambda slab, pts: "Leste"
    window._neighbor_by_direction = lambda slab, slabs, poly_map, direction: {
        "name": "L324", "fields": {"laje_dim": "h=14"},
    }
    window._slab_height_value = lambda slab: "12" if slab and slab.get("name") == "L318" else ("14" if slab else "")
    window._slab_dim_text = lambda slab: "h=12" if slab and slab.get("name") == "L318" else "h=14"
    window._find_cut_view_cotas = lambda pts, direction: {
        "all_cotas": [], "beam_height_cota": None, "scale_v": 1.0, "bw_cota": None,
    }
    window._parse_cut_poly_sections = lambda pts, direction: {
        "beam_height": 55, "bw": 19,
        "own_slab_h": 12, "neigh_slab_h": 57.2,
        "own_dist_topo": 0, "own_dist_fundo": 43,
        "neigh_dist_topo": 30, "neigh_dist_fundo": -32.2,
    }
    window._nearest_dxf_text = lambda center, pattern, max_dist: (
        {"text": "55", "pos": (5, 5)} if pattern.startswith("^\\d") else None
    )

    slab = {"name": "L318"}
    link = {"points": [[0, 0], [1, 0], [1, 1], [0, 1]], "ficha": {}}
    window._auto_fill_cut_view_ficha(slab, link, [slab], {})

    ficha = link["ficha"]
    assert ficha["neighbor_height"] == "14"
    assert ficha["neigh_slab_height"] == "14.0"
    assert ficha["neighbor_dist_bottom"] == "11.0"
    assert "d_topo(30) = 11 cm" in ficha["neigh_dist_fundo_formula"]


def test_sealed_slab_preserves_cut_geometry_but_refreshes_inferred_cut_formula():
    points = [[0, 0], [10, 0], [10, 5], [0, 5], [0, 0]]
    old = {
        "id": "l1", "project_id": "p", "name": "L1", "is_validated": True,
        "links": {"laje_visao_corte": {"cut_view_geom": [{
            "is_inferred": True, "validated": True, "points": points,
            "ficha": {"neigh_slab_height": "57.2", "neighbor_dist_bottom": "-32.2"},
        }]}},
    }
    fresh = {
        "id": "new", "project_id": "other", "name": "L1", "id_item": "01",
        "links": {"laje_visao_corte": {"cut_view_geom": [{
            "is_inferred": True, "points": points,
            "ficha": {"neigh_slab_height": "14", "neighbor_dist_bottom": "11"},
        }]}},
    }
    merged = merge_analysis_item(old, fresh, "LAJ")
    cut = merged["links"]["laje_visao_corte"]["cut_view_geom"][0]
    assert cut["validated"] is True
    assert cut["points"] == points
    assert cut["ficha"]["neigh_slab_height"] == "14"
    assert cut["ficha"]["neighbor_dist_bottom"] == "11"
