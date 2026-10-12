from pathlib import Path
import ezdxf
from portal.app.preprocessamento.adapters.level_convention import extract_level_convention
from portal.app.preprocessamento.adapters.level_crossing import _floor_reference
from portal.app.preprocessamento.adapters.auxiliary import crosscheck_reference, semantic_roles, inventory_auxiliary


def drawing(path, *, offset=0, scale=1, title=True, conflict=False):
    doc = ezdxf.new()
    m = doc.modelspace()
    def pos(x, y): return (offset+x*scale, offset+y*scale)
    def text(t,x,y): m.add_text(t,dxfattribs={'insert':pos(x,y),'height':8*scale})
    text('DIMENSOES EM CM - COTAS EM METROS',400,400)
    if title: text('FORMA DO PISO DO 3° PAVIMENTO TIPO ao PISO',400,500)
    for floor,y,value in [(2,0,'-2.00'),(3,100,'0.92'),(4,200,'3.84')]:
        m.add_lwpolyline([pos(-10,y+25),pos(0,y+10),pos(10,y+25),pos(-10,y+25)])
        text(f'{floor}° PAVIMENTO',0,y)
        text(value,-8,y+32)
        text('292',-40,y+32)
        if floor>=3: text('TIPO',100,y)
        if conflict and floor==3: text('5.00',0,y+33)
    doc.saveas(path)


def test_geometry_markers_scale_and_translation(tmp_path):
    for scale,offset in [(1,0),(10,-10000),(.1,3000)]:
        path=tmp_path/f'{scale}.dxf'
        drawing(path,scale=scale,offset=offset)
        ref=_floor_reference(path,'TIPO_TESTE','raw')
        assert ref['status']=='direct_local_reference'
        assert (ref['base'],ref['top'],ref['height'])==(-2,.92,2.92)
        assert ref['floor_selection']['represented_floors']==[3,4]


def test_typical_without_title_is_not_assumed(tmp_path):
    path=tmp_path/'no_title.dxf';drawing(path,title=False)
    assert _floor_reference(path,'TIPO_TESTE','raw')['status']=='unsupported_floor_name'


def test_ambiguous_marker_does_not_choose_nearest_numeric_text(tmp_path):
    path=tmp_path/'conflict.dxf';drawing(path,conflict=True)
    rows=extract_level_convention(path)['direct_floor_levels']
    assert next(r for r in rows if r['floor_label']=='3° PAVIMENTO')['selected'] is None


def test_same_original_is_not_independent_confirmation():
    ref={'floor_selection':{'representative_floor':3},'unit':'m','top':.92}
    evidence={'source_id':'crop','source_revision':'hash','level_convention':{
        'direct_floor_levels':[{'floor_label':'3° PAVIMENTO','selected':{
            'value':.92,'unit':'m','text_handle':'1'}}]}}
    qa=crosscheck_reference(ref,[evidence])
    assert qa['status']=='consistent' and qa['independent_vote_count']==0
    evidence['level_convention']['direct_floor_levels'][0]['selected']['value']=1.92
    assert crosscheck_reference(ref,[evidence])['status']=='conflicting'


def test_crop_without_unit_cannot_contradict_absolute_reference():
    ref={'floor_selection':{'representative_floor':3},'unit':'m','top':.92}
    evidence={'source_id':'crop','source_revision':'hash','level_convention':{
        'direct_floor_levels':[{'floor_label':'3° PAVIMENTO','selected':{
            'value':92,'unit':None,'text_handle':'1'}}]}}
    qa=crosscheck_reference(ref,[evidence])
    assert qa['status']=='partial_confirmation'
    assert not qa['conflicts'] and qa['independent_vote_count']==0


def test_two_floor_labels_cannot_own_one_geometric_datum(tmp_path):
    path = tmp_path/'shared.dxf'
    drawing(path)
    doc = ezdxf.readfile(path)
    doc.modelspace().add_text('5° PAVIMENTO', dxfattribs={'insert': (0, 102), 'height': 8})
    doc.saveas(path)
    rows = extract_level_convention(path)['direct_floor_levels']
    shared = [r for r in rows if r['floor_label'] in ('3° PAVIMENTO', '5° PAVIMENTO')]
    assert len(shared) == 2
    assert all(r['selected'] is None and r['status'] == 'ambiguous' for r in shared)


def test_materials_table_is_not_pillar_legend(tmp_path):
    from types import SimpleNamespace
    from portal.app.preprocessamento.sources import SourceKind
    path = tmp_path/'materials.dxf'
    doc = ezdxf.new()
    for i, text in enumerate(('RESUMO DOS MATERIAIS', 'PILARES', 'CONCRETO (m3)', 'FORMA (m2)')):
        doc.modelspace().add_text(text, dxfattribs={'insert': (0, i*20)})
    doc.saveas(path)
    result = inventory_auxiliary(path, SimpleNamespace(source_id='crop', revision='sha', kind=SourceKind.OTHER))
    assert [r['role'] for r in result['semantic_roles']] == ['materials_summary']
    assert result['pillar_convention'] is None
    assert result['level_convention'] is None


def test_named_sections_do_not_claim_item_or_level_association():
    texts = [{'text': t, 'handle': str(i), 'position': [0, i*10]}
             for i, t in enumerate(('CORTE A-A', 'CORTE 1-1', 'VER CORTE 1-1', 'CORTE A-B', 'P14', '537.86'))]
    roles = semantic_roles(texts)
    assert [r['title'] for r in roles] == ['CORTE A-A', 'CORTE 1-1']
    assert all(r['authority'] == 'explicit_title_only' for r in roles)
