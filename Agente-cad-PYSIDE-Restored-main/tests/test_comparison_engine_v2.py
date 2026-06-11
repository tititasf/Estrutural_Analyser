#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_comparison_engine_v2.py — CAD-10.5
Testa AuditExporter + lógica do Comparison Engine renovado (sem Qt).
"""
import json
import pathlib
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.core.services.audit_exporter import AuditExporter, _load_db_items, _score_item


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_obra_with_items(tmp: pathlib.Path, itens: list[dict]) -> pathlib.Path:
    """Cria obra com JSON_Pilares para cada item da lista."""
    obra = tmp / "Obra_AUDIT_TEST"
    (obra / "Fase-4_Sincronizacao" / "JSON_Pilares").mkdir(parents=True)
    (obra / "Fase-4_Sincronizacao" / "JSON_Vigas_Laterais").mkdir(parents=True)
    (obra / "Fase-4_Sincronizacao" / "JSON_Vigas_Fundo").mkdir(parents=True)
    (obra / "Fase-4_Sincronizacao" / "JSON_Lajes").mkdir(parents=True)
    (obra / "Fase-8_Revisao_Entrega").mkdir(parents=True)

    for item in itens:
        nome = item.get('nome', 'P1')
        (obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{nome}.json").write_text(
            json.dumps(item), encoding='utf-8')
    return obra


def _pilar_json(nome='P1', grade=88.0):
    return {
        "nome": nome, "floor": "TERREO",
        "comprimento": 19.0, "largura": 19.0, "altura": 280.0,
        "grade_1": grade, "par_1_2": 20.0,
        "distancia_1": 5.0, "distancia_2": 5.0,
        "h1_A": 5.0, "h2_A": 260.0, "h3_A": 15.0, "larg1_A": 19.0,
        "h1_B": 5.0, "h2_B": 260.0, "h3_B": 15.0, "larg1_B": 19.0,
        "h1_C": 5.0, "h2_C": 260.0, "h3_C": 15.0, "larg1_C": 19.0,
        "h1_D": 5.0, "h2_D": 260.0, "h3_D": 15.0, "larg1_D": 19.0,
    }


def _item_data(nome='P1', overrides=None):
    d = {
        'id': f'proj1_pil_{nome}', 'id_item': nome, 'name': nome,
        'type': 'Pilar', 'validated_fields': [], 'sides_data': {},
    }
    if overrides:
        d.update(overrides)
    return d


def _make_db(pillars=None, beams=None, slabs=None):
    db = MagicMock()
    db.load_pillars.return_value = pillars or []
    db.load_beams.return_value   = beams   or []
    db.load_slabs.return_value   = slabs   or []
    return db


# ─── AC-1: _score_item ────────────────────────────────────────────────────────

class TestScoreItem(unittest.TestCase):
    def test_score_item_with_fase4(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra_with_items(pathlib.Path(tmp), [_pilar_json('P1')])
            result = _score_item(_item_data('P1'), str(obra))

        self.assertTrue(result['has_fase4'])
        self.assertIsNotNone(result['score'])
        self.assertIsNotNone(result['completude'])
        self.assertEqual(result['id'], 'P1')

    def test_score_item_without_fase4(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = pathlib.Path(tmp) / "Obra_EMPTY"
            (obra / "Fase-4_Sincronizacao" / "JSON_Pilares").mkdir(parents=True)
            result = _score_item(_item_data('P99'), str(obra))

        self.assertFalse(result['has_fase4'])
        self.assertIsNone(result['score'])

    def test_score_item_returns_conflicts_list(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra_with_items(pathlib.Path(tmp), [_pilar_json('P1')])
            # grade_1 validado com valor diferente → CONFLITO
            item = _item_data('P1', {'grade_1': 99.0, 'validated_fields': ['grade_1']})
            result = _score_item(item, str(obra))

        self.assertIn('conflicts', result)
        self.assertIn('grade_1', result['conflicts'])


# ─── AC-2: AuditExporter.build_report ────────────────────────────────────────

class TestBuildReport(unittest.TestCase):
    def _run(self, itens_json, item_datas):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra_with_items(pathlib.Path(tmp), itens_json)
            db   = _make_db(pillars=item_datas)
            exp  = AuditExporter(str(obra), 'proj1', db)
            report = exp.build_report(tipos=['pilar'])
        return report

    def test_report_keys(self):
        report = self._run([_pilar_json('P1')], [_item_data('P1')])
        for k in ('obra', 'project_id', 'timestamp', 'summary', 'items'):
            self.assertIn(k, report, f"Chave {k} ausente")

    def test_report_summary_pilares(self):
        report = self._run(
            [_pilar_json('P1'), _pilar_json('P2')],
            [_item_data('P1'), _item_data('P2')]
        )
        self.assertIn('pilares', report['summary'])
        self.assertEqual(report['summary']['pilares']['total'], 2)

    def test_report_items_count(self):
        report = self._run([_pilar_json('P1')], [_item_data('P1')])
        self.assertEqual(len(report['items']), 1)
        self.assertEqual(report['items'][0]['id'], 'P1')

    def test_avg_score_computed(self):
        report = self._run(
            [_pilar_json('P1'), _pilar_json('P2')],
            [_item_data('P1'), _item_data('P2')]
        )
        s = report['summary']['pilares']
        self.assertIsNotNone(s.get('avg_score'))
        self.assertGreaterEqual(s['avg_score'], 0)

    def test_report_empty_when_no_items(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = pathlib.Path(tmp) / "Obra_EMPTY"
            (obra / "Fase-8_Revisao_Entrega").mkdir(parents=True)
            db   = _make_db(pillars=[])
            exp  = AuditExporter(str(obra), 'proj1', db)
            report = exp.build_report(tipos=['pilar'])
        # Sem itens → summary pode estar vazio, não deve crashar
        self.assertIn('summary', report)
        self.assertIn('items', report)


# ─── AC-3: AuditExporter.save ─────────────────────────────────────────────────

class TestSaveReport(unittest.TestCase):
    def test_saves_json_and_markdown(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra_with_items(pathlib.Path(tmp), [_pilar_json('P1')])
            db   = _make_db(pillars=[_item_data('P1')])
            exp  = AuditExporter(str(obra), 'proj1', db)
            report = exp.build_report(tipos=['pilar'])
            json_path = exp.save(report)

            self.assertTrue(json_path.exists())
            md_path = json_path.with_suffix('.md')
            self.assertTrue(md_path.exists())

    def test_json_content_valid(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra_with_items(pathlib.Path(tmp), [_pilar_json('P1')])
            db   = _make_db(pillars=[_item_data('P1')])
            exp  = AuditExporter(str(obra), 'proj1', db)
            report = exp.build_report(tipos=['pilar'])
            json_path = exp.save(report)

            loaded = json.loads(json_path.read_text(encoding='utf-8'))
            self.assertIn('summary', loaded)
            self.assertIn('items', loaded)

    def test_markdown_has_summary_table(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra_with_items(pathlib.Path(tmp), [_pilar_json('P1')])
            db   = _make_db(pillars=[_item_data('P1')])
            exp  = AuditExporter(str(obra), 'proj1', db)
            report = exp.build_report(tipos=['pilar'])
            json_path = exp.save(report)

            md = json_path.with_suffix('.md').read_text(encoding='utf-8')
            self.assertIn('Resumo por Tipo', md)
            self.assertIn('Itens Detalhados', md)

    def test_saves_to_fase8_dir_by_default(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra_with_items(pathlib.Path(tmp), [_pilar_json('P1')])
            db   = _make_db(pillars=[_item_data('P1')])
            exp  = AuditExporter(str(obra), 'proj1', db)
            report = exp.build_report(tipos=['pilar'])
            json_path = exp.save(report)

            self.assertIn('Fase-8_Revisao_Entrega', str(json_path))

    def test_custom_output_dir(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra    = _make_obra_with_items(pathlib.Path(tmp), [_pilar_json('P1')])
            out_dir = pathlib.Path(tmp) / "custom_out"
            db      = _make_db(pillars=[_item_data('P1')])
            exp     = AuditExporter(str(obra), 'proj1', db)
            report  = exp.build_report(tipos=['pilar'])
            json_path = exp.save(report, output_dir=out_dir)

            self.assertTrue(out_dir.exists())
            self.assertTrue(json_path.exists())


# ─── AC-4: _load_db_items ────────────────────────────────────────────────────

class TestLoadDbItems(unittest.TestCase):
    def test_loads_pillars(self):
        db = _make_db(pillars=[_item_data('P1'), _item_data('P2')])
        items = _load_db_items(db, 'proj1', 'pilar')
        self.assertEqual(len(items), 2)

    def test_loads_slabs(self):
        db = _make_db(slabs=[{'id_item': 'L1', 'type': 'Laje'}])
        items = _load_db_items(db, 'proj1', 'laje')
        self.assertEqual(len(items), 1)

    def test_returns_empty_on_db_error(self):
        db = MagicMock()
        db.load_pillars.side_effect = Exception("DB error")
        items = _load_db_items(db, 'proj1', 'pilar')
        self.assertEqual(items, [])


# ─── AC-5: Múltiplos tipos no relatório ──────────────────────────────────────

class TestMultiTipoReport(unittest.TestCase):
    def test_report_with_all_tipos(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obra = _make_obra_with_items(pathlib.Path(tmp), [_pilar_json('P1')])
            db = _make_db(
                pillars=[_item_data('P1')],
                beams=[{'id_item': 'V1', 'id': 'proj1_vig_V1', 'name': 'V1',
                        'type': 'Viga', 'validated_fields': [], 'sides_data': {}}],
                slabs=[{'id_item': 'L1', 'id': 'proj1_laj_L1', 'name': 'L1',
                        'type': 'Laje', 'validated_fields': [], 'links': {}}],
            )
            exp = AuditExporter(str(obra), 'proj1', db)
            report = exp.build_report(tipos=['pilar', 'viga', 'laje'])

        # Pilar tem Fase-4, viga e laje não têm → devem aparecer mas sem score
        self.assertIn('pilares', report['summary'])
        self.assertEqual(report['summary']['pilares']['total'], 1)
        # Total de items = 3 (um de cada tipo)
        self.assertEqual(len(report['items']), 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
