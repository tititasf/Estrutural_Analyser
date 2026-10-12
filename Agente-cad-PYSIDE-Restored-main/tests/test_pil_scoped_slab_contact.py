import pytest
from src.core.pillar_abcd_tables import scoped_slab_contact_height


def test_region_loader_scopes_evidence_to_same_project(tmp_path):
    import json, sqlite3
    from scripts.arete.pil_agentic_highlight_draw import load_slab_regions
    db=tmp_path/'regions.db'
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE slabs (project_id TEXT, name TEXT, extra_data_json TEXT)')
        c.executemany('INSERT INTO slabs VALUES (?,?,?)', [
            ('one','L',json.dumps({'slab_steps':[region([(20,0),(200,0),(200,100),(20,100)])]})),
            ('two','L',json.dumps({'slab_steps':[{'height_cm':99}]})),
            ('one','Empty','{}')])
    loaded=load_slab_regions(db,'one')
    assert loaded['Empty'] == []
    assert scoped_slab_contact_height('B',(0,0,20,100),loaded['L'][0]['points'],loaded['L'],'12') == ('10','explicit_region_contact')


def region(points, height=10, **extra):
    return dict(points=points, height_cm=height,
                evidence_checks={'closed_cad_boundary': True, 'internal_height': True}, **extra)


@pytest.mark.parametrize('offset', [0, 1450])
def test_contact_uses_local_thickness_even_without_absolute_level(offset):
    box=(offset, 0, offset+20, 100)
    slab=[(offset+20, 40),(offset+200,40),(offset+200,200),(offset+20,200)]
    local=region([(offset+20,40),(offset+70,40),(offset+70,110),(offset+20,110)])
    assert scoped_slab_contact_height('B',box,slab,[local],'12') == ('10','explicit_region_contact')


def test_internal_region_away_from_face_does_not_change_principal_height():
    slab=[(20,0),(200,0),(200,100),(20,100)]
    local=region([(30,0),(70,0),(70,100),(30,100)])
    assert scoped_slab_contact_height('B',(0,0,20,100),slab,[local],'12') == ('12','principal_contact')


def test_mixed_contact_does_not_publish_principal_scalar_as_local_truth():
    slab=[(20,0),(200,0),(200,100),(20,100)]
    local=region([(20,0),(70,0),(70,40),(20,40)])
    assert scoped_slab_contact_height('B',(0,0,20,100),slab,[local],'12') == ('','mixed_or_conflicting_contact_thickness')


def test_mixed_contact_preserves_both_physical_intervals_without_invented_level():
    from src.core.pillar_abcd_tables import slab_face_contact_intervals
    slab=[(20,0),(200,0),(200,100),(20,100)]
    contacts=slab_face_contact_intervals('B',(0,0,20,100),slab,
                [region([(20,0),(70,0),(70,40),(20,40)])],'12')
    assert [(c['start_cm'],c['end_cm'],c['thickness_cm']) for c in contacts] == [(0,40,10),(40,100,12)]
    assert all(c['level_m'] is None for c in contacts)
    assert [(c['left_distance_cm'],c['right_distance_cm']) for c in contacts] == [(0,60),(40,0)]


@pytest.mark.parametrize('kind', ['unknown', 'conflicting_owner', 'mixed'])
def test_regional_row_does_not_inherit_principal_top(kind):
    from src.core.pillar_abcd_tables import refine_slab_contact_thickness
    polygon=[(20,0),(200,0),(200,100),(20,100)]
    local=region(polygon,uid='local')
    if kind!='unknown':
        local.update(level_m=852.22,method='owner_confirmed_scoped_same_bottom',
                     owner_review={'decision_id':'scoped-proof'})
    if kind=='conflicting_owner': local['review_conflict']={'decision_id':'conflict'}
    if kind=='mixed': local['points']=[(20,0),(200,0),(200,40),(20,40)]
    tables={'orientation':'vertical','faces':{'B':{'lajes':[{'nome':'L','dim':'13','nivel':'852.25'}]}}}
    pillar={'points':[(0,0),(20,0),(20,100),(0,100)]}
    row=refine_slab_contact_thickness(tables,pillar,{'L':{
        'height':'13','nivel':'852.25','points':polygon,'slab_steps':[local]}})['faces']['B']['lajes'][0]
    assert row['nivel']==''
    assert tables['faces']['B']['lajes'][0]['nivel']=='852.25'
    if kind=='mixed':
        assert [c['level_m'] for c in row['_contact_intervals']]==[852.22,None]


def test_notched_slab_contact_does_not_fill_gap_using_bbox():
    from src.core.pillar_abcd_tables import slab_face_contact_intervals
    # Slab connected away from the pillar, with a beam/notch between contacts.
    slab=[(20,0),(100,0),(100,100),(20,100),(20,60),(40,60),(40,40),(20,40)]
    contacts=slab_face_contact_intervals('B',(0,0,20,100),slab,[],'12')
    assert len(contacts)==2
    assert contacts[0]['end_cm'] == pytest.approx(40,abs=.002)
    assert contacts[1]['start_cm'] == pytest.approx(60,abs=.002)
    assert sum(c['width_cm'] for c in contacts) == pytest.approx(80,abs=.003)


def test_contact_quantization_does_not_create_principal_tail():
    from src.core.pillar_abcd_tables import slab_face_contact_intervals
    slab=[(20,-60),(200,-60),(200,67),(20,67)]
    local=region(slab,uid='local',level_m=852.22)
    local['evidence_checks']['direct_internal_level']=True
    contacts=slab_face_contact_intervals('B',(0,0,20,86),slab,[local],'13')
    assert len(contacts)==1 and contacts[0]['end_cm']==67
    assert contacts[0]['level_m']==852.22


