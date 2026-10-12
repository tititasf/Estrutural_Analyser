import pytest
from src.core import niveis_extractor as levels


def test_verified_run_datum_wins_over_another_floor_convention(monkeypatch):
    def wrong_convention(*args):
        pytest.fail('Pinned context must not be replaced by the legacy resolver')
    monkeypatch.setattr(levels, 'get_pavimento_niveis_abs', wrong_convention)
    result = levels.resolve_panel_level_reference('obra', 'TIPO', {
        'base': 534.94, 'top': 537.86, 'height': 2.92,
        'unit': 'm', 'source_id': 'verified-source'})
    assert result['saida_abs'] == 534.94
    assert result['chegada_abs'] == 537.86
    assert result['altura_cm'] == pytest.approx(292)


@pytest.mark.parametrize('change', [
    {'source_id': ''}, {'unit': 'cm'}, {'top': float('nan')},
    {'height': 3.1}, {'top': 800}, {'base': None}])
def test_invalid_context_falls_back_only_to_explicit_floor(monkeypatch, change):
    calls = []
    monkeypatch.setattr(levels, 'get_pavimento_niveis_abs',
                        lambda obra, pav: calls.append((obra, pav)) or {})
    pinned = dict(base=100, top=103, height=3, unit='m', source_id='source')
    pinned.update(change)
    assert levels.resolve_panel_level_reference('/actual/obra', '7_PAV', pinned) == {}
    assert calls == [('/actual/obra', '7_PAV')]


def test_unknown_floor_does_not_default_to_thirteen(monkeypatch):
    monkeypatch.setattr(levels, 'get_pavimento_niveis_abs',
                        lambda *args: pytest.fail('No floor has been selected'))
    assert levels.resolve_panel_level_reference('obra', '') == {}


def test_beam_default_formats_known_metre_datum_and_keeps_unknown_empty(monkeypatch):
    pinned = dict(base=852.19, top=855.25, height=3.06, unit='m', source_id='verified')
    assert levels.resolve_beam_default_level('', '', pinned) == '855,25 m'
    assert levels.resolve_beam_default_level('', '') == ''
    monkeypatch.setattr(levels, 'get_pavimento_niveis_abs',
                        lambda *args: {'chegada_abs': 852})
    assert levels.resolve_beam_default_level('/explicit/obra', 'PAV') == '852,00 m'


@pytest.mark.parametrize('name,expected', [
    ('TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA', 13),
    ('TMC-EST-EX-3000-1PV-R00', 1), ('13_PAV', 13), ('13', 13),
    ('EST-PE-007-TIPO-R01', None), ('TIPO_TESTE', None),
    ('TMC-EST-EX-2000-TER-R01', 0), ('TER', 0),
    ('TMC-EST-PE-8000-COB-R03', 9999), ('ATC', 10000),
    ('TMC-EST-EX-5000-TIP-R00', None), ('sheet_007_R01', None),
])
def test_floor_identity_never_comes_from_sheet_or_revision(name, expected):
    assert levels.pav_num_from_sa_name(name) == expected


def test_unknown_height_never_becomes_default_panel(tmp_path, monkeypatch):
    import ezdxf
    ezdxf.new().saveas(tmp_path / 'convencao_niveis.dxf')
    monkeypatch.setattr(levels, 'extract_elevacao_tipica', lambda texts: [
        {'pav_num': 1, 'chegada': '530', 'altura': '?'},
        {'pav_num': 7, 'chegada': '550', 'altura': '?'}])
    assert levels.get_pavimento_niveis_abs(str(tmp_path), '7_PAV') == {}
