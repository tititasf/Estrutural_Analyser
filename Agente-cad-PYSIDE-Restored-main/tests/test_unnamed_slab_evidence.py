from src.core.slab_tracer import SlabTracer
from src.core.spatial_index import SpatialIndex


def tracer(points, layer='VIGA'):
    si = SpatialIndex()
    si.insert({'points': points, 'layer': layer, 'type': 'POLYLINE'}, (0, 0, 100, 80))
    return SlabTracer(si)


RECT = [(0, 0), (100, 0), (100, 80), (0, 80), (0, 0)]


def test_unnamed_slab_requires_thickness_and_closed_structural_geometry():
    seeds = [{'text': 'h=12', 'pos': (50, 40)}]
    slabs = tracer(RECT).detect_slabs_from_texts(seeds)
    assert len(slabs) == 1 and slabs[0]['area'] == 8000
    assert slabs[0]['trace_diagnostics']['generated_name']
    assert slabs[0]['trace_diagnostics']['source_text'] == 'h=12'
    assert not slabs[0]['is_validated']
    assert tracer(RECT[:-1]).detect_slabs_from_texts(seeds) == []
    assert tracer(RECT, 'COTA').detect_slabs_from_texts(seeds) == []
    assert tracer(RECT).detect_slabs_from_texts([{'text': 'h=12', 'pos': (150, 40)}]) == []


def test_unnamed_slab_deduplicates_agreement_rejects_conflicts_and_is_stable():
    seeds = [{'text': 'h=12', 'pos': (50, 40)}, {'text': 'h=12', 'pos': (20, 20)}]
    slabs = tracer(RECT).detect_slabs_from_texts(seeds)
    assert len(slabs) == 1
    assert tracer(list(reversed(RECT))).detect_slabs_from_texts(list(reversed(seeds)))[0]['name'] == slabs[0]['name']
    seeds[1]['text'] = 'h=15'
    assert tracer(RECT).detect_slabs_from_texts(seeds) == []
