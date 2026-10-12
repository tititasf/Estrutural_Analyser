import copy
import json
from types import SimpleNamespace

import httpx
import pytest

from portal.app import auth, item_geometry, structural_review as review, structural_audit as audit
from portal.app.main import create_app
from portal.db import connection, repository as repo


def entry():
    return dict(beam='VX', behavior='para', kind='interpreted', fundo_id='f1', cut_index=0,
        section_contract=dict(width_cm=19, height_cm=55, slabs=dict(
            A=[dict(name='L1',height_cm=13,drop_cm=7)], B=[])),
        pairs=[dict(start=[0,0],end=[100,0],profiles=dict(A=dict(slabs=[dict(name='L1',level=852.12)])))],
        drawing=dict(points=[[0,0],[19,0],[19,50],[0,50]],primitives=[]))


def test_review_locality_roundtrip_expiration_and_rejection(tmp_path):
    e = entry()
    uid = review.entry_id(e)
    review.decide(tmp_path,'13_PAV',dict(entries=[e]),uid,'validate','operator')
    decisions = review.load(tmp_path,'13_PAV')
    assert review.status(decisions,uid,e) == 'validated'
    republished = copy.deepcopy(e)
    republished['cut_index'] = 9
    assert review.status(decisions,review.entry_id(republished),republished) == 'validated'
    republished['section_contract']['height_cm'] = 60
    assert review.status(decisions,review.entry_id(republished),republished) is None
    cut = dict(kind='inferred',pairs=copy.deepcopy(e['pairs']))
    cut['pairs'][0]['start'] = tuple(cut['pairs'][0]['start'])
    slabs=[dict(name='L1',nivel=852.12)]
    result=review.apply_levels([cut],decisions,'VX',slabs)[0]
    assert result['beam_top_level_m'] == 852.19
    assert result['beam_datum_source'] == 'human_validated_section'
    changed = dict(cut, beam_height_cm=60)
    assert 'beam_top_level_m' not in review.apply_levels([changed],decisions,'VX',slabs)[0]
    assert 'beam_top_level_m' not in review.apply_levels([cut],decisions,'OTHER',slabs)[0]
    cut['pairs'][0]['end'] = [200,0]
    assert 'beam_top_level_m' not in review.apply_levels([cut],decisions,'VX',slabs)[0]
    review.decide(tmp_path,'13_PAV',dict(entries=[e]),uid,'delete','operator')
    deleted=review.load(tmp_path,'13_PAV')
    assert review.status(deleted,uid,e) == 'deleted'
    assert review.load(tmp_path,'14_PAV') == {}
    original=dict(kind='inferred',pairs=e['pairs'],beam_top_level_m=852.19,
                  beam_datum_source='original_cad_section',beam_datum_evidence_ids=['CAD'])
    kept=review.apply_levels([original],deleted,'VX',slabs)[0]
    assert kept['beam_datum_evidence_ids'] == ['CAD']
    assert kept['excluded_interpreted_reference_ids'] == [uid]
    renamed=copy.deepcopy(e);renamed['cut_index']=4
    new_uid=review.entry_id(renamed)
    review.decide(tmp_path,'13_PAV',dict(entries=[renamed]),new_uid,'validate','operator')
    review.decide(tmp_path,'13_PAV',dict(entries=[renamed]),new_uid,'delete','operator')
    fresh=dict(kind='calculated',pairs=e['pairs'])
    assert 'beam_top_level_m' not in review.apply_levels([fresh],review.load(tmp_path,'13_PAV'),'VX',slabs)[0]


def test_validated_recess_preserves_absolute_collision_levels(tmp_path):
    from src.core.lv_n3_cut_contract import build_cut_contract
    e=entry(); uid=review.entry_id(e)
    review.decide(tmp_path,'13_PAV',dict(entries=[e]),uid,'validate','operator')
    slab=dict(name='L1',height_cm=13,level=852.12)
    profile=dict(level=852.12,slabs=[slab],level_source='paired_touching_slabs')
    cut=dict(id='c',beam='VX',kind='calculated',width_cm=19,beam_height_cm=55,
             pairs=e['pairs'],profiles=dict(A=profile,B=dict(level=852.12,slabs=[])))
    reviewed=review.apply_levels([cut],review.load(tmp_path,'13_PAV'),'VX',[dict(name='L1',nivel=852.12)])[0]
    contract=build_cut_contract(reviewed)
    assert contract['slabs']['A'][0]['drop_cm']==7
    assert contract['top_level_m']==852.19
    assert contract['base_level_m']==851.64
    assert contract['vertical_datum_source']=='human_validated_section'


