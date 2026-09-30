import pytest

from scripts.arete.pil_agentic_highlight_draw import (
    CONTACT_MARKER_EDGE_WIDTH,
    CONTACT_MARKER_SIZE,
    FACE_WALL_OFFSET,
    TAG_FONT_SCALE,
    _arrival_nominal_distances,
    _beam_seg_on_face,
    _contact_tip,
    _route_tag_position,
    _segments_cross,
)


def _row(corner, dim="19/55", left="—", right="—"):
    return {"canto": corner, "dim": dim, "dist_esq": left, "dist_dir": right}


def test_vertical_corner_arrivals_use_nominal_width_from_correct_end():
    assert _arrival_nominal_distances("A", _row("AD"), 66, horizontal=False) == (47, 0)
    assert _arrival_nominal_distances("B", _row("BD"), 66, horizontal=False) == (0, 47)
    assert _arrival_nominal_distances("A", _row("AC"), 104, horizontal=False) == (0, 85)


def test_horizontal_bd_arrival_is_anchored_at_right_end():
    assert _arrival_nominal_distances("B", _row("BD"), 60, horizontal=True) == (41, 0)


def test_renderer_places_vertical_a_ad_at_bottom_beam_section():
    p0, p1, _ = _beam_seg_on_face(
        "A", "chega", _row("AD"), 0, 0, 19, 66, pad=10, horizontal=False
    )
    assert {p0[1], p1[1]} == {0, 19}


def test_explicit_measurement_still_has_priority_over_nominal_fallback():
    p0, p1, _ = _beam_seg_on_face(
        "A", "chega", _row("AD", left="14cm", right="33cm"),
        0, 0, 19, 66, pad=10, horizontal=False,
    )
    assert {p0[1], p1[1]} == {33, 52}


def test_pass_tip_is_exact_physical_corner_for_p49_equivalent_tags():
    box = (10, 20, 30, 80)
    p0, p1 = (10, 68), (10, 80)
    assert _contact_tip("A", "passa", _row("AC"), p0, p1, *box) == (10, 80)
    assert _contact_tip("B", "passa", _row("BC"), p0, p1, *box) == (30, 80)
    assert _contact_tip("C", "passa", _row("CA"), p0, p1, *box) == (10, 80)
    assert _contact_tip("A", "passa", _row("AD"), p0, p1, *box) == (10, 20)
    assert _contact_tip("B", "passa", _row("BD"), p0, p1, *box) == (30, 20)


def test_arrival_tip_is_centered_in_beam_band_not_moved_to_corner():
    box = (10, 20, 30, 80)
    p0, p1 = (10, 68), (10, 80)
    tip = _contact_tip("A", "chega", _row("AC"), p0, p1, *box)
    assert tip == pytest.approx((-0.8, 74))
    assert tip != (10, 80)


def test_interior_and_slab_tips_use_face_and_contact_centers():
    box = (10, 20, 30, 80)
    p0, p1 = (14, 80), (26, 80)
    assert _contact_tip("C", "interior", _row("CC"), p0, p1, *box) == (20, 80)
    assert _contact_tip("C", "laje", _row("CC"), p0, p1, *box) == (20, 80)


def test_visual_contract_uses_doubled_contact_dot_and_zero_face_offset():
    assert CONTACT_MARKER_SIZE == 1.4
    assert CONTACT_MARKER_EDGE_WIDTH == 0.3
    assert FACE_WALL_OFFSET == 0.0
    assert TAG_FONT_SCALE == 1.10


def test_connector_router_moves_tag_until_arrow_lines_do_not_cross():
    existing = [((0.0, 0.0), (4.0, 4.0))]
    routed = _route_tag_position(
        0.0, 4.0, (4.0, 0.0), 0.3, 0.2, [], existing,
        (0.0, 1.0), gap=0.1,
    )
    assert routed != (0.0, 4.0)
    assert not _segments_cross(routed, (4.0, 0.0), *existing[0])


def test_connectors_may_share_the_same_physical_tip_without_false_crossing():
    assert not _segments_cross((0, 0), (5, 5), (10, 0), (5, 5))


def test_connector_router_keeps_whole_tag_inside_viewbox_bounds():
    routed = _route_tag_position(
        9.8, 9.8, (5.0, 5.0), 1.0, 0.5, [], [], (1.0, 1.0),
        gap=0.2, bounds=(0.0, 0.0, 10.0, 10.0),
    )
    assert 1.0 <= routed[0] <= 9.0
    assert 0.5 <= routed[1] <= 9.5
