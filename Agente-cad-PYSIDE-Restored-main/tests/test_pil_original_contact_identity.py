"""Mutation guards; source geometric/numeric readers have separate DXF tests."""
import copy

import pytest

from src.core.pil_original_contact_identity import reconcile_original_contact_identity


@pytest.mark.parametrize('veto',['none','normalization','distance','human'])
def test_original_narrow_short_face_alias_requires_stable_r2_arrival(monkeypatch,veto):
    from portal.app import qa_cad_gate
    from src.core import pillar_abcd_tables
    slot={'name':'V1','dim':'','start':10,'end':24}
    if veto=='human':slot['human_override']=True
    p={'points':[[0,0],[100,0],[100,19],[0,19],[0,0]],
       'face_beams':{'C':{'interior':[slot],'para':[]}}}
    def tables(p,**kwargs):
        family='para' if p['face_beams']['C']['para'] else 'interior'
        name=p['face_beams']['C'][family][0]['name']
        role='chega' if family=='para' else 'interior'
        if veto=='normalization' and name=='V2':role='interior'
        return {'faces':{'C':{role:[dict(nome=name,dim='14/55',canto='CC',dist_esq='0',dist_dir='5')]}}}
    monkeypatch.setattr(pillar_abcd_tables,'build_abcd_tables_from_pillar',tables)
    def measure(source,snapshot):
        faces=snapshot['collections']['pilares'][0]['interpretacao_abcd']['faces']
        role='chega' if 'chega' in faces['C'] else 'interior'
        name=faces['C'][role][0]['nome']
        c=dict(face='C',role=role,beam=name,status='uncertain',errors={},
               identity_path_review={'names':['V2']},geometry_only={'section':'14/55','wall_handles':['a','b']})
        if name=='V2':
            c.update(status='measured',wall_handles=['a','b'],beam_handles=['n'],section_handles=['s'])
            if veto=='distance':c['errors']={'distancias_cantos':'different'}
        return dict(contacts=[c],source_sha256='source-test-double')
    monkeypatch.setattr(qa_cad_gate,'measure',measure)
    before=copy.deepcopy(p)
    changes=reconcile_original_contact_identity('original.dxf',{'P1':p},[])
    if veto!='none':assert not changes and p==before
    else:
        assert len(changes)==1 and changes[0]['role']=='chega'
        assert not p['face_beams']['C']['interior']
        assert p['face_beams']['C']['para'][0] is slot
        assert (slot['name'],slot['dim'],slot['corner'],slot['start'],slot['end'])==('V2','14/55','CC',10,24)


@pytest.mark.parametrize('veto',['none','distance','walls','human','duplicate','explicit_corner','normalization'])
def test_automatic_interior_corner_matches_unique_uncornered_source_slot(monkeypatch,veto):
    from portal.app import qa_cad_gate
    from src.core import pillar_abcd_tables
    slot={'name':'V1','dim':'','start':10,'end':24}
    if veto=='human':slot['human_override']=True
    if veto=='explicit_corner':slot['corner']='CA'
    slots=[slot]
    if veto=='duplicate':slots.append(dict(slot))
    pillar={'face_beams':{'C':{'interior':slots}}}
    def tables(p,**kwargs):
        name=p['face_beams']['C']['interior'][0]['name']
        if veto=='normalization' and name=='V2':
            return {'faces':{'A':{'passa':[dict(nome=name,dim='14/55',canto='AC')]}}}
        return {'faces':{'C':{'interior':[dict(nome=name,dim='',canto='CC')]}}}
    monkeypatch.setattr(pillar_abcd_tables,'build_abcd_tables_from_pillar',tables)
    def measure(source,snapshot):
        faces=snapshot['collections']['pilares'][0]['interpretacao_abcd']['faces']
        if 'C' not in faces:
            return dict(contacts=[dict(face='A',role='passa',beam='V2',status='uncertain',errors={})],source_sha256='source-test-double')
        name=faces['C']['interior'][0]['nome']
        c=dict(face='C',role='interior',beam=name,status='uncertain',errors={},
            identity_path_review={'names':['V2']},geometry_only={'section':'14/55','wall_handles':['a','b']})
        if name=='V2':
            c.update(status='measured',wall_handles=['a','b'],beam_handles=['n'],section_handles=['s'])
            if veto=='distance':c['errors']={'distancias_cantos':'different'}
            if veto=='walls':c['wall_handles']=['foreign']
        return dict(contacts=[c],source_sha256='source-test-double')
    monkeypatch.setattr(qa_cad_gate,'measure',measure)
    before=copy.deepcopy(pillar)
    changed=reconcile_original_contact_identity('original.dxf',{'P1':pillar},[])
    if veto!='none':
        assert not changed and pillar==before
    else:
        assert len(changed)==1
        assert slot['name']=='V2' and slot['dim']=='14/55'
        assert (slot['start'],slot['end'])==(10,24)
        assert 'corner' not in slot


