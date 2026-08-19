from __future__ import annotations

from src.core import analysis_helpers
from src.core.pillar_geometry_recovery import repair_truncated_named_pillars_from_dxf


def _rect(x0: float, y0: float, width: float, height: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x0 + width, y0), (x0 + width, y0 + height), (x0, y0 + height), (x0, y0)]


def test_recovers_same_name_rectangular_continuation(monkeypatch):
    report = {
        "P13": {
            "name": "P13",
            "points": _rect(100, 200, 19, 26),
        }
    }
    monkeypatch.setattr(
        analysis_helpers,
        "detect_pilares_from_polylines",
        lambda *_: [
            {"name": "P13", "points": _rect(100, 40, 19, 98)},
            {"name": "P13", "points": _rect(95, 210, 80, 15)},
        ],
    )

    repaired = repair_truncated_named_pillars_from_dxf(report, polylines=[], texts=[])

    assert [item["item"] for item in repaired] == ["P13"]
    assert report["P13"]["bbox"] == (100.0, 40.0, 119.0, 138.0)
    assert report["P13"]["_geometry_repaired"]["to"]["long"] == 98.0


def test_does_not_replace_with_different_name_or_non_rectangular_candidate(monkeypatch):
    original = _rect(100, 200, 19, 26)
    report = {"P13": {"name": "P13", "points": original}}
    monkeypatch.setattr(
        analysis_helpers,
        "detect_pilares_from_polylines",
        lambda *_: [
            {"name": "P99", "points": _rect(100, 40, 19, 98)},
            {"name": "P13", "points": [(0, 0), (19, 0), (19, 98), (5, 60), (0, 0)]},
        ],
    )

    repaired = repair_truncated_named_pillars_from_dxf(report, polylines=[], texts=[])

    assert repaired == []
    assert report["P13"]["points"] == original
