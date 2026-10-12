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


def test_dimension_inside_floor_band_never_becomes_elevation():
    s = {'points': [[0, 0], [10, 0], [10, 10], [0, 10]], 'fields': {}}
    assert _link_bare_slab_levels_from_floor_band([s], [
        {'text': '852.12', 'pos': (5, 5), 'annotation_role': 'dimension'}
    ], level_exit=848.98, level_arrival=852.19) == 0


def test_floor_band_accepts_zero_negative_and_small_altitudes():
    for raw in ('0.00', '-3.00', '12.50'):
        value = float(raw)
        s = {'points': [[0, 0], [10, 0], [10, 10], [0, 10]], 'fields': {}}
        assert _link_bare_slab_levels_from_floor_band([s], [{'text': raw, 'pos': (5, 5)}],
            level_exit=value-3, level_arrival=value) == 1
        assert s['fields']['laje_nivel'] == raw


def test_floor_band_conflict_does_not_choose_nearest_text():
    s = {'points': [[0, 0], [10, 0], [10, 10], [0, 10]], 'fields': {}}
    assert _link_bare_slab_levels_from_floor_band([s], [
        {'text': '852.12', 'pos': (5, 5)}, {'text': '852.19', 'pos': (6, 6)}
    ], level_exit=848.98, level_arrival=852.19) == 0
    assert s['_nivel_provenance']['needs_human_review'] is True
