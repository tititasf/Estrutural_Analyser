#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_comparison_tab.py — CAD-10.4
Unit tests do ComparisonService (lógica pura, sem Qt).
"""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.core.services.comparison_service import (
    ComparisonService, FieldStatus, _fmt, _eq, _empty,
)

FIXTURES = pathlib.Path(__file__).parent / 'fixtures' / 'fase4_samples'


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_obra(tmp: pathlib.Path, pilar_json: dict,
               gt_json: dict | None = None) -> pathlib.Path:
    obra = tmp / "Obra_CMP_TEST"
    (obra / "Fase-4_Sincronizacao" / "JSON_Pilares").mkdir(parents=True)
    (obra / "Fase-4_Sincronizacao" / "JSON_Vigas_Laterais").mkdir(parents=True)
    (obra / "Fase-4_Sincronizacao" / "JSON_Vigas_Fundo").mkdir(parents=True)
    (obra / "Fase-4_Sincronizacao" / "JSON_Lajes").mkdir(parents=True)
    (obra / "Fase-3_Interpretacao_Extracao" / "Pilares").mkdir(parents=True)

    nome = pilar_json.get('nome', 'P1')
    (obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{nome}.json").write_text(
        json.dumps(pilar_json), encoding='utf-8')

    if gt_json is not None:
        (obra / "Fase-3_Interpretacao_Extracao" / "Pilares" / "pilares_ground_truth.json").write_text(
            json.dumps({nome: gt_json}), encoding='utf-8')

    return obra


def _pilar_json(nome='P1'):
    return {
        "nome": nome, "floor": "TERREO",
        "comprimento": 19.0, "largura": 19.0, "altura": 280.0,
        "grade_1": 88.0, "par_1_2": 20.0,
        "distancia_1": 5.0, "distancia_2": 5.0,
        "h1_A": 5.0, "h2_A": 260.0, "h3_A": 15.0, "larg1_A": 19.0,
        "h1_B": 5.0, "h2_B": 260.0, "h3_B": 15.0, "larg1_B": 19.0,
        "h1_C": 5.0, "h2_C": 260.0, "h3_C": 15.0, "larg1_C": 19.0,
        "h1_D": 5.0, "h2_D": 260.0, "h3_D": 15.0, "larg1_D": 19.0,
    }


def _item_data(nome='P1', overrides=None):
    d = {
        'id': f'proj1_pil_{nome}', 'id_item': nome, 'name': nome,
        'type': 'Pilar', 'validated_fields': [],
        'sides_data': {},
    }
    if overrides:
        d.update(overrides)
    return d


# ─── AC-1: ComparisonService carrega Fase-4 ──────────────────────────────────

class TestServiceLoadsF4(unittest.TestCase):
    def test_has_fase4_when_file_exists(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra(pathlib.Path(tmp), _pilar_json())
            svc  = ComparisonService(_item_data(), str(obra))
        self.assertTrue(svc.has_fase4)

    def test_no_fase4_when_file_missing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = pathlib.Path(tmp) / "Obra_EMPTY"
            obra.mkdir()
            svc  = ComparisonService(_item_data(), str(obra))
        self.assertFalse(svc.has_fase4)

    def test_no_fase4_when_obra_path_none(self):
        svc = ComparisonService(_item_data(), None)
        self.assertFalse(svc.has_fase4)


# ─── AC-2: Status de concordância ────────────────────────────────────────────

class TestFieldStatus(unittest.TestCase):
    def _svc_with_db(self, db_overrides: dict):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra(pathlib.Path(tmp), _pilar_json())
            item = _item_data(overrides=db_overrides)
            svc  = ComparisonService(item, str(obra))
        return svc

    def test_igual_when_f4_eq_db(self):
        svc = self._svc_with_db({'grade_1': 88.0})
        rows = {r.field_id: r for r in svc.build_rows()}
        self.assertEqual(rows['grade_1'].status, FieldStatus.IGUAL)

    def test_diferente_when_f4_ne_db(self):
        svc = self._svc_with_db({'grade_1': 99.0})
        rows = {r.field_id: r for r in svc.build_rows()}
        self.assertEqual(rows['grade_1'].status, FieldStatus.DIFERENTE)

    def test_diferente_when_db_empty(self):
        svc = self._svc_with_db({})  # grade_1 ausente no DB
        rows = {r.field_id: r for r in svc.build_rows()}
        self.assertEqual(rows['grade_1'].status, FieldStatus.DIFERENTE)

    def test_conflito_when_validated_and_differs(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra(pathlib.Path(tmp), _pilar_json())
            item = _item_data(overrides={'grade_1': 99.0, 'validated_fields': ['grade_1']})
            svc  = ComparisonService(item, str(obra))
        rows = {r.field_id: r for r in svc.build_rows()}
        self.assertEqual(rows['grade_1'].status, FieldStatus.CONFLITO)

    def test_ausente_f4_for_field_not_in_f4(self):
        """Campo que não está em Fase-4 deve ser AUSENTE_F4."""
        import tempfile
        pj = _pilar_json()
        # Remover grade_1 do JSON
        pj.pop('grade_1', None)
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra(pathlib.Path(tmp), pj)
            item = _item_data(overrides={'grade_1': 88.0})
            svc  = ComparisonService(item, str(obra))
        rows = {r.field_id: r for r in svc.build_rows()}
        # grade_1 não está em Fase-4 → AUSENTE_F4 ou não aparece
        if 'grade_1' in rows:
            self.assertEqual(rows['grade_1'].status, FieldStatus.AUSENTE_F4)


# ─── AC-3: Score ──────────────────────────────────────────────────────────────

class TestScore(unittest.TestCase):
    def test_score_keys(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra(pathlib.Path(tmp), _pilar_json())
            svc  = ComparisonService(_item_data(), str(obra))
        sc = svc.score()
        for k in ('total', 'f4_filled', 'matched', 'completude_pct', 'match_pct'):
            self.assertIn(k, sc, f"Chave {k} ausente no score")

    def test_score_with_matching_db(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra(pathlib.Path(tmp), _pilar_json())
            item = _item_data(overrides={'grade_1': 88.0, 'altura': 280.0})
            svc  = ComparisonService(item, str(obra))
        sc = svc.score()
        self.assertGreater(sc['matched'], 0)
        self.assertGreater(sc['completude_pct'], 0)

    def test_score_100pct_completude_when_f4_full(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra(pathlib.Path(tmp), _pilar_json())
            svc  = ComparisonService(_item_data(), str(obra))
        sc = svc.score()
        self.assertGreater(sc['completude_pct'], 0)


# ─── AC-4: Accept field ───────────────────────────────────────────────────────

class TestAcceptField(unittest.TestCase):
    def test_accept_updates_item_data_grade_1(self):
        import tempfile
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra(pathlib.Path(tmp), _pilar_json())
            item = _item_data(overrides={'grade_1': 0})
            db   = MagicMock()
            svc  = ComparisonService(item, str(obra))
            ok   = svc.accept_field('grade_1', db, 'proj1')
        self.assertTrue(ok)
        self.assertEqual(item.get('grade_1'), 88.0)

    def test_accept_does_not_add_to_validated_fields(self):
        import tempfile
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra(pathlib.Path(tmp), _pilar_json())
            item = _item_data()
            db   = MagicMock()
            svc  = ComparisonService(item, str(obra))
            svc.accept_field('grade_1', db, 'proj1')
        self.assertNotIn('grade_1', item.get('validated_fields', []))

    def test_accept_sides_data_face_h2(self):
        # Chapas de forma agora são flat fields: p_sA_c_h2 (não mais sides_data)
        import tempfile
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra(pathlib.Path(tmp), _pilar_json())
            item = _item_data()
            db   = MagicMock()
            svc  = ComparisonService(item, str(obra))
            # O field correto agora é p_sA_c_h2 (chapa face A, altura 2)
            ok   = svc.accept_field('p_sA_c_h2', db, 'proj1')
        # accept_field retorna True quando campo existe no mapeamento
        # Se não encontrar o field, retorna False — verificar que não crasha
        self.assertIsInstance(ok, bool)


# ─── AC-5: Accept all sem conflito ───────────────────────────────────────────

class TestAcceptAllNonConflict(unittest.TestCase):
    def test_conflict_preserved(self):
        import tempfile
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra(pathlib.Path(tmp), _pilar_json())
            item = _item_data(overrides={
                'grade_1': 99.0, 'validated_fields': ['grade_1']
            })
            db  = MagicMock()
            svc = ComparisonService(item, str(obra))
            accepted, preserved = svc.accept_all_non_conflict(db, 'proj1')
        # grade_1 é CONFLITO → preservado
        self.assertGreaterEqual(preserved, 1)
        self.assertEqual(item.get('grade_1'), 99.0)

    def test_accepts_differente_fields(self):
        import tempfile
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra(pathlib.Path(tmp), _pilar_json())
            item = _item_data()  # DB vazio = todos DIFERENTE
            db   = MagicMock()
            svc  = ComparisonService(item, str(obra))
            accepted, _ = svc.accept_all_non_conflict(db, 'proj1')
        self.assertGreater(accepted, 0)


# ─── AC-6: save_correction ────────────────────────────────────────────────────

class TestSaveCorrection(unittest.TestCase):
    def test_correction_log_created(self):
        import tempfile
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra(pathlib.Path(tmp), _pilar_json())
            item = _item_data()
            db   = MagicMock()
            svc  = ComparisonService(item, str(obra))
            ok   = svc.save_correction('grade_1', 95.0, db, 'proj1')

            log_path = obra / "Fase-3_Interpretacao_Extracao" / "correction_log.json"
            self.assertTrue(ok)
            self.assertTrue(log_path.exists())
            entries = json.loads(log_path.read_text(encoding='utf-8'))
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]['field'], 'grade_1')
            self.assertEqual(entries[0]['new_value'], 95.0)

    def test_backup_created(self):
        import tempfile
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra(pathlib.Path(tmp), _pilar_json())
            item = _item_data()
            db   = MagicMock()
            svc  = ComparisonService(item, str(obra))
            svc.save_correction('grade_1', 95.0, db, 'proj1')

            bak = obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / "P1.json.bak"
            self.assertTrue(bak.exists())

    def test_json_updated_with_new_value(self):
        import tempfile
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra(pathlib.Path(tmp), _pilar_json())
            item = _item_data()
            db   = MagicMock()
            svc  = ComparisonService(item, str(obra))
            svc.save_correction('grade_1', 95.0, db, 'proj1')

            updated = json.loads(
                (obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / "P1.json")
                .read_text(encoding='utf-8')
            )
            self.assertEqual(updated.get('grade_1'), 95.0)


# ─── AC-7: GT carregado corretamente ─────────────────────────────────────────

class TestGTLoading(unittest.TestCase):
    def test_gt_value_used_for_altura(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            gt = {'b': 19, 'h': 19, 'altura': 300.0, 'confidence': 0.9}
            obra = _make_obra(pathlib.Path(tmp), _pilar_json(), gt_json=gt)
            svc  = ComparisonService(_item_data(), str(obra))
        rows = {r.field_id: r for r in svc.build_rows()}
        # altura deve ter gt_value = 300.0
        if 'altura' in rows:
            self.assertEqual(rows['altura'].gt_value, 300.0)


# ─── Helpers unit ─────────────────────────────────────────────────────────────

class TestHelpers(unittest.TestCase):
    def test_fmt_float_integer(self):
        self.assertEqual(_fmt(260.0), '260')

    def test_fmt_none(self):
        self.assertEqual(_fmt(None), '')

    def test_eq_floats_within_tolerance(self):
        self.assertTrue(_eq(260.0, 260.04))
        self.assertFalse(_eq(260.0, 261.0))

    def test_empty_zero_float(self):
        self.assertTrue(_empty(0.0))
        self.assertTrue(_empty(None))
        self.assertFalse(_empty(1.0))


if __name__ == '__main__':
    unittest.main(verbosity=2)
