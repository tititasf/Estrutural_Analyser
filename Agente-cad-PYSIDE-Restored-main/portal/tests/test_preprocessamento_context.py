import copy
import importlib.util
import json
from pathlib import Path

import pytest

from portal.app.preprocessamento.context_resolver import pin_context, load_context, convention_input, level_reference_input
from portal.app.preprocessamento.service import run_floor
from portal.tests.test_preprocessamento_service import prepare


def prepared(tmp_path):
    import ezdxf
    declarations = prepare(tmp_path)
    legend = tmp_path / 'Fase-2_Triagem/recortes/A/convencao_pilares.dxf'
    doc = ezdxf.readfile(legend)
    model = doc.modelspace()
    for a, b in [((-20,-20),(20,-20)), ((20,-20),(20,20)),
                 ((20,20),(-20,20)), ((-20,20),(-20,-20))]:
        model.add_line(a, b)
    doc.saveas(legend)
    run_floor(obra_dir=tmp_path, obra_id='obra-1', pavimento='14_PAV', declarations=declarations)
    dxf = tmp_path / 'Fase-2_Triagem/recortes/A/torre_1.dxf'
    path, reason = pin_context(obra_dir=tmp_path, obra_id='obra-1', pavimento='14_PAV',
                               project_id='project-1', dxf_path=dxf)
    assert reason == 'accepted'
    payload = json.loads(path.read_text(encoding='utf-8'))
    kwargs = dict(expected_hash=payload['context_hash'], obra_dir=tmp_path,
                  pavimento='14_PAV', project_id='project-1', dxf_path=dxf)
    return path, kwargs, payload


def test_pinned_scope_hash_revision_and_actual_consumer(tmp_path):
    path, kwargs, payload = prepared(tmp_path)
    convention, receipt = load_context(path, **kwargs)
    assert receipt['status'] == 'accepted'
    assert receipt['context_run_id'] == payload['context_run_id']
    # Método real do desktop, sem construir janela nem alterar algoritmo.
    # Outras suítes carregam um ``main`` homônimo de _ROBOS_ABAS.
    spec = importlib.util.spec_from_file_location(
        'cad_desktop_main_for_preprocess_test', Path(__file__).parents[2] / 'main.py'
    )
    desktop = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(desktop)
    MainWindow = desktop.MainWindow
    from types import SimpleNamespace, MethodType
    runner = SimpleNamespace(dxf_data={'lines': []})
    runner._pillar_geom_sig = MethodType(MainWindow._pillar_geom_sig, runner)
    points = [(0, 0), (20, 0), (20, 40), (0, 40)]
    assert MainWindow._classify_pillar_hatch(runner, points, {}) == 'INDETERMINADO'
    assert MainWindow._classify_pillar_hatch(runner, points, convention) == 'MORRE'
    assert receipt['cache'] == 'disabled'


@pytest.mark.parametrize('field,value', [('pavimento','15_PAV'), ('project_id','other'),
                                        ('expected_hash', '0'*64)])
def test_contexto_errado_nao_consume(tmp_path, field, value):
    path, kwargs, _ = prepared(tmp_path)
    kwargs[field] = value
    convention, receipt = load_context(path, **kwargs)
    assert not convention
    assert receipt['status'] == 'not_consumed'


def test_mesmo_p1_ou_mesmos_bytes_na_outra_torre_nao_autoriza(tmp_path):
    path, kwargs, _ = prepared(tmp_path)
    kwargs['dxf_path'] = tmp_path / 'Fase-2_Triagem/recortes/A/torre_2.dxf'
    assert load_context(path, **kwargs)[0] == {}


