from pathlib import Path

import pytest

from src.core.n2_pilar_views import find_n2_pilar_recorte, zone_windows

_RECORTES = Path(
    r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes_reversos"
)
_P26_SEL = _RECORTES / "ALIMONTI - PARAISO - 13° PAV.- PL - R00" / "PIL_P26_sel_1781379290.dxf"
_P27_MOTOR = _RECORTES / "ALIMONTI - PARAISO - 13° PAV.- PL - R00" / "PIL_P27_motor_178111335539.dxf"
_P26_MOTOR_ABCD = (
    _RECORTES / "ALIMONTI - PARAISO - 13° PAV.- PL - R00" / "PIL_P26_motor_178111041111.dxf"
)
_DB = Path(r"D:\Agente-cad-PYSIDE\project_data.vision")

pytestmark = pytest.mark.skipif(
    not _P26_SEL.is_file() or not _P27_MOTOR.is_file(),
    reason="recortes N2 reais de P26/P27 ausentes",
)


def test_p26_sel_has_cima_and_abcdef_faces():
    windows = zone_windows(_P26_SEL, "P26")
    assert "cima" in windows
    assert "abcd" in windows
    assert "ef" in windows
    # CIMA (planta+grades) fica entre E/F e A-D, não mistura as elevações.
    assert windows["ef"][1] < windows["cima"][0]
    assert windows["cima"][1] < windows["abcd"][0]


def test_p27_motor_has_cima_abcd_and_ef():
    windows = zone_windows(_P27_MOTOR, "P27")
    assert "cima" in windows
    assert "abcd" in windows
    assert "ef" in windows


def test_p26_truncated_motor_has_abcd_without_cima():
    windows = zone_windows(_P26_MOTOR_ABCD, "P26")
    assert "abcd" in windows
    assert "cima" not in windows
    assert "ef" not in windows


def test_find_n2_prefers_sel_on_13_pav():
    if not _DB.is_file():
        pytest.skip("DB real ausente")
    path = find_n2_pilar_recorte("Obra_TREINO_1", "13_PAV", "P26", db_path=_DB)
    assert path is not None
    assert path.name.startswith("PIL_P26_sel_")
    assert "13° PAV" in path.parent.name
