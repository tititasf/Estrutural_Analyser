from portal.tests.test_segment_level_correspondence import fixture, beam, regional_fixture
from portal.app.preprocessamento.sa_levels import merge_sa_levels


def test_geometry_refreshes_stale_name_and_estimate():
    tower,c,fund,side=fixture()
    stale=fund(1,50,100,98,'L1');stale['level_source']='nearest_levelled_slab'
    c['state']['segmentos']={'fundo':[stale],'lateral_a_para':[side(9,50,100,98,'L1')]}
    result=beam(merge_sa_levels(tower,c))
    fv,lv=result['segments']
    assert fv['level']==lv['level']==101
    assert fv['status']=='inferred'
    assert fv['native_level_evidence']['source_slabs']==['L2']
    assert fv['native_level_evidence']['spatial_coverage']==1
    assert fv['native_level_evidence']['source_fact_ids']
    assert lv['confidence_pct']<=fv['confidence_pct']<=95*.9


def test_regional_contact_does_not_borrow_scalar_over_unknown_hole():
    tower,c=regional_fixture(None)
    _,_,fund,_=fixture()
    stale=fund(1,30,70,98,'L1');stale['points']=[[30,30],[70,30],[70,40],[30,40],[30,30]]
    stale['level_source']='nearest_levelled_slab'
    c['state']['segmentos']={'fundo':[stale]}
    fv=beam(merge_sa_levels(tower,c))['segments'][0]
    assert fv['level']==98 and fv['status']=='estimated'


def test_known_inner_region_refreshes_weak_seed_using_own_level():
    tower,c=regional_fixture(99)
    _,_,fund,_=fixture()
    stale=fund(1,30,70,98,'L1');stale['points']=[[30,30],[70,30],[70,40],[30,40],[30,30]]
    stale['level_source']='nearest_levelled_slab'
    c['state']['segmentos']={'fundo':[stale]}
    fv=beam(merge_sa_levels(tower,c))['segments'][0]
    assert fv['level']==99
    assert fv['native_level_evidence']['region_ids']==['inner']


def test_endpoint_contact_does_not_fill_entire_segment():
    tower,c,fund,_=fixture()
    stale=fund(1,100,150,98,None);stale['level_source']='estimated_beam_level'
    c['state']['segmentos']={'fundo':[stale]}
    fv=beam(merge_sa_levels(tower,c))['segments'][0]
    assert fv['level']==98 and fv['status']=='estimated'


def test_geometric_reference_preserves_human_level():
    tower,c,fund,_=fixture()
    human=fund(1,0,50,103,None);human['level_evidence_fields']=['confirmed']
    human['level_source']='explicit_beam_or_side'
    c['state']['segmentos']={'fundo':[human]}
    fv=beam(merge_sa_levels(tower,c))['segments'][0]
    assert fv['level']==103 and fv['status']=='human_review'
