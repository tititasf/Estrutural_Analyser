import copy
import json
from types import SimpleNamespace

import pytest

from portal.app import qa_interpretation as q, qa_versions as versions, ficha_reader

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M0 0H20V20Z"/></svg>'


def test_pil_render_preserves_explicit_candidate_abcd_edits(tmp_path,monkeypatch):
    from scripts.arete import pil_agentic_highlight_draw as renderer
    from portal.app import dxf_preview
    from src.core import pillar_abcd_tables
    state,item=state_for('PIL')
    row=state['pilares'][0]
    row['interpretacao_abcd']={'faces':{'B':{'lajes':[{'nome':'L1','canto':'BD','nivel':'800.00'}],
        'chega':[{'nome':'V1','canto':'BC'}]}}}
    candidate=q.snapshot(state,'PIL',item)
    captured=[]
    monkeypatch.setattr(ficha_reader,'_fonte_estrutural_producao',lambda *a:tmp_path/'original.dxf')
    monkeypatch.setattr(dxf_preview,'obter_bbox_dxf',lambda *a:(0,0,100,100))
    monkeypatch.setattr(pillar_abcd_tables,'build_abcd_tables_from_pillar',lambda *a,**k:pytest.fail('edição ABCD foi descartada'))
    def draw(path,points,tables,**kw):
        captured.append(copy.deepcopy(tables))
        tables['faces']['B']['lajes'][0]['nome']='renderer mutation'
        return SVG
    monkeypatch.setattr(renderer,'render_agentic_svg',draw)
    output=q.render(tmp_path,'13_PAV',candidate,state,'L1')
    assert captured[0] == row['interpretacao_abcd']
    assert candidate['collections']['pilares'][0]['interpretacao_abcd'] == row['interpretacao_abcd']
    assert q.fingerprint(candidate) in output
    assert not versions.candidate_integrity_errors(candidate,output)
    assert versions.candidate_integrity_errors(candidate,SVG)


def test_pil_inconsistent_slab_corner_blocks_adoption():
    import xml.etree.ElementTree as ET
    state,item=state_for('PIL')
    state['pilares'][0]['interpretacao_abcd']={'faces':{'B':{
        'lajes':[{'nome':'L1','canto':'BB'}], 'chega':[{'nome':'V1','canto':'BC'}]}}}
    candidate=q.snapshot(state,'PIL',item)
    root=ET.fromstring(SVG)
    root.set('data-qa-pil-render','snapshot-abcd-v1')
    root.set('data-qa-interpretation-sha256',q.fingerprint(candidate))
    assert any('laje esperada' in e for e in versions.candidate_integrity_errors(candidate,ET.tostring(root,encoding='unicode')))


def state_for(classe, behavior='para'):
    row = {'points': [[0,0],[20,0],[20,20],[0,20]], 'height':12}
    if classe in {'PIL','LAJ'}:
        item = 'P1' if classe == 'PIL' else 'L301'
        row['name'] = item
        return {('pilares' if classe == 'PIL' else 'slabs'):[row]}, item
    row.update(uid='segment-1',beam_name='V301',segment_label='1',side='Fundo',behavior='Fundo')
    if classe == 'FV':
        return {'segmentos':{'fundo':[row]}}, 'V301'
    return {'segmentos':{f'lateral_{side.lower()}_{behavior}':[dict(row,uid=side+'-1',side=side,behavior=behavior.title(),points=[[0,0],[20,0]])]
                         for side in ['A','B']}}, 'V301'


@pytest.mark.parametrize('classe,behavior',[('PIL','para'),('LAJ','para'),('FV','para'),('LV','para'),('LV','passa')])
def test_complete_candidate_scoped_and_independent(classe,behavior):
    state,item = state_for(classe,behavior)
    original=q.snapshot(state,classe,item,behavior)
    key=next(iter(original['collections']))
    candidate=q.compile_candidate(original,{'field_corrections':[{'field_path':f'/collections/{key}/0/height',
        'before':12,'after':13,'evidence':[{'source':'reference.png','finding':'h=13'}],'rule_refs':['manual#altura']}]})
    assert original['collections'][key][0]['height']==12
    assert candidate['collections'][key][0]['height']==13
    changed=q.replace_item(state,candidate)
    assert q.snapshot(changed,classe,item,behavior)==candidate
    assert q.snapshot(state,classe,item,behavior)==original


