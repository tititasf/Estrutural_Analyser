from pathlib import Path

import ezdxf

from scripts.arete.pil_agentic_highlight_draw import render_agentic_svg
from scripts.arete.pil_blind_l1_calibration import (
    check_corner_occupancy,
    check_orientation_contract,
)
from src.core.pillar_abcd_tables import build_abcd_tables_from_pillar


def test_prefixed_horizontal_orientation_is_not_silently_downgraded_to_vertical():
    pillar = {
        "name": "PX",
        "orientation": "RETANGULAR HORIZONTAL",
        "points": [(0, 0), (100, 0), (100, 19), (0, 19), (0, 0)],
        "face_beams": {},
        "lajes": [],
    }

    tables = build_abcd_tables_from_pillar(pillar)

    assert tables["orientation"] == "horizontal"
    assert tables["faces"]["A"]["label"] == "A — base (sul) · face longa"


def test_qa_flags_horizontal_geometry_published_with_vertical_abcd_contract():
    issues = check_orientation_contract(
        [(0, 0), (100, 0), (100, 19), (0, 19), (0, 0)],
        {"orientation": "vertical"},
    )

    assert issues == ["orientação ABCD divergente: geometria=horizontal, tabela=vertical"]


def test_qa_flags_two_distinct_beams_occupying_same_face_corner():
    tables = {
        "faces": {
            "B": {
                "passa": [
                    {"nome": "V301", "canto": "BC"},
                    {"nome": "V309A", "canto": "BC"},
                ]
            }
        }
    }

    assert check_corner_occupancy(tables) == [
        "B.passa@BC: canto ocupado por múltiplas vigas ['V301', 'V309A']"
    ]


def test_empty_face_has_no_fake_placeholder_tag(tmp_path: Path):
    dxf_path = tmp_path / "empty.dxf"
    ezdxf.new("R2010").saveas(dxf_path)
    tables = {
        "orientation": "vertical",
        "faces": {
            face: {"lajes": [], "passa": [], "chega": [], "interior": []}
            for face in "ABCD"
        },
    }

    svg = render_agentic_svg(
        dxf_path,
        [(0, 0), (19, 0), (19, 98), (0, 98), (0, 0)],
        tables,
        layer="l2",
    )

    assert "A · —" not in svg
    assert "B · —" not in svg
    assert "C · —" not in svg
    assert "D · —" not in svg
