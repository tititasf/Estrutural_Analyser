from scripts.smart_panner import cells_fit_sheet, distribute_panels, panel_fits_sheet


def _signature(lines):
    return [(line["value"], line["is_union"]) for line in lines]


def test_panel_fits_sheet_rule_244x122():
    assert panel_fits_sheet(244, 122) is True
    assert panel_fits_sheet(238, 122) is True
    assert panel_fits_sheet(244, 169) is False
    assert panel_fits_sheet(169, 244) is False
    assert panel_fits_sheet(122, 122) is True


def test_l408_shape_never_makes_244_by_169():
    """L408 real: 726×311 — proibido residual 169 no eixo Y com 244 no X."""
    result = distribute_panels(726.0, 311.0)
    assert _signature(result["linhas_horizontais"]) == [
        (122.0, False),
        (142.0, True),
        (264.0, False),
    ]
    assert cells_fit_sheet(
        result["linhas_verticais"],
        result["linhas_horizontais"],
        726.0,
        311.0,
    )


def test_311_span_caps_residual_to_fit_sheet_with_244():
    """311 no eixo menor: 122 + união + 122 + residual 47 (não 169)."""
    result = distribute_panels(405.5, 311.0)
    assert _signature(result["linhas_horizontais"]) == [
        (122.0, False),
        (142.0, True),
        (264.0, False),
    ]
    assert cells_fit_sheet(
        result["linhas_verticais"],
        result["linhas_horizontais"],
        405.5,
        311.0,
    )


def test_long_strip_183_splits_when_major_is_244():
    """Tira 183 com eixo longo em 244 não pode ficar sem junta (244×183)."""
    result = distribute_panels(405.5, 183.0)
    assert result["linhas_horizontais"]  # tem junta
    assert cells_fit_sheet(
        result["linhas_verticais"],
        result["linhas_horizontais"],
        405.5,
        183.0,
    )


def test_three_medium_panels_share_union_gaps():
    result = distribute_panels(418.0, 423.0)
    assert _signature(result["linhas_verticais"]) == [
        (122.0, False),
        (148.0, True),
        (270.0, False),
        (296.0, True),
    ]
    assert cells_fit_sheet(
        result["linhas_verticais"],
        result["linhas_horizontais"],
        418.0,
        423.0,
    )


def test_narrow_strip_is_bisected_on_both_axes_when_short_enough():
    result = distribute_panels(233.74, 71.0)
    assert _signature(result["linhas_verticais"]) == [(116.9, False)]
    assert _signature(result["linhas_horizontais"]) == [(35.0, False)]


def test_narrow_strip_prefers_multiple_of_five_and_residual():
    result = distribute_panels(233.74, 75.7)
    assert _signature(result["linhas_horizontais"]) == [(40.0, False)]