def original():
    return dict(uid='cut1',beam_name='VX',beam_w=19,beam_h=55,own_laje='L1',
        points=[[0,0],[19,0],[19,55],[0,55]],ficha=dict(direction='norte',
        side_a_laje_name='L1',side_a_laje_height=13,own_slab_height=13,
        own_dist_top=0,own_dist_bottom=42))


def test_original_fields_and_deletion_survive_duplicate_sources(tmp_path):
    raw=original()
    (tmp_path/'estado_13_PAV.json').write_text(json.dumps(dict(cortes=[raw],slabs=[])))
    fields=dict(ficha=dict(raw['ficha'],own_dist_top=7,own_dist_bottom=35))
    result=item_geometry.mutate(tmp_path,'13_PAV','cortes','cut1',fields=fields)
    assert result['before'][0]['ficha']['own_dist_top'] == 0
    assert result['after'][0]['ficha']['own_dist_top'] == 7
    assert audit.render(result['before'],[], 'delete').startswith(b'\x89PNG')
    # Rich slab-link evidence must not undo a manual edit or resurrect deletion.
    duplicate=dict(raw,uid='L1_duplicate')
    merged=item_geometry.apply_cut_sources([raw,duplicate],tmp_path,'13_PAV')
    assert len(merged)==1
    assert merged[0]['ficha']['own_dist_top']==7
    item_geometry.mutate(tmp_path,'13_PAV','cortes','cut1',delete=True)
    assert item_geometry.apply_cut_sources([raw,duplicate],tmp_path,'13_PAV') == []


@pytest.mark.asyncio
async def test_routes_audit_inbox_and_readonly_interpreted(settings,tmp_path,monkeypatch):
    root=tmp_path/'work';root.mkdir()
    import ezdxf
    source=root/'structural.dxf'
    doc=ezdxf.new()
    doc.modelspace().add_line((-120,-120),(220,180))
    doc.modelspace().add_text('VIZINHO P8',dxfattribs={'insert':(-100,100),'height':15})
    doc.saveas(source)
    monkeypatch.setattr('portal.app.ficha_reader._fonte_estrutural_producao',lambda *a:source)
    (root/'estado_13_PAV.json').write_text(json.dumps(dict(cortes=[original()],slabs=[])))
    db=connection.init_db(settings.db_path)
    member=repo.criar_membro(db,login='review',nome='Reviewer',senha_hash=auth.hash_senha('test123'),drive_folder_id='r')
    work=repo.criar_obra(db,membro_id=member,nome='Review',pasta_drive_id='r',arquivo_hash='r',estado='pronta',local_path=str(root))
    db.close()
    e=entry();uid=review.entry_id(e)
    monkeypatch.setattr('portal.app.structural_cut_overlay.collect_sections',lambda *a,**kw:dict(entries=[e]))
    app=create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            base=f'/obras/{work}/itens'
            await client.post('/login',json=dict(login='review',senha='test123'))
            fields=dict(ficha=dict(original()['ficha'],own_dist_top=7,own_dist_bottom=35))
            response=await client.put(base+'/cortes/cut1/geometria?pavimento=13_PAV',json=dict(fields=fields))
            assert response.status_code==200,response.text
            assert response.json()['apontamento_id']
            response=await client.post(base+f'/cortes_interpretados/{uid}/validar?pavimento=13_PAV')
            assert response.status_code==200,response.text
            assert (await client.put(base+f'/cortes_interpretados/{uid}/geometria?pavimento=13_PAV',json=dict(points=original()['points']))).status_code==422
            assert (await client.post(base+f'/cortes_interpretados/{uid}/validar?pavimento=14_PAV')).status_code==404
            assert (await client.request('DELETE',base+f'/cortes_interpretados/{uid}?pavimento=13_PAV',
                json=dict(comentario='  Nível incorreto; rever a laje <teste>  '))).status_code==200
            listing=await client.get(f'/obras/{work}/cortes-interpretados?pavimento=13_PAV')
            assert listing.json()['itens']==[]
            inbox=(await client.get('/apontamentos-ui/sessoes')).json()
            assert inbox['total']==3
            points=[s['paginas'][0]['pontos'][0] for s in inbox['sessoes']]
            assert all(p['tem_captura'] and len(p['anexos'])==2 for p in points)
            assert all(p['elemento']['structural_context']['status']=='captured' for p in points)
            assert all(p['elemento']['structural_context']['source']==str(source) for p in points)
            assert {p['elemento']['action'] for p in points}=={'edit','validate','delete'}
            deleted=next(p for p in points if p['elemento']['action']=='delete')
            assert deleted['elemento']['comentario']=='Nível incorreto; rever a laje <teste>'
            assert 'Nível incorreto; rever a laje <teste>' in deleted['texto']
            assert review.load(root,'13_PAV')[uid]['comentario']==deleted['elemento']['comentario']


