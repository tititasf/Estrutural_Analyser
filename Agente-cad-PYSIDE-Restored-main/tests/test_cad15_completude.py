"""
tests/test_cad15_completude.py -- CAD-15
Testes do completude_cache.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

OBRA_TREINO = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1"


# ── invalidate_cache ─────────────────────────────────────────────────────────

def test_invalidate_cache_no_error_on_missing():
    from src.core.services.completude_cache import invalidate_cache, _cache
    invalidate_cache('nonexistent_project')  # should not raise


def test_invalidate_cache_removes_entry():
    from src.core.services import completude_cache as cc
    cc._cache['test_pid'] = {'P1': 75.0}
    cc.invalidate_cache('test_pid')
    assert 'test_pid' not in cc._cache


# ── compute_completude_batch ──────────────────────────────────────────────────

def test_compute_completude_batch_empty_items():
    from src.core.services.completude_cache import compute_completude_batch
    result = compute_completude_batch([], obra_path=OBRA_TREINO)
    assert result == {}


def test_compute_completude_batch_returns_dict_of_floats():
    from src.core.services.completude_cache import compute_completude_batch
    items = [
        {'id_item': 'P1', 'type': 'Pilar'},
        {'id_item': 'P2', 'type': 'Pilar'},
    ]
    mock_svc = MagicMock()
    mock_svc.score.return_value = {'completude_pct': 65.0, 'match_pct': 50.0, 'total': 10, 'f4_filled': 6, 'matched': 3}
    with patch('src.core.services.completude_cache.ComparisonService', return_value=mock_svc):
        result = compute_completude_batch(items, obra_path=OBRA_TREINO)
    assert set(result.keys()) == {'P1', 'P2'}
    for v in result.values():
        assert isinstance(v, float)


def test_compute_completude_batch_uses_cache(tmp_path):
    from src.core.services import completude_cache as cc
    pid = 'cached_pid_test'
    cc._cache[pid] = {'X1': 88.0}
    items = [{'id_item': 'X1', 'type': 'Pilar'}]
    result = cc.compute_completude_batch(items, project_id=pid)
    assert result == {'X1': 88.0}
    cc._cache.pop(pid, None)


def test_compute_completude_batch_populates_cache():
    from src.core.services import completude_cache as cc
    pid = 'new_pid_cad15'
    cc._cache.pop(pid, None)
    items = [{'id_item': 'P1', 'type': 'Pilar'}]
    mock_svc = MagicMock()
    mock_svc.score.return_value = {'completude_pct': 50.0}
    with patch('src.core.services.completude_cache.ComparisonService', return_value=mock_svc):
        cc.compute_completude_batch(items, obra_path=OBRA_TREINO, project_id=pid)
    assert pid in cc._cache
    assert cc._cache[pid].get('P1') == pytest.approx(50.0)
    cc._cache.pop(pid, None)


def test_compute_completude_batch_zero_on_exception():
    from src.core.services.completude_cache import compute_completude_batch
    items = [{'id_item': 'P1', 'type': 'Pilar'}]
    with patch('src.core.services.completude_cache.ComparisonService', side_effect=Exception("boom")):
        result = compute_completude_batch(items, obra_path=OBRA_TREINO)
    assert result.get('P1', -1) == pytest.approx(0.0)


# ── get_completude ────────────────────────────────────────────────────────────

def test_get_completude_single_item():
    from src.core.services import completude_cache as cc
    pid = 'single_pid_cad15'
    cc._cache.pop(pid, None)
    item = {'id_item': 'P3', 'type': 'Laje'}
    mock_svc = MagicMock()
    mock_svc.score.return_value = {'completude_pct': 72.0}
    with patch('src.core.services.completude_cache.ComparisonService', return_value=mock_svc):
        val = cc.get_completude(item, obra_path=OBRA_TREINO, project_id=pid)
    assert val == pytest.approx(72.0)
    cc._cache.pop(pid, None)


def test_get_completude_from_cache():
    from src.core.services import completude_cache as cc
    pid = 'cached_get_pid'
    cc._cache[pid] = {'P5': 33.0}
    item = {'id_item': 'P5', 'type': 'Pilar'}
    val = cc.get_completude(item, project_id=pid)
    assert val == pytest.approx(33.0)
    cc._cache.pop(pid, None)
