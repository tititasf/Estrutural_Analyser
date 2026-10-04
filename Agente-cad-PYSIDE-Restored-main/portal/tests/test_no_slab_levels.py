from shapely.geometry import box
from portal.app.preprocessamento.no_slab_levels import floor_source, level, regions
from portal.app.preprocessamento.segment_levels import inherited, projected_coverage


def source():
    return floor_source({'reference':dict(status='direct_local_reference',unit='m',top=852.19,
        datum_id='tower',evidence_handles=['A'])}, {})


def native():
    return dict(value=852.12,status='estimated',fact_id='fv',evidence_ids=[],warnings=[])


def apply(shape, slabs=(), areas=None, fact=None):
    return level(shape,fact or native(),areas or [(box(10,10,110,110),'red_cross_no_slab',['X','Y'])],
                 source(),slabs,inherited,projected_coverage)


def test_void_border_uses_exit_convention_without_creating_slab():
    r=apply(box(0,10,10,110))
    assert r['value']==852.19 and r['status']=='inferred'
    assert r['confidence_pct']==85.5
    assert r['source_fact_ids']==[source()['fact_id']]
    assert 'cad:X' in r['evidence_ids']


def test_unknown_slab_blocks_void_reference():
    assert apply(box(0,10,10,110),[box(0,10,10,110)]) is None


def test_explicit_cut_or_human_level_preserved():
    for status in ('human_review','sa_evidence','inferred','conflict'):
        assert apply(box(0,10,10,110),fact={**native(),'status':status}) is None


def test_partial_void_border_cannot_fill_whole_beam():
    assert apply(box(0,10,10,310)) is None


def test_mode_requires_majority_and_distinct_slab_votes():
    slabs={str(i):dict(value=v,status='sa_evidence',fact_id=str(i),confidence_pct=95,evidence_ids=[])
           for i,v in enumerate([10,10,11])}
    r=floor_source({},slabs)
    assert r['value']==10 and r['confidence_pct']==63.3
    assert floor_source({},dict(a=slabs['0'],b=slabs['2'])) is None
    assert floor_source({'reference':dict(status='direct_local_reference',unit='m',top=12)},slabs)['value']==12


def test_cad_requires_cross_and_regular_stair_array(tmp_path):
    import ezdxf
    d=ezdxf.new(); m=d.modelspace()
    m.add_line((0,0),(100,100),dxfattribs={'color':1})
    m.add_line((0,100),(100,0),dxfattribs={'color':1})
    for y in range(0,126,25):
        m.add_line((200,y),(300,y),dxfattribs={'color':8})
    # Dimensions and one isolated diagonal must not count.
    for y in range(0,126,25):
        m.add_line((400,y),(500,y),dxfattribs={'color':2})
    p=tmp_path/'cad.dxf';d.saveas(p)
    found=regions({'tower_path':p})
    assert [kind for _,kind,_ in found]==['red_cross_no_slab','stair_tread_array']


def test_stair_landing_expands_only_with_closed_structural_boundary(tmp_path):
    import ezdxf
    d=ezdxf.new();m=d.modelspace()
    for y in range(20,146,25):
        m.add_line((30,y),(130,y),dxfattribs={'color':8})
    for a,b in [((0,0),(200,0)),((0,180),(200,180)),((0,0),(0,180)),((200,0),(200,180))]:
        m.add_lwpolyline([a,b],dxfattribs={'color':3})
    p=tmp_path/'stair.dxf';d.saveas(p)
    assert regions({'tower_path':p})[0][0].bounds==(0,0,200,180)
    # Opening one side preserves only the observed tread footprint.
    m.delete_entity(list(m.query('LWPOLYLINE'))[-1]);d.saveas(p)
    assert regions({'tower_path':p})[0][0].bounds==(30,20,130,145)
