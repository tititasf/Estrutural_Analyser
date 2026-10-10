"""Gate CAD automático pós-SA: sidecar por pavimento, merge parcial e status na ficha."""
import json

from portal.app import qa_cad_gate_run as run


def _fake(monkeypatch, tmp_path, reports, fail=()):
    state = {'pilares': [{'name': 'P1'}, {'name': 'P2'}], 'lajes': [{'name': 'L1'}],
             'fundo': [{'beam_name': 'V1'}], 'lateral_a_passa': [{'beam_name': 'V1'}]}
    monkeypatch.setattr(run.ficha_reader, 'ler_estado_pavimento', lambda o, p: state)
    monkeypatch.setattr(run.ficha_reader, '_fonte_estrutural_producao', lambda o, p: tmp_path / 'torre.dxf')
    monkeypatch.setattr(run.ficha_reader, 'listar_itens_n1', lambda s, c: [{'item_id': 'L1'}])
    monkeypatch.setattr(run.item_geometry, 'collection', lambda s, c: s.get(c) or [])
    monkeypatch.setattr(run.gate, '_sha256', lambda p: 'sha')
    monkeypatch.setattr(run.interp, 'snapshot', lambda s, c, n, b='para': {'classe': c, 'item': n, 'v': reports.get('v', 1),
                                                                  'collections': {'lajes': [{'name': n}]}})
    monkeypatch.setattr(run.interp, 'fingerprint', lambda snap: f"{snap['item']}:{snap['v']}")

    def measure(source, snap):
        if snap['item'] in fail:
            raise RuntimeError('boom')
        return reports[snap['item']]
    monkeypatch.setattr(run.gate, 'measure', measure)
    monkeypatch.setattr(run.gate, 'measure_slabs', measure)
    monkeypatch.setattr(run.gate, 'measure_beams', lambda source, snap, slabs, pav: dict(measure(source, snap), slabs=slabs))
    monkeypatch.setattr(run.gate, 'measure_lateral_beams', lambda source, snap, slabs, pav: measure(source, snap))
    return state


OK = {'contacts': [{'face': 'A', 'beam': 'V1', 'status': 'measured', 'errors': {}}]}
BAD = {'contacts': [{'face': 'B', 'beam': 'V2', 'status': 'measured', 'errors': {'b': 'largura 14 ≠ 19'}}]}
UNC = {'contacts': [{'face': 'C', 'beam': 'V3', 'status': 'uncertain', 'reason': 'sem parede'}]}


def test_resumo_classifica_status():
    assert run.resumo(OK)['status'] == 'confere'
    assert run.resumo(BAD) == dict(status='diverge', divergencias=['face B V2: largura 14 ≠ 19'], incertos=[], medidos=1)
    assert run.resumo(UNC)['incertos'] == ['face C V3: sem parede']
    assert run.resumo({'error': 'sem DXF', 'contacts': []})['status'] == 'indisponivel'
    # aviso que não bloqueia promoção não vira incerto
    assert run.resumo({'contacts': [dict(UNC['contacts'][0], blocks_promotion=False)]})['status'] == 'confere'


def test_run_pavimento_grava_sidecar_e_item_ruim_nao_derruba(monkeypatch, tmp_path):
    _fake(monkeypatch, tmp_path, {'P1': OK, 'P2': BAD, 'L1': UNC, 'V1': OK}, fail={'P2'})
    path = run.run_pavimento(tmp_path, '13_PAV')
    data = json.loads(path.read_text(encoding='utf-8'))
    assert path == tmp_path / '.portal_overrides' / 'qa_cad_gate' / '13_PAV.json'
    assert data['classes']['PIL']['P1']['status'] == 'confere'
    assert data['classes']['PIL']['P2']['status'] == 'indisponivel'
    assert data['classes']['LAJ']['L1']['status'] == 'incerto'
    assert data['classes']['FV']['V1']['status'] == 'confere'
    assert data['classes']['LV'] == {'V1|passa': data['classes']['LV']['V1|passa']}
    assert data['classes']['LV']['V1|passa']['status'] == 'confere'
    assert set(data['tempos_s']) == {'PIL', 'LAJ', 'FV', 'LV'}


def test_microciclo_mescla_sem_apagar_outros_itens(monkeypatch, tmp_path):
    reports = {'P1': OK, 'P2': OK, 'L1': OK, 'V1': OK}
    _fake(monkeypatch, tmp_path, reports)
    run.run_pavimento(tmp_path, '13_PAV')
    reports['P2'] = BAD
    run.run_pavimento(tmp_path, '13_PAV', secao='pilares', item_names={'P2'})
    data = json.loads(run.sidecar_path(tmp_path, '13_PAV').read_text(encoding='utf-8'))
    assert data['classes']['PIL']['P1']['status'] == 'confere'
    assert data['classes']['PIL']['P2']['status'] == 'diverge'
    assert data['classes']['FV']['V1']['status'] == 'confere'


def test_best_effort_nunca_levanta_e_ignora_secao_sem_gate(monkeypatch, tmp_path):
    monkeypatch.setattr(run, 'run_pavimento', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('x')))
    assert run.best_effort(tmp_path, '13_PAV') is None
    assert run.best_effort(tmp_path, '13_PAV', secao='laterais_viga') is None


def test_item_status_desatualizado_e_nome_do_fundo(monkeypatch, tmp_path):
    reports = {'P1': OK, 'P2': OK, 'L1': OK, 'V1': BAD}
    state = _fake(monkeypatch, tmp_path, reports)
    run.run_pavimento(tmp_path, '13_PAV')
    assert run.item_status(tmp_path, '13_PAV', 'pilares', 'P1_Para', state)['desatualizado'] is False
    assert run.item_status(tmp_path, '13_PAV', 'fundo', 'V1_S1', state, beam_name='V1')['status'] == 'diverge'
    assert run.item_status(tmp_path, '13_PAV', 'laterais_viga', 'V1', state) is None
    assert run.classe_status(tmp_path, '13_PAV', 'pilares') == {'P1': 'confere', 'P2': 'confere'}
    reports['v'] = 2
    assert run.item_status(tmp_path, '13_PAV', 'pilares', 'P1', state)['desatualizado'] is True
