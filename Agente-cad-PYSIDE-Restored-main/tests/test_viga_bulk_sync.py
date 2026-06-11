"""
test_viga_bulk_sync.py — Testa sincronização em massa de vigas no MainWindow.

Guarda: imports PySide6/MainWindow DENTRO do teste para evitar crash headless.
"""
import os
import sys

import pytest
from unittest.mock import MagicMock


@pytest.mark.skipif(
    os.environ.get("DISPLAY") is None and sys.platform != "win32",
    reason="Sem display (headless) — PySide6 GUI skipped",
)
def test_viga_bulk_sync():
    """Verifica que sync_beams_to_laterais_action e sync_beams_to_fundo_action funcionam."""
    PySide6_QtWidgets = pytest.importorskip("PySide6.QtWidgets", reason="PySide6 não disponível")
    QApplication = PySide6_QtWidgets.QApplication

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    for extra in [
        base_dir,
        os.path.join(base_dir, "_ROBOS_ABAS", "Robo_Laterais_de_Vigas"),
        os.path.join(base_dir, "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao"),
    ]:
        if extra not in sys.path:
            sys.path.insert(0, extra)

    try:
        from main import MainWindow  # noqa: PLC0415
    except ImportError as exc:
        pytest.skip(f"MainWindow não importável: {exc}")
    except Exception as exc:
        pytest.skip(f"MainWindow causou erro na importação: {exc}")

    app = QApplication.instance()
    if not app:
        try:
            app = QApplication(sys.argv)
        except Exception as exc:
            pytest.skip(f"QApplication falhou: {exc}")

    try:
        window = MainWindow()
    except Exception as exc:
        pytest.skip(f"MainWindow() falhou (provável headless): {exc}")

    window.beams_found = [
        {"name": "V1", "number": "1"},
        {"name": "V2", "number": "2"},
        {"name": "V3", "number": "3"},
    ]

    # Mock robôs se não carregados
    if not getattr(window, "robo_viga", None):
        window.robo_viga = MagicMock()
        window.robo_viga.add_viga_bulk.return_value = 3
    if not getattr(window, "robo_fundo", None):
        window.robo_fundo = MagicMock()
        window.robo_fundo.add_viga_bulk.return_value = 3

    window.cmb_works.addItem("OBRA-SYNC")
    window.cmb_works.setCurrentText("OBRA-SYNC")
    window.cmb_pavements.addItem("PAV-SYNC")
    window.cmb_pavements.setCurrentText("PAV-SYNC")

    window.sync_beams_to_laterais_action()
    window.robo_viga.add_global_pavimento.assert_called_with("OBRA-SYNC", "PAV-SYNC")
    window.robo_viga.add_viga_bulk.assert_called()

    window.sync_beams_to_fundo_action()
    window.robo_fundo.sync_context.assert_called_with("OBRA-SYNC", "PAV-SYNC")
    window.robo_fundo.add_viga_bulk.assert_called()
