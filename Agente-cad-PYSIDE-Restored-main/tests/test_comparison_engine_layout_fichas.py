import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gerar_lv_dxf_stog as lv_generator

from src.ui.modules.comparison_engine import (
    LevelColumn,
    DXFVectorView,
    NIVEL_DEFS,
    VisualModeSelector,
    _n3_structured_ficha_rows,
    _structured_ficha_rows,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_viewer_y_ratios_reduce_main_and_compare_by_exactly_25_percent():
    old_single = 0.70
    new_single = LevelColumn.SINGLE_VIEWER_SIZES[0] / sum(
        LevelColumn.SINGLE_VIEWER_SIZES
    )
    assert new_single == pytest.approx(old_single * 0.75)

    old_compare = 7 / 17
    outer_total = sum(LevelColumn.COMPARE_OUTER_STRETCH)
    new_compare = LevelColumn.COMPARE_OUTER_STRETCH[0] / outer_total
    new_main = (
        LevelColumn.COMPARE_OUTER_STRETCH[1]
        / outer_total
        * LevelColumn.COMPARE_INNER_STRETCH[0]
        / sum(LevelColumn.COMPARE_INNER_STRETCH)
    )
    assert new_compare == pytest.approx(old_compare * 0.75)
    assert new_main == pytest.approx(old_compare * 0.75)


def test_all_five_levels_keep_a_ficha_below_their_viewer(app):
    columns = [
        LevelColumn(level, title, bg, accent, description, mode)
        for level, title, bg, accent, description, mode in NIVEL_DEFS
    ]
    assert [column.nivel_id for column in columns] == [
        "N1", "N2", "N3", "N4", "N5"
    ]
    for column in columns:
        assert column.img_widget.minimumHeight() == 120
        assert column._splitter_vf.indexOf(column.img_widget) == 0
        assert column._ficha_scroll.parent() is not None
        assert column._splitter_vf.count() == 2
        column.deleteLater()


def test_structured_ficha_preserves_nested_characteristics():
    rows = _structured_ficha_rows(
        {
            "nome": "V10",
            "b_cm": 19,
            "h_cm": 45,
            "face_units": [
                {"side": "A", "panels": 3},
                {"side": "B", "panels": 2},
            ],
            "holes": [{"width": 20, "height": 30}],
            "confidence": 0.93,
        },
        "V10",
        "LV",
        title="FICHA N4",
        status="extraída",
        confidence=0.93,
        source="motor LV",
    )

    sections = [value for label, value in rows if label == "=="]
    labels = [label.strip() for label, _ in rows]
    assert "DIMENSÕES E NÍVEIS" in sections
    assert "COMPONENTES E DETALHAMENTO" in sections
    assert "VALIDAÇÃO E ORIGEM" in sections
    assert "Face units 1" in labels
    assert "Holes 1" in labels


def test_structured_ficha_accepts_numpy_arrays_without_ambiguous_truth_value():
    np = pytest.importorskip("numpy")

    rows = _structured_ficha_rows(
        {
            "name": "V303",
            "segments_rich": [
                {
                    "total_width": 437,
                    "panels": [{
                        "width": 193,
                        "vertices": np.array([], dtype=object),
                    }],
                }
            ],
            "empty_vertices": np.array([], dtype=object),
        },
        "V303",
        "FV",
        title="FICHA N4",
    )

    labels = [label.strip() for label, _ in rows]
    assert "Segments rich 1" in labels
    assert any(label == "Empty vertices" for label, _ in rows)


def test_n3_uses_n4_detail_contract_but_keeps_n1_lineage():
    rows = _n3_structured_ficha_rows(
        {
            "name": "V301",
            "total_width": 19,
            "segments_rich": [
                {"total_width": 244, "panels": [{"width": 244}]},
            ],
            "holes": [{"active": True, "width": 20}],
            "_sa_meta": {"completude_pct": 90},
        },
        "V301",
        "FV",
    )

    sections = [value for label, value in rows if label == "=="]
    values = [str(value) for _, value in rows]
    labels = [label.strip() for label, _ in rows]
    assert any("FICHA N3" in section for section in sections)
    assert "COMPONENTES E DETALHAMENTO" in sections
    assert "Segments rich 1" in labels
    assert "Holes 1" in labels
    assert "Structural Analyzer / N1" in values
    assert "90%" in values


def test_n3_and_n4_load_the_same_robot_visual_profile(app):
    settings = QSettings("AgenteCAD", "ComparisonEngine")
    keys = ["visual_mode/ROBOT/FV", "visual_mode/N3/FV", "visual_mode/N4/FV"]
    backup = {
        key: (settings.contains(key), settings.value(key))
        for key in keys
    }
    n3 = VisualModeSelector("N3", "#ff9900")
    n4 = VisualModeSelector("N4", "#aa77ff")
    try:
        settings.setValue("visual_mode/ROBOT/FV", "INI")
        n3.set_classe("FV")
        n4.set_classe("FV")
        assert n3.mode == "INI"
        assert n4.mode == "INI"

        n3.sync_mode("NOVA")
        n4.set_classe("FV")
        assert n4.mode == "NOVA"
    finally:
        for key, (existed, value) in backup.items():
            if existed:
                settings.setValue(key, value)
            else:
                settings.remove(key)
        n3.deleteLater()
        n4.deleteLater()


def test_lv_uses_three_independent_viewers_and_side_fichas(
    app, tmp_path, monkeypatch
):
    monkeypatch.setattr(DXFVectorView, "load_dxf", lambda *_args, **_kwargs: None)
    paths = {}
    for zone in ("Visão Corte", "Visão A", "Visão B"):
        path = tmp_path / f"{zone.replace(' ', '_')}.dxf"
        path.write_text("placeholder", encoding="utf-8")
        paths[zone] = (str(path), None)

    column = LevelColumn("N4", "Robô", "#221133", "#a855f7", "LV", "dxf")
    try:
        column.switch_to_lv_zones(
            paths,
            {
                "section_views": [{"h_section": 55, "h_A": 45, "h_B": 40}],
                "face_units": [
                    {"side": "A", "label": "V1.A", "panels": [{"width": 100}]},
                    {"side": "B", "label": "V1.B", "panels": [{"width": 90}]},
                ],
            },
        )
        assert list(column._zone_views) == ["Visão Corte", "Visão A", "Visão B"]
        assert list(column._zone_fichas) == ["Visão Corte", "Visão A", "Visão B"]
    finally:
        column.deleteLater()


def test_lv_face_units_are_horizontal_with_exact_50cm_gap(monkeypatch):
    calls = []

    def record_face(_msp, x0, y0, panels, _height, label, **_kwargs):
        calls.append((x0, y0, sum(panel["width"] for panel in panels), label))

    monkeypatch.setattr(lv_generator, "draw_lv_face", record_face)
    units = [
        {
            "side": "A",
            "label": "V1.A",
            "bbox": {"x_left": 0, "y_top": 200},
            "h_body": 40,
            "panels": [{"width": 100}],
        },
        {
            "side": "A",
            "label": "CONT. V1.A",
            "bbox": {"x_left": 0, "y_top": 100},
            "h_body": 45,
            "panels": [{"width": 80}],
        },
        {
            "side": "B",
            "label": "V1.B",
            "bbox": {"x_left": 500, "y_top": 200},
            "h_body": 35,
            "panels": [{"width": 70}],
        },
    ]

    lv_generator.draw_viga_lateral_face_units(
        None, 0, 0, "V1", units, view="A"
    )

    assert [call[0] for call in calls] == [0.0, 150.0]
    assert calls[1][0] - (calls[0][0] + calls[0][2]) == 50.0
    assert [call[3] for call in calls] == ["V1.A", "CONT. V1.A"]
