from portal.app import lv_n3_cuts, ficha_reader, lv_ficha


def setup_inventory(monkeypatch):
    state = {'cuts': ['first']}
    calls = []
    monkeypatch.setattr(ficha_reader, 'ler_estado_pavimento', lambda *args: state)
    monkeypatch.setattr(ficha_reader, 'listar_itens_n1', lambda s, key:
                        [{'beam_name': 'V1'}, {'beam_name': 'V2'}] if key.endswith('passa') else [])
    monkeypatch.setattr(lv_ficha, 'montar_ficha_lv', lambda *args, **kwargs:
                        {'cut_views': [{'id': c} for c in state['cuts']]})
    def resolve(obra, floor, behavior, cut, mode, assembly):
        calls.append((floor, behavior, cut['id'], mode, assembly))
        return {'available': True, 'svg': '<svg/>', 'fingerprint': cut['id']}
    monkeypatch.setattr(lv_n3_cuts, 'resolve', resolve)
    return state, calls


def test_rebuilds_current_inventory_and_respects_item_floor_mode(monkeypatch, tmp_path):
    state, calls = setup_inventory(monkeypatch)
    first = lv_n3_cuts.materialize_pavimento(tmp_path, 'P1', 'MOLDE_2', ['V1'])
    assert (first['beams'], first['generated']) == (1, 2)
    state['cuts'] = ['new', 'additional']
    second = lv_n3_cuts.materialize_pavimento(tmp_path, 'P2', 'INI', ['V1'])
    assert [r['id'] for r in second['rows']] == ['new', 'new', 'additional', 'additional']
    assert calls == [(floor, 'passa', cut, mode, assembly)
                     for floor, mode, cuts in [('P1','MOLDE_2',['first']),('P2','INI',['new','additional'])]
                     for cut in cuts for assembly in ('gradeadas','sarrafeadas')]


def test_all_beams_and_failed_svg_are_reported(monkeypatch, tmp_path):
    setup_inventory(monkeypatch)
    monkeypatch.setattr(lv_n3_cuts, 'resolve', lambda *args: {'available': True, 'svg': ''})
    result = lv_n3_cuts.materialize_pavimento(tmp_path, 'P')
    assert result['beams'] == 2
    assert result['expected'] == len(result['errors']) == 4
    assert result['generated'] == 0


def test_missing_section_does_not_claim_success(monkeypatch, tmp_path):
    state, _ = setup_inventory(monkeypatch)
    state['cuts'] = []
    result = lv_n3_cuts.materialize_pavimento(tmp_path, 'P')
    assert len(result['errors']) == 2


def test_parallel_inventory_has_one_writer_and_reports_every_occurrence(monkeypatch, tmp_path):
    from src.core import n3_local_tasks
    state, _ = setup_inventory(monkeypatch)
    state['cuts'] = ['first', 'first']
    contexts = []
    def ficha(*args, **kwargs):
        contexts.append(kwargs['reference_context'])
        return {'cut_views': [{'id': 'first'}, {'id': 'first'}]}
    monkeypatch.setattr(lv_ficha, 'montar_ficha_lv', ficha)
    monkeypatch.setattr(lv_n3_cuts, 'artifact_identity', lambda obra, floor, behavior, cut, mode, assembly:
                        ({}, tmp_path/f'{assembly}.dxf', mode))
    batches = []
    def batch(tasks, workers):
        batches.append(tasks)
        assert workers == 3
        return [(True, 'grade', '', 1), (False, None, 'falha de desenho', 1)]
    monkeypatch.setattr(n3_local_tasks, 'run_cut_tasks', batch)
    result = lv_n3_cuts.materialize_pavimento(tmp_path, 'P', max_workers=3)
    assert len(batches[0]) == result['unique_artifacts'] == 2
    assert result['expected'] == 8 and result['generated'] == 4
    assert len(result['errors']) == 4
    assert all(r['status'] in ('generated', 'blocked') for r in result['rows'])
    assert contexts[0] is contexts[1]
    lv_n3_cuts.materialize_pavimento(tmp_path, 'P', max_workers=3)
    assert contexts[2] is not contexts[0]


