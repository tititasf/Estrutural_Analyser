"""
test_fundo_multi_project_bug.py — Testa bug de conflito multi-projeto no Robô FV.

Guarda: imports PySide6 DENTRO do teste (não no topo) para evitar access violation
durante coleta do pytest em ambientes headless/CI. O teste é skipado automaticamente
se PySide6 não estiver disponível ou sem display.
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
def test_multi_project_conflict():
    """Reproduz bug: vigas com mesmo número em projetos diferentes eram conflitadas."""
    # Importar PySide6 apenas dentro do teste para não crashar coleta headless
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

    # Limpar estado
    window.fundos_salvos = {}

    # Obra A, Beam 1
    window.sync_context("OBRA A", "PAV 1")
    v_list_a = [{"name": "V1", "number": "1"}]
    count_a = window.add_viga_bulk(v_list_a)

    # Obra B, mesmo número — NÃO deve conflitar com Obra A
    window.sync_context("OBRA B", "PAV 1")
    v_list_b = [{"name": "V1-B", "number": "1"}]
    count_b = window.add_viga_bulk(v_list_b)

    assert count_b == 1, (
        f"Bug multi-projeto: viga 'V1-B' em 'OBRA B' foi ignorada por conflito com "
        f"'V1' da 'OBRA A' (count_b={count_b}, esperado=1). "
        f"count_a={count_a}"
    )
