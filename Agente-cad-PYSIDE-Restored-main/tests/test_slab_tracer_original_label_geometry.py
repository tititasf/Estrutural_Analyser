from shapely.geometry import Point, Polygon
from src.core.slab_tracer import SlabTracer
from src.core.spatial_index import SpatialIndex


def test_noded_duplicate_corner_cannot_create_triangle_or_lose_label():
    polygon = Polygon([(60, .0000005), (59.9999995, 0), (40, 0),
                       (40, .0000005), (39.9999995, 0), (0, 0),
                       (0, 99.9999995), (0, 100), (40, 100), (45, 100),
                       (55, 100), (60, 100), (200, 100), (200, 0),
                       (60, 0), (60, .0000005)])
    label = Point(20, 80)
    result = SlabTracer(SpatialIndex())._clean_small_orthogonal_notches(polygon, label)
    assert result.covers(label)
    assert abs(result.area - polygon.area) < .001
    assert len(result.exterior.coords) == 5


def test_real_diagonal_outline_is_preserved():
    polygon = Polygon([(0, 0), (100, 0), (100, 50), (50, 100), (0, 100)])
    result = SlabTracer(SpatialIndex())._clean_small_orthogonal_notches(polygon, Point(20, 20))
    assert result.equals(polygon)


def test_near_duplicate_corner_rotation_translation_preserves_own_label():
    source = [(60, .0000005), (59.9999995, 0), (40, 0),
              (40, .0000005), (39.9999995, 0), (0, 0),
              (0, 99.9999995), (0, 100), (40, 100), (45, 100),
              (55, 100), (60, 100), (200, 100), (200, 0),
              (60, 0), (60, .0000005)]
    for rotation in range(4):
        def transform(point):
            x, y = point
            for _ in range(rotation):
                x, y = -y, x
            return x + 3700, y + 2700
        polygon = Polygon([transform(p) for p in source])
        label = Point(transform((20, 80)))
        result = SlabTracer(SpatialIndex())._clean_small_orthogonal_notches(polygon, label)
        assert result.covers(label)
        assert abs(result.area - polygon.area) < .001