def test_parallel_cut_tasks_publish_svg_and_preserve_dxf(tmp_path):
    import importlib.util
    from pathlib import Path
    from src.core.n3_local_tasks import run_cut_tasks
    spec = importlib.util.spec_from_file_location('cut_parity', Path(__file__).resolve().parents[1]/
        'scripts/arete/relatorios/20261008_n3_performance/compare_dxf.py')
    parity = importlib.util.module_from_spec(spec); spec.loader.exec_module(parity)
    cut = dict(kind='calculated', id='x', beam='V1', width_cm=19, beam_height_cm=55,
               profiles={s: dict(level=852.19, slabs=[]) for s in 'AB'}, pairs=[])
    tasks = [(str(tmp_path/'serial'), 'P', 'para', cut, 'INI', assembly)
             for assembly in ('gradeadas', 'sarrafeadas')]
    serial = run_cut_tasks(tasks, 1)
    parallel = run_cut_tasks([(str(tmp_path/'parallel'), *t[1:]) for t in tasks], 2)
    assert all(r[0] for r in serial + parallel)
    assert [r[1] for r in serial] == [r[1] for r in parallel]
    assert parity.compare(tmp_path/'serial', tmp_path/'parallel')['equal']
    assert len(list((tmp_path/'parallel').rglob('*.svg'))) == 2


def test_current_cut_identity_is_read_only_and_units_are_verified(tmp_path):
    from src.core.n5_lateral_frames import read_units
    import pytest
    cut=dict(kind='calculated',id='x',beam='V1',width_cm=19,beam_height_cm=55,
             profiles={s:dict(level=852.19,slabs=[]) for s in 'AB'},pairs=[])
    contract,path,_=lv_n3_cuts.artifact_identity(tmp_path,'P','para',cut,assembly='gradeadas')
    assert not path.parent.exists()
    result=lv_n3_cuts.resolve(tmp_path,'P','para',cut,assembly='gradeadas',render=False)
    assert result['path']==str(path) and result['svg'] is None
    manifest=path.with_suffix('.units')/'manifest.json'
    units=read_units([manifest],'gradeadas','PARA')
    assert len(units)==1 and units[0][1].read_bytes()==path.read_bytes()
    _,other,_=lv_n3_cuts.artifact_identity(tmp_path,'P','para',cut,assembly='sarrafeadas')
    assert other!=path and not other.parent.exists()
    cut['beam_height_cm']=65
    _,changed,_=lv_n3_cuts.artifact_identity(tmp_path,'P','para',cut,assembly='gradeadas')
    assert changed!=path and not changed.parent.exists()
    units[0][1].write_bytes(b'changed')
    with pytest.raises(ValueError,match='alterada'):
        read_units([manifest],'gradeadas','PARA')


def test_panels_materialize_both_assemblies_without_losing_failed_units(monkeypatch,tmp_path):
    from portal.app import lv_n3_panels
    monkeypatch.setattr(ficha_reader,'ler_estado_pavimento',lambda *args: {'current':True})
    monkeypatch.setattr(ficha_reader,'listar_itens_n1',lambda s,key:
                        [{'beam_name':'V1'},{'beam_name':'V2'}] if key=='lateral_a_para' else [])
    def resolve(obra,floor,behavior,beam,side,**kwargs):
        assert kwargs['render'] is False
        if kwargs['assembly']=='gradeadas':
            raise ValueError('perfil pendente')
        return dict(path='current.dxf',fingerprint='current')
    monkeypatch.setattr(lv_n3_panels,'resolve',resolve)
    result=lv_n3_panels.materialize_pavimento(tmp_path,'P',item_names=['V1'])
    assert result['expected']==2 and result['generated']==1
    assert [r['status'] for r in result['rows']]==['blocked','generated']
    assert len(result['errors'])==1
