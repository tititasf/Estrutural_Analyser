from shapely.geometry import LineString, Point, box

from src.core.slab_tracer import SlabTracer
from src.core.spatial_index import SpatialIndex


def _tracer():
    tracer = SlabTracer(SpatialIndex())
    tracer._local_dimension_values_near_laje = lambda point: [(100.0, 0.0, "100"), (80.0, 0.0, "80")]
    return tracer


def _rectangle_edges():
    return [LineString([(0, 0), (100, 0)]), LineString([(100, 0), (100, 80)]),
            LineString([(100, 80), (0, 80)]), LineString([(0, 80), (0, 0)])]


def test_dimensions_cannot_create_walls_from_unclassified_lines():
    edges = _rectangle_edges()
    result = _tracer()._outline_from_local_dimension_texts(
        edges, Point(50, 40), (-200, -200, 300, 300), box(-50, -50, 150, 150))
    assert result is None


def test_short_structural_witnesses_cannot_be_extended_into_walls():
    edges = [LineString([(0, 30), (0, 50)]), LineString([(100, 30), (100, 50)]),
             LineString([(40, 0), (60, 0)]), LineString([(40, 80), (60, 80)])]
    result = _tracer()._outline_from_local_dimension_texts(
        edges, Point(50, 40), (-200, -200, 300, 300), box(-50, -50, 150, 150),
        preferred_lines=edges)
    assert result is None


def test_dimensions_can_refine_a_contour_supported_by_four_real_edges():
    edges = _rectangle_edges()
    result = _tracer()._outline_from_local_dimension_texts(
        edges, Point(50, 40), (-200, -200, 300, 300), box(-50, -50, 150, 150),
        preferred_lines=edges)
    assert result is not None
    assert result.equals(box(0, 0, 100, 80))
