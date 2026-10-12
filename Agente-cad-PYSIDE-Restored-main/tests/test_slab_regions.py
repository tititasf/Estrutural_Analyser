from shapely.geometry import Polygon
from src.core.spatial_index import SpatialIndex
from src.core.slab_tracer import SlabTracer
from src.core.slab_regions import striped_regions, scoped_thickness, name_generated_slabs


def line(a,b,layer='VIGA',**extra):
    return dict(start=a,end=b,layer=layer,**extra)


def fixture():
    ring=[(0,0),(200,0),(200,100),(0,100),(0,0)]
    walls=[line(a,b) for a,b in zip(ring,ring[1:])]
    pattern=[line((50,0),(50,100),'ANNOTATION_REGION'),
             *[line((0,y),(50,y+50),'ANNOTATION_REGION') for y in (0,20,40)]]
    return walls,pattern


def detect(items,seeds):
    si=SpatialIndex()
    for x in items:
        si.insert(x,(-1000,-1000,1000,1000))
    return SlabTracer(si).detect_slabs_from_texts(seeds,floor_name='TEST')


def test_striped_region_scopes_conflicting_heights_without_splitting_slab():
    walls,pattern=fixture()
    slabs=detect(walls+pattern,[dict(text='h=12',pos=(100,50)),dict(text='h=10',pos=(25,50))])
    assert len(slabs)==1
    assert slabs[0]['area']==20000
    assert slabs[0]['name']=='L1'
    region=slabs[0]['trace_diagnostics']['striped_regions'][0]
    assert Polygon(region['points']).area==5000
    assert region['height_cm']==10 and region['owner_height_cm']==12
    assert region['status']=='unknown' and region['bottom_delta_m'] is None
    assert region['level_m'] is None


def test_strokes_never_close_missing_structural_edge():
    walls,pattern=fixture()
    assert detect(walls[:-1]+pattern,[dict(text='h=12',pos=(100,50))])==[]


def test_dangling_beam_blocks_merged_region():
    walls,_=fixture()
    assert detect(walls+[line((80,0),(80,60))],[dict(text='h=12',pos=(100,50))])==[]


def test_pattern_requires_periodic_repetition_and_actual_delimiter():
    walls,pattern=fixture()
    assert striped_regions(pattern[1:],[__import__('shapely').geometry.LineString([x['start'],x['end']]) for x in walls])==[]
    pattern[-1]=line((0,45),(50,95),'ANNOTATION_REGION')
    assert detect(walls+pattern,[dict(text='h=12',pos=(100,50)),dict(text='h=10',pos=(25,50))])==[]


def test_reading_order_uses_rows_and_is_independent_of_entity_order():
    def slab(x,y):
        return dict(points=[(x,y),(x+100,y),(x+100,y+100),(x,y+100),(x,y)])
    left,right,below=slab(0,200),slab(150,210),slab(0,0)
    result=name_generated_slabs([below,right,left],'TIPO_TESTE')
    assert result==[left,right,below]
    assert [s['name'] for s in result]==['L1','L2','L3']


def test_micron_endpoint_gap_nodes_but_real_gap_stays_open():
    walls,_=fixture()
    walls[-1]['end']=(0,.00003)
    assert len(detect(walls,[dict(text='h=12',pos=(100,50))]))==1
    walls[-1]['end']=(0,1)
    assert detect(walls,[dict(text='h=12',pos=(100,50))])==[]


def test_serialized_slab_recognizes_stripes_from_dxf(tmp_path):
    import ezdxf
    from src.core.slab_steps import enrich_state
    doc=ezdxf.new()
    walls,pattern=fixture()
    for x in walls+pattern:
        doc.modelspace().add_line(x['start'],x['end'],dxfattribs={'layer':x['layer']})
    for text,pos in [('h=12',(100,50)),('h=10',(25,50))]:
        doc.modelspace().add_text(text,dxfattribs={'insert':pos})
    path=tmp_path/'drawing.dxf';doc.saveas(path)
    slab=dict(name='L1_TEST',points=[(0,0),(200,0),(200,100),(0,100),(0,0)])
    enrich_state(dict(slabs=[slab]),path)
    assert len(slab['slab_steps'])==1
    region=slab['slab_steps'][0]
    assert region['height_cm']==10 and region['owner_height_cm']==12
    assert region['status']=='unknown' and region['bottom_delta_m'] is None


def test_unmeasured_striped_region_never_gets_a_computed_bottom():
    from src.core.slab_steps import fill_region_levels
    walls,pattern=fixture()
    slab=detect(walls+pattern,[dict(text='h=12',pos=(100,50))])[0]
    region=slab['trace_diagnostics']['striped_regions'][0]
    fill_region_levels([region],{'principal':{'value':852},region['uid']:{'value':852.1}})
    assert region['height_cm'] is None
    assert region['bottom_m'] is None and region['bottom_delta_m'] is None
    assert region['status']=='unknown'


def test_connected_pillar_pieces_carve_the_inner_arm():
    si=SpatialIndex()
    for pts in [[(-19,0),(-19,67),(0,67),(0,0),(-19,0)],
                [(0,55),(50,55),(50,67),(0,67),(0,55)]]:
        si.insert(dict(points=pts,layer='PILLAR'),(-20,0,50,70))
    si.insert(dict(text='P12',pos=(50,10)),(45,5,55,15))
    slab=dict(points=[(0,0),(300,0),(300,170),(0,170),(0,0)])
    SlabTracer(si)._carve_boundary_pillar_intrusions([slab])
    assert Polygon(slab['points']).area==51000-600
    assert Polygon(slab['points']).intersection(Polygon([(0,55),(50,55),(50,67),(0,67)])).area==0


def test_section_near_pillar_label_never_carves_a_slab():
    si=SpatialIndex()
    for pts in [[(-19,0),(-19,67),(0,67),(0,0),(-19,0)],
                [(0,55),(50,55),(50,67),(0,67),(0,55)]]:
        si.insert(dict(points=pts,layer='LINHA-SEÇÃO'),(-20,0,50,70))
    si.insert(dict(text='P12',pos=(50,10)),(45,5,55,15))
    slab=dict(points=[(0,0),(300,0),(300,170),(0,170),(0,0)])
    SlabTracer(si)._carve_boundary_pillar_intrusions([slab])
    assert Polygon(slab['points']).area==51000


def test_block_height_callout_does_not_conflict_with_slab_height():
    walls,_=fixture()
    # Closed block occupies the lower-right corner, separately from the slab.
    walls += [line((150,0),(150,20)),line((150,20),(200,20))]
    leader=dict(points=[(95,45),(130,40),(150,20),(140,22),(150,20),(148,30)],layer='DIM')
    texts=[dict(text='h=12',pos=(60,60)),
           dict(text='h=45',pos=(95,40),height=5),
           dict(text='BL.1',pos=(95,48),height=5)]
    slabs=detect(walls+[leader],texts)
    assert len(slabs)==1 and slabs[0]['area']==19000
    assert slabs[0]['trace_diagnostics']['observed_thickness_cm']==12


def test_plain_polyline_does_not_scope_an_annotation_as_a_leader():
    from src.core.cad_object_recognition import thickness_references
    refs=thickness_references([dict(text='h=45',pos=(5,5)),dict(text='BL.1',pos=(5,10))],
                             [dict(points=[(5,5),(10,10),(30,0)])])
    assert refs[0][0]['pos']==(5,5)
    assert 'target_class' not in refs[0][0]