@pytest.mark.parametrize('veto', ['none', 'distance', 'wall', 'section',
                                'same_physical_duplicate', 'other_distance_duplicate',
                                'other_wall_duplicate',
                                'competing', 'human_slot', 'human_field'])
def test_reconciliation_requires_same_physical_contact_and_complete_proof(monkeypatch, veto):
    from portal.app import qa_cad_gate
    from src.core import pillar_abcd_tables
    slot = dict(name='V1', dim='14/60', corner='left', start=12, end=26)
    duplicate = dict(name='V2', dim='14/55', corner='left', validated=True)
    pillar = {'face_beams': {'A': {'para': [slot, duplicate]}}}
    if veto == 'human_slot':
        slot['human_override'] = True
    if veto == 'human_field':
        pillar['validated_fields'] = ['p_sA_v_ch1_n']
    table = {'faces': {'A': {'chega': [dict(nome='V1', dim='14/60', canto='left')]}}}
    monkeypatch.setattr(pillar_abcd_tables, 'build_abcd_tables_from_pillar', lambda *a, **k: copy.deepcopy(table))
    def measure(source, snapshot):
        name = snapshot['collections']['pilares'][0]['interpretacao_abcd']['faces']['A']['chega'][0]['nome']
        contact = dict(beam=name, face='A', role='chega', status='uncertain', errors=[],
                       identity_path_review={'names': ['V2'] if veto != 'competing' else ['V2', 'V3']},
                       geometry_only={'section': '14/55', 'wall_handles': ['1', '2']})
        if name == 'V2':
            contact.update(status='measured', wall_handles=['1', '2'], beam_handles=['3'], section_handles=['4'])
            if veto.endswith('_duplicate'):
                contact['distances_cm'] = [12, 26]
                other = copy.deepcopy(contact)
                if veto == 'other_distance_duplicate':
                    other['distances_cm'] = [13, 25]
                if veto == 'other_wall_duplicate':
                    other['wall_handles'] = ['5', '6']
                return {'contacts': [contact, other], 'source_sha256': 'source-test-double'}
            if veto == 'distance':
                contact['errors'] = ['dist_esq']
            if veto == 'wall':
                contact['wall_handles'] = ['5', '6']
            if veto == 'section':
                contact['section_handles'] = []
        return {'contacts': [contact], 'source_sha256': 'source-test-double'}
    monkeypatch.setattr(qa_cad_gate, 'measure', measure)
    before = copy.deepcopy(pillar)
    changed = reconcile_original_contact_identity('source.dxf', {'P1': pillar}, [])
    if veto not in ('none', 'same_physical_duplicate'):
        assert not changed
        assert pillar == before
    else:
        assert len(changed) == 1
        assert (slot['name'], slot['dim'], slot['start'], slot['end']) == ('V2', '14/55', 12, 26)
        assert duplicate in pillar['face_beams']['A']['para']
        assert duplicate['validated']


