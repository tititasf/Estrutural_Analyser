import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from src.ui.modules.comparison_engine import (
    LevelColumn,
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
