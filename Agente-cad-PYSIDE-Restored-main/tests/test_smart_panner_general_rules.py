from scripts.smart_panner import distribute_panels


def _signature(lines):
    return [(line["value"], line["is_union"]) for line in lines]


def test_minor_span_anchors_small_panel_and_union_at_end():
    result = distribute_panels(405.5, 183.0)
    assert _signature(result["linhas_horizontais"]) == [
        (102.0, False),
        (122.0, True),
    ]


def test_two_edge_panels_keep_central_union():
    result = distribute_panels(405.5, 311.0)
    assert _signature(result["linhas_horizontais"]) == [
        (122.0, False),
        (169.0, False),
        (189.0, True),
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
    assert _signature(result["linhas_horizontais"]) == [(35.5, False)]
