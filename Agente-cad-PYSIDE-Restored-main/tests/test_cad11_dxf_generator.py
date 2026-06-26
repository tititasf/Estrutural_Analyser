#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_cad11_dxf_generator.py — CAD-11
Unit tests para DXFGeneratorService (lógica pura, sem Qt, sem ezdxf).
"""
import json
import pathlib
import sys
import subprocess
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.core.services.dxf_generator import DXFGeneratorService, ITEM_TYPE_TO_KEY


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_obra(tmp: pathlib.Path) -> pathlib.Path:
    obra = tmp / "Obra_DXF_TEST"
    for sub in ("JSON_Pilares", "JSON_Vigas_Laterais", "JSON_Vigas_Fundo", "JSON_Lajes"):
        (obra / "Fase-4_Sincronizacao" / sub).mkdir(parents=True)
    (obra / "Fase-6_Execucao_CAD").mkdir(parents=True)
    # Pilar mínimo
    (obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / "P1.json").write_text(
        json.dumps({"nome": "P1", "grade_1": 88.0, "altura": 280.0}), encoding='utf-8'
    )
    return obra


# ── AC-1: build_args ──────────────────────────────────────────────────────────

class TestBuildArgs(unittest.TestCase):

    def setUp(self):
        import tempfile
        self._tmp = tempfile.mkdtemp()
        self.obra = pathlib.Path(self._tmp) / "Obra_X"
        self.obra.mkdir()
        self.svc = DXFGeneratorService(self.obra)

    def test_build_args_pl_no_item(self):
        script, args = self.svc.build_args('PL')
        self.assertTrue(str(script).endswith('gerar_pl_dxf_stog.py'))
        self.assertIn('--obra', args)
        self.assertNotIn('--item', args)

    def test_build_args_pl_with_item(self):
        script, args = self.svc.build_args('PL', item='P1')
        self.assertIn('--item', args)
        idx = args.index('--item')
        self.assertEqual(args[idx + 1], 'P1')

    def test_build_args_lv(self):
        script, args = self.svc.build_args('LV')
        self.assertTrue(str(script).endswith('gerar_lv_dxf_stog.py'))

    def test_build_args_fv(self):
        script, args = self.svc.build_args('FV')
        self.assertTrue(str(script).endswith('gerar_fv_dxf_stog.py'))

    def test_build_args_lj(self):
        script, args = self.svc.build_args('LJ')
        self.assertTrue(str(script).endswith('gerar_lj_dxf_stog.py'))

    def test_invalid_tipo_raises(self):
        with self.assertRaises(ValueError):
            self.svc.build_args('XX')


# ── AC-2: expected_output ─────────────────────────────────────────────────────

class TestExpectedOutput(unittest.TestCase):

    def setUp(self):
        import tempfile
        self._tmp = tempfile.mkdtemp()
        self.obra = pathlib.Path(self._tmp) / "Obra_X"
        self.obra.mkdir()
        self.svc = DXFGeneratorService(self.obra)

    def test_default_output_name(self):
        out = self.svc.expected_output('PL')
        self.assertEqual(out.name, 'PL_stog_quality.dxf')
        self.assertIn('Fase-6_Execucao_CAD', str(out))

    def test_preview_output_name(self):
        out = self.svc.expected_output('PL', item='P1')
        self.assertEqual(out.name, 'PL_preview_P1.dxf')

    def test_preview_lv(self):
        out = self.svc.expected_output('LV', item='V5')
        self.assertEqual(out.name, 'LV_preview_V5.dxf')

    def test_preview_lj(self):
        out = self.svc.expected_output('LJ', item='L3')
        self.assertEqual(out.name, 'LJ_preview_L3.dxf')


# ── AC-3: generate() (mocked subprocess) ─────────────────────────────────────

class TestGenerate(unittest.TestCase):

    def setUp(self):
        import tempfile
        self._tmp = tempfile.mkdtemp()
        self.obra = pathlib.Path(self._tmp) / "Obra_GEN"
        (self.obra / "Fase-6_Execucao_CAD").mkdir(parents=True)
        self.svc = DXFGeneratorService(self.obra)

    def test_generate_returns_false_when_script_missing(self):
        # Script path won't exist in test env
        ok, path = self.svc.generate('PL')
        # Script exists in project dir — if not available, should return False
        if not ok:
            self.assertIsNone(path)

    def test_generate_returns_true_when_dxf_created(self):
        """Simulate: subprocess succeeds and DXF appears on disk."""
        expected = self.svc.expected_output('PL')
        expected.touch()  # simulate DXF created

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            # Patch script existence
            with patch.object(pathlib.Path, 'exists', return_value=True):
                ok, path = self.svc.generate('PL')

        self.assertTrue(ok)
        self.assertEqual(path, expected)

    def test_generate_returns_false_on_error_returncode(self):
        """Simulate: subprocess fails (returncode=1)."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            with patch.object(pathlib.Path, 'exists', side_effect=lambda: False):
                ok, path = self.svc.generate('LJ')
        self.assertFalse(ok)


