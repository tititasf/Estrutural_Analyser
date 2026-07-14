from pathlib import Path

from src.core.recorte_motor import RecorteMotor


def _motor(tmp_path: Path) -> RecorteMotor:
    source = tmp_path / "shared-lv-frame.dxf"
    source.touch()
    motor = RecorteMotor(source, er_type="LV")
    motor._pkl = {
        "lines": [],
        "polylines": [],
        "texts": [],
        "hatches": [],
        "circles": [],
    }
    return motor


def test_partitioned_lv_clips_crossing_geometry_at_item_boundary(tmp_path: Path):
    motor = _motor(tmp_path)
    bbox = (10.0, 0.0, 20.0, 10.0)
    motor._lv_partitioned_bboxes.add(bbox)
    motor._pkl["lines"] = [
        {"start": (0.0, 5.0), "end": (20.0, 5.0), "layer": "COTA"},
    ]
    motor._pkl["polylines"] = [
        {
            "points": [(0.0, 2.0), (15.0, 2.0), (15.0, 8.0)],
            "closed": False,
            "layer": "PAINEL",
        },
    ]
    motor._pkl["hatches"] = [
        {
            "paths": [[(0.0, 1.0), (20.0, 1.0), (20.0, 9.0), (0.0, 9.0)]],
            "layer": "HACHURA",
            "solid": True,
        },
    ]

    entities = motor._collect_in_bboxes([bbox])

    points = []
    for kind, entity in entities:
        if kind == "line":
            points.extend((entity["start"], entity["end"]))
        elif kind == "poly":
            points.extend(entity["points"])
        elif kind == "hatch":
            points.extend(point for path in entity["paths"] for point in path)
    assert points
    assert min(float(point[0]) for point in points) == 10.0
    assert max(float(point[0]) for point in points) == 20.0


def test_regular_single_item_lv_keeps_complete_crossing_entity(tmp_path: Path):
    motor = _motor(tmp_path)
    bbox = (10.0, 0.0, 20.0, 10.0)
    line = {"start": (0.0, 5.0), "end": (20.0, 5.0), "layer": "COTA"}
    motor._pkl["lines"] = [line]

    entities = motor._collect_in_bboxes([bbox])

    assert entities == [("line", line)]
