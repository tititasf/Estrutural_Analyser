from pathlib import Path

from src.core.recorte_motor import RecorteMotor, _constrain_laj_bbox_to_neighbor_cells


def _motor(tmp_path):
    source = Path(tmp_path) / "fonte.dxf"
    source.touch()
    motor = RecorteMotor(source, er_type="LAJ")
    motor._pkl = {"texts": [], "lines": [], "polylines": []}
    motor._laj_geometry_layers = lambda **_kwargs: {"PAINEIS"}
    return motor


def test_laj_stog_dimensions_use_only_the_local_label_cell(tmp_path):
    motor = _motor(tmp_path)
    # L1 and L2 share the dimension row. Without the centroid cell boundary,
    # their four values would be summed into one contaminated L1 width.
    motor._pkl["texts"] = [
        {"layer": "PAINEIS", "text": "156.5", "pos": (110, 230), "rotation": 0},
        {"layer": "PAINEIS", "text": "238.5", "pos": (300, 230), "rotation": 0},
        {"layer": "PAINEIS", "text": "168.5", "pos": (520, 230), "rotation": 0},
        {"layer": "PAINEIS", "text": "220.5", "pos": (710, 230), "rotation": 0},
        {"layer": "PAINEIS", "text": "35.5", "pos": (180, 180), "rotation": 90},
        {"layer": "PAINEIS", "text": "35.5", "pos": (200, 220), "rotation": 90},
    ]
    received = {}

    def _expected(cx, cy, width, height):
        received.update(width=width, height=height)
        return (cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2)

    motor._laj_bbox_from_expected_dimensions = _expected
    bbox = motor._laj_bbox_from_stog_dimensions(
        "L1",
        200,
        200,
        all_centroids={"L1": (200, 200), "L2": (650, 200)},
    )

    assert received == {"width": 395.0, "height": 71.0}
    # The small lateral allowance preserves local support/hatch evidence.
    assert bbox == (-3.5, 164.5, 403.5, 235.5)


def test_laj_stog_dimensions_reject_candidate_that_captures_neighbor_label(tmp_path):
    motor = _motor(tmp_path)
    motor._pkl["texts"] = [
        {"layer": "PAINEIS", "text": "100", "pos": (160, 230), "rotation": 0},
        {"layer": "PAINEIS", "text": "100", "pos": (240, 230), "rotation": 0},
        {"layer": "PAINEIS", "text": "35", "pos": (180, 180), "rotation": 90},
        {"layer": "PAINEIS", "text": "35", "pos": (200, 220), "rotation": 90},
    ]
    motor._laj_bbox_from_expected_dimensions = lambda *_args: (100, 150, 520, 250)

    assert motor._laj_bbox_from_stog_dimensions(
        "L1",
        200,
        200,
        all_centroids={"L1": (200, 200), "L2": (450, 200)},
    ) is None


def test_laj_bbox_prefers_good_stog_evidence_over_legacy_n1(tmp_path):
    motor = _motor(tmp_path)
    independent = (0, 0, 100, 100)
    legacy = (0, 0, 300, 300)
    scores = {independent: 85.0, legacy: 99.0}
    motor._collect_in_bboxes = lambda _bboxes: [
        ("line", {"start": (0, 0), "end": (1, 1)})
    ]
    motor._compute_laj_confidence = lambda _ents, **kwargs: scores[kwargs["search_bboxes"][0]]

    assert motor._choose_laj_bbox(
        "L1", [(50, 50)], independent_bboxes=(independent,), legacy_bbox=legacy
    ) == independent


def test_laj_bbox_uses_legacy_only_when_independent_evidence_is_weak(tmp_path):
    motor = _motor(tmp_path)
    independent = (0, 0, 100, 100)
    legacy = (0, 0, 300, 300)
    scores = {independent: 60.0, legacy: 90.0}
    motor._collect_in_bboxes = lambda _bboxes: [
        ("line", {"start": (0, 0), "end": (1, 1)})
    ]
    motor._compute_laj_confidence = lambda _ents, **kwargs: scores[kwargs["search_bboxes"][0]]

    assert motor._choose_laj_bbox(
        "L1", [(50, 50)], independent_bboxes=(independent,), legacy_bbox=legacy
    ) == legacy


def test_laj_bbox_rejects_long_thin_structural_span(tmp_path):
    motor = _motor(tmp_path)
    # A prancha pode ter uma linha estrutural que cruza varios paineis. Mesmo
    # com entidades suficientes, ela nao pode vencer o fallback local.
    span = (0, 0, 3000, 90)
    motor._collect_in_bboxes = lambda _bboxes: [
        ("line", {"start": (0, 0), "end": (1, 1)})
    ]

    assert motor._choose_laj_bbox(
        "L1", [(50, 50)], independent_bboxes=(span,), legacy_bbox=None
    ) is None


def test_laj_bbox_prefers_compact_local_stog_over_larger_structural_span(tmp_path):
    motor = _motor(tmp_path)
    structural = (0, 0, 500, 100)
    stog = (40, 10, 360, 90)
    motor._collect_in_bboxes = lambda _bboxes: [("line", {"start": (0, 0), "end": (1, 1)})]
    motor._compute_laj_confidence = lambda _ents, **_kwargs: 60.0

    assert motor._choose_laj_bbox(
        "L1",
        [(200, 50)],
        independent_bboxes=(structural, stog),
        legacy_bbox=None,
        preferred_bbox=stog,
    ) == stog


def test_laj_neighbor_cell_barrier_stops_thin_crop_before_lateral_neighbor():
    # L2 sits slightly above the strip, exactly the case missed by the old
    # "label inside bbox" guard. The crop must stop at the label-cell boundary.
    bbox = (0, 0, 700, 80)
    result = _constrain_laj_bbox_to_neighbor_cells(
        bbox,
        "L1",
        {"L1": (200, 40), "L2": (620, 95)},
    )

    assert result == (0.0, 0.0, 420.0, 80.0)
