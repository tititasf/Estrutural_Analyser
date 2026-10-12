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
    from portal.app import qa_cad_gate_cortes as cortes
    monkeypatch.setattr(cortes, 'measure_obra', lambda o, p, src, st, slabs, item_names=None: {
        n: dict(reports.get(f'VC:{n}', OK), inputs=[n]) for n in ('V1', 'L1') if not item_names or n in item_names})
    return state


OK = {'contacts': [{'face': 'A', 'beam': 'V1', 'status': 'measured', 'errors': {}}]}
BAD = {'contacts': [{'face': 'B', 'beam': 'V2', 'status': 'measured', 'errors': {'b': 'largura 14 ≠ 19'}}]}
UNC = {'contacts': [{'face': 'C', 'beam': 'V3', 'status': 'uncertain', 'reason': 'sem parede'}]}


def test_resumo_classifica_status():
    assert run.resumo(OK)['status'] == 'confere'
    assert run.resumo(BAD) == dict(status='diverge', divergencias=['face B V2: largura 14 ≠ 19'], incertos=[], medidos=1)
    assert run.resumo(UNC)['incertos'] == ['face C V3: sem parede']
    assert run.resumo({'error': 'sem DXF', 'contacts': []})['status'] == 'indisponivel'
    # Um aviso opcional não substitui uma medição real.
    optional = dict(UNC['contacts'][0], blocks_promotion=False)
    assert run.resumo({'contacts': [optional]}) == dict(
        status='incerto', divergencias=[], incertos=['face C V3: sem parede'], medidos=0)
    assert run.resumo({'contacts': OK['contacts'] + [optional]}) == dict(
        status='confere', divergencias=[], incertos=[], medidos=1)


def test_resumo_empty_measurements_do_not_approve():
    assert run.resumo({'contacts': []}) == dict(
        status='incerto', divergencias=[],
        incertos=['nenhum aspecto medido no CAD original'], medidos=0)
    assert run.resumo({'schema': 'cad.qa_original_contacts/v1'})['status'] == 'incerto'
    assert run.resumo(None) is None


def test_resumo_retains_unmeasured_contour_reason():
    report = {'contacts': [{'item': 'V1', 'aspect': 'contorno',
                           'status': 'uncertain', 'blocks_promotion': False,
                           'reason': 'contorno não retangular; medidor indisponível'}]}
    summary = run.resumo(report)
    assert summary['status'] == 'incerto' and summary['medidos'] == 0
    assert summary['incertos'] == ['V1 contorno: contorno não retangular; medidor indisponível']


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
    assert set(data['tempos_s']) == {'PIL', 'LAJ', 'FV', 'LV', 'VC'}
    assert data['classes']['VC']['V1']['status'] == 'confere'


def test_microciclo_mescla_sem_apagar_outros_itens(monkeypatch, tmp_path):
    reports = {'P1': OK, 'P2': OK, 'L1': OK, 'V1': OK}
    _fake(monkeypatch, tmp_path, reports)
    run.run_pavimento(tmp_path, '13_PAV')
    reports['P2'] = BAD
    reports['VC:V1'] = BAD
    run.run_pavimento(tmp_path, '13_PAV', secao='pilares', item_names={'P2'})
    data = json.loads(run.sidecar_path(tmp_path, '13_PAV').read_text(encoding='utf-8'))
    assert data['classes']['PIL']['P1']['status'] == 'confere'
    assert data['classes']['PIL']['P2']['status'] == 'diverge'
    assert data['classes']['FV']['V1']['status'] == 'confere'
    assert data['classes']['VC']['V1']['status'] == 'confere'  # seção pilares não refaz cortes
    run.run_pavimento(tmp_path, '13_PAV', secao='fundos_viga', item_names={'V1'})
    data = json.loads(run.sidecar_path(tmp_path, '13_PAV').read_text(encoding='utf-8'))
    assert data['classes']['VC']['V1']['status'] == 'diverge'
    assert data['classes']['VC']['L1']['status'] == 'confere'


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



def test_measure_state_matches_saved_report_with_all_classes_and_failures(monkeypatch, tmp_path):
    from copy import deepcopy
    state = _fake(monkeypatch, tmp_path, {'P1': OK, 'P2': BAD, 'L1': UNC, 'V1': OK}, fail={'P2'})
    original = deepcopy(state)
    monkeypatch.setattr(run.time, 'perf_counter', lambda: 10.0)
    monkeypatch.setattr(run.time, 'strftime', lambda fmt: '2026-10-10T12:00:00')
    measured = run.measure_state(tmp_path / 'torre.dxf', state, '13_PAV', obra_dir=tmp_path)
    assert state == original
    assert not run.sidecar_path(tmp_path, '13_PAV').exists()
    path = run.run_pavimento(tmp_path, '13_PAV')
    assert json.loads(path.read_text(encoding='utf-8')) == measured
    assert measured['classes']['PIL']['P2']['status'] == 'indisponivel'
    assert measured['classes']['LAJ']['L1']['status'] == 'incerto'
    assert measured['classes']['LV']['V1|passa']['status'] == 'confere'


