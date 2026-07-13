import os
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gerar_lv_dxf_stog as lv_generator

from src.ui.modules.comparison_engine import (
    ComparisonEngineModule,
    LevelColumn,
    DXFVectorView,
    NIVEL_DEFS,
    TriLevelArea,
    VisualModeSelector,
    _n3_structured_ficha_rows,
    _structured_ficha_rows,
)


def test_n1_project_dxf_prefers_latest_duplicate_project(tmp_path, monkeypatch):
    db_path = tmp_path / "project_data.vision"
    old_dxf = tmp_path / "EL-Torre-0.dxf"
    latest_dxf = tmp_path / "torre_1.dxf"
    old_dxf.write_text("old", encoding="utf-8")
    latest_dxf.write_text("latest", encoding="utf-8")

    real_connect = sqlite3.connect
    with real_connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE projects ("
            "id TEXT, work_name TEXT, pavement_name TEXT, dxf_path TEXT, "
            "created_at TEXT, updated_at TEXT)"
        )
        conn.executemany(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    "old",
                    "Obra_TREINO_1",
                    "13_PAV",
                    str(old_dxf),
                    "2026-06-07 05:00:49",
                    "2026-06-07 05:00:49",
                ),
                (
                    "latest",
                    "Obra_TREINO_1",
                    "13_PAV",
                    str(latest_dxf),
                    "2026-06-26 14:03:23",
                    "2026-07-01 01:22:11",
                ),
            ],
        )

    monkeypatch.setattr(
        sqlite3, "connect", lambda _database: real_connect(db_path)
    )

    selected = TriLevelArea._find_n1_project_dxf(
        "Obra_TREINO_1", "13_PAV"
    )

    assert selected == latest_dxf


def test_compare_n1_keeps_full_map_and_focuses_the_slab(tmp_path):
    n1_path = tmp_path / "torre_1.dxf"
    n1_path.write_text("placeholder", encoding="utf-8")
    bbox = (2476.5, 2660.0, 2934.5, 3011.0)
    points = [[2496.5, 2680.0], [2914.5, 2680.0], [2914.5, 2991.0]]
    shown = []
    focused = []

    compare_view = SimpleNamespace(
        focus_on_bbox=lambda value, context_factor: focused.append(
            (value, context_factor)
        )
    )
    n3_column = SimpleNamespace(
        _n2_above_view=compare_view,
        show_n2_above=lambda path, **kwargs: shown.append((path, kwargs)),
    )
    fake = SimpleNamespace(
        _btn_comparar_n1=SimpleNamespace(isChecked=lambda: True),
        nav_sidebar=SimpleNamespace(
            _selected_classe="LJ",
            _selected_item="L312",
        ),
        tri_level=SimpleNamespace(
            _columns=[
                SimpleNamespace(_last_loaded_dxf=str(n1_path)),
                None,
                n3_column,
            ],
            _get_n1_bbox_for=lambda *_args: bbox,
            _get_lj_n1_points=lambda *_args: points,
        ),
    )

    assert ComparisonEngineModule._refresh_n3_compare_if_active(
        fake, "LJ", "L312"
    )
    assert shown[0][1]["cull_to_bbox"] is False
    assert shown[0][1]["highlight_points"] == points
    assert focused == [(bbox, 2.2)]


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


def test_n3_n4_and_n5_load_the_same_class_visual_profile(app):
    settings = QSettings("AgenteCAD", "ComparisonEngine")
    keys = [
        "visual_mode/ROBOT/FV",
        "visual_mode/N3/FV",
        "visual_mode/N4/FV",
        "visual_mode/N5/FV",
        "visual_mode/ROBOT/PL",
    ]
    backup = {
        key: (settings.contains(key), settings.value(key))
        for key in keys
    }
    n3 = VisualModeSelector("N3", "#ff9900")
    n4 = VisualModeSelector("N4", "#aa77ff")
    n5 = VisualModeSelector("N5", "#44ccff")
    try:
        settings.setValue("visual_mode/ROBOT/FV", "INI")
        n3.set_classe("FV")
        n4.set_classe("FV")
        n5.set_classe("FV")
        assert n3.mode == "INI"
        assert n4.mode == "INI"
        assert n5.mode == "INI"

        n3.sync_mode("NOVA")
        n4.set_classe("FV")
        n5.set_classe("FV")
        assert n4.mode == "NOVA"
        assert n5.mode == "NOVA"

        settings.setValue("visual_mode/ROBOT/FV", "INI")
        settings.setValue("visual_mode/ROBOT/PL", "NOVA")
        n5.set_classe("FV")
        assert n5.mode == "INI"
        n5.set_classe("PL")
        assert n5.mode == "NOVA"
    finally:
        for key, (existed, value) in backup.items():
            if existed:
                settings.setValue(key, value)
            else:
                settings.remove(key)
        n3.deleteLater()
        n4.deleteLater()
        n5.deleteLater()


