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


def test_inverted_preview_routes_corte_to_local_adapter_and_keeps_side_generator(tmp_path, monkeypatch):
    section = {'beam_type': 'inverted'}
    sides = {side: {'panels': [{'width': 100}], 'structural_segments': [
        {'section_contract': section}]} for side in ('A', 'B')}
    beam = {'name': 'V330', 'lv_generation_contracts': {'Para': sides}}
    calls = []

    def local(contracts, target, mode, behavior):
        assert contracts == sides
        target.write_text('adapter called')
        calls.append((mode, behavior))

    def subprocesses(tasks, **kwargs):
        assert [task[1][task[1].index('--view')+1] for task in tasks] == ['A', 'B']
        return [task[0] for task in tasks], []

    monkeypatch.setattr('scripts.arete.lv_n3_cut_draw.generate_local_sections', local)
    monkeypatch.setattr(runner, '_run_n3_subprocess_tasks', subprocesses)
    generated, failed = runner._generate_lv_n3_nova_previews(tmp_path, [beam], tmp_path/'dxf')
    assert generated == ['V330_Para_CORTE', 'V330_Para_VIEW_A', 'V330_Para_VIEW_B']
    assert failed == [] and calls == [('NOVA', 'Para')]
