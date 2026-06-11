"""
tests/test_cad13_ml_feedback.py -- CAD-13
Testes do MLFeedbackService.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

OBRA_TREINO = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1"
OBRA_FAKE   = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/__fake_cad13__"


# ── Init ──────────────────────────────────────────────────────────────────────

def test_init_sets_obra_path():
    from src.core.services.ml_feedback_service import MLFeedbackService
    svc = MLFeedbackService(OBRA_TREINO)
    assert Path(svc.obra_path) == Path(OBRA_TREINO)


# ── _load_log ─────────────────────────────────────────────────────────────────

def test_load_log_empty_when_no_file():
    from src.core.services.ml_feedback_service import MLFeedbackService
    svc = MLFeedbackService(OBRA_FAKE)
    assert svc._load_log() == []


def test_load_log_returns_list(tmp_path):
    from src.core.services.ml_feedback_service import MLFeedbackService
    log_dir = tmp_path / 'Fase-3_Interpretacao_Extracao'
    log_dir.mkdir()
    entries = [
        {'field': 'altura', 'old_value': '280', 'new_value': '300',
         'item_id': 'P1', 'item_type': 'Pilar', 'timestamp': '2026-01-01'},
    ]
    (log_dir / 'correction_log.json').write_text(json.dumps(entries))
    svc = MLFeedbackService(str(tmp_path))
    assert svc._load_log() == entries


def test_load_log_handles_invalid_json(tmp_path):
    from src.core.services.ml_feedback_service import MLFeedbackService
    log_dir = tmp_path / 'Fase-3_Interpretacao_Extracao'
    log_dir.mkdir()
    (log_dir / 'correction_log.json').write_text("NOT JSON{{")
    svc = MLFeedbackService(str(tmp_path))
    assert svc._load_log() == []


# ── _safe_delta ───────────────────────────────────────────────────────────────

def test_safe_delta_numeric():
    from src.core.services.ml_feedback_service import MLFeedbackService
    assert MLFeedbackService._safe_delta(100, 120) == pytest.approx(20.0)


def test_safe_delta_strings():
    from src.core.services.ml_feedback_service import MLFeedbackService
    assert MLFeedbackService._safe_delta('280', '300') == pytest.approx(20.0)


def test_safe_delta_non_numeric():
    from src.core.services.ml_feedback_service import MLFeedbackService
    assert MLFeedbackService._safe_delta('abc', 'xyz') is None


def test_safe_delta_none_values():
    from src.core.services.ml_feedback_service import MLFeedbackService
    assert MLFeedbackService._safe_delta(None, 10) is None


# ── export_training_data (empty) ──────────────────────────────────────────────

def test_export_training_data_empty():
    from src.core.services.ml_feedback_service import MLFeedbackService
    svc = MLFeedbackService(OBRA_FAKE)
    result = svc.export_training_data()
    assert result['entries'] == 0
    assert result['top_uncertain_fields'] == []
    assert result['export_path'] is None


# ── export_training_data (with data) ─────────────────────────────────────────

def test_export_training_data_writes_file(tmp_path):
    from src.core.services.ml_feedback_service import MLFeedbackService
    log_dir = tmp_path / 'Fase-3_Interpretacao_Extracao'
    log_dir.mkdir()
    entries = [
        {'field': 'altura', 'old_value': '280', 'new_value': '300',
         'item_id': 'P1', 'item_type': 'Pilar', 'timestamp': '2026-01-01T00:00:00'},
        {'field': 'altura', 'old_value': '300', 'new_value': '320',
         'item_id': 'P2', 'item_type': 'Pilar', 'timestamp': '2026-01-02T00:00:00'},
        {'field': 'largura', 'old_value': '14', 'new_value': '16',
         'item_id': 'P1', 'item_type': 'Pilar', 'timestamp': '2026-01-03T00:00:00'},
    ]
    (log_dir / 'correction_log.json').write_text(json.dumps(entries))
    svc = MLFeedbackService(str(tmp_path))
    result = svc.export_training_data()
    assert result['entries'] == 3
    assert len(result['top_uncertain_fields']) >= 1
    assert result['export_path'] is not None
    assert Path(result['export_path']).exists()
    data = json.loads(Path(result['export_path']).read_text())
    assert len(data['training']) == 3
    assert data['training'][0]['field'] == 'altura'


def test_export_training_data_top_uncertain_sorted(tmp_path):
    from src.core.services.ml_feedback_service import MLFeedbackService
    log_dir = tmp_path / 'Fase-3_Interpretacao_Extracao'
    log_dir.mkdir()
    entries = (
        [{'field': 'altura', 'old_value': '280', 'new_value': '300', 'item_id': f'P{i}', 'item_type': 'Pilar', 'timestamp': '2026-01-01'} for i in range(5)] +
        [{'field': 'largura', 'old_value': '14', 'new_value': '16', 'item_id': f'P{i}', 'item_type': 'Pilar', 'timestamp': '2026-01-01'} for i in range(2)]
    )
    (log_dir / 'correction_log.json').write_text(json.dumps(entries))
    svc = MLFeedbackService(str(tmp_path))
    result = svc.export_training_data()
    top = result['top_uncertain_fields']
    assert top[0]['field'] == 'altura'
    assert top[0]['corrections'] == 5


# ── get_model_insights (empty) ────────────────────────────────────────────────

def test_get_model_insights_empty():
    from src.core.services.ml_feedback_service import MLFeedbackService
    svc = MLFeedbackService(OBRA_FAKE)
    result = svc.get_model_insights()
    assert result['total_corrections'] == 0
    assert isinstance(result['insights'], list)
    assert len(result['insights']) >= 1


# ── get_model_insights (with data) ───────────────────────────────────────────

def test_get_model_insights_detects_systematic_field(tmp_path):
    from src.core.services.ml_feedback_service import MLFeedbackService
    log_dir = tmp_path / 'Fase-3_Interpretacao_Extracao'
    log_dir.mkdir()
    # 'altura' corrigido em 60% dos casos → sistematicamente incerto
    entries = (
        [{'field': 'altura', 'old_value': '280', 'new_value': '300', 'item_id': f'P{i}', 'item_type': 'Pilar', 'timestamp': '2026'} for i in range(6)] +
        [{'field': 'largura', 'old_value': '14', 'new_value': '16', 'item_id': f'P{i}', 'item_type': 'Pilar', 'timestamp': '2026'} for i in range(4)]
    )
    (log_dir / 'correction_log.json').write_text(json.dumps(entries))
    svc = MLFeedbackService(str(tmp_path))
    result = svc.get_model_insights()
    assert result['total_corrections'] == 10
    assert any('sistematicamente incerto' in ins for ins in result['insights'])


def test_get_model_insights_accuracy_by_field_structure(tmp_path):
    from src.core.services.ml_feedback_service import MLFeedbackService
    log_dir = tmp_path / 'Fase-3_Interpretacao_Extracao'
    log_dir.mkdir()
    entries = [
        {'field': 'altura', 'old_value': '280', 'new_value': '300',
         'item_id': 'P1', 'item_type': 'Pilar', 'timestamp': '2026'}
    ]
    (log_dir / 'correction_log.json').write_text(json.dumps(entries))
    svc = MLFeedbackService(str(tmp_path))
    result = svc.get_model_insights()
    assert 'altura' in result['accuracy_by_field']
    info = result['accuracy_by_field']['altura']
    assert info['corrections'] == 1
    assert info['avg_delta'] == pytest.approx(20.0)
    assert info['items_affected'] == 1
