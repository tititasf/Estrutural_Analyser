from scripts.motor_reverso_laj import _extract_obstacles, _filter_obstacles_by_outline


def test_ignores_closed_polyline_inside_bbox_but_outside_real_outline():
    slab_box = (100.0, 200.0, 200.0, 300.0)
    outline = [
        [0.0, 49.0],
        [100.0, 49.0],
        [100.0, 100.0],
        [0.0, 100.0],
        [0.0, 49.0],
    ]
    polylines = [
        (
            "3",
            [
                (110.0, 210.0),
                (130.0, 210.0),
                (130.0, 229.0),
                (110.0, 229.0),
                (110.0, 210.0),
            ],
        )
    ]

    assert _extract_obstacles(polylines, slab_box, outline) == []


def test_keeps_closed_polyline_inside_real_outline():
    slab_box = (100.0, 200.0, 200.0, 300.0)
    outline = [
        [0.0, 0.0],
        [100.0, 0.0],
        [100.0, 100.0],
        [0.0, 100.0],
        [0.0, 0.0],
    ]
    polylines = [
        (
            "3",
            [
                (110.0, 210.0),
                (130.0, 210.0),
                (130.0, 229.0),
                (110.0, 229.0),
                (110.0, 210.0),
            ],
        )
    ]

    obstacles = _extract_obstacles(polylines, slab_box, outline)

    assert len(obstacles) == 1
    assert obstacles[0]["width"] == 20.0


def test_revalidates_obstacles_after_final_outline_replaces_dxf_bbox():
    outline = [
        [0.0, 49.0],
        [100.0, 49.0],
        [100.0, 100.0],
        [0.0, 100.0],
        [0.0, 49.0],
    ]
    obstacles = [{"x": 10.0, "y": 10.0, "width": 20.0, "height": 19.0}]

    assert _filter_obstacles_by_outline(obstacles, outline) == []
