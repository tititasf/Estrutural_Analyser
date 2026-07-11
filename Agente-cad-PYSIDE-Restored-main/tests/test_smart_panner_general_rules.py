from scripts.smart_panner import distribute_panels


def _signature(lines):
    return [(line["value"], line["is_union"]) for line in lines]


def test_long_uniform_narrow_strip_avoids_artificial_transverse_union():
    result = distribute_panels(405.5, 183.0)
    assert _signature(result["linhas_horizontais"]) == []
    assert result["hlaz"] == [{"x": 0.0, "y": 102.0, "width": 405.5, "height": 20.0}]


def test_311_span_prefers_single_large_residual_over_sub_60_cut():
    result = distribute_panels(405.5, 311.0)
    assert _signature(result["linhas_horizontais"]) == [
        (122.0, False),
        (142.0, True),
    ]


def test_three_medium_panels_share_union_gaps():
    result = distribute_panels(418.0, 423.0)
    assert _signature(result["linhas_verticais"]) == [
        (122.0, False),
        (148.0, True),
        (270.0, False),
        (296.0, True),
    ]


def test_narrow_strip_is_bisected_on_both_axes_when_short_enough():
    result = distribute_panels(233.74, 71.0)
    assert _signature(result["linhas_verticais"]) == [(116.9, False)]
    assert _signature(result["linhas_horizontais"]) == [(35.0, False)]


def test_narrow_strip_prefers_multiple_of_five_and_residual():
    result = distribute_panels(233.74, 75.7)
    assert _signature(result["linhas_horizontais"]) == [(40.0, False)]
