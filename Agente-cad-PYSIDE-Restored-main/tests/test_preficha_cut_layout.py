from src.ui.widgets.pre_validation_dialog import _cut_compact_width


def test_cut_information_columns_are_reduced_by_exactly_forty_percent():
    assert _cut_compact_width(210) == 126
    assert _cut_compact_width(230) == 138
    assert _cut_compact_width(276) == 166
    assert _cut_compact_width(220) == 132
    assert _cut_compact_width(300) == 180


def test_cut_viewer_width_is_not_passed_through_compaction():
    informational_total = sum(
        _cut_compact_width(width)
        for width in (210, 230, 276, 276, 220, 300)
    )

    assert informational_total == 908
