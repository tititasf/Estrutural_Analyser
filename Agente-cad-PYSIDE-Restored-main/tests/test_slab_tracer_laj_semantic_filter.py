from src.core.slab_tracer import SlabTracer
from src.core.spatial_index import SpatialIndex


def _insert_line(si, start, end, layer="VIGA"):
    item = {"start": start, "end": end, "layer": layer, "type": "LINE"}
    si.insert(item, (min(start[0], end[0]), min(start[1], end[1]), max(start[0], end[0]), max(start[1], end[1])))


def _insert_poly(si, points, layer="VIGA"):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    si.insert({"points": points, "layer": layer, "type": "LWPOLYLINE"}, (min(xs), min(ys), max(xs), max(ys)))


def test_semantic_filter_keeps_simple_rectangle():
    si = SpatialIndex()
    _insert_poly(si, [(0, 0), (100, 0), (100, 80), (0, 80), (0, 0)], "VIGA")
    poly = SlabTracer(si).trace_boundary((50, 40))
    assert round(poly.area, 1) == 8000.0


def test_deformed_laje_does_not_become_rectangle():
    si = SpatialIndex()
    pts = [(0, 0), (120, 0), (120, 60), (80, 90), (0, 90), (0, 0)]
    _insert_poly(si, pts, "VIGA")
    poly = SlabTracer(si).trace_boundary((50, 40))
    assert len(list(poly.exterior.coords)) == 6
    assert round(poly.area, 1) == 10200.0


def test_small_informative_beam_notch_is_removed_from_outline():
    si = SpatialIndex()
    pts = [
        (0, 0), (420, 0), (420, 190),
        (260, 190), (260, 70), (205, 70), (205, 190),
        (0, 190), (0, 0),
    ]
    _insert_poly(si, pts, "VIGA")
    poly = SlabTracer(si).trace_boundary((100, 100))
    assert round(poly.area, 1) == 79800.0
    assert len(list(poly.exterior.coords)) == 5


def test_dimension_crossing_laje_is_rejected_from_contour():
    si = SpatialIndex()
    _insert_poly(si, [(0, 0), (100, 0), (100, 80), (0, 80), (0, 0)], "VIGA")
    _insert_line(si, (-10, 40), (110, 40), "COTA")
    tracer = SlabTracer(si)
    poly = tracer.trace_boundary((50, 20))
    assert round(poly.area, 1) == 8000.0
    assert tracer.last_trace_diagnostics["rejected_line_count"] == 1


def test_unclassified_dimension_crossing_does_not_split_slab_face():
    si = SpatialIndex()
    _insert_poly(si, [(0, 0), (100, 0), (100, 80), (0, 80), (0, 0)], "VIGA")
    _insert_line(si, (-10, 40), (110, 40), "VIGA")
    tracer = SlabTracer(si)
    poly = tracer.trace_boundary((50, 20), label_id="L301")
    assert round(poly.area, 1) == 8000.0
    assert tracer.last_trace_diagnostics["outline_source"] == "n2_axes"


def test_informative_beam_cut_is_rejected_from_contour():
    si = SpatialIndex()
    _insert_poly(si, [(0, 0), (100, 0), (100, 80), (0, 80), (0, 0)], "VIGA")
    _insert_poly(si, [(10, 10), (30, 10), (30, 25), (10, 25), (10, 10)], "CORTE_VIGA")
    tracer = SlabTracer(si)
    poly = tracer.trace_boundary((50, 40))
    assert round(poly.area, 1) == 8000.0
    assert tracer.last_trace_diagnostics["rejected_line_count"] == 1
