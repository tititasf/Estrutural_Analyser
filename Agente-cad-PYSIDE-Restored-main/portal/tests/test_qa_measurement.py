import pytest
from portal.app.qa_measurement import geometry, polyline, decisions

SQUARE=[[0,0],[10,0],[10,10],[0,10]]

def test_missing_strip_and_repair_measured_against_reference():
    broken=[[0,0],[8,0],[8,10],[0,10]]
    m=geometry(broken,SQUARE,units_per_cm=2)
    assert m['iou']==pytest.approx(.8)
    assert m['missing_area_cm2']==pytest.approx(5)
    assert m['boundary_error_cm']==pytest.approx(1)
    assert not m['gate_pass']
    assert geometry(list(reversed(SQUARE)),SQUARE,units_per_cm=2)['gate_pass']


def test_small_hole_cannot_disappear_even_with_high_iou_and_loose_distance():
    reference={'type':'Polygon','coordinates':[SQUARE+[SQUARE[0]],
                 [[4.99,4.99],[5.01,4.99],[5.01,5.01],[4.99,5.01],[4.99,4.99]]]}
    missing=geometry(SQUARE,reference,units_per_cm=1,tolerance_cm=100)
    assert missing['iou'] > .99
    assert missing['reference_topology']=={'components':1,'holes':1}
    assert not missing['topology_pass'] and not missing['gate_pass']
    assert geometry(reference,reference,units_per_cm=1)['gate_pass']


def test_small_disconnected_component_cannot_disappear():
    second=[[11,0],[11.01,0],[11.01,.01],[11,.01],[11,0]]
    reference={'type':'MultiPolygon','coordinates':[[SQUARE+[SQUARE[0]]],[second]]}
    missing=geometry(SQUARE,reference,units_per_cm=1,tolerance_cm=100)
    assert missing['iou'] > .99
    assert missing['reference_topology']['components']==2
    assert not missing['gate_pass']
    assert geometry(reference,reference,units_per_cm=1)['gate_pass']


def test_invalid_hole_is_not_healed():
    outside={'type':'Polygon','coordinates':[SQUARE+[SQUARE[0]],
                [[20,20],[21,20],[21,21],[20,21],[20,20]]]}
    with pytest.raises(ValueError,match='reparar'):geometry(outside,SQUARE,units_per_cm=1)


@pytest.mark.parametrize('value',[[],[0,0],[[0,0],[1,1]],
                                 {'type':'Polygon','coordinates':[0,0]}])
def test_malformed_polygon_has_no_measurement(value):
    with pytest.raises(ValueError):geometry(value,SQUARE,units_per_cm=1)


def test_boolean_scale_cannot_be_a_cad_measurement():
    with pytest.raises(ValueError):geometry(SQUARE,SQUARE,units_per_cm=True)


def test_lv_boundary_detects_translation_shortening_and_bend():
    reference=[[0,0],[10,0]]
    assert polyline(list(reversed(reference)),reference,units_per_cm=1)['gate_pass']
    shifted=polyline([[0,2],[10,2]],reference,units_per_cm=2)
    assert shifted['boundary_error_cm']==pytest.approx(1)
    assert shifted['length_error_cm']==0 and not shifted['gate_pass']
    short=polyline([[0,0],[8,0]],reference,units_per_cm=1)
    assert short['endpoint_error_cm']==short['length_error_cm']==2
    assert not short['gate_pass']
    bend=polyline([[0,0],[5,1],[10,0]],reference,units_per_cm=1)
    assert bend['endpoint_error_cm']==0 and not bend['gate_pass']
    assert 'iou' not in bend


@pytest.mark.parametrize('points', [[[0,0]],[[0,0],[0,0]],[[0,0],[1,1],[0,1],[1,0]],
                                    [[0,0],[1,0],[1,1],[0,0]],[[0,0],[float('nan'),0]]])
def test_invalid_lv_boundaries_are_rejected(points):
    with pytest.raises(ValueError):polyline(points,[[0,0],[10,0]],units_per_cm=1)

def test_topology_and_unknown_scale_are_rejected():
    with pytest.raises(ValueError): geometry([[0,0],[10,10],[0,10],[10,0]],SQUARE,units_per_cm=1)
    with pytest.raises(ValueError): geometry(SQUARE,SQUARE,units_per_cm=0)

def test_abstentions_and_transport_do_not_inflate_accuracy():
    rows=[{'reference_correct':False,'assessment':'pass'},
          {'reference_correct':False,'assessment':'fail'},
          {'reference_correct':True,'assessment':'inconclusive'},
          {'reference_correct':True,'assessment':'technical_failure'}]
    m=decisions(rows)
    assert m['end_to_end_accuracy']==.25
    assert m['selective_accuracy']==.5
    assert m['decision_coverage']==.5
    assert m['false_approval_rate']==.5
    assert not m['certified']
    with pytest.raises(ValueError): decisions([{'assessment':'pass'}])

def test_empty_sample_never_reports_success():
    assert decisions([])['end_to_end_accuracy'] is None

def test_nonzero_area_self_intersection_cannot_generate_viewer():
    from portal.app.qa_versions import corrected_svg
    with pytest.raises(ValueError,match='topologicamente'):
        corrected_svg('<svg viewBox="0 0 100 100"/>',
                      [{'points':[[1,1],[80,70],[1,70],[50,1]]}])

def test_cli_receipts_require_completed_reads_and_unchanged_evidence(tmp_path):
    import json
    from scripts.arete.qa_cli_fallback import antigravity_stream_response, TechnicalFailure
    from portal.app.qa_review_contract import validate_read_receipts
    folder=tmp_path/'pack';folder.mkdir()
    for name in ('source.png','reference.png'):(folder/name).write_bytes(b'unit fixture')
    events=[{'event':'init','init':{'model':'test-model'}}]
    for index,name in enumerate(('source.png','reference.png')):
        events.append({'event':'step_update','step_update':{
            'state':'DONE','tool_name':'view_file','step_index':index,
            'tool_info':{'parameters':{'AbsolutePath':str(folder/name)}}}})
    events.append({'event':'result','result':{'status':'SUCCESS','response':'{}'}})
    raw,model=antigravity_stream_response('\n'.join(json.dumps(e) for e in events),tmp_path)
    audit=json.loads(raw)['qa_execution_audit']
    assert model=='test-model' and not audit['proves_comprehension']
    validate_read_receipts(audit,folder,tmp_path,'LAJ')
    (folder/'source.png').write_bytes(b'changed')
    with pytest.raises(ValueError,match='alterado'):validate_read_receipts(audit,folder,tmp_path,'LAJ')
    with pytest.raises(ValueError):validate_read_receipts({},folder,tmp_path,'LAJ')
    with pytest.raises(TechnicalFailure):antigravity_stream_response('{}',tmp_path)
