from copy import deepcopy
from shapely.geometry import box
from portal.app.qa_fv_crossing_gap import crossing_gap_evidence, crossing_owner_evidence


def source_cross():
    texts=[dict(text='V1',local_position=(10,25),rotation=0,handle='N1'),
           dict(text='19/55',local_position=(100,25),rotation=0,handle='S1'),
           dict(text='V2',local_position=(195,40),rotation=90,handle='N2'),
           dict(text='19/55',local_position=(205,80),rotation=90,handle='S2')]
    strokes=[]
    for y in (0,19):
        strokes.extend([((0,y),(200,y),f'L{y}'),((219,y),(400,y),f'R{y}')])
    for x in (200,219):
        strokes.extend([((x,-81),(x,0),f'B{x}'),((x,19),(x,119),f'T{x}')])
    return texts,strokes


def owner(texts,strokes,**kwargs):
    gap=crossing_gap_evidence(200,219,(0,19),0,texts,strokes)
    assert gap
    return crossing_owner_evidence('V1',(0,19),0,texts,strokes,gap,**kwargs)


def test_equal_section_uses_independent_continuity_and_development_not_sa():
    texts,strokes=source_cross();before=deepcopy((texts,strokes))
    proof=owner(texts,strokes,solid_polygons=[],human_ownership_checked=True)
    assert proof['owner_status']=='proved' and proof['owner_name']=='V1'
    assert proof['own']['physical_components_cm']==[[0,400]]
    assert proof['transverse']['physical_components_cm']==[[-81,119]]
    assert proof['own']['continuity']==proof['transverse']['continuity']==1
    assert (texts,strokes)==before


def test_source_only_does_not_certify_without_solid_and_human_inventory():
    texts,strokes=source_cross()
    for kwargs in ({},{'solid_polygons':[]},{'human_ownership_checked':True}):
        assert owner(texts,strokes,**kwargs)['owner_status']!='proved'


def test_solid_interruption_changes_continuity_before_total_development():
    texts,strokes=source_cross()
    proof=owner(texts,strokes,solid_polygons=[box(50,0,60,19)],human_ownership_checked=True)
    assert proof['own']['development_cm']>proof['transverse']['development_cm']
    assert proof['own']['continuity']<proof['transverse']['continuity']
    assert proof['owner_name']=='V2'


def test_depth_precedes_longer_continuous_corridor():
    texts,strokes=source_cross();texts[-1]['text']='19/60'
    assert owner(texts,strokes,solid_polygons=[],human_ownership_checked=True)['owner_name']=='V2'


def test_competing_name_and_conflicting_depth_fail_closed():
    for extra in (dict(text='V3',local_position=(300,25),rotation=0,handle='N3'),
                  dict(text='19/60',local_position=(300,25),rotation=0,handle='S3')):
        texts,strokes=source_cross();texts.append(extra)
        assert owner(texts,strokes,solid_polygons=[],human_ownership_checked=True) is None


def test_arbitrary_wall_gap_cannot_become_continuity_bridge():
    texts,strokes=source_cross()
    # Removing an entire original transverse wall prevents even gap identity.
    strokes=[s for s in strokes if s[2]!='T219']
    assert crossing_gap_evidence(200,219,(0,19),0,texts,strokes) is None


def test_original_inventory_can_replace_human_reference_only_for_through_crossing():
    texts,strokes=source_cross()
    assert owner(texts,strokes,solid_polygons=[],source_inventory_checked=True)['owner_status']=='proved'
    # The arriving beam stops at the far face: equal depth is a T, not a
    # source-wide through crossing. D-90 must be resolved separately.
    strokes=[s for s in strokes if not s[2].startswith('B')]
    proof=owner(texts,strokes,solid_polygons=[],source_inventory_checked=True)
    assert proof is None or proof['owner_status']!='proved'


def test_disconnected_parallel_name_is_not_a_local_competitor():
    texts,strokes=source_cross()
    texts.extend([dict(text='V3',local_position=(610,25),rotation=0,handle='N3'),
                  dict(text='19/60',local_position=(680,25),rotation=0,handle='S3')])
    strokes.extend([((600,y),(750,y),f'X{y}') for y in (0,19)])
    proof=owner(texts,strokes,solid_polygons=[],source_inventory_checked=True)
    assert proof['owner_status']=='proved' and proof['owner_name']=='V1'
