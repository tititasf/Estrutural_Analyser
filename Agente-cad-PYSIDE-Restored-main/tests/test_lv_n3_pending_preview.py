import os


# Importing the CLI configures its process for unattended execution. Keep that
# configuration out of unrelated generator subprocess tests in this process.
_cli_env_keys = ('QT_QPA_PLATFORM', 'QT_QUICK_BACKEND', 'MPLBACKEND', 'CAD_MOTOR_HEADLESS')
_previous_cli_env = {key: os.environ.get(key) for key in _cli_env_keys}
try:
    from scripts.arete import headless_sa_analise as runner
finally:
    for _key, _value in _previous_cli_env.items():
        if _value is None:
            os.environ.pop(_key, None)
        else:
            os.environ[_key] = _value


def test_pending_lateral_profiles_are_reported_as_failed_not_zero_missing(tmp_path, monkeypatch):
    pending = {'vertical_pending': 'cruzamento sem nível confirmado', 'panels': [],
               'generation_ready': False}
    beam = {'name': 'V330', 'lv_generation_contracts': {
        behavior: {'A': pending, 'B': pending} for behavior in ('Para', 'Passa')
    }}
    monkeypatch.setattr(runner, '_run_n3_subprocess_tasks', lambda tasks, **kwargs: ([], []))
    generated, failed = runner._generate_lv_n3_nova_previews(tmp_path, [beam], tmp_path / 'dxf')
    assert generated == []
    assert failed == ['V330_Para', 'V330_Passa']
    for behavior in ('PARA', 'PASSA'):
        assert (tmp_path / 'contracts_lv' / f'LV-{behavior}' / 'V330_A.json').exists()


def test_missing_measure_in_one_beam_does_not_abort_other_beams(tmp_path, monkeypatch):
    import json
    from copy import deepcopy
    import src.core.vigas_drawing_config as config
    def beam(name):
        sides={side:{'beam_name':name,'side':side,'panels':[{'width':100}],
                      'structural_segments':[]} for side in ('A','B')}
        return {'name':name,'lv_generation_contracts':{'Para':sides}}
    def prepare(sides, **kwargs):
        if sides['A']['beam_name']=='V301':
            raise ValueError('A.L320.level: nível ausente')
        return deepcopy(sides)
    monkeypatch.setattr(config,'prepare_lv_sources',prepare)
    monkeypatch.setattr(runner,'_run_n3_subprocess_tasks',lambda *a,**k:([],[]))
    def draw(*args):
        args[1].write_text('generated')
    monkeypatch.setattr('scripts.arete.lv_n3_cut_draw.generate_local_sections',draw)
    monkeypatch.setattr('scripts.arete.lv_n3_cut_draw.generate_local_panels',draw)
    generated,failed=runner._generate_lv_n3_nova_previews(tmp_path,[beam('V301'),beam('V302')],tmp_path/'dxf')
    assert failed==['V301_Para']
    assert len(generated)==6 and all(label.startswith('V302_Para_') for label in generated)
    pending=json.loads((tmp_path/'contracts_lv/LV-PARA/V301_A.json').read_text(encoding='utf8'))
    assert pending['vertical_pending']=='A.L320.level: nível ausente'


def test_granular_context_keeps_selected_geometry_and_adds_only_incident_spans():
    from copy import deepcopy
    selected = {'beam_name': 'V330', 'points': [[10, 0], [10, 100]],
                'lv_cell': {'beam_openings': [{'name': 'V301'}]}}
    def record(name):
        return {'id': name, 'name': name, 'links': {
            'viga_a_seg_1_comprimento_total': {'seg_side_a': [
                {'points': [[0, 0], [100, 0]], 'len': 100, 'lv_dimensao': '19/55'}]}}}
    records = {name: record(name) for name in ('V330', 'V301', 'V302')}
    before = deepcopy(records)
    state = {'segmentos': {'lateral_a_para': [deepcopy(selected)]}, 'slabs': []}
    names = runner._complete_lv_section_context(state, records)
    assert names == ['V301', 'V330']
    assert state['segmentos']['lateral_a_para'][0] == selected
    assert {s['beam_name'] for rows in state['segmentos'].values() for s in rows} == {'V301', 'V330'}
    assert records == before


def test_inverted_preview_routes_all_views_to_local_adapters(tmp_path, monkeypatch):
    section = {'beam_type': 'inverted'}
    sides = {side: {'panels': [{'width': 100}], 'structural_segments': [
        {'section_contract': section}]} for side in ('A', 'B')}
    beam = {'name': 'V330', 'lv_generation_contracts': {'Para': sides}}
    calls = []

    def local(contracts, target, mode, behavior):
        assert contracts['A']['structural_segments'] == sides['A']['structural_segments']
        assert contracts['A']['assembly_variant'] in ('gradeadas','sarrafeadas')
        target.write_text('adapter called')
        calls.append((mode, behavior))

    def subprocesses(tasks, **kwargs):
        assert tasks == []
        return [task[0] for task in tasks], []

    def panels(contracts, target, side, mode, behavior):
        assert contracts[side]['structural_segments'] == sides[side]['structural_segments']
        assert contracts[side]['assembly_variant'] in ('gradeadas','sarrafeadas')
        target.write_text('local panels called')
        calls.append((mode, behavior, side))

    monkeypatch.setattr('scripts.arete.lv_n3_cut_draw.generate_local_sections', local)
    monkeypatch.setattr('scripts.arete.lv_n3_cut_draw.generate_local_panels', panels)
    monkeypatch.setattr(runner, '_run_n3_subprocess_tasks', subprocesses)
    generated, failed = runner._generate_lv_n3_nova_previews(tmp_path, [beam], tmp_path/'dxf')
    assert generated == [f'V330_Para_{view}_{kind}' for kind in ('gradeadas','sarrafeadas')
                         for view in ('CORTE','VIEW_A','VIEW_B')]
    assert failed == [] and calls == [('NOVA', 'Para'), ('NOVA', 'Para', 'A'), ('NOVA', 'Para', 'B')]*2
