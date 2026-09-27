from src.core.fundo_segment_levels import derive_fundo_segment_level


def test_fundo_uses_highest_level_of_geometrically_touching_slabs():
    segment = [(0, 0), (100, 0), (100, 20), (0, 20), (0, 0)]
    slabs = [
        {"name": "L1", "nivel": "852.12", "points": [(0, 20), (100, 20), (100, 80), (0, 80)]},
        {"name": "L2", "nivel": "852.19", "points": [(0, -60), (100, -60), (100, 0), (0, 0)]},
        {"name": "L99", "nivel": "999.00", "points": [(300, 300), (400, 300), (400, 400), (300, 400)]},
    ]

    result = derive_fundo_segment_level(segment, slabs)

    assert result == {
        "value": 852.19,
        "source": "highest_touching_slab",
        "slabs": ["L2"],
        "distance_cm": 0.0,
    }


def test_explicit_segment_level_has_priority_over_slab_inference():
    result = derive_fundo_segment_level(
        [(0, 0), (100, 0)],
        [{"name": "L1", "nivel": "852.19", "points": [(0, 0), (100, 0), (100, 50), (0, 50)]}],
        explicit_levels=("853,07",),
    )
    assert result == {
        "value": 853.07,
        "source": "explicit_beam_or_side",
        "slabs": [],
        "distance_cm": 0.0,
    }


def test_fundo_level_remains_unresolved_without_evidence():
    result = derive_fundo_segment_level([(0, 0), (100, 0)], [])
    assert result == {
        "value": None,
        "source": "unresolved",
        "slabs": [],
        "distance_cm": None,
    }


def test_edge_beam_uses_nearest_levelled_slab_with_distance_provenance():
    result = derive_fundo_segment_level(
        [(0, 0), (100, 0), (100, 10), (0, 10)],
        [
            {"name": "L1", "nivel": 850, "points": [(0, 30), (100, 30), (100, 80), (0, 80)]},
            {"name": "L2", "nivel": 851, "points": [(0, 130), (100, 130), (100, 180), (0, 180)]},
        ],
    )

    assert result == {
        "value": 850.0,
        "source": "nearest_levelled_slab",
        "slabs": ["L1"],
        "distance_cm": 20.0,
    }


def test_zero_is_a_valid_slab_level_but_not_an_unset_explicit_default():
    result = derive_fundo_segment_level(
        [(0, 0), (100, 0), (100, 10), (0, 10)],
        [{"name": "L0", "nivel": 0, "points": [(0, 20), (100, 20), (100, 80), (0, 80)]}],
        explicit_levels=(0, ""),
    )

    assert result["value"] == 0.0
    assert result["source"] == "highest_touching_slab"


def test_d61_estimated_beam_level_comes_before_nearest_slab_but_after_touching():
    fundo = [(0, 0), (100, 0), (100, 10), (0, 10)]
    far = [{"name": "L1", "nivel": 850, "points": [(0, 30), (100, 30), (100, 80), (0, 80)]}]
    result = derive_fundo_segment_level(fundo, far, estimated_levels=("851.5",))
    assert result["value"] == 851.5 and result["source"] == "estimated_beam_level"

    touching = [{"name": "L2", "nivel": 852, "points": [(0, 10), (100, 10), (100, 80), (0, 80)]}]
    result = derive_fundo_segment_level(fundo, touching, estimated_levels=("851.5",))
    assert result["value"] == 852.0 and result["source"] == "highest_touching_slab"


def test_d61_slabs_touching_counts_partial_touch_and_rejects_distant_slab():
    from src.core.fundo_segment_levels import slabs_touching

    face = [(0, 0), (200, 0)]
    slabs = [
        # toque parcial: so' encosta no ultimo trecho da face (D-57)
        {"name": "L1", "points": [(180, 0.5), (300, 0.5), (300, 100), (180, 100)]},
        {"name": "L2", "points": [(0, -300), (200, -300), (200, -200), (0, -200)]},
    ]
    assert slabs_touching(face, slabs) == ["L1"]
    assert slabs_touching([], slabs) is None