@pytest.mark.parametrize('veto', ['none', 'distance', 'human', 'walls'])
@pytest.mark.parametrize('storage', ['interior', 'para'])
def test_same_name_section_correction_reproves_same_contact_and_keeps_position(monkeypatch, veto, storage):
    from portal.app import qa_cad_gate
    from src.core import pillar_abcd_tables
    slot = dict(name='V1', dim='19/71', corner='CC', start=12, end=31)
    if veto == 'human': slot['validated'] = True
    pillar = {'face_beams': {'C': {storage: [slot]}}}
    monkeypatch.setattr(pillar_abcd_tables, 'build_abcd_tables_from_pillar', lambda *a, **k: {
        'faces': {'C': {'interior': [dict(nome='V1', dim=slot['dim'], canto='CC')]}}})
    def measure(source, snapshot):
        dim = snapshot['collections']['pilares'][0]['interpretacao_abcd']['faces']['C']['interior'][0]['dim']
        contact = dict(beam='V1', face='C', role='interior', status='measured',
                       errors={'dimensoes': 'original numeric section differs'} if dim != '19/120' else {},
                       section='19/120', wall_handles=['1', '2'], beam_handles=['3'], section_handles=['4'])
        if veto == 'distance': contact['errors']['dist_esq'] = 'mismatch'
        if veto == 'walls' and dim == '19/120': contact['wall_handles'] = ['5', '6']
        return {'contacts': [contact], 'source_sha256': 'source-test-double'}
    monkeypatch.setattr(qa_cad_gate, 'measure', measure)
    before = copy.deepcopy(pillar)
    changed = reconcile_original_contact_identity('source.dxf', {'P1': pillar}, [])
    if veto != 'none':
        assert not changed
        assert pillar == before
    else:
        assert len(changed) == 1
        assert (slot['name'], slot['dim'], slot['start'], slot['end']) == ('V1', '19/120', 12, 31)
        assert slot['source'] == 'original_contact_section'


@pytest.mark.parametrize('veto',['none','human','wall','corner','source_face','no_corner_proof'])
def test_passage_section_is_bound_to_its_own_original_corner(monkeypatch,veto):
    from portal.app import qa_cad_gate
    from src.core import pillar_abcd_tables
    correct=dict(name='V1',dim='19/120',corner='DA',start=12,end=31)
    wrong=dict(name='V1',dim='19/120',corner='DB',start=12,end=31)
    if veto=='human':wrong['validated']=True
    pillar={'face_beams':{'D':{'passa_esq':correct,'passa_dir':wrong}}}
    monkeypatch.setattr(pillar_abcd_tables,'build_abcd_tables_from_pillar',lambda *a,**k:{
        'faces':{'D':{'passa':[dict(nome='V1',dim=correct['dim'],canto='DA'),
                              dict(nome='V1',dim=wrong['dim'],canto='DB')]}}})
    def measure(source,snapshot):
        rows=snapshot['collections']['pilares'][0]['interpretacao_abcd']['faces']['D']['passa']
        contacts=[]
        for row,section,source_face in zip(rows,['19/120','19/50'],['A','B']):
            c=dict(beam='V1',face='D',role='passa',status='measured',section=section,
                   errors={} if row['dim']==section else {'dimensoes':'different source section'},
                   wall_handles=['w1','w2'],beam_handles=['n'],section_handles=['s'],
                   aspect='passa_corner',corner=row['canto'],source_contact_face=source_face)
            if veto=='no_corner_proof':c.pop('aspect')
            if row['canto']=='DB' and row['dim']=='19/50':
                if veto=='wall':c['wall_handles']=['other']
                if veto=='corner':c['corner']='DA'
                if veto=='source_face':c['source_contact_face']='A'
            contacts.append(c)
        return dict(contacts=contacts,source_sha256='source-test-double')
    monkeypatch.setattr(qa_cad_gate,'measure',measure)
    before=copy.deepcopy(pillar)
    changes=reconcile_original_contact_identity('original.dxf',{'P1':pillar},[])
    if veto!='none':
        assert not changes
        assert pillar==before
    else:
        assert len(changes)==1
        assert wrong['dim']=='19/50'
        assert (wrong['corner'],wrong['start'],wrong['end'])==('DB',12,31)
        assert correct==before['face_beams']['D']['passa_esq']
