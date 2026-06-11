#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_apply_correction.py — CAD-10.6
Testa correction_service e CLI apply_correction.py (sem Qt).
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.core.services.correction_service import (
    apply_correction,
    append_correction_log,
    build_log_entry,
    apply_from_log,
    compute_stats,
    detect_divergences,
    _find_json_path,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_f4_tree(tmp: pathlib.Path, item_id='P1', data: dict | None = None) -> pathlib.Path:
    """Cria obra com JSON Fase-4 para um pilar."""
    obra = tmp / "Obra_CORR_TEST"
    json_dir = obra / "Fase-4_Sincronizacao" / "JSON_Pilares"
    json_dir.mkdir(parents=True)
    (obra / "Fase-3_Interpretacao_Extracao").mkdir(parents=True)

    payload = data or {"grade_1": 88.0, "comprimento": 19.0, "largura": 19.0}
    (json_dir / f"{item_id}.json").write_text(
        json.dumps(payload), encoding='utf-8')
    return obra


# ─── AC-1: apply_correction atômico ──────────────────────────────────────────

class TestApplyCorrection(unittest.TestCase):
    def test_applies_new_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp))
            json_path = obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / "P1.json"

            changed = apply_correction(json_path, 'grade_1', 99.0)

            self.assertTrue(changed)
            data = json.loads(json_path.read_text())
            self.assertAlmostEqual(data['grade_1'], 99.0)

    def test_idempotent_same_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp))
            json_path = obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / "P1.json"

            changed = apply_correction(json_path, 'grade_1', 88.0)

            self.assertFalse(changed)

    def test_creates_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp))
            json_path = obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / "P1.json"

            apply_correction(json_path, 'grade_1', 95.0, create_backup=True)

            backups = list(json_path.parent.glob("P1.json.bak.*"))
            self.assertEqual(len(backups), 1)

    def test_no_backup_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp))
            json_path = obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / "P1.json"

            apply_correction(json_path, 'grade_1', 95.0, create_backup=False)

            backups = list(json_path.parent.glob("P1.json.bak.*"))
            self.assertEqual(len(backups), 0)

    def test_returns_false_for_missing_file(self):
        p = pathlib.Path("/tmp/nonexistent_xyz.json")
        changed = apply_correction(p, 'field', 1.0)
        self.assertFalse(changed)

    def test_string_field_correction(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp),
                                  data={"tipo": "PILAR", "grade_1": 88.0})
            json_path = obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / "P1.json"

            changed = apply_correction(json_path, 'tipo', 'PILAR_CANTO')

            self.assertTrue(changed)
            data = json.loads(json_path.read_text())
            self.assertEqual(data['tipo'], 'PILAR_CANTO')

    def test_nested_field_correction(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp),
                                  data={"panels": [{"width": 10.0}, {"width": 20.0}]})
            json_path = obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / "P1.json"

            changed = apply_correction(json_path, 'panels[1].width', 25.0)

            self.assertTrue(changed)
            data = json.loads(json_path.read_text())
            self.assertAlmostEqual(data['panels'][1]['width'], 25.0)


# ─── AC-2: correction_log ─────────────────────────────────────────────────────

