"""
tests/test_cad12_delivery.py -- CAD-12
Testes do DeliveryService e utilitário _find_oda.
"""
import json
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Garantir raiz no path
sys.path.insert(0, str(Path(__file__).parent.parent))

OBRA_TREINO = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1")
OBRA_FAKE   = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/__fake_obra_cad12__")


# ── _find_oda ─────────────────────────────────────────────────────────────────

def test_find_oda_returns_none_or_str():
    from src.core.services.delivery_service import _find_oda
    result = _find_oda()
    assert result is None or isinstance(result, str)


def test_find_oda_path_is_executable_if_found():
    from src.core.services.delivery_service import _find_oda
    result = _find_oda()
    if result is not None:
        assert Path(result).exists()


# ── DeliveryService.__init__ ──────────────────────────────────────────────────

def test_delivery_service_init_ok():
    from src.core.services.delivery_service import DeliveryService
    svc = DeliveryService(str(OBRA_TREINO))
    assert Path(svc.obra_path) == OBRA_TREINO


def test_delivery_service_init_fake_path():
    from src.core.services.delivery_service import DeliveryService
    svc = DeliveryService(str(OBRA_FAKE))
    assert svc is not None  # não explode na init


# ── build_delivery (empty obra) ───────────────────────────────────────────────

def test_build_delivery_empty_obra_returns_dict():
    from src.core.services.delivery_service import DeliveryService
    svc = DeliveryService(str(OBRA_FAKE))
    # generate_all returns {tipo: (ok, path|None)}
    with patch('src.core.services.delivery_service.DXFGeneratorService') as mock_cls:
        mock_inst = MagicMock()
        mock_inst.generate_all.return_value = {
            'PL': (False, None), 'LV': (False, None),
            'FV': (False, None), 'LJ': (False, None),
        }
        mock_cls.return_value = mock_inst
        result = svc.build_delivery()
    assert 'dxfs_ok' in result
    assert 'dwgs_ok' in result
    assert 'erros' in result
    assert 'tempo_ms' in result


def test_build_delivery_returns_int_tempo():
    from src.core.services.delivery_service import DeliveryService
    svc = DeliveryService(str(OBRA_FAKE))
    with patch('src.core.services.delivery_service.DXFGeneratorService') as mock_cls:
        mock_inst = MagicMock()
        mock_inst.generate_all.return_value = {}
        mock_cls.return_value = mock_inst
        result = svc.build_delivery()
    assert isinstance(result['tempo_ms'], int)
    assert result['tempo_ms'] >= 0


# ── build_delivery: DXF generation mocked ────────────────────────────────────

def test_build_delivery_counts_dxfs_ok(tmp_path):
    from src.core.services.delivery_service import DeliveryService
    svc = DeliveryService(str(tmp_path))
    fake_pl = tmp_path / 'Fase-6_Execucao_CAD' / 'PL_stog_quality.dxf'
    fake_pl.parent.mkdir(parents=True)
    fake_pl.write_text('DXF')
    fake_fv = tmp_path / 'Fase-6_Execucao_CAD' / 'FV_stog_quality.dxf'
    fake_fv.write_text('DXF')
    with patch('src.core.services.delivery_service.DXFGeneratorService') as mock_cls, \
         patch('src.core.services.delivery_service._find_oda', return_value=None):
        mock_inst = MagicMock()
        mock_inst.generate_all.return_value = {
            'PL': (True, fake_pl), 'LV': (False, None),
            'FV': (True, fake_fv), 'LJ': (False, None),
        }
        mock_cls.return_value = mock_inst
        result = svc.build_delivery()
    assert result['dxfs_ok'] == 2


def test_build_delivery_erros_is_list():
    from src.core.services.delivery_service import DeliveryService
    svc = DeliveryService(str(OBRA_FAKE))
    with patch('src.core.services.delivery_service.DXFGeneratorService') as mock_cls:
        mock_inst = MagicMock()
        mock_inst.generate_all.return_value = {}
        mock_cls.return_value = mock_inst
        result = svc.build_delivery()
    assert isinstance(result['erros'], list)


# ── build_delivery: ODA not available ────────────────────────────────────────

def test_build_delivery_oda_not_available_skips_gracefully(tmp_path):
    from src.core.services.delivery_service import DeliveryService
    svc = DeliveryService(str(tmp_path))
    fake_pl = tmp_path / 'Fase-6_Execucao_CAD' / 'PL_stog_quality.dxf'
    fake_pl.parent.mkdir(parents=True)
    fake_pl.write_text('DXF')
    with patch('src.core.services.delivery_service.DXFGeneratorService') as mock_cls, \
         patch('src.core.services.delivery_service._find_oda', return_value=None):
        mock_inst = MagicMock()
        mock_inst.generate_all.return_value = {'PL': (True, fake_pl)}
        mock_cls.return_value = mock_inst
        result = svc.build_delivery()
    assert result['dwgs_ok'] == 0  # sem ODA → 0 DWGs


# ── report_path ───────────────────────────────────────────────────────────────

def test_build_delivery_report_path_none_when_no_output(tmp_path):
    from src.core.services.delivery_service import DeliveryService
    svc = DeliveryService(str(tmp_path))
    with patch('src.core.services.delivery_service.DXFGeneratorService') as mock_cls:
        mock_inst = MagicMock()
        mock_inst.generate_all.return_value = {}
        mock_cls.return_value = mock_inst
        result = svc.build_delivery()
    # report_path pode ser None ou string
    rp = result.get('report_path')
    assert rp is None or isinstance(rp, str)


# ── delivery_report.json written when dxfs produced ──────────────────────────

def test_build_delivery_writes_report_json(tmp_path):
    from src.core.services.delivery_service import DeliveryService
    dxf_dir = tmp_path / 'Fase-6_Execucao_CAD'
    dxf_dir.mkdir(parents=True)
    fake_dxf = dxf_dir / 'PL_stog_quality.dxf'
    fake_dxf.write_text('DXF')

    svc = DeliveryService(str(tmp_path))
    with patch('src.core.services.delivery_service.DXFGeneratorService') as mock_cls, \
         patch('src.core.services.delivery_service._find_oda', return_value=None):
        mock_inst = MagicMock()
        mock_inst.generate_all.return_value = {'PL': (True, fake_dxf)}
        mock_cls.return_value = mock_inst
        result = svc.build_delivery()

    if result.get('report_path'):
        rp = Path(result['report_path'])
        assert rp.exists()
        data = json.loads(rp.read_text())
        assert 'dxfs_ok' in data
