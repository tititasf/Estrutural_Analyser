import ezdxf
import pytest
from shapely.geometry import box
from portal.app.qa_fv_source_inventory import pillar_solids, competing_ownership_checked, inventory_scope_checked


def fixture():
    doc=ezdxf.new();space=doc.modelspace()
    space.add_lwpolyline([(0,0),(20,0),(20,20),(0,20)],close=True)
    space.add_text('P1',dxfattribs={'insert':(10,10)})
    return doc


@pytest.fixture(autouse=True)
def original_owned_contour(monkeypatch):
    def scene(doc,eps):
        poly=next(iter(doc.modelspace().query('LWPOLYLINE')))
        name=next(iter(doc.modelspace().query('TEXT')))
        return {'supports':[{'handle':poly.dxf.handle,'name_handles':[name.dxf.handle],
                             'dimension_handles':['original_numeric_section']}]}
    monkeypatch.setattr('src.core.pil_qa_identity_paths.collect_identity_scene',scene)


def test_missing_source_legend_never_certifies_empty_solid_inventory():
    shapes,proof=pillar_solids(fixture(),{}, {})
    assert shapes is None and not proof['checked']


def test_nasce_excludes_own_contour_only(monkeypatch):
    monkeypatch.setattr('src.core.pillar_convention_recognition.recognize',lambda *args:('NASCE',{}))
    shapes,proof=pillar_solids(fixture(),{}, {'NASCE':{'sig':'X'}})
    assert shapes==[] and proof['checked']
    monkeypatch.setattr('src.core.pillar_convention_recognition.recognize',lambda *args:('SEGUE',{}))
    shapes,proof=pillar_solids(fixture(),{}, {'SEGUE':{'sig':'X'}})
    assert len(shapes)==1 and shapes[0].area==400 and proof['checked']


def test_unmatched_name_and_ambiguous_symbol_fail_closed(monkeypatch):
    doc=fixture();doc.modelspace().add_text('P2',dxfattribs={'insert':(200,200)})
    shapes,proof=pillar_solids(doc,{}, {'SEGUE':{'sig':'X'}})
    assert not proof['checked']
    assert not inventory_scope_checked(proof,box(190,190,210,210))
    monkeypatch.setattr('src.core.pillar_convention_recognition.recognize',lambda *args:('INDETERMINADO',{}))
    assert not pillar_solids(fixture(),{}, {'SEGUE':{'sig':'X'}})[1]['checked']


def test_any_manual_or_validated_competitor_requires_reconciliation():
    assert competing_ownership_checked([{'geometry_source':'automatic'}])
    for row in ({'validated_fields':['points']},{'validated':True},{'is_validated':True},
                {'manual':True},{'geometry_source':'human'},{'geometry_source':'manual_edit'}):
        assert not competing_ownership_checked([row])


def test_nearby_name_without_numeric_contour_ownership_is_not_authority(monkeypatch):
    monkeypatch.setattr('src.core.pil_qa_identity_paths.collect_identity_scene',lambda *args:{'supports':[]})
    assert not pillar_solids(fixture(),{}, {'SEGUE':{'sig':'X'}})[1]['checked']


def test_distant_original_ambiguity_does_not_block_local_connected_component():
    proof={'checked':False,'local_scope_available':True,'uncertainties':[
        {'points':[(1000,1000),(1020,1000),(1020,1020),(1000,1020)]}]}
    assert inventory_scope_checked(proof,box(0,0,400,19))
    assert not inventory_scope_checked(proof,box(999,999,1005,1005))


def test_original_adjacent_details_declaration_and_conflicts(tmp_path,monkeypatch):
    from portal.app.qa_fv_source_inventory import original_convention,declaration_signature
    source=tmp_path/'tower.dxf';source.write_text('source')
    details=tmp_path/'detalhes.dxf';details.write_text('original details')
    def declaration(path):
        if path==source:return {'status':'partial','entries':[]}
        return {'status':'complete','conflicts':[],
                'entries':[{'label':'NASCE','signature':'CROSS','line_count':4}]}
    monkeypatch.setattr('portal.app.preprocessamento.adapters.pillar_convention.extract_pillar_convention',declaration)
    assert original_convention(source,{})=={'NASCE':{'label':'NASCE','sig':'CROSS'}}
    assert original_convention(source,{'NASCE':{'label':'NASCE','sig':'DIAG'}})=={}
    assert 'detalhes.dxf' in declaration_signature(source)
