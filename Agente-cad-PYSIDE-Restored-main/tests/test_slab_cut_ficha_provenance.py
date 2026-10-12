"""Regressões de proveniência dos cálculos internos da visão de corte LAJ."""

from main import MainWindow
from src.core.sa_db_persistence import merge_analysis_item


def test_cut_ficha_rejects_geometric_neighbor_height_that_creates_negative_clearance():
    window = MainWindow.__new__(MainWindow)
    window.dxf_data = {}
    window._points_bbox_tuple = lambda pts: (0, 0, 10, 10)
    window._bbox_center_tuple = lambda bbox: (5, 5)
    window._slab_cut_direction = lambda slab, pts: "Leste"
    window._neighbor_by_direction = lambda slab, slabs, poly_map, direction, **_kw: {
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


def test_annotated_height_wins_even_with_positive_geometric_clearances():
    window = MainWindow.__new__(MainWindow)
    window.dxf_data = {}
    window._points_bbox_tuple = lambda pts: (0, 0, 10, 10)
    window._bbox_center_tuple = lambda bbox: (5, 5)
    window._slab_cut_direction = lambda slab, pts: 'Sul'
    window._neighbor_by_direction = lambda *args, **_kw: {'name': 'L2'}
    window._slab_height_value = lambda slab: '12'
    window._slab_dim_text = lambda slab: 'h=12'
    window._find_cut_view_cotas = lambda *args: dict(all_cotas=[], beam_height_cota=None, scale_v=1.0, bw_cota=None)
    window._parse_cut_poly_sections = lambda *args: dict(beam_height=55, bw=19,
        own_slab_h=10, neigh_slab_h=10, own_dist_topo=7, own_dist_fundo=38,
        neigh_dist_topo=0, neigh_dist_fundo=45)
    window._nearest_dxf_text = lambda *args, **kwargs: None
    link = {'points': [[0,0],[1,0],[1,1],[0,1]], 'ficha': {}}
    window._auto_fill_cut_view_ficha({'name': 'L1'}, link, [], {})
    ficha = link['ficha']
    assert float(ficha['own_slab_height']) == 12
    assert float(ficha['own_dist_top']) == 7
    assert float(ficha['own_dist_bottom']) == 36
    assert float(ficha['neigh_slab_height']) == 12
    assert float(ficha['neighbor_dist_bottom']) == 43


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


def test_cut_neighbor_is_slab_across_beam_not_by_slab_centers():
    # L318 (corredor longo) fica ao norte da L321, mas o centro dela está mais
    # a leste que ao norte: pelos centros ela não era vizinha e o corte saía "nulo".
    from shapely.geometry import box
    window = MainWindow.__new__(MainWindow)
    own = {'name': 'L321'}
    corridor = {'name': 'L318'}
    poly_map = {'L321': box(2060, 2100, 2440, 2489), 'L318': box(1394, 2509, 4533, 2661)}
    found = window._neighbor_by_direction(own, [own, corridor], poly_map, 'Norte', anchor=(2231, 2500))
    assert found is corridor
