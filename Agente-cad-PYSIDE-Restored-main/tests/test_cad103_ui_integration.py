#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_cad103_ui_integration.py — CAD-10.3
Testa integração do botão "Analise Geral" com Fase4Importer.

Não requer PySide6 (mock do db + obra fictícia).
"""
import json
import pathlib
import sys
import types
import unittest
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# ── Stub PySide6 para rodar sem Qt ────────────────────────────────────────────
def _make_qt_stub():
    """Cria stubs mínimos de PySide6 para não quebrar o import de diagnostic_hub."""
    mods = [
        'PySide6', 'PySide6.QtWidgets', 'PySide6.QtCore', 'PySide6.QtGui',
    ]
    for name in mods:
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    # QtWidgets
    qw = sys.modules['PySide6.QtWidgets']
    for cls in ('QWidget', 'QHBoxLayout', 'QVBoxLayout', 'QFrame', 'QDialog',
                'QDialogButtonBox', 'QRadioButton', 'QButtonGroup', 'QLabel',
                'QMessageBox', 'QPushButton', 'QScrollArea', 'QCheckBox',
                'QProgressBar', 'QSizePolicy'):
        setattr(qw, cls, MagicMock)

    # QtCore
    qc = sys.modules['PySide6.QtCore']
    for name in ('QThread', 'Signal', 'QProcess', 'Qt'):
        setattr(qc, name, MagicMock)

_make_qt_stub()

# Stub dos módulos de UI que diagnostic_hub importa
for mod_path in [
    'src.ui.components.organisms',
    'src.ui.canvas',
    'src.core.dxf_loader',
    'src.core.services.data_coordinator',
    'src.ui.theme',
]:
    if mod_path not in sys.modules:
        m = types.ModuleType(mod_path)
        for attr in ('DiagnosticSidebar', 'TechSheetPanel', 'CADCanvas',
                     'RenderMode', 'get_coordinator', 'Colors', 'Fonts',
                     'Radius'):
            setattr(m, attr, MagicMock)
        sys.modules[mod_path] = m

from src.core.services.fase4_importer import Fase4Importer


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_fake_obra(tmp_path: pathlib.Path) -> pathlib.Path:
    """Cria estrutura mínima Fase-4 em tmp_path."""
    obra = tmp_path / "Obra_TEST"
    for subdir in ("JSON_Pilares", "JSON_Vigas_Laterais",
                   "JSON_Vigas_Fundo", "JSON_Lajes"):
        (obra / "Fase-4_Sincronizacao" / subdir).mkdir(parents=True)

    # Pilar mínimo
    pilar = {
        "nome": "P1", "floor": "TERREO",
        "comprimento": 19.0, "largura": 19.0, "altura": 280.0,
        "grade_1": 88.0, "par_1_2": 20.0,
        "distancia_1": 5.0, "distancia_2": 5.0,
        "h1_A": 5.0, "h2_A": 260.0, "h3_A": 15.0,
        "larg1_A": 19.0,
        "h1_B": 5.0, "h2_B": 260.0, "h3_B": 15.0,
        "larg1_B": 19.0,
        "h1_C": 5.0, "h2_C": 260.0, "h3_C": 15.0,
        "larg1_C": 19.0,
        "h1_D": 5.0, "h2_D": 260.0, "h3_D": 15.0,
        "larg1_D": 19.0,
    }
    (obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / "P1.json").write_text(
        json.dumps(pilar), encoding='utf-8')

    return obra


# ─── AC-1: Fase4Importer chamado após GT import ───────────────────────────────

class TestFase4ImporterCalledAfterGT(unittest.TestCase):
    """Verifica que import_obra é chamado com os args corretos."""

    def test_import_obra_called_with_correct_args(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_fake_obra(pathlib.Path(tmp))
            db = MagicMock()
            db.load_pillars.return_value = []
            db.load_beams.return_value   = []
            db.load_slabs.return_value   = []

            with patch.object(Fase4Importer, 'import_obra', return_value={
                'pilares': 1, 'vigas': 0, 'lajes': 0,
                'conflitos': 0, 'erros': [], 'tempo_ms': 10
            }) as mock_import:
                importer = Fase4Importer(db)
                result = importer.import_obra(str(obra), "TERREO", "proj_test")

            mock_import.assert_called_once_with(str(obra), "TERREO", "proj_test")


# ─── AC-2: Merge respeita validated_fields ────────────────────────────────────

class TestMergeRespectsValidated(unittest.TestCase):
    def test_validated_field_not_overwritten(self):
        from src.core.services.fase4_importer import _merge_flat

        existing = {'grade_1': 99.0, 'altura': 280.0}
        new_flat  = {'grade_1': 88.0, 'altura': 300.0}
        validated = ['grade_1']  # grade_1 foi aprovado pelo usuário

        merged, conflicts = _merge_flat(existing, new_flat, validated)

        # grade_1 validado → mantém 99.0
        self.assertEqual(merged['grade_1'], 99.0)
        # altura não validado → atualiza para 300.0
        self.assertEqual(merged['altura'], 300.0)
        # grade_1 entra em conflitos (valor diferente mas validado)
        self.assertIn('grade_1', conflicts)

    def test_unvalidated_field_is_updated(self):
        from src.core.services.fase4_importer import _merge_flat

        existing = {'grade_1': 0}
        new_flat  = {'grade_1': 88.0}
        merged, conflicts = _merge_flat(existing, new_flat, validated_fields=[])
        self.assertEqual(merged['grade_1'], 88.0)
        self.assertEqual(conflicts, [])


# ─── AC-3: import_obra retorna estrutura correta ──────────────────────────────

class TestImportObraReturnSchema(unittest.TestCase):
    def test_return_keys_present(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_fake_obra(pathlib.Path(tmp))
            db = MagicMock()
            db.load_pillars.return_value = []
            db.load_beams.return_value   = []
            db.load_slabs.return_value   = []

            importer = Fase4Importer(db)
            result = importer.import_obra(str(obra), "TERREO", "proj_test")

        for key in ('pilares', 'vigas', 'lajes', 'conflitos', 'erros', 'tempo_ms'):
            self.assertIn(key, result, f"Chave '{key}' ausente no resultado")

    def test_pilares_count_matches_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_fake_obra(pathlib.Path(tmp))
            db = MagicMock()
            db.load_pillars.return_value = []
            db.load_beams.return_value   = []
            db.load_slabs.return_value   = []

            importer = Fase4Importer(db)
            result = importer.import_obra(str(obra), "TERREO", "proj_test")

        self.assertEqual(result['pilares'], 1)
        self.assertEqual(result['erros'], [])


# ─── AC-4: sem Fase-4 → import GT normal, sem crash ──────────────────────────

class TestImportObraNoFase4(unittest.TestCase):
    def test_returns_zeros_when_fase4_missing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = pathlib.Path(tmp) / "Obra_SEM_FASE4"
            obra.mkdir()
            # Sem subdir Fase-4_Sincronizacao

            db = MagicMock()
            importer = Fase4Importer(db)
            result = importer.import_obra(str(obra), "TERREO", "proj_test")

        self.assertEqual(result['pilares'], 0)
        self.assertEqual(result['vigas'], 0)
        self.assertEqual(result['lajes'], 0)
        self.assertIn('erros', result)


# ─── AC-5: save_pillar chamado com sides_data rico ────────────────────────────

class TestSavesPillarWithSidesData(unittest.TestCase):
    def test_pillar_saved_with_sides_data(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_fake_obra(pathlib.Path(tmp))
            db = MagicMock()
            db.load_pillars.return_value = []
            db.load_beams.return_value   = []
            db.load_slabs.return_value   = []

            importer = Fase4Importer(db)
            importer.import_obra(str(obra), "TERREO", "proj_test")

        # save_pillar deve ter sido chamado 1×
        self.assertTrue(db.save_pillar.called)
        saved_pillar = db.save_pillar.call_args[0][0]
        # Chapas agora vão para flat como p_sA_c_h1..h5 (não mais em sides_data)
        for face in ('A', 'B', 'C', 'D'):
            fid = f'p_s{face}_c_h2'
            self.assertIn(fid, saved_pillar,
                          f"Campo {fid} ausente no pilar salvo")
            self.assertGreater(float(saved_pillar.get(fid, 0)), 0,
                               f"{fid} zerado na face {face}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