def test_measure_state_filtered_report_does_not_load_existing_sidecar(monkeypatch, tmp_path):
    state = _fake(monkeypatch, tmp_path, {'P1': OK, 'P2': BAD, 'L1': OK, 'V1': OK})
    def forbidden(*args, **kwargs):
        raise AssertionError('pure measurement accessed published files')
    monkeypatch.setattr(run, '_read', forbidden)
    monkeypatch.setattr(run, '_write', forbidden)
    monkeypatch.setattr(run.ficha_reader, 'ler_estado_pavimento', forbidden)
    monkeypatch.setattr(run.ficha_reader, '_fonte_estrutural_producao', forbidden)
    data = run.measure_state(tmp_path / 'torre.dxf', state, '13_PAV', secao='pilares', item_names={'P2'})
    assert set(data['classes']) == {'PIL'}
    assert set(data['classes']['PIL']) == {'P2'}
    assert data['classes']['PIL']['P2']['status'] == 'diverge'
    assert set(data['tempos_s']) == {'PIL'}


def test_measure_state_missing_source_and_empty_state(monkeypatch):
    from copy import deepcopy
    state = {'pilares': [{'name': 'P1'}]}
    original = deepcopy(state)
    data = run.measure_state(None, state, 'PAV')
    assert data['source'] is None and data['source_sha256'] is None
    assert data['classes']['PIL']['P1']['status'] == 'indisponivel'
    assert state == original  # missing collection keys stay missing
    assert run.measure_state(None, {}, 'PAV') is None


def test_measure_state_real_dxf_no_filesystem_writes_and_report_parity(monkeypatch, tmp_path):
    import builtins
    import io
    from copy import deepcopy
    from pathlib import Path
    import ezdxf
    doc = ezdxf.new()
    ms = doc.modelspace()
    ms.add_lwpolyline([(0,0), (20,0), (20,66), (0,66)], close=True)
    ms.add_line((20,52), (100,52))
    ms.add_line((20,66), (100,66))
    ms.add_text('V1', dxfattribs={'insert': (30,70), 'height': 3})
    ms.add_text('14/55', dxfattribs={'insert': (80,70), 'height': 3})
    source = tmp_path / 'source.dxf'
    doc.saveas(source)
    state = {'pilares': [{'name': 'P1', 'points': [[0,0],[20,0],[20,66],[0,66]],
                         'interpretacao_abcd': {'faces': {'B': {'chega': [
                             {'nome': 'V1', 'dim': '14/55', 'dist_esq': '52cm', 'dist_dir': '0cm'}]}}}}]}
    original = deepcopy(state)
    before = source.read_bytes()
    writes = []
    def readonly_open(open_func):
        def checked(file, mode='r', *args, **kwargs):
            if any(c in mode for c in 'wax+'):
                writes.append((str(file), mode))
                raise AssertionError('filesystem write forbidden during measure_state')
            return open_func(file, mode, *args, **kwargs)
        return checked
    with monkeypatch.context() as guard:
        guard.setattr(builtins, 'open', readonly_open(builtins.open))
        guard.setattr(io, 'open', readonly_open(io.open))
        guard.setattr(Path, 'mkdir', lambda *a, **k: writes.append('mkdir'))
        measured = run.measure_state(source, state, 'PAV', secao='pilares')
    assert writes == []
    assert state == original and source.read_bytes() == before
    assert measured['classes']['PIL']['P1']['status'] == 'confere'
    assert measured['classes']['PIL']['P1']['medidos'] > 0
    monkeypatch.setattr(run.ficha_reader, 'ler_estado_pavimento', lambda *a: state)
    monkeypatch.setattr(run.ficha_reader, '_fonte_estrutural_producao', lambda *a: source)
    saved = json.loads(run.run_pavimento(tmp_path, 'PAV', secao='pilares').read_text(encoding='utf-8'))
    def stable(data):
        result = deepcopy(data)
        for key in ('duracao_s', 'gerado_em', 'tempos_s'):
            result.pop(key, None)
        for bucket in result['classes'].values():
            for entry in bucket.values():
                entry.pop('medido_em', None)
        return result
    assert stable(saved) == stable(measured)