def test_n4_visual_change_generates_candidate_and_syncs_n5():
    synced = []
    generated = []
    selector = lambda level: SimpleNamespace(
        sync_mode=lambda mode, value=level: synced.append((value, mode))
    )
    fake = SimpleNamespace(
        nav_sidebar=SimpleNamespace(
            _current_classe="FV",
            _selected_classe="FV",
            _selected_item="V301",
        ),
        _visual_mode_n3=selector("N3"),
        _visual_mode_n4=selector("N4"),
        _visual_mode_n5=selector("N5"),
        _seq_id=0,
        _on_gerar_n4=lambda *args, **kwargs: generated.append((args, kwargs)),
    )

    ComparisonEngineModule._on_visual_mode_changed(fake, "N4", "INI")

    assert synced == [("N3", "INI"), ("N5", "INI")]
    assert generated == [
        (("FV", "V301"), {"allow_validated_candidate": True})
    ]


def _fake_fv_n3_module(contract_path):
    pipeline_events = []
    started = []
    pipeline = SimpleNamespace(
        reset=lambda: pipeline_events.append(("reset",)),
        set_step=lambda *args: pipeline_events.append(args),
    )
    column = SimpleNamespace(
        pipeline=pipeline,
        set_ficha=lambda *_args: None,
        load_content=lambda *_args: None,
    )
    module = SimpleNamespace(
        _seq_id=1,
        _current_pav="13_PAV",
        _load_human_validated_level=lambda *_args: False,
        fase8_panel=SimpleNamespace(
            cmb_obra=SimpleNamespace(
                currentData=lambda: "Obra_TREINO_1",
                currentText=lambda: "Obra_TREINO_1",
            ),
        ),
        tri_level=SimpleNamespace(
            _columns=[None, None, column],
            _find_n3_dxf=lambda *_args: None,
            _ficha_n3_for=lambda *_args: [],
        ),
        nav_sidebar=SimpleNamespace(
            set_status=lambda *_args: None,
            _enable_item_btns=lambda: None,
        ),
        _materialize_fv_n3_json_from_n1=lambda *_args: contract_path,
        _configure_level_attention=lambda *_args: None,
        _start_n3_generation=lambda *args, **kwargs: started.append((args, kwargs)),
    )
    return module, pipeline_events, started


def test_fv_n3_refuses_to_generate_from_a_stale_fase4_ficha():
    fake, events, started = _fake_fv_n3_module(None)

    ComparisonEngineModule._on_gerar_n3(
        fake, "FV", "V305", seq=1
    )

    assert started == []
    assert (1, "error", "Ficha N1 FV ausente") in events
    assert (2, "error", "N3 não gerado") in events


def test_fv_n3_passes_the_fresh_n1_contract_to_the_current_generator(tmp_path):
    contract_path = tmp_path / "V305_fundo.json"
    contract_path.write_text("{}", encoding="utf-8")
    fake, _events, started = _fake_fv_n3_module(contract_path)

    ComparisonEngineModule._on_gerar_n3(
        fake, "FV", "V305", seq=1
    )

    assert len(started) == 1
    args, kwargs = started[0]
    assert args[0:2] == ("FV", "V305")
    assert kwargs["fv_contract_path"] == contract_path


def test_selecting_structural_fv_automatically_chains_n1_to_n3(monkeypatch):
    generated = []
    pipeline = SimpleNamespace(
        reset=lambda: None,
        set_step=lambda *_args: None,
    )
    image = SimpleNamespace(
        is_loaded=True,
        set_highlight_geometry=lambda *_args: None,
        fit_all=lambda: None,
    )
    n1_column = SimpleNamespace(
        pipeline=pipeline,
        img_widget=image,
        set_ficha=lambda *_args: None,
    )
    fake = SimpleNamespace(
        _seq_id=7,
        _analise_cache=SimpleNamespace(has=lambda *_args: True),
        fase8_panel=SimpleNamespace(
            current_pav_key="13_PAV",
            cmb_obra=SimpleNamespace(
                currentData=lambda: "Obra_TREINO_1",
                currentText=lambda: "Obra_TREINO_1",
            ),
        ),
        nav_sidebar=SimpleNamespace(
            _current_flow="estrutural",
            set_status=lambda *_args: None,
            _enable_item_btns=lambda: None,
        ),
        tri_level=SimpleNamespace(
            _columns=[n1_column],
            _get_n1_bbox_for=lambda *_args: None,
            _get_n1_highlight_points=lambda *_args: [],
            _ficha_n1_for=lambda *_args: [],
        ),
        _refresh_n3_compare_if_active=lambda *_args: None,
        _on_gerar_n3=lambda *args, **kwargs: generated.append((args, kwargs)),
    )
    monkeypatch.setattr(QTimer, "singleShot", lambda _ms, callback: callback())

    ComparisonEngineModule._on_gerar_n1(
        fake, "FV", "V305", auto_chain=True, seq=7
    )

    assert generated == [
        (("FV", "V305"), {"auto_chain": False, "seq": 7})
    ]


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


def test_lv_face_units_forward_detected_edge_vertical_sarrafos(monkeypatch):
    calls = []

    def record_face(_msp, _x0, _y0, _panels, _height, _label, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(lv_generator, "draw_lv_face", record_face)
    lv_generator.draw_viga_lateral_face_units(
        None, 0, 0, "V1",
        [{
            "side": "A", "label": "V1.A",
            "bbox": {"x_left": 0, "y_top": 100},
            "h_body": 50, "panels": [{"width": 100}],
            "sarrafo_vertical_esquerdo": True,
            "sarrafo_vertical_direito": False,
        }],
        view="A",
    )

    assert len(calls) == 1
    assert calls[0]["sarrafo_vertical_esquerdo"] is True
    assert calls[0]["sarrafo_vertical_direito"] is False