class TestCorrectionLog(unittest.TestCase):
    def _entry(self, item_id='P1', field='grade_1', new_value=99.0):
        return build_log_entry(
            item_id=item_id, item_type='pilar', json_key=field,
            detail_field_id=field, old_value=88.0, new_value=new_value
        )

    def test_append_creates_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = pathlib.Path(tmp) / "obra"
            (obra / "Fase-3_Interpretacao_Extracao").mkdir(parents=True)

            append_correction_log(obra, self._entry())

            log_path = obra / "Fase-3_Interpretacao_Extracao" / "correction_log.json"
            self.assertTrue(log_path.exists())
            entries = json.loads(log_path.read_text())
            self.assertEqual(len(entries), 1)

    def test_append_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = pathlib.Path(tmp) / "obra"
            (obra / "Fase-3_Interpretacao_Extracao").mkdir(parents=True)

            entry = self._entry()
            append_correction_log(obra, entry)
            append_correction_log(obra, entry)  # duplicata

            log_path = obra / "Fase-3_Interpretacao_Extracao" / "correction_log.json"
            entries = json.loads(log_path.read_text())
            self.assertEqual(len(entries), 1)

    def test_append_multiple_different(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = pathlib.Path(tmp) / "obra"
            (obra / "Fase-3_Interpretacao_Extracao").mkdir(parents=True)

            append_correction_log(obra, self._entry('P1', 'grade_1', 95.0))
            append_correction_log(obra, self._entry('P2', 'grade_1', 95.0))

            log_path = obra / "Fase-3_Interpretacao_Extracao" / "correction_log.json"
            entries = json.loads(log_path.read_text())
            self.assertEqual(len(entries), 2)

    def test_build_log_entry_fields(self):
        e = self._entry()
        for key in ('item_id', 'item_type', 'field', 'old_value', 'new_value',
                    'timestamp', 'confidence_before', 'confidence_after'):
            self.assertIn(key, e)
        self.assertEqual(e['confidence_after'], 1.0)


# ─── AC-3: apply_from_log ─────────────────────────────────────────────────────

class TestApplyFromLog(unittest.TestCase):
    def test_apply_from_log_basic(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp))
            # Criar log
            entry = build_log_entry('P1', 'pilar', 'grade_1', 'grade_1',
                                    old_value=88.0, new_value=95.0)
            append_correction_log(obra, entry)

            result = apply_from_log(obra)

            self.assertGreater(result['applied'], 0)
            self.assertEqual(result['errors'], [])
            # Verificar que o JSON foi atualizado
            json_path = obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / "P1.json"
            data = json.loads(json_path.read_text())
            self.assertAlmostEqual(data['grade_1'], 95.0)

    def test_apply_from_log_skips_when_already_equal(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp))
            # Valor já igual ao JSON (88.0 = 88.0)
            entry = build_log_entry('P1', 'pilar', 'grade_1', 'grade_1',
                                    old_value=88.0, new_value=88.0)
            append_correction_log(obra, entry)

            result = apply_from_log(obra)

            self.assertEqual(result['applied'], 0)
            self.assertGreater(result['skipped'], 0)

    def test_apply_from_log_returns_empty_when_no_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = pathlib.Path(tmp) / "Obra_NO_LOG"
            obra.mkdir()

            result = apply_from_log(obra)

            self.assertEqual(result['applied'], 0)
            self.assertEqual(result['skipped'], 0)

    def test_apply_from_log_error_for_missing_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp))
            # Item inexistente
            entry = build_log_entry('P999', 'pilar', 'grade_1', 'grade_1',
                                    old_value=88.0, new_value=95.0)
            append_correction_log(obra, entry)

            result = apply_from_log(obra)

            self.assertEqual(len(result['errors']), 1)


# ─── AC-4: compute_stats ──────────────────────────────────────────────────────

class TestComputeStats(unittest.TestCase):
    def test_stats_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = pathlib.Path(tmp) / "obra"
            obra.mkdir()
            stats = compute_stats(obra)
            self.assertEqual(stats['total'], 0)

    def test_stats_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp))
            for i, val in enumerate([90.0, 92.0, 94.0]):
                entry = build_log_entry(f'P{i}', 'pilar', 'grade_1', 'grade_1',
                                        old_value=88.0, new_value=val)
                append_correction_log(obra, entry)

            stats = compute_stats(obra)
            self.assertEqual(stats['total'], 3)
            self.assertIn('pilares' if 'pilares' in stats.get('by_type', {}) else 'pilar',
                          stats['by_type'])

    def test_stats_top_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp))
            for i in range(5):
                entry = build_log_entry(f'P{i}', 'pilar', 'grade_1', 'grade_1',
                                        old_value=88.0, new_value=90.0 + i)
                append_correction_log(obra, entry)

            stats = compute_stats(obra)
            self.assertTrue(len(stats['top_fields']) >= 1)
            self.assertEqual(stats['top_fields'][0]['field'], 'grade_1')
            self.assertEqual(stats['top_fields'][0]['count'], 5)


