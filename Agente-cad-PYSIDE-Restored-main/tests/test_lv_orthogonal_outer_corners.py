"""Paredes externas de encontros em L; interiores mantem G7."""
import pytest

from src.core.lv_beam_scene import LvScene, _attach_context, _orthogonal_outer_corners, _trim_end_pillars
from src.core.beam_interpreters.lateral_viga_cells import segment_cell


@pytest.mark.parametrize("horizontal", [True, False])
@pytest.mark.parametrize("side", ["A", "B"])
@pytest.mark.parametrize("end", ["start", "end"])
@pytest.mark.parametrize("behavior", ["para", "passa"])
def test_outer_l_wall_reaches_corner_without_extending_inner_wall(horizontal, side, end, behavior):
    own = LvScene("V1", horizontal, 0, 19, 0, 300)
    # Different depths do not remove the exposed exterior wall at the corner.
    own.sections = [dict(start=0, end=300, depth=120, dim="19/120")]
    transverse = (-19, 0) if end == "start" else (300, 319)
    axis = (19, 200) if side == "A" else (-200, 0)
    other = LvScene("V2", not horizontal, *transverse, *axis)
    other.sections = [dict(start=axis[0], end=axis[1], depth=50, dim="19/50")]
    own.face_coverage = {s: [[0, 300]] for s in ("A", "B")}
    own.face_coverage[side] = [[-19 if end == "start" else 0, 319 if end == "end" else 300]]
    _orthogonal_outer_corners(own, [own, other])
    _attach_context(own, [], [own, other], [])
    outer = segment_cell(own, side, behavior)
    assert min(min(s.start, s.end) for s in outer) == (-19 if end == "start" else 0)
    assert max(max(s.start, s.end) for s in outer) == (319 if end == "end" else 300)
    inner_side = "B" if side == "A" else "A"
    assert inner_side not in own.face_extent


@pytest.mark.parametrize("rejection", ["T", "crossing", "no_wall", "dimension", "parallel"])
def test_extension_requires_l_topology_and_source_wall(rejection):
    own = LvScene("V1", True, 0, 19, 0, 300)
    other = LvScene("V2", False, 300, 319, 19, 200)
    own.face_coverage["A"] = [[0, 319]]
    if rejection == "T":
        other.start = -100
    elif rejection == "crossing":
        other.start = -100
        other.t_lo, other.t_hi = 200, 219
    elif rejection == "no_wall":
        own.face_coverage["A"] = [[0, 300]]
    elif rejection == "dimension":
        own.face_coverage["A"] = [[0, 300]]
        own.dimension_coverage["A"] = [[300, 319]]
    else:
        other.is_horizontal = True
    _orthogonal_outer_corners(own, [own, other])
    assert not own.face_extent


@pytest.mark.parametrize("end", ["start", "end"])
def test_corner_extension_preserves_pillar_trim_at_opposite_end(end):
    own = LvScene("V1", True, 0, 19, 0, 300)
    own.face_extent["A"] = (-19, 300) if end == "start" else (0, 319)
    support = dict(name="P1", start=280, end=300) if end == "start" else dict(name="P1", start=0, end=20)
    own.pillars = {side: [dict(support)] for side in ("A", "B")}
    _trim_end_pillars(own)
    assert own.face_extent["A"] == ((-19, 280) if end == "start" else (20, 319))
