import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gerar_lj_dxf_stog.py"
SPEC = importlib.util.spec_from_file_location("gerar_lj_dxf_stog", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_rejects_obstacle_whose_center_is_outside_slab_polygon():
    polygon = [(0.0, 49.0), (100.0, 49.0), (100.0, 100.0), (0.0, 100.0)]
    obstacle = {"x": 10.0, "y": 10.0, "width": 20.0, "height": 19.0}

    assert not MODULE._obstacle_is_inside_polygon(obstacle, polygon, 0.0, 0.0)


def test_keeps_obstacle_whose_center_is_inside_slab_polygon():
    polygon = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
    obstacle = {"x": 10.0, "y": 10.0, "width": 20.0, "height": 19.0}

    assert MODULE._obstacle_is_inside_polygon(obstacle, polygon, 0.0, 0.0)


def test_short_vertical_segments_move_dimension_chain_outside(monkeypatch):
    calls = []
    monkeypatch.setattr(MODULE, "add_dim_on_paineis", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        MODULE,
        "add_dim_vertical_on_paineis",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    MODULE._add_reference_dimensions(
        object(), 100.0, 200.0, 234.0, 71.0, [117.0], [35.5], []
    )

    assert len(calls) == 2
    assert all(call[0][3] < 100.0 for call in calls)
    assert all(call[0][4] == 100.0 for call in calls)
    assert calls[0][1]["text_location"][0] != calls[1][1]["text_location"][0]


def test_regular_vertical_segments_keep_internal_dimension_chain(monkeypatch):
    calls = []
    monkeypatch.setattr(MODULE, "add_dim_on_paineis", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        MODULE,
        "add_dim_vertical_on_paineis",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    MODULE._add_reference_dimensions(
        object(), 100.0, 200.0, 406.0, 613.0, [122.0, 264.0], [179.0, 331.0], []
    )

    assert calls
    assert all(call[0][3] > 100.0 for call in calls)
