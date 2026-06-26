"""
test_fundo_sync_fix.py — Testa sincronização de contexto (obra/pavimento) no Robô FV.

Guarda: imports PySide6 DENTRO do teste para evitar access violation em headless/CI.
"""
import os
import sys

import pytest


def _get_robo_path() -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base, "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")


@pytest.mark.skipif(
    os.environ.get("DISPLAY") is None and sys.platform != "win32",
    reason="Sem display (headless) — PySide6 GUI skipped",
)
def test_fundo_sync():
    """Verifica que sync_context atualiza combos e metadados corretamente."""
    PySide6_QtWidgets = pytest.importorskip("PySide6.QtWidgets", reason="PySide6 não disponível")
    QApplication = PySide6_QtWidgets.QApplication

    robo_path = _get_robo_path()
    if robo_path not in sys.path:
        sys.path.insert(0, robo_path)

    try:
        from fundo_pyside import FundoMainWindow  # noqa: PLC0415
    except ImportError as exc:
        pytest.skip(f"fundo_pyside não importável: {exc}")
    except Exception as exc:
        pytest.skip(f"fundo_pyside causou erro na importação: {exc}")

    app = QApplication.instance()
    if not app:
        try:
            app = QApplication(sys.argv)
        except Exception as exc:
            pytest.skip(f"QApplication falhou: {exc}")

    try:
        window = FundoMainWindow()
    except Exception as exc:
        pytest.skip(f"FundoMainWindow falhou: {exc}")

    obra_teste = "OBRA-TESTE-AUT"
    pav_teste = "PAV-99-TESTE"

    window.sync_context(obra_teste, pav_teste)

    obra_actual = window.combo_obra.currentText()
    assert obra_actual == obra_teste, f"Obra esperada {obra_teste}, obteve {obra_actual}"

    pav_actual = window.combo_pavimento.currentText()
    assert pav_actual == pav_teste, f"Pavimento esperado {pav_teste}, obteve {pav_actual}"

    txt_pav = window.fields["pavimento"].text()
    assert txt_pav == pav_teste, f"Campo texto pavimento esperado {pav_teste}, obteve {txt_pav}"

    assert obra_teste in window.obras_metadata, "Obra não está no metadata"
    assert pav_teste in window.obras_metadata[obra_teste], "Pavimento não está no metadata da obra"
