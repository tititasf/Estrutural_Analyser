from scripts.arete.pil_blind_l1_calibration import (
    check_directional_topology,
    expected_short_face_bridge_links,
)


def _seg(x0, y0, x1, y1):
    return {
        "type": "poly",
        "points": [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]],
    }


def test_qa_derives_four_directed_links_from_geometry_without_item_names():
    beams = {
        "VX": {
            "name": "VX",
            "links": {
                "fundo_area_segs": {
                    "contour": [
                        _seg(0, 0, 100, 19),
                        _seg(119, 0, 220, 19),
                    ]
                }
            },
        }
    }
    expected = expected_short_face_bridge_links(beams, 100, 0, 119, 98)
    assert expected == {
        ("D", "passa", "VX", "DA"),
        ("D", "passa", "VX", "DB"),
        ("A", "chega", "VX", "AD"),
        ("B", "chega", "VX", "BD"),
    }

    incomplete = {
        "A": {"passa_esq": None, "passa_dir": None, "para": []},
        "B": {"passa_esq": None, "passa_dir": None, "para": []},
        "C": {"passa_esq": None, "passa_dir": None, "para": []},
        "D": {
            "passa_esq": {"name": "VX", "corner": "DA"},
            "passa_dir": None,
            "para": [],
        },
    }
    issues = check_directional_topology(beams, 100, 0, 119, 98, incomplete)
    assert any("A.chega VX@AD" in issue for issue in issues)
    assert any("B.chega VX@BD" in issue for issue in issues)
    assert any("D.passa VX@DB" in issue for issue in issues)
