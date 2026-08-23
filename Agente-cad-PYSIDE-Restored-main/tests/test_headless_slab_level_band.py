from scripts.arete.headless_sa_analise import _link_bare_slab_levels_from_floor_band


def test_links_only_plausible_floor_level_inside_slab_polygon():
    slabs = [{
        "name": "L1",
        "pos": (5, 5),
        "points": [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
        "fields": {},
        "links": {"laje_nivel": {"label": []}},
    }]
    texts = [
        {"text": "852.12", "pos": (7, 7), "layer": "3"},
        {"text": "305.5", "pos": (5, 5), "layer": "3"},
        {"text": "852.19", "pos": (20, 20), "layer": "3"},
    ]

    assert _link_bare_slab_levels_from_floor_band(
        slabs, texts, level_exit=848.98, level_arrival=852.19,
    ) == 1
    assert slabs[0]["fields"]["laje_nivel"] == "852.12"
    assert slabs[0]["links"]["laje_nivel"]["label"][0]["source"] == (
        "floor_band_polygon_containment"
    )
