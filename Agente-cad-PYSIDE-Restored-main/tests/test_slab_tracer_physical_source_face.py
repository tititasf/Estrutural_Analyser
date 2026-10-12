from shapely.geometry import Point, Polygon
from src.core.spatial_index import SpatialIndex
from src.core.slab_tracer import SlabTracer


def insert(index,row):
    p=row.get('points') or [row['pos']]
    index.insert(row,(min(x[0] for x in p),min(x[1] for x in p),max(x[0] for x in p),max(x[1] for x in p)))


def fixture(close=True, different=False, beam_evidence=True, pillar_evidence=True):
    index=SpatialIndex()
    # Arbitrary numeric layer names; established source styling supplies edges.
    for points in [[(0,0),(390,0)],[(0,100),(390,100)],[(0,0),(0,100)]]:
        insert(index,dict(points=points,layer='701',aci=3,linetype='CONTINUOUS'))
    if beam_evidence:
        insert(index,dict(points=[(0,-14),(390,-14)],layer='701',aci=3))
        insert(index,dict(points=[(0,114),(390,114)],layer='701',aci=3))
        insert(index,dict(points=[(-14,0),(-14,100)],layer='701',aci=3))
        for name,pos,rotation in [('V3',(-6,40),90),('V4',(80,106),0)]:
            insert(index,dict(text=name,pos=pos,rotation=rotation,height=10,layer='labels'))
            insert(index,dict(text='14/55',pos=pos,rotation=rotation,height=10,layer='labels'))
        for x,name in [(80,'V1'),(300,'V2')]:
            insert(index,dict(text=name,pos=(x,-6),rotation=0,height=10,layer='labels'))
            insert(index,dict(text='14/55',pos=(x+10,-6),rotation=0,height=10,layer='labels'))
    if pillar_evidence:
        insert(index,dict(text='P1',pos=(415,50),height=10,layer='labels'))
    if close:
        insert(index,dict(points=[(390,0),(410,0),(410,100),(390,100),(390,0)],layer='845',aci=7))
    insert(index,dict(points=[(40,50),(200,50)],layer='906',aci=9))
    insert(index,dict(points=[(200,20),(230,20),(230,80),(200,80),(200,20)],layer='432',aci=8))
    for x,name in [(60,'L7'),(300,'L8' if different else 'L7')]:
        insert(index,dict(text=name,pos=(x,50),handle=str(x),layer='labels'))
    return SlabTracer(index)


def test_repeated_labels_inside_one_exact_source_face_without_dimension_split():
    tracer=fixture()
    left=tracer.trace_boundary((60,50),label_id='L7')
    right=tracer.trace_boundary((300,50),label_id='L7')
    assert left.equals(right) and left.area == 39000
    assert tracer.last_trace_diagnostics['outline_source']=='physical_source_face'


def test_missing_support_and_different_labels_are_not_invented_or_merged():
    assert fixture(close=False)._physical_source_face(Point(60,50),'L7') is None
    assert fixture(different=True)._physical_source_face(Point(60,50),'L7') is None


def test_green_style_without_original_beam_role_is_not_authority():
    assert fixture(beam_evidence=False)._physical_source_face(Point(60,50),'L7') is None


def test_closer_pillar_dimension_cannot_hide_source_beam_wall_pair():
    tracer=fixture()
    insert(tracer.spatial_index,dict(text='100/19',pos=(80,-6),rotation=0,
                                   height=10,layer='labels'))
    # The real bottom section lies farther along the same source beam.
    for row in tracer.spatial_index.items.values():
        if row.get('text')=='14/55' and row.get('pos')==(90,-6):
            row['pos']=(150,-6)
    assert tracer._physical_source_face(Point(60,50),'L7').area==39000


def test_contacted_green_section_or_frame_without_pillar_role_cannot_close():
    assert fixture(pillar_evidence=False)._physical_source_face(Point(60,50),'L7') is None


def test_in_place_source_mutation_invalidates_face_cache():
    tracer=fixture()
    assert tracer._physical_source_face(Point(60,50),'L7').area == 39000
    for row in tracer.spatial_index.items.values():
        if row.get('text') == 'P1':
            row['text']='DETAIL'
    assert tracer._physical_source_face(Point(60,50),'L7') is None


def test_unlabelled_green_cut_on_same_structural_layer_cannot_split_face():
    tracer=fixture()
    # Exploded artificial rectangle around the left label, same green layer.
    for pts in [[(40,20),(100,20)],[(100,20),(100,80)],
                [(100,80),(40,80)],[(40,80),(40,20)]]:
        insert(tracer.spatial_index,dict(points=pts,layer='701',aci=3))
    face=tracer._physical_source_face(Point(60,50),'L7')
    assert face.area==39000 and face.covers(Point(300,50))


def test_frame_borrowing_nearby_p_label_and_beam_endpoints_is_not_support():
    tracer=fixture(close=False)
    insert(tracer.spatial_index,dict(points=[(0,0),(390,0),(390,100),(0,100),(0,0)],
                                   layer='845',aci=3))
    # The frame contacts four beam endpoints and P1 lies only 25 cm away.
    assert tracer._physical_source_face(Point(60,50),'L7') is None


def test_detect_applies_exact_faces_after_heuristics_without_neighbor_pollution():
    tracer=fixture()
    rows=[r for r in tracer.spatial_index.items.values() if r.get('text')]
    observed=[]
    def mutate(slabs):
        observed.extend(s['method'] for s in slabs)
        for slab in slabs:
            slab['points']=[(0,0),(1,0),(1,1),(0,1),(0,0)]
            slab['area']=1
    tracer._carve_boundary_pillar_intrusions=mutate
    result=tracer.detect_slabs_from_texts(rows)
    assert 'physical_source_face' not in observed
    assert len(result)==2
    assert all(Polygon(s['points']).area==39000 and s['area']==39000
               and s['method']=='physical_source_face' for s in result)