def test_face_reversed_direction_and_regional_level_require_direct_evidence():
    from src.core.pillar_abcd_tables import slab_face_contact_intervals
    slab=[(-100,0),(0,0),(0,100),(-100,100)]
    local=region([(-100,0),(0,0),(0,40),(-100,40)],level_m=852.0)
    contacts=slab_face_contact_intervals('A',(0,0,20,100),slab,[local],'12')
    assert [(c['start_cm'],c['end_cm'],c['thickness_cm']) for c in contacts] == [(0,60,12),(60,100,10)]
    assert contacts[1]['level_m'] is None
    local['evidence_checks']['direct_internal_level']=True
    assert slab_face_contact_intervals('A',(0,0,20,100),slab,[local],'12')[1]['level_m']==852.0


def test_conflicting_regions_are_reported_per_interval():
    from src.core.pillar_abcd_tables import slab_face_contact_intervals, face_slab_beam_violations
    slab=[(20,0),(200,0),(200,100),(20,100)]
    contacts=slab_face_contact_intervals('B',(0,0,20,100),slab,[region(slab,10),region(slab,11)],'12')
    assert contacts[0]['conflict'] and contacts[0]['thickness_cm'] is None
    assert face_slab_beam_violations('B',{'lajes':[{'nome':'L','_contact_intervals':contacts}]})[0]['rule']=='contato_laje_conflitante'


def test_hatch_without_explicit_height_proof_cannot_override_tag():
    slab=[(20,0),(200,0),(200,100),(20,100)]
    local=region(slab); local['evidence_checks']['internal_height']=False
    assert scoped_slab_contact_height('B',(0,0,20,100),slab,[local],'12') == ('12','principal_contact')


def test_horizontal_pillar_contact_uses_physical_south_face():
    slab=[(0,-100),(100,-100),(100,0),(0,0)]
    assert scoped_slab_contact_height('A',(0,0,100,20),slab,[region(slab)],'12',vertical=False) == ('10','explicit_region_contact')


def test_portal_refines_serialized_table_without_mutating_source():
    from portal.app.ficha_reader import _normalizar_pilar
    pillar = {'name':'P', 'points':[(0,0),(20,0),(20,100),(0,100)], 'lajes':[{'side':'B','laje':'L'}],
              'interpretacao_abcd':{'orientation':'vertical', 'faces':{
                  'B':{'label':'B', 'lajes':[{'nome':'L','dim':'12','nivel':'','canto':'BC'}]}}}}
    slab = {'height':'12','points':[(20,0),(200,0),(200,100),(20,100)]}
    slab['slab_steps'] = [region(slab['points'])]
    result = _normalizar_pilar(pillar, {'L':slab})
    row = result['interpretacao_abcd']['faces']['B']['lajes'][0]
    assert row['dim'] == '10'
    assert result['campos']['Laje B #1 — Altura'] == '10'
    assert pillar['interpretacao_abcd']['faces']['B']['lajes'][0]['dim'] == '12'
    assert row['nivel'] == ''
    slab['slab_steps'] = [region([(20,0),(200,0),(200,40),(20,40)])]
    mixed = _normalizar_pilar(pillar, {'L':slab})
    assert mixed['interpretacao_abcd']['faces']['B']['lajes'][0]['dim'] == ''
    assert mixed['campos']['Laje B #1 — Altura'] == ''
    assert 'Espessuras distintas no contato' in mixed['interpretacao_abcd_html']


def test_special_pillar_cannot_recover_old_bbox_tags(tmp_path):
    from portal.app.ficha_reader import resolver_visualizacoes_n1_pilar, resolver_camadas_qa_pilar
    pack = tmp_path/'TIPO_older_pilares_abcd'
    (pack/'propostas').mkdir(parents=True)
    (pack/'propostas'/'P_sa_motor.svg').write_text('<svg>old bbox tag</svg>')
    item = {'beam_name':'P', 'points':[(0,0),(40,0),(40,20),(20,20),(20,40),(0,40)]}
    views = resolver_visualizacoes_n1_pilar(tmp_path,'TIPO','pilares',item,
        foto_n1_fallback='<svg>source</svg>',html_fichas_root=tmp_path)
    assert views['com_tag'] is None
    assert views['proximo'] == '<svg>source</svg>'
    assert all(not x['disponivel'] for x in resolver_camadas_qa_pilar(
        tmp_path,'TIPO','pilares',item,html_fichas_root=tmp_path).values())


def test_physical_l_tags_require_matching_contour(tmp_path):
    from src.core.pillar_special_faces import physical_tag_geometry_key
    from portal.app.ficha_reader import resolver_visualizacoes_n1_pilar
    points = [(0,0),(40,0),(40,20),(20,20),(20,40),(0,40)]
    pack = tmp_path/'TIPO_new_pilares_abcd'/'propostas'
    pack.mkdir(parents=True)
    svg = (f'<svg data-pil-physical-version="1" '
           f'data-pil-geometry="{physical_tag_geometry_key(points)}">physical</svg>')
    (pack/'P_sa_motor.svg').write_text(svg)
    item = {'beam_name':'P', 'points':points}
    views = resolver_visualizacoes_n1_pilar(tmp_path,'TIPO','pilares',item,html_fichas_root=tmp_path)
    assert views['com_tag'] == svg
    item['points'] = [(x+1,y) for x,y in points]
    views = resolver_visualizacoes_n1_pilar(tmp_path,'TIPO','pilares',item,html_fichas_root=tmp_path)
    assert views['com_tag'] is None
    assert physical_tag_geometry_key(points) == physical_tag_geometry_key(list(reversed(points)))