@pytest.mark.parametrize('path',['/collections/lajes/-1/height','/collections/lajes/00/height','/collections/lajes/9/height'])
def test_bad_pointer_rejected(path):
    state,item=state_for('LAJ');original=q.snapshot(state,'LAJ',item)
    with pytest.raises(ValueError):
        q.compile_candidate(original,{'field_corrections':[dict(field_path=path,before=12,after=13,evidence=['proof'],rule_refs=['rule'])]})


def test_complete_candidate_requires_own_proof_and_single_representation():
    state,item=state_for('LAJ');original=q.snapshot(state,'LAJ',item)
    candidate=copy.deepcopy(original);candidate['collections']['lajes'][0]['height']=13
    suggestion={'candidate_interpretation':candidate}
    with pytest.raises(ValueError,match='candidate_evidence'):
        q.compile_candidate(original,suggestion)
    suggestion.update(candidate_evidence=[{'source':'reference.png','finding':'h=13'}],
                      candidate_rule_refs=['manual#altura'])
    assert q.compile_candidate(original,suggestion)==candidate
    suggestion['field_corrections']=[{'field_path':'/collections/lajes/0/height'}]
    with pytest.raises(ValueError,match='não envie ambos'):
        q.compile_candidate(original,suggestion)


def test_foreign_identity_crossed_geometry_and_side_rejected():
    state,item=state_for('LV');original=q.snapshot(state,'LV',item)
    for change in [dict(side='B'),dict(beam_name='V302'),dict(points=[[0,0],[20,20],[0,20],[20,0]])]:
        candidate=copy.deepcopy(original);candidate['collections']['lateral_a_para'][0].update(change)
        with pytest.raises(ValueError):q.validate(candidate,original)


def test_lateral_level_correction_cannot_leave_stale_internal_level():
    state,item=state_for('LV');original=q.snapshot(state,'LV',item)
    row=original['collections']['lateral_a_para'][0]
    row.update(level='852.19',lv_cell={'level':'852.19'})
    candidate=copy.deepcopy(original)
    candidate['collections']['lateral_a_para'][0]['level']='852.12'
    with pytest.raises(ValueError,match='contraditórios'):q.validate(candidate,original)
    candidate['collections']['lateral_a_para'][0]['lv_cell']['level']='852,12'
    assert q.validate(candidate,original)==candidate


@pytest.mark.parametrize('classe',['PIL','LAJ','FV','LV'])
def test_human_adoption_hash_gate_and_rollback(tmp_path,monkeypatch,classe):
    state,item=state_for(classe);original=q.snapshot(state,classe,item)
    candidate=copy.deepcopy(original);next(iter(candidate['collections'].values()))[0]['height']=13
    token=q.fingerprint({'interpretation':candidate,'svg':versions.digest(SVG)})
    record=dict(round_id='r1',svg=SVG,promotion_ready=True,candidate_sha256=token,
        candidate_interpretation=candidate,base_snapshot_sha256=q.fingerprint(original),post_review={'assessment':'pass'})
    monkeypatch.setattr(versions,'read',lambda *a:{'L1':record})
    monkeypatch.setattr(ficha_reader,'ler_estado_pavimento',lambda *a,**kw:copy.deepcopy(state))
    with pytest.raises(ValueError):q.promote(tmp_path,'13_PAV',classe,item,'para','L1','r1','wrong',7)
    assert not q.manifest_path(tmp_path,'13_PAV').exists()
    q.promote(tmp_path,'13_PAV',classe,item,'para','L1','r1',token,7)
    applied=q.apply_effective(copy.deepcopy(state),tmp_path,'13_PAV')
    assert q.snapshot(applied,classe,item)==candidate
    assert q.effective_entry(tmp_path,'13_PAV',classe,item,'para',applied)['member_id']==7
    updated=copy.deepcopy(state)
    from portal.app.item_geometry import collection
    collection(updated,q.classes(classe)[0])[0]['height']=15
    assert not q.apply_effective(updated,tmp_path,'13_PAV')['_qa_effective']
    with pytest.raises(ValueError):q.rollback(tmp_path,'13_PAV',classe,item,'para','wrong',7)
    q.rollback(tmp_path,'13_PAV',classe,item,'para','r1',7)
    assert q.load_manifest(tmp_path,'13_PAV')['items']=={}
    assert len(q.load_manifest(tmp_path,'13_PAV')['history'])==2


