from scripts.motor_reverso_laj import (
    _extract_obstacles,
    _filter_obstacles_by_outline,
    is_spurious_laj_obstacle,
    sanitize_laj_obstacles,
)


def test_spurious_5x5_tick_is_rejected():
    """Ticks de cota / diagonais 5×5 não são obstáculos reais (quadradinhos amarelos N4)."""
    spur = {
        "x": 171.5,
        "y": 7.37,
        "width": 5.0,
        "height": 5.0,
        "coords": [[171.5, 7.37], [176.5, 12.37]],
    }
    real = {"x": 10.0, "y": 10.0, "width": 80.0, "height": 19.0, "coords": [
        [10, 10], [90, 10], [90, 29], [10, 29], [10, 10]
    ]}
    assert is_spurious_laj_obstacle(spur) is True
    assert is_spurious_laj_obstacle(real) is False
    cleaned = sanitize_laj_obstacles([spur, real, {"width": 5, "height": 5}])
    assert len(cleaned) == 1
    assert cleaned[0]["width"] == 80.0


def test_extract_rejects_tiny_diagonal_polyline():
    slab_box = (0.0, 0.0, 300.0, 100.0)
    outline = [[0, 0], [300, 0], [300, 100], [0, 100], [0, 0]]
    # Diagonal 5cm no miolo — bbox ~5×5
    polylines = [
        ("3", [(50.0, 50.0), (55.0, 55.0)]),
        (
            "3",
            [
                (100.0, 40.0),
                (180.0, 40.0),
                (180.0, 59.0),
                (100.0, 59.0),
                (100.0, 40.0),
            ],
        ),
    ]
    obstacles = _extract_obstacles(polylines, slab_box, outline)
    assert len(obstacles) == 1
    assert obstacles[0]["width"] == 80.0


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


def test_filter_outline_also_drops_spurious_5x5():
    outline = [
        [0.0, 0.0],
        [200.0, 0.0],
        [200.0, 100.0],
        [0.0, 100.0],
        [0.0, 0.0],
    ]
    obstacles = [
        {"x": 50.0, "y": 40.0, "width": 5.0, "height": 5.0},
        {"x": 20.0, "y": 30.0, "width": 80.0, "height": 19.0},
    ]
    kept = _filter_obstacles_by_outline(obstacles, outline)
    assert len(kept) == 1
    assert kept[0]["width"] == 80.0
