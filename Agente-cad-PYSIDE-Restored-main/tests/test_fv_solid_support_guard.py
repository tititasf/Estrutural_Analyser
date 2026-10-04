import copy

import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from src.core.beam_interpreters.fundo_viga_lateral_ref import (
    _panels, clip_automatic_bottoms_to_solid_pillars,
    complete_measured_junctions_all,
)


def beam(poly, **extra):
    return {"name": "V1", "fv_is_h": True, "fields": {}, "links": {
        "viga_fundo_seg_1_area_segs": {"contour": [dict(
            points=list(poly.exterior.coords), **extra)]}}}


def pillar(poly, **extra):
    return {"P1": dict(points=list(poly.exterior.coords), classification="SEGUE", **extra)}


def union(b):
    return unary_union([p for _, _, p in _panels(b)])


@pytest.mark.parametrize("solid", [box(1, 0, 99, 19), box(30, 5, 70, 14), box(0, 0, 20, 19)])
def test_exact_difference_tiny_fragments_holes_and_idempotence(solid):
    original = box(0, 0, 100, 19)
    b = beam(original)
    assert clip_automatic_bottoms_to_solid_pillars([b], pillar(solid))
    assert union(b).symmetric_difference(original.difference(solid)).area < 1e-8
    assert all(not p.interiors for _, _, p in _panels(b))
    saved = copy.deepcopy(b)
    assert clip_automatic_bottoms_to_solid_pillars([b], pillar(solid)) == {}
    assert b == saved


@pytest.mark.parametrize("extra", [{"validated": True}, {"geometry_source": "manual_svg"}])
def test_human_geometry_preserved_and_conflict_reported(extra):
    b = beam(box(0, 0, 100, 19), **extra)
    before = copy.deepcopy(b)
    assert clip_automatic_bottoms_to_solid_pillars([b], pillar(box(30, 0, 70, 19)))
    assert b == before


@pytest.mark.parametrize("classification,ignored", [("NASCE", False), ("SEGUE", True)])
def test_non_solid_never_blocks(classification, ignored):
    b = beam(box(0, 0, 100, 19))
    p = pillar(box(30, 0, 70, 19), ignore_in_beams=ignored)
    p["P1"]["classification"] = classification
    before = copy.deepcopy(b)
    assert clip_automatic_bottoms_to_solid_pillars([b], p) == {}
    assert b == before


def test_final_junction_pass_clips_rebuilt_geometry(monkeypatch):
    import src.core.lv_beam_scene as scene
    monkeypatch.setattr(scene, "build_scene_runs", lambda *a, **kw: {})
    b = beam(box(0, 0, 100, 19))
    solid = box(30, 0, 70, 19)
    complete_measured_junctions_all([b], [], [], pillar(solid))
    assert union(b).intersection(solid).area == 0


@pytest.mark.parametrize("panel,solid,expected", [
    ((1380.3825,2490.038,1603.3825,2509.038), (1572.8825,2490.038,1652.8825,2509.038),
     (1380.3825,2490.038,1572.8825,2509.038)),
    ((1622.3825,2490.038,2040.3825,2509.038), (1572.8825,2490.038,1652.8825,2509.038),
     (1652.8825,2490.038,2040.3825,2509.038)),
    ((4533.4,2661.038,4552.4,3207.038), (4533.3825,2601.038,4552.3825,2680.038), None),
])
def test_p18_p19_regression_real_coordinates(panel, solid, expected):
    b = beam(box(*panel))
    clip_automatic_bottoms_to_solid_pillars([b], pillar(box(*solid)))
    result = union(b)
    assert result.intersection(box(*solid)).area < 1e-8
    assert result.symmetric_difference(box(*panel).difference(box(*solid))).area < 1e-8
    if expected:
        assert result.bounds == pytest.approx(expected)
