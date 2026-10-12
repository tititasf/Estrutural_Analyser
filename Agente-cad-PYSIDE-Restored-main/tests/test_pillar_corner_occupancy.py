import pytest

from src.core.pillar_abcd_tables import prune_beams_without_face_occupancy


@pytest.mark.parametrize("vertical", [True, False])
@pytest.mark.parametrize("short", ["C", "D"])
@pytest.mark.parametrize("long", ["A", "B"])
@pytest.mark.parametrize("gap", [0.0, 5.0])
def test_corner_dual_preserves_all_physical_corners_but_not_gaps(vertical, short, long, gap):
    bbox = (100., 200., 119., 314.) if vertical else (100., 200., 214., 219.)
    x0, y0, x1, y1 = bbox
    if vertical:
        cx = x0 if long == "A" else x1
        cy = y1 if short == "C" else y0
        lo, hi = (cy - 19 - gap, cy - gap) if short == "C" else (cy + gap, cy + 19 + gap)
        run = (cx - 100, lo, cx, hi) if long == "A" else (cx, lo, cx + 100, hi)
    else:
        cx = x0 if short == "C" else x1
        cy = y0 if long == "A" else y1
        lo, hi = (cx + gap, cx + 19 + gap) if short == "C" else (cx - 19 - gap, cx - gap)
        run = (lo, cy - 100, hi, cy) if long == "A" else (lo, cy, hi, cy + 100)
    tables = {face: {"passa": [], "chega": []} for face in "ABCD"}
    tables[long]["chega"] = [{"nome": "VX", "canto": long + short}]
    tables[short]["passa"] = [{"nome": "VX", "canto": short + long}]
    beam = {"name": "VX", "_recovered_corridor": run, "dim": "19/50", "is_h": vertical}
    prune_beams_without_face_occupancy(tables, bbox, [beam], vertical=vertical)
    assert bool(tables[short]["passa"]) is (gap == 0)
