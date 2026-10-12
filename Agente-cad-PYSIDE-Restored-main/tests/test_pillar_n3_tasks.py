from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import pytest
from src.core.pillar_n3_tasks import run_pillar_tasks


@pytest.mark.parametrize('mode', ['INI', 'NOVA', 'MOLDE_1', 'MOLDE_2', 'MOLDE_3'])
def test_all_zones_preserve_drawings_and_input_in_processes(tmp_path, mode):
    spec = importlib.util.spec_from_file_location('pillar_parity', Path(__file__).resolve().parents[1] /
        'scripts/arete/relatorios/20261008_n3_performance/compare_dxf.py')
    parity = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parity)
    payload = dict(nome='PX', comprimento=66, largura=19, altura=280,
                   modo='para', modo_distribuicao='NOVA')
    for key in 'ABCD':
        payload.update({f'larg1_{key}': 66 if key in 'AB' else 19,
                        f'h1_{key}': 2, f'h2_{key}': 244, f'h3_{key}': 34})
    tasks = []
    for root in ('serial', 'parallel'):
        folder = tmp_path / root / 'draw'
        folder.mkdir(parents=True)
        (folder/'PX.json').write_text(json.dumps(payload))
        tasks.append([('PX_para', payload, str(folder), mode, [str(tmp_path/root/'published')]),
                      ('bad_para', {}, str(folder), 'INVALID', [])])
    original = deepcopy(payload)
    serial = run_pillar_tasks(tasks[0], 1)
    parallel = run_pillar_tasks(tasks[1], 2)
    assert payload == original
    assert [bool(row[2]) for row in serial] == [bool(row[2]) for row in parallel] == [False, True]
    assert set(serial[0][1]) == set(parallel[0][1]) == {'cima', 'abcd', 'grades'}
    assert parity.compare(tmp_path/'serial', tmp_path/'parallel')['equal']
    assert len(list((tmp_path/'parallel'/'published').glob('*.dxf'))) == 3