def test_audit_outbox_retries_once(settings,tmp_path,monkeypatch):
    db=connection.init_db(settings.db_path)
    member=repo.criar_membro(db,login='outbox',nome='Outbox',senha_hash='x',drive_folder_id='q')
    work=repo.criar_obra(db,membro_id=member,nome='Outbox',pasta_drive_id='q',arquivo_hash='q',estado='pronta',local_path=str(tmp_path))
    request=SimpleNamespace(base_url='http://test',app=SimpleNamespace(state=SimpleNamespace(settings=settings)))
    result=dict(event_id='test-event',affected=[dict(classe='cortes',item_id='cut1')],action='delete',before=[original()],after=[])
    import base64
    frozen=audit.render([original()],[],'delete')
    monkeypatch.setattr('portal.app.structural_audit_context.capture',lambda *a:dict(
        status='captured',png_base64=base64.b64encode(frozen).decode(),nearby_items=[dict(item_id='P8')]))
    persist=audit._persist
    monkeypatch.setattr(audit,'_persist',lambda *a: (_ for _ in ()).throw(RuntimeError('temporary DB failure')))
    assert audit.record(db,request,dict(id=member),work,'13_PAV',result,tmp_path) is None
    # Retry must use the frozen evidence, even after a drawing changes.
    monkeypatch.setattr('portal.app.structural_audit_context.capture',lambda *a: (_ for _ in ()).throw(AssertionError('recapture')))
    monkeypatch.setattr(audit,'_persist',persist)
    audit.flush(db,request,dict(id=member))
    audit.flush(db,request,dict(id=member))
    assert db.execute('SELECT count(*) FROM portal_apontamento_sessoes').fetchone()[0]==1
    assert db.execute('SELECT captura_blob FROM portal_apontamentos_ui').fetchone()[0]==frozen
    db.close()

def test_rejection_regenerates_without_resurrecting_validation(tmp_path):
    import time
    e = entry(); uid = review.entry_id(e)
    review.decide(tmp_path, '13_PAV', {'entries': [e]}, uid, 'validate', 'human')
    review.decide(tmp_path, '13_PAV', {'entries': [e]}, uid, 'delete', 'human', 'wrong level')
    rejected = review.load(tmp_path, '13_PAV')[uid]
    assert review.status({uid: rejected}, uid, e) == 'deleted'
    assert review.restore_generated(tmp_path, '13_PAV', time.time(), inventory={}) == 0
    changed = copy.deepcopy(e); changed['section_contract']['height_cm'] = 60
    assert review.restore_generated(tmp_path, '14_PAV', time.time(), inventory={'entries': [changed]}) == 0
    assert review.restore_generated(tmp_path, '13_PAV', time.time(), inventory={'entries': [changed]}) == 1
    decisions = review.load(tmp_path, '13_PAV')
    assert review.status(decisions, uid, e) is None
    assert decisions[uid]['event_id'] == rejected['event_id']
    assert decisions[uid]['comentario'] == 'wrong level'
    assert decisions[uid]['entry'] == rejected['entry']
    cut = dict(kind='calculated', pairs=e['pairs'])
    assert 'beam_top_level_m' not in review.apply_levels([cut], decisions, 'VX', [dict(name='L1', nivel=852.12)])[0]
    assert review.restore_generated(tmp_path, '13_PAV', time.time(), inventory={'entries': [changed]}) == 0


def test_generation_does_not_release_newer_rejection_or_other_class(tmp_path):
    import time
    from portal.app.pipeline_runner import _restore_generated_section_reviews
    e = entry(); uid = review.entry_id(e)
    started = time.time()
    review.decide(tmp_path, '13_PAV', {'entries': [e]}, uid, 'delete', 'human')
    state = {'segmentos': {'lateral_a_para': [{'beam_name': 'VX'}], 'fundo': [{'beam_name': 'OTHER'}]}}
    assert review.restore_generated(tmp_path, '13_PAV', started - 1, beam_names={'VX'}) == 0
    _restore_generated_section_reviews(tmp_path, '13_PAV', state, 'pilares', set(), time.time())
    _restore_generated_section_reviews(tmp_path, '13_PAV', state, 'fundos_viga', set(), time.time())
    _restore_generated_section_reviews(tmp_path, '13_PAV', state, 'laterais_viga', {'OTHER'}, time.time())
    assert review.status(review.load(tmp_path, '13_PAV'), uid, e) == 'deleted'
    _restore_generated_section_reviews(tmp_path, '13_PAV', state, 'laterais_viga', {'VX'}, time.time())
    assert review.status(review.load(tmp_path, '13_PAV'), uid, e) is None