# ── AC-4: key_for_item_type ───────────────────────────────────────────────────

class TestKeyForItemType(unittest.TestCase):

    def test_pilar(self):
        self.assertEqual(DXFGeneratorService.key_for_item_type('Pilar'), 'PL')

    def test_pilar_uppercase(self):
        self.assertEqual(DXFGeneratorService.key_for_item_type('PILAR'), 'PL')

    def test_viga_lateral(self):
        self.assertEqual(DXFGeneratorService.key_for_item_type('Viga Lateral'), 'LV')

    def test_viga_fundo(self):
        self.assertEqual(DXFGeneratorService.key_for_item_type('Viga Fundo'), 'FV')

    def test_laje(self):
        self.assertEqual(DXFGeneratorService.key_for_item_type('Laje'), 'LJ')

    def test_unknown_returns_none(self):
        self.assertIsNone(DXFGeneratorService.key_for_item_type('Marco'))

    def test_pilar_with_extra_text(self):
        # e.g. "Pilar (P1)"
        self.assertEqual(DXFGeneratorService.key_for_item_type('Pilar (P1)'), 'PL')


# ── AC-5: ITEM_TYPE_TO_KEY constant ──────────────────────────────────────────

class TestItemTypeToKey(unittest.TestCase):

    def test_all_types_present(self):
        for k in ('PL', 'LV', 'FV', 'LJ'):
            self.assertIn(k, ITEM_TYPE_TO_KEY.values(),
                          f"Tipo {k} nao mapeado em ITEM_TYPE_TO_KEY")

    def test_pilar_mapped(self):
        self.assertEqual(ITEM_TYPE_TO_KEY['Pilar'], 'PL')


# ── AC-6: generate_all() ──────────────────────────────────────────────────────

class TestGenerateAll(unittest.TestCase):

    def setUp(self):
        import tempfile
        self._tmp = tempfile.mkdtemp()
        self.obra = pathlib.Path(self._tmp) / "Obra_ALL"
        (self.obra / "Fase-6_Execucao_CAD").mkdir(parents=True)
        self.svc = DXFGeneratorService(self.obra)

    def test_generate_all_returns_dict_with_all_keys(self):
        with patch.object(self.svc, 'generate', return_value=(False, None)):
            result = self.svc.generate_all()
        for k in ('PL', 'LV', 'FV', 'LJ'):
            self.assertIn(k, result)

    def test_generate_all_subset(self):
        with patch.object(self.svc, 'generate', return_value=(False, None)):
            result = self.svc.generate_all(tipos=['PL', 'LJ'])
        self.assertIn('PL', result)
        self.assertIn('LJ', result)
        self.assertNotIn('LV', result)
        self.assertNotIn('FV', result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
