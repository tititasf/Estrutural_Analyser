import json
from portal.app import item_geometry, pipeline_runner


def test_fresh_class_publication_restores_generated_beams_only(tmp_path):
    sidecar = item_geometry.sidecar_path(tmp_path, '13_PAV')
    sidecar.parent.mkdir(parents=True)
    custom = dict(deleted=dict(lateral_a_para=['old', 'beam:VF301', 'manual', 'beam:V2'],
                              fundo=['f1']), edits=dict(lateral_a_para={'old': {'length': 20}}))
    sidecar.write_text(json.dumps(custom))
    fresh = dict(pilares=[], segmentos=dict(lateral_a_para=[
        dict(uid='old', beam_name='VF301'), dict(uid='new', beam_name='V2')],
        fundo=[dict(uid='f1', beam_name='VF301')]))
    candidate = tmp_path / 'estado_13_PAV_laterais_123.json'
    candidate.write_text(json.dumps(fresh))
    pipeline_runner.promover_snapshot_sa(tmp_path, '13_PAV', secao='laterais_viga', item_names={'VF301'})
    after = item_geometry.load(tmp_path, '13_PAV')
    assert after['deleted'] == dict(lateral_a_para=['manual', 'beam:V2'], fundo=['f1'])
    assert after['edits'] == custom['edits']
    assert list(sidecar.parent.glob('*.bak'))


def test_invalid_snapshot_never_restores_removals(tmp_path):
    sidecar = item_geometry.sidecar_path(tmp_path, '13_PAV')
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text(json.dumps(dict(deleted=dict(lateral_a_para=['beam:VF301']))))
    before = sidecar.read_bytes()
    (tmp_path / 'estado_13_PAV_laterais_123.json').write_text('{"segmentos": {}}')
    assert pipeline_runner.promover_snapshot_sa(tmp_path, '13_PAV', secao='laterais_viga') is None
    assert sidecar.read_bytes() == before
