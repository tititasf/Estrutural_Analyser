from portal.app.lv_segment_relations import pillar_passages


def test_only_long_parallel_faces_and_reading_order():
    pillars = [{"name": "P1", "points": [[20, 0], [80, 0], [80, 19], [20, 19]],
                "classification": "CONTINUA"}]
    forward = pillar_passages([[0, 0], [100, 0]], pillars, "passa")
    assert forward == [{"name": "P1", "face": "A", "distance_left_cm": 20,
                        "length_cm": 60, "distance_right_cm": 20}]
    reverse = pillar_passages([[90, 0], [0, 0]], pillars, "passa")
    assert reverse[0]["distance_left_cm"] == 10
    assert reverse[0]["distance_right_cm"] == 20
    assert pillar_passages([[80, -20], [80, 40]], pillars, "passa") == []
    assert pillar_passages([[0, 0], [100, 0]], pillars, "para") == []
    assert pillar_passages([[0, 10], [100, 10]], pillars, "passa") == []


def test_l_uses_actual_wall_and_excludes_its_short_c_and_d():
    pillars = [{"name": "P2", "points": [[0, 0], [165, 0], [165, 19],
                                           [19, 19], [19, 218], [0, 218]]}]
    rows = pillar_passages([[-10, 0], [200, 0]], pillars, "passa")
    assert rows == [{"name": "P2", "face": "E", "distance_left_cm": 10,
                     "length_cm": 165, "distance_right_cm": 35}]
    assert pillar_passages([[165, -10], [165, 100]], pillars, "passa") == []
    assert pillar_passages([[0, 100], [165, 100]], pillars, "passa") == []


def test_partial_wall_at_segment_end_and_pillar_born_here():
    pillar = {"name": "P1", "points": [[20, 0], [80, 0], [80, 19], [20, 19]]}
    rows = pillar_passages([[50, 0], [100, 0]], [pillar], "passa")
    assert rows[0]["length_cm"] == 30
    assert rows[0]["distance_left_cm"] == 0
    assert rows[0]["distance_right_cm"] == 20
    pillar["classification"] = "NASCE"
    assert pillar_passages([[50, 0], [100, 0]], [pillar], "passa") == []
