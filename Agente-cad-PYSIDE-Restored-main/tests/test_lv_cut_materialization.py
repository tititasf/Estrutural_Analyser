from portal.app import lv_n3_cuts, ficha_reader, lv_ficha


def setup_inventory(monkeypatch):
    state = {'cuts': ['first']}
    calls = []
    monkeypatch.setattr(ficha_reader, 'ler_estado_pavimento', lambda *args: state)
    monkeypatch.setattr(ficha_reader, 'listar_itens_n1', lambda s, key:
                        [{'beam_name': 'V1'}, {'beam_name': 'V2'}] if key.endswith('passa') else [])
    monkeypatch.setattr(lv_ficha, 'montar_ficha_lv', lambda *args, **kwargs:
                        {'cut_views': [{'id': c} for c in state['cuts']]})
    def resolve(obra, floor, behavior, cut, mode):
        calls.append((floor, behavior, cut['id'], mode))
        return {'available': True, 'svg': '<svg/>', 'fingerprint': cut['id']}
    monkeypatch.setattr(lv_n3_cuts, 'resolve', resolve)
    return state, calls


def test_rebuilds_current_inventory_and_respects_item_floor_mode(monkeypatch, tmp_path):
    state, calls = setup_inventory(monkeypatch)
    first = lv_n3_cuts.materialize_pavimento(tmp_path, 'P1', 'MOLDE_2', ['V1'])
    assert (first['beams'], first['generated']) == (1, 1)
    state['cuts'] = ['new', 'additional']
    second = lv_n3_cuts.materialize_pavimento(tmp_path, 'P2', 'INI', ['V1'])
    assert [r['id'] for r in second['rows']] == ['new', 'additional']
    assert calls == [('P1', 'passa', 'first', 'MOLDE_2'),
                     ('P2', 'passa', 'new', 'INI'), ('P2', 'passa', 'additional', 'INI')]


def test_all_beams_and_failed_svg_are_reported(monkeypatch, tmp_path):
    setup_inventory(monkeypatch)
    monkeypatch.setattr(lv_n3_cuts, 'resolve', lambda *args: {'available': True, 'svg': ''})
    result = lv_n3_cuts.materialize_pavimento(tmp_path, 'P')
    assert result['beams'] == result['expected'] == len(result['errors']) == 2
    assert result['generated'] == 0


def test_missing_section_does_not_claim_success(monkeypatch, tmp_path):
    state, _ = setup_inventory(monkeypatch)
    state['cuts'] = []
    result = lv_n3_cuts.materialize_pavimento(tmp_path, 'P')
    assert len(result['errors']) == 2
