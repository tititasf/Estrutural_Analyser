"""
CAD-TEST-01.5: Error path tests for motor_fase4.py
Validates graceful handling of corrupted/missing inputs.
"""

import pytest
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path("D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts")


def test_motor_fase4_obra_inexistente():
    """motor_fase4 must fail gracefully when obra directory does not exist."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "motor_fase4.py"), "--obra", "/tmp/obra_que_nao_existe_xyz"],
        capture_output=True, text=True, timeout=30
    )
    # Deve falhar de forma controlada
    assert result.returncode != 0 or "erro" in result.stdout.lower() or "nao encontrada" in result.stdout.lower() or "not found" in result.stderr.lower()


def test_motor_fase4_fase3_vazia(tmp_path):
    """motor_fase4 must handle an empty Fase-3 directory without crashing."""
    # Obra existe mas sem Fase-3
    obra = tmp_path / "Obra_Vazia"
    obra.mkdir()
    (obra / "Fase-3_Interpretacao_Extracao").mkdir()
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "motor_fase4.py"), "--obra", str(obra)],
        capture_output=True, text=True, timeout=30
    )
    # Deve terminar sem crash (rc 0 ou 1, mas nao exception nao tratada)
    assert result.returncode in (0, 1), f"rc inesperado: {result.returncode}\n{result.stderr[:300]}"
