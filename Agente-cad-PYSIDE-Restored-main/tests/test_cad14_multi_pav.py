"""
tests/test_cad14_multi_pav.py -- CAD-14
Testes do MultiPavImporter.
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

OBRA_TREINO = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1"
OBRA_FAKE   = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/__fake_cad14__"


def _make_pav_json(tmp_path: Path, pavimentos: list[str], pav_data: dict | None = None) -> Path:
    """Helper: cria Fase-4/pavimentos_lista.json em tmp_path."""
    fase4 = tmp_path / 'Fase-4_Sincronizacao'
    fase4.mkdir(parents=True, exist_ok=True)
    if pav_data is None:
        pav_data = {name: {'nome': name, 'numero': str(i+1), 'nivel_chegada': '0.0', 'nivel_saida': '280.0'}
                    for i, name in enumerate(pavimentos)}
    content = {tmp_path.name: {'pavimentos': pavimentos, 'pavimentos_data': pav_data}}
    (fase4 / 'pavimentos_lista.json').write_text(json.dumps(content))
    return fase4


# ── detect_pavimentos ────────────────────────────────────────────────────────

def test_detect_pavimentos_no_file():
    from src.core.services.multi_pav_importer import MultiPavImporter
    imp = MultiPavImporter(MagicMock())
    result = imp.detect_pavimentos(OBRA_FAKE)
    assert result == []


def test_detect_pavimentos_returns_list(tmp_path):
    from src.core.services.multi_pav_importer import MultiPavImporter
    _make_pav_json(tmp_path, ['1PV', '2PV', '3PV'])
    imp = MultiPavImporter(MagicMock())
    result = imp.detect_pavimentos(str(tmp_path))
    assert len(result) == 3
    assert result[0]['nome'] == '1PV'


def test_detect_pavimentos_real_obra():
    from src.core.services.multi_pav_importer import MultiPavImporter
    imp = MultiPavImporter(MagicMock())
    result = imp.detect_pavimentos(OBRA_TREINO)
    # Obra_TREINO_1 tem pelo menos 1 pavimento
    assert isinstance(result, list)
    if result:
        assert 'nome' in result[0]
        assert 'nivel_chegada' in result[0]


def test_detect_pavimentos_structure(tmp_path):
    from src.core.services.multi_pav_importer import MultiPavImporter
    _make_pav_json(tmp_path, ['12 PAV'],
                   {'12 PAV': {'nome': '12 PAV', 'numero': '1', 'nivel_chegada': '0.0', 'nivel_saida': '280.0'}})
    imp = MultiPavImporter(MagicMock())
    result = imp.detect_pavimentos(str(tmp_path))
    assert result[0] == {'nome': '12 PAV', 'numero': '1', 'nivel_chegada': '0.0', 'nivel_saida': '280.0'}


# ── import_all_pavimentos ─────────────────────────────────────────────────────

def test_import_all_no_pav_json():
    from src.core.services.multi_pav_importer import MultiPavImporter
    imp = MultiPavImporter(MagicMock())
    result = imp.import_all_pavimentos(OBRA_FAKE, 'pid_001')
    assert result['pavimentos_importados'] == 0
    assert len(result['erros']) >= 1


def test_import_all_returns_required_keys(tmp_path):
    from src.core.services.multi_pav_importer import MultiPavImporter
    _make_pav_json(tmp_path, ['1PV'])
    mock_db = MagicMock()
    imp = MultiPavImporter(mock_db)
    with patch('src.core.services.multi_pav_importer.Fase4Importer') as mock_cls:
        mock_inst = MagicMock()
        mock_inst.import_obra.return_value = {
            'pilares': 5, 'vigas': 3, 'lajes': 2,
            'conflitos': 0, 'erros': [], 'tempo_ms': 100
        }
        mock_cls.return_value = mock_inst
        result = imp.import_all_pavimentos(str(tmp_path), 'pid_001')
    required = {'pavimentos_importados', 'total_pilares', 'total_vigas',
                'total_lajes', 'total_conflitos', 'erros', 'por_pavimento', 'tempo_ms'}
    assert required.issubset(result.keys())


def test_import_all_aggregates_totals(tmp_path):
    from src.core.services.multi_pav_importer import MultiPavImporter
    _make_pav_json(tmp_path, ['1PV', '2PV'])
    imp = MultiPavImporter(MagicMock())
    with patch('src.core.services.multi_pav_importer.Fase4Importer') as mock_cls:
        mock_inst = MagicMock()
        mock_inst.import_obra.return_value = {
            'pilares': 4, 'vigas': 2, 'lajes': 1,
            'conflitos': 0, 'erros': [], 'tempo_ms': 50
        }
        mock_cls.return_value = mock_inst
        result = imp.import_all_pavimentos(str(tmp_path), 'pid_001')
    assert result['total_pilares'] == 8
    assert result['total_vigas'] == 4
    assert result['total_lajes'] == 2
    assert result['pavimentos_importados'] == 2


def test_import_all_handles_exception_per_pav(tmp_path):
    from src.core.services.multi_pav_importer import MultiPavImporter
    _make_pav_json(tmp_path, ['1PV', '2PV'])
    imp = MultiPavImporter(MagicMock())
    call_count = 0

    def mock_import(obra, pav, pid):
        nonlocal call_count
        call_count += 1
        if pav == '1PV':
            raise RuntimeError("Falha simulada")
        return {'pilares': 3, 'vigas': 1, 'lajes': 1, 'conflitos': 0, 'erros': [], 'tempo_ms': 10}

    with patch('src.core.services.multi_pav_importer.Fase4Importer') as mock_cls:
        mock_inst = MagicMock()
        mock_inst.import_obra.side_effect = mock_import
        mock_cls.return_value = mock_inst
        result = imp.import_all_pavimentos(str(tmp_path), 'pid_001')
    assert result['total_pilares'] == 3
    assert any("Falha simulada" in e for e in result['erros'])