def test_candidate_requires_post_audit_real_receipts(tmp_path):
    state,item=state_for('LAJ');original=q.snapshot(state,'LAJ',item)
    candidate=copy.deepcopy(original);candidate['collections']['lajes'][0]['height']=13
    for receipts,round_id in [(False,'r1'),(True,'r2')]:
        result=SimpleNamespace(status='completed',item=item,verdict='invalidou',note='altura corrigida',provider='test',model='unit',
            suggestion={'action':'corrigir','checks':[dict(criterion='altura',observation='h13',status='fail')],
                '_candidate_package':dict(svg=SVG,interpretation=candidate),
                'post_review':dict(status='completed',assessment='pass',execution_audit={'origin':'cli'} if receipts else None),
                'execution_audit':{'origin':'cli'} if receipts else None})
        versions.persist(tmp_path,dict(id=round_id,pavimento='13_PAV',classe='LAJ',layer='L1'),result,SVG,
                         dict(sa_snapshot=original,base_sa_snapshot=original))
        assert versions.read(tmp_path,'13_PAV','LAJ',item)['L1']['promotion_ready'] is receipts


@pytest.mark.parametrize('assessment',['fail','inconclusive'])
def test_pending_candidate_requires_explicit_human_ack(tmp_path,monkeypatch,assessment):
    state,item=state_for('LAJ');original=q.snapshot(state,'LAJ',item)
    candidate=copy.deepcopy(original);candidate['collections']['lajes'][0]['height']=13
    token=q.fingerprint({'interpretation':candidate,'svg':versions.digest(SVG)})
    record=dict(round_id='r1',svg=SVG,promotion_ready=True,candidate_sha256=token,
        candidate_interpretation=candidate,base_snapshot_sha256=q.fingerprint(original),
        post_review={'assessment':assessment})
    monkeypatch.setattr(versions,'read',lambda *a:{'L1':record})
    monkeypatch.setattr(ficha_reader,'ler_estado_pavimento',lambda *a,**kw:copy.deepcopy(state))
    with pytest.raises(ValueError):q.promote(tmp_path,'13_PAV','LAJ',item,'para','L1','r1',token,7)
    assert not q.manifest_path(tmp_path,'13_PAV').exists()
    q.promote(tmp_path,'13_PAV','LAJ',item,'para','L1','r1',token,7,acknowledge_pending=True)
    assert q.load_manifest(tmp_path,'13_PAV')['history'][-1]['acknowledge_pending'] is True


@pytest.mark.parametrize('classe,behavior',[('PIL','para'),('LAJ','para'),('FV','para'),('LV','para'),('LV','passa')])
def test_geometry_adoption_preserves_base_and_requires_current_round(tmp_path,monkeypatch,classe,behavior):
    state,item=state_for(classe,behavior);original=q.snapshot(state,classe,item,behavior)
    candidate=copy.deepcopy(original)
    for rows in candidate['collections'].values():
        for row in rows:row['points']=[[x+2,y+3] for x,y in row['points']]
    q.validate(candidate,original)
    token=q.fingerprint({'interpretation':candidate,'svg':versions.digest(SVG)})
    record=dict(round_id='r2',svg=SVG,promotion_ready=True,candidate_sha256=token,
        candidate_interpretation=candidate,base_snapshot_sha256=q.fingerprint(original),post_review={'assessment':'pass'})
    monkeypatch.setattr(versions,'read',lambda *a:{'L1':record})
    monkeypatch.setattr(ficha_reader,'ler_estado_pavimento',lambda *a,**kw:copy.deepcopy(state))
    with pytest.raises(ValueError):q.promote(tmp_path,'13_PAV',classe,item,behavior,'L1','r1',token,7)
    q.promote(tmp_path,'13_PAV',classe,item,behavior,'L1','r2',token,7)
    assert q.snapshot(q.apply_effective(copy.deepcopy(state),tmp_path,'13_PAV'),classe,item,behavior)==candidate
    assert q.snapshot(state,classe,item,behavior)==original
