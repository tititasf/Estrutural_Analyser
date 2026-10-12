"""Source isolation and actual exploded-dimension consumption across a crop."""
from copy import deepcopy
import hashlib
import ezdxf
import pytest
from portal.app.preprocessamento.adapters import local_pillar_details as adapter
from portal.tests.test_local_pillar_details import dimension_fixture


@pytest.fixture
def declared(tmp_path, monkeypatch):
    region,contours,texts,pillars,lines=dimension_fixture()
    tower=tmp_path/'tower.dxf';ezdxf.new().saveas(tower)
    raw=tmp_path/'raw.dxf';doc=ezdxf.new();ms=doc.modelspace()
    ms.add_lwpolyline(contours[0]['points'],close=True)
    for t in texts:
        ms.add_text(t['text'],dxfattribs={'insert':t['position'],'height':t.get('height',4),'rotation':t.get('rotation',0)})
    for line in lines:ms.add_line(line['start'],line['end'])
    doc.saveas(raw)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    scope={'obra_id':'work','pavimento_id':'floor','source_revision':digest(tower)}
    common={'obra_id':'work','pavimento_id':'floor','bruto_id':'sheet','validated':True}
    package={'scope':scope,'sources':[
        dict(common,kind='tower',relative_path='tower.dxf',revision=digest(tower),source_id='tower'),
        dict(common,kind='raw_level_reference',relative_path='raw.dxf',revision=digest(raw),source_id='raw')]}
    # Fix only the region detector's scope; all CAD chains and consumer
    # geometry/revision checks below execute their real implementation.
    original=adapter.inventory_local_details
    def inventory(path,owners):
        detection={'detalhes':[dict(region,idx=0)] if path==raw else []}
        return original(path,owners,detection=detection)
    monkeypatch.setattr(adapter,'inventory_local_details',inventory)
    return tmp_path,tower,raw,package,pillars


def test_declared_original_detail_is_consumed_without_mutating_sa(declared):
    root,tower,raw,package,pillars=declared
    before=deepcopy(pillars)
    result=adapter.inventory_declared_details(root,package,tower,pillars)
    assert result['status']=='proved_details'
    assert len(result['records'])==1
    record=result['records'][0]
    assert record['source_role']=='declared_raw_detail'
    assert record['source_revision']==package['sources'][1]['revision']
    assert record['plan_source_revision']==package['scope']['source_revision']
    report={p['name']:deepcopy(p) for p in pillars}
    receipt=adapter.crosscheck_sa_details(result,report,package['scope']['source_revision'])
    assert receipt['status']=='checked' and len(receipt['consumer_calls'])==2
    assert pillars==before and list(report.values())==before
    assert all(c['geometry_modified'] is False for c in receipt['consumer_calls'])


@pytest.mark.parametrize('field,value',[('bruto_id','other-sheet'),('pavimento_id','other-floor'),('obra_id','other-work')])
def test_another_scope_cannot_supply_details(declared,field,value):
    root,tower,raw,package,pillars=declared
    package['sources'][1][field]=value
    result=adapter.inventory_declared_details(root,package,tower,pillars)
    assert result['records']==[] and result['status']!='proved_details'


@pytest.mark.parametrize('blocker',['duplicate','hash','validated','escape'])
def test_ambiguous_or_untrusted_declared_original_blocks(declared,blocker):
    root,tower,raw,package,pillars=declared
    if blocker=='duplicate':package['sources'].append(deepcopy(package['sources'][1]))
    if blocker=='hash':package['sources'][1]['revision']='wrong'
    if blocker=='validated':package['sources'][1]['validated']=False
    if blocker=='escape':package['sources'][1]['relative_path']='../raw.dxf'
    result=adapter.inventory_declared_details(root,package,tower,pillars)
    assert result['status']=='unavailable' and result['records']==[]


def test_consumer_rechecks_external_revision_and_plan_scope(declared):
    root,tower,raw,package,pillars=declared
    result=adapter.inventory_declared_details(root,package,tower,pillars)
    report={p['name']:p for p in pillars}
    receipt=adapter.crosscheck_sa_details(result,report,'other-plan-revision')
    assert receipt['status']=='blocked'
    assert {r['reason'] for r in receipt['blocked']}=={'detail_plan_source_revision_mismatch'}
    raw.write_bytes(raw.read_bytes()+b'\n')
    receipt=adapter.crosscheck_sa_details(result,report,package['scope']['source_revision'])
    assert receipt['status']=='blocked'
    assert {r['reason'] for r in receipt['blocked']}=={'detail_external_source_revision_mismatch'}
