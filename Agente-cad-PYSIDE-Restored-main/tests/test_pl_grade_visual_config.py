from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from pl_grade_visual_config import (  # noqa: E402
    DEFAULT_PROFILES,
    distances_to_positions,
    load_profiles,
    positions_for_mode,
    positions_to_distances,
    save_profiles,
)


def test_reference_profiles_match_robo_grades():
    assert positions_for_mode("INI") == [
        60.0, 170.0, 280.0, 390.0, 500.0, 610.0, 720.0, 830.0, 940.0,
    ]
    assert positions_for_mode("nova") == [
        30.0, 120.0, 210.0, 300.0, 390.0, 480.0, 720.0, 830.0, 940.0,
    ]


def test_ui_distances_round_trip_to_accumulated_positions():
    positions = [30.0, 120.0, 210.0, 300.0, 390.0, 480.0, 720.0]
    distances = positions_to_distances(positions)
    assert distances == [30.0, 90.0, 90.0, 90.0, 90.0, 90.0, 240.0]
    assert distances_to_positions(distances) == positions


def test_profiles_are_saved_atomically_and_reloaded(tmp_path):
    path = tmp_path / "profiles.json"
    profiles = json.loads(json.dumps(DEFAULT_PROFILES))
    profiles["modos"]["INI"]["horizontal_positions_cm"] = [45, 145, 245]
    profiles["modos"]["NOVA"]["horizontal_positions_cm"] = [25, 100, 175]

    assert save_profiles(profiles, path) == path
    assert not path.with_suffix(".json.tmp").exists()
    loaded = load_profiles(path)
    assert loaded["modos"]["INI"]["horizontal_positions_cm"] == [45.0, 145.0, 245.0]
    assert loaded["modos"]["NOVA"]["horizontal_positions_cm"] == [25.0, 100.0, 175.0]


@pytest.mark.parametrize(
    ("mode", "expected_lower_edges"),
    [
        ("INI", {62.2, 172.2}),
        ("NOVA", {32.2, 122.2, 212.2}),
    ],
)
def test_draw_grades_uses_mode_specific_horizontal_positions(
    mode, expected_lower_edges,
):
    generator = importlib.import_module("gerar_pl_dxf_stog")
    doc = generator.setup_doc()
    msp = doc.modelspace()
    pj = {
        "nome": "P_TESTE",
        "comprimento": 80.0,
        "largura": 40.0,
        "altura": 280.0,
        "grade_1": 102.0,
        "grade_2": 62.0,
    }

    generator.draw_grades(
        msp, 0.0, 0.0, 102.0, 62.0, 80.0, 40.0, 280.0,
        "P_TESTE", pj, visual_mode=mode,
    )

    horizontal_edges = {
        round(entity.dxf.start.y, 1)
        for entity in msp.query('LINE[layer=="SARR_2.2x10"]')
        if abs(entity.dxf.start.y - entity.dxf.end.y) < 1e-6
    }
    assert expected_lower_edges <= horizontal_edges
    other_mode_first = 32.2 if mode == "INI" else 62.2
    assert other_mode_first not in horizontal_edges


def test_vertical_height_uses_abcd_top_and_only_affected_opening_width():
    generator = importlib.import_module("gerar_pl_dxf_stog")
    pj = {
        "altura": 280.0,
        "h1_geom_A": 0.0,
        "paineis_intervals_A": [122.0, 97.0, 26.0, 15.0, 40.0],
        "abertura_A_1": {
            "lado": "esquerdo", "largura": 11.0,
            "y_rel": 260.0, "altura": 40.0,
        },
        "abertura_A_2": {
            "lado": "direito", "largura": 29.0,
            "y_rel": 260.0, "altura": 40.0,
        },
    }

    assert generator._grade_face_panel_top(pj, "A", 280.0) == 280.0
    assert generator._grade_vertical_height(pj, "A", 3.5, 102.0, 280.0) == 242.8
    assert generator._grade_vertical_height(pj, "A", 51.0, 102.0, 280.0) == 262.8
    assert generator._grade_vertical_height(pj, "A", 76.5, 102.0, 280.0) == 242.8
    assert generator._grade_vertical_height(pj, "A", 98.5, 102.0, 280.0) == 242.8


def test_draw_grades_materializes_independent_vertical_heights():
    generator = importlib.import_module("gerar_pl_dxf_stog")
    doc = generator.setup_doc()
    msp = doc.modelspace()
    pj = {
        "nome": "P28",
        "comprimento": 80.0,
        "largura": 24.0,
        "altura": 280.0,
        "h1_geom_A": 0.0,
        "h1_geom_B": 0.0,
        "paineis_intervals_A": [122.0, 97.0, 26.0, 15.0, 40.0],
        "paineis_intervals_B": [122.0, 97.0, 26.0, 15.0, 40.0],
        "abertura_A_1": {"lado": "esquerdo", "largura": 11.0, "y_rel": 260.0, "altura": 40.0},
        "abertura_A_2": {"lado": "direito", "largura": 29.0, "y_rel": 260.0, "altura": 40.0},
    }

    generator.draw_grades(
        msp, 0.0, 0.0, 102.0, 88.0, 80.0, 24.0, 280.0,
        "P28", pj, visual_mode="NOVA",
    )
    lengths = {
        round(abs(line.dxf.end.y - line.dxf.start.y), 1)
        for line in msp.query('LINE[layer=="SARR_3.5x7"]')
        if abs(line.dxf.end.x - line.dxf.start.x) < 1e-6
        and abs(line.dxf.end.y - line.dxf.start.y) > 50
    }
    assert 242.8 in lengths
    assert 262.8 in lengths


def test_only_global_grade_extremities_use_seven_centimeters():
    generator = importlib.import_module("gerar_pl_dxf_stog")
    doc = generator.setup_doc()
    msp = doc.modelspace()
    pj = {
        "nome": "P_LONGO", "comprimento": 200.0, "largura": 24.0,
        "altura": 280.0, "paineis_intervals_A": [280.0],
        "paineis_intervals_B": [280.0],
    }
    generator.draw_grades(
        msp, 0.0, 0.0, 0.0, 0.0, 200.0, 24.0, 280.0,
        "P_LONGO", pj, visual_mode="NOVA",
    )
    vertical_sides = [
        line for line in msp.query('LINE[layer=="SARR_2.2x7"]')
        if abs(line.dxf.end.x - line.dxf.start.x) < 1e-6
        and abs(line.dxf.end.y - line.dxf.start.y) > 50
    ]
    # Dois retângulos externos por face A/B, duas laterais LINE por retângulo.
    assert len(vertical_sides) == 8


@pytest.mark.parametrize(("width", "has_short_faces"), [(49.9, False), (50.0, True)])
def test_faces_c_and_d_start_at_fifty_centimeters(width, has_short_faces):
    generator = importlib.import_module("gerar_pl_dxf_stog")
    doc = generator.setup_doc()
    msp = doc.modelspace()
    pj = {
        "nome": "P_CD", "comprimento": 60.0, "largura": width,
        "altura": 280.0,
        "paineis_intervals_A": [280.0], "paineis_intervals_B": [280.0],
        "paineis_intervals_C": [280.0], "paineis_intervals_D": [280.0],
    }
    generator.draw_grades(
        msp, 0.0, 0.0, 0.0, 0.0, 60.0, width, 280.0,
        "P_CD", pj, visual_mode="NOVA",
    )
    labels = {entity.dxf.text for entity in msp.query("TEXT")}
    assert ("P_CD.C" in labels and "P_CD.D" in labels) is has_short_faces