# ─── AC-5: detect_divergences ────────────────────────────────────────────────

class TestDetectDivergences(unittest.TestCase):
    def test_detects_numeric_divergence(self):
        import unittest.mock as mock
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp), data={'grade_1': 88.0})
            item_data = {'id_item': 'P1', 'type': 'Pilar'}

            # Simular map_detail_to_fase4 retornando ('grade_1', 88.0)
            with mock.patch('src.core.services.correction_service.map_detail_to_fase4',
                            return_value=('grade_1', 99.0)):
                divs = detect_divergences(item_data, obra, {'grade_1': 99.0})

            # 88.0 vs 99.0 → divergência
            self.assertEqual(len(divs), 1)
            self.assertEqual(divs[0]['field_id'], 'grade_1')

    def test_no_divergence_when_equal(self):
        import unittest.mock as mock
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp), data={'grade_1': 88.0})
            item_data = {'id_item': 'P1', 'type': 'Pilar'}

            with mock.patch('src.core.services.correction_service.map_detail_to_fase4',
                            return_value=('grade_1', 88.0)):
                divs = detect_divergences(item_data, obra, {'grade_1': 88.0})

            self.assertEqual(len(divs), 0)

    def test_returns_empty_without_obra(self):
        divs = detect_divergences({'id_item': 'P1', 'type': 'Pilar'}, None, {'grade_1': 88.0})
        self.assertEqual(divs, [])


# ─── AC-6: CLI apply_correction.py ───────────────────────────────────────────

class TestCLI(unittest.TestCase):
    def _run_cli(self, *args) -> subprocess.CompletedProcess:
        script = pathlib.Path(__file__).parent.parent / "scripts" / "apply_correction.py"
        return subprocess.run(
            [sys.executable, str(script)] + list(args),
            capture_output=True, text=True,
            cwd=str(pathlib.Path(__file__).parent.parent)
        )

    def test_cli_stats_no_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = pathlib.Path(tmp) / "Obra_CLI"
            obra.mkdir()
            result = self._run_cli('--obra', str(obra), '--stats')
            self.assertEqual(result.returncode, 0)
            self.assertIn('0', result.stdout)

    def test_cli_from_log_no_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = pathlib.Path(tmp) / "Obra_CLI"
            obra.mkdir()
            result = self._run_cli('--obra', str(obra), '--from-log')
            self.assertEqual(result.returncode, 0)

    def test_cli_single_correction(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp))
            result = self._run_cli(
                '--obra', str(obra),
                '--item', 'P1', '--type', 'pilar',
                '--field', 'grade_1', '--value', '95.0'
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn('P1.grade_1', result.stdout)
            # Verificar JSON atualizado
            json_path = obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / "P1.json"
            data = json.loads(json_path.read_text())
            self.assertAlmostEqual(data['grade_1'], 95.0)

    def test_cli_from_log_applies(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp))
            entry = build_log_entry('P1', 'pilar', 'grade_1', 'grade_1',
                                    old_value=88.0, new_value=97.0)
            append_correction_log(obra, entry)

            result = self._run_cli('--obra', str(obra), '--from-log')
            self.assertEqual(result.returncode, 0)
            self.assertIn('Aplicadas: 1', result.stdout)

    def test_cli_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_f4_tree(pathlib.Path(tmp))
            entry = build_log_entry('P1', 'pilar', 'grade_1', 'grade_1',
                                    old_value=88.0, new_value=97.0)
            append_correction_log(obra, entry)

            result = self._run_cli('--obra', str(obra), '--from-log', '--dry-run')
            self.assertEqual(result.returncode, 0)
            self.assertIn('DRY-RUN', result.stdout)
            # JSON não deve ter mudado
            json_path = obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / "P1.json"
            data = json.loads(json_path.read_text())
            self.assertAlmostEqual(data['grade_1'], 88.0)  # inalterado

    def test_cli_no_args_exits_nonzero(self):
        result = self._run_cli('--obra', '/tmp/qualquer')
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
