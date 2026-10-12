import ezdxf
from portal.app.preprocessamento.adapters.dimensioned_section_profiles import inventory_dimensioned_section_profiles


def source(tmp_path, rotation=0, reflection=False, missing_tick=False, wrong_dimension=False, pillar_label=False):
    doc=ezdxf.new()
    doc.layers.new('profile',dxfattribs={'color':8})
    ms=doc.modelspace()
    def tr(point):
        x,y=point
        if reflection:x=-x
        for _ in range(rotation):x,y=-y,x
        return x+1000,y+2000
    profile=ms.add_lwpolyline([tr(p) for p in [(0,0),(64,0),(64,13),(34,13),(34,10),(0,10)]],close=True,dxfattribs={'layer':'profile'})
    ms.add_line(tr((10,10)),tr((10,13)),dxfattribs={'layer':'0'})
    for y in ([10] if missing_tick else [10,13]):
        ms.add_line(tr((8,y+2)),tr((12,y-2)),dxfattribs={'layer':'0'})
    ms.add_text('4' if wrong_dimension else '3',dxfattribs={'insert':tr((7,20)),'height':5})
    if pillar_label:ms.add_text('P101',dxfattribs={'insert':tr((20,5)),'height':5})
    path=tmp_path/f'fixture{rotation}{reflection}{missing_tick}{wrong_dimension}{pillar_label}.dxf'
    doc.saveas(path)
    return path,profile.dxf.handle


def test_original_dimensioned_profile_preserves_direction_and_provenance(tmp_path):
    for r in range(4):
        for reflection in (False,True):
            path,handle=source(tmp_path,r,reflection)
            result=inventory_dimensioned_section_profiles(path)
            assert len(result['records'])==1
            record=result['records'][0]
            assert record['source_entity_handles']==[handle]
            assert len(record['dimension_evidence_handles'])==4
            assert sorted(record['measured_thicknesses_cm'])==[10,13]
            assert record['step_delta_cm']==3
            assert record['level_transfer_authorized'] is False


def test_missing_tick_wrong_numeric_or_competing_plan_label_blocks_role(tmp_path):
    for kwargs in ({'missing_tick':True},{'wrong_dimension':True},{'pillar_label':True}):
        path,_=source(tmp_path,**kwargs)
        assert inventory_dimensioned_section_profiles(path)['records']==[]
