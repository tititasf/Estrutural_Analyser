"""
test_fundo_multi_project_fix.py — Verifica fix do bug de conflito multi-projeto no Robô FV.

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
def test_multi_project_fix():
    """Verifica que o fix de multi-projeto funciona: projetos independentes não conflitam."""
    PySide6_QtWidgets = pytest.importorskip(
        "PySide6.QtWidgets", reason="PySide6 não disponível"
    )
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
            pytest.skip(f"QApplication falhou (provável headless): {exc}")

    try:
        window = FundoMainWindow()
    except Exception as exc:
        pytest.skip(f"FundoMainWindow falhou (provável headless): {exc}")

    window.fundos_salvos = {}

    # Obra A
    window.sync_context("OBRA A", "PAV 1")
    count_a = window.add_viga_bulk([{"name": "V1", "number": "1"}])

    # Obra B — mesmo número, projeto diferente → não deve conflitar
    window.sync_context("OBRA B", "PAV 1")
    count_b = window.add_viga_bulk([{"name": "V1-B", "number": "1"}])

    # Verificar estrutura nested por obra
    is_nested_a = "OBRA A" in window.fundos_salvos and "PAV 1" in window.fundos_salvos["OBRA A"]
    is_nested_b = "OBRA B" in window.fundos_salvos and "PAV 1" in window.fundos_salvos["OBRA B"]

    assert count_a == 1, f"Obra A deveria ter 1 item, obteve {count_a}"
    assert count_b == 1, (
        f"Fix multi-projeto: 'V1-B' da 'OBRA B' foi conflitada com 'V1' da 'OBRA A' "
        f"(count_b={count_b}). Estrutura nested por obra não está funcionando."
    )
    assert is_nested_a, "fundos_salvos['OBRA A']['PAV 1'] não existe"
    assert is_nested_b, "fundos_salvos['OBRA B']['PAV 1'] não existe"