def test_duas_torres_mesmo_p1_consumo_escopado_por_dxf(tmp_path):
    import ezdxf
    from portal.tests.test_preprocessamento_service import prepare
    prepare(tmp_path)
    recortes = tmp_path / 'Fase-2_Triagem/recortes'
    legend = recortes / 'A/convencao_pilares.dxf'
    doc = ezdxf.readfile(legend)
    model = doc.modelspace()
    for a, b in [((-20,-20),(20,-20)), ((20,-20),(20,20)),
                 ((20,20),(-20,20)), ((-20,20),(-20,-20))]:
        model.add_line(a, b)
    doc.saveas(legend)
    for bruto, filename in (('B', 'torre_2.dxf'), ('C', 'convencao_pilares.dxf')):
        folder = recortes / bruto
        folder.mkdir()
        (recortes / 'A' / filename).rename(folder / filename)
        (folder / 'validado.json').write_text(json.dumps({filename.removesuffix('.dxf'): True}))
    (recortes / 'A/validado.json').write_text('{"torre_1":true,"detalhes":true}')
    run_floor(obra_dir=tmp_path, obra_id='obra-1', pavimento='14_PAV', declarations=[
        {'bruto_id': 'A', 'item_id': 'torre_1'},
        {'bruto_id': 'B', 'item_id': 'torre_2'},
        {'bruto_id': 'C', 'item_id': 'convencao_pilares'},
    ])
    tower_a = recortes / 'A/torre_1.dxf'
    tower_b = recortes / 'B/torre_2.dxf'
    pinned_a, reason_a = pin_context(obra_dir=tmp_path, obra_id='obra-1', pavimento='14_PAV',
                                      project_id='sa-a', dxf_path=tower_a)
    pinned_b, reason_b = pin_context(obra_dir=tmp_path, obra_id='obra-1', pavimento='14_PAV',
                                      project_id='sa-b', dxf_path=tower_b)
    assert (reason_a, reason_b) == ('accepted', 'accepted')
    payload_a = json.loads(pinned_a.read_text())
    payload_b = json.loads(pinned_b.read_text())
    assert payload_a['scope']['recorte_id'] != payload_b['scope']['recorte_id']
    assert payload_a['context_hash'] != payload_b['context_hash']
    assert load_context(pinned_a, expected_hash=payload_a['context_hash'], obra_dir=tmp_path,
                        pavimento='14_PAV', project_id='sa-a', dxf_path=tower_b)[0] == {}
    assert load_context(pinned_b, expected_hash=payload_b['context_hash'], obra_dir=tmp_path,
                        pavimento='14_PAV', project_id='sa-b', dxf_path=tower_b)[1]['status'] == 'accepted'


def test_fonte_antiga_validacao_removida_e_tamper(tmp_path):
    path, kwargs, payload = prepared(tmp_path)
    validation = tmp_path / 'Fase-2_Triagem/recortes/A/validado.json'
    validation.write_text('{}')
    assert load_context(path, **kwargs)[1]['reason'] == 'stale_context'
    payload['convention']['MORRE']['label'] = 'NASCE'
    path.write_text(json.dumps(payload))
    assert load_context(path, **kwargs)[1]['reason'] == 'context_hash_mismatch'


def test_conflito_e_simbolo_ausente_nao_decidem(tmp_path):
    _, _, payload = prepared(tmp_path)
    package = copy.deepcopy(payload['package'])
    convention = next(iter(package['pillar_conventions'].values()))
    convention['conflicts'] = [{'signature':'EMPTY', 'labels':['MORRE', 'NASCE']}]
    assert convention_input(package)[0] == {}
    convention['conflicts'] = []
    convention['entries'][0]['line_handles'] = []
    assert convention_input(package)[0] == {}


def test_nasce_fica_como_evidencia_sem_mudar_topologia_automaticamente(tmp_path):
    _, _, payload = prepared(tmp_path)
    package = copy.deepcopy(payload['package'])
    convention = next(iter(package['pillar_conventions'].values()))
    convention['entries'][0]['label'] = 'NASCE'
    convention['entries'][0]['label_normalized'] = 'NASCE'
    assert convention_input(package)[0] == {}


def test_referencia_direta_fixada_pode_informar_altura_n3_sem_recorte(tmp_path):
    import ezdxf

    path, kwargs, payload = prepared(tmp_path)
    raw = tmp_path / 'entrada/A.dxf'
    raw.parent.mkdir(exist_ok=True)
    doc = ezdxf.new('R2010')
    for label, point in [('NIVEIS EM METROS', (0, 150)), ('13 PAV.', (0, 120)),
                         ('852.19', (100, 120)), ('14 PAV.', (0, 100)),
                         ('855.25', (100, 100))]:
        doc.modelspace().add_text(label, dxfattribs={'insert': point})
    doc.saveas(raw)
    declarations = [{'bruto_id': 'A', 'item_id': item}
                    for item in ('torre_1', 'torre_2', 'convencao_pilares', 'detalhes')]
    run_floor(obra_dir=tmp_path, obra_id='obra-1', pavimento='14_PAV', declarations=declarations)
    dxf = kwargs['dxf_path']
    path, reason = pin_context(obra_dir=tmp_path, obra_id='obra-1', pavimento='14_PAV',
                               project_id='project-1', dxf_path=dxf)
    assert reason == 'accepted'
    payload = json.loads(path.read_text())
    _, receipt = load_context(path, expected_hash=payload['context_hash'], obra_dir=tmp_path,
                              pavimento='14_PAV', project_id='project-1', dxf_path=dxf)
    assert receipt['level_reference']['height'] == 3.06
    package = copy.deepcopy(payload['package'])
    package['level_inventory']['reference']['status'] = 'partial'
    assert level_reference_input(package) is None
