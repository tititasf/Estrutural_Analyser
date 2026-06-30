import gc
import sqlite3
import sys
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[1] / "Agente-cad-PYSIDE-Restored-main"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


def test_sa_diff_keeps_only_changed_top_level_fields():
    from main import MainWindow

    before, after, changed = MainWindow._sa_mcp_diff(
        {"name": "P1", "classification": "PIL", "height": 300},
        {"name": "P1", "classification": "PIL", "height": 315},
    )

    assert changed == ["height"]
    assert before == {"height": 300}
    assert after == {"height": 315}


def test_sa_edit_event_stays_captured_t0(tmp_path):
    from src.mcp.db_bridge import save_human_edit_event

    db_path = tmp_path / "project_data.vision"
    log_id = save_human_edit_event(
        obra_id="OBRA_TESTE",
        classe="PIL",
        item_id="P1",
        fase_editada="N1_FICHA",
        ui_context="StructuralAnalyzer",
        estado_anterior={"height": 300},
        estado_novo={"height": 315},
        source_agent="structural_analyzer_ui",
        db_path=db_path,
    )

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, tier, event_kind FROM human_event_logs WHERE log_id=?",
            (log_id,),
        ).fetchone()

    assert row == ("CAPTURED", "T0", "edit")


@pytest.mark.skipif(sys.platform != "win32", reason="Smoke da aplicacao desktop Windows")
def test_embedded_project_manager_tabs_accept_mouse_clicks(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
    from src.core.database import DatabaseManager
    from src.ui.widgets.project_manager import ProjectManager

    app = QApplication.instance() or QApplication([])
    host = QWidget()
    layout = QVBoxLayout(host)
    manager = ProjectManager(DatabaseManager(str(tmp_path / "project_data.vision")))
    layout.addWidget(manager)
    host.resize(1400, 900)
    host.show()
    app.processEvents()

    assert not manager.isWindow()
    main_bar = manager.tabs.tabBar()
    QTest.mouseClick(main_bar, Qt.LeftButton, pos=main_bar.tabRect(1).center())
    app.processEvents()
    assert manager.tabs.currentIndex() == 1

    assert manager.curadoria_rag_tabs.tabText(1) == "Evidencias MCP"
    evidence_bar = manager.curadoria_rag_tabs.tabBar()
    QTest.mouseClick(evidence_bar, Qt.LeftButton, pos=evidence_bar.tabRect(1).center())
    app.processEvents()
    assert manager.curadoria_rag_tabs.currentIndex() == 1

    host.close()
    manager.setParent(None)
    manager.deleteLater()
    host.deleteLater()
    app.processEvents()
    del manager
    del host
    gc.collect()

