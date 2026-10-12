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


def test_partial_slab_contact_certifies_only_the_facing_stretch():
    tower, c, _, side = fixture()
    c['state']['slabs'] = [c['state']['slabs'][0]]
    c['marks'] = [dict(value=100, pos=[25, -5], handle='A')]
    lateral = side(1, 0, 80, 100, None)
    lateral['level_source'] = 'lv_cell_estimado'
    c['state']['segmentos'] = {'lateral_b_passa': [lateral]}
    row = next(s for s in beam(merge_sa_levels(tower, c))['segments'] if s['family'] == 'lateral_b_passa')
    ranges = row['level_ranges']
    native = row['native_level_evidence']
    assert native['method'] == 'lv_cell_estimado' and native['status'] == 'estimated'
    assert row['level'] == 100 and row['status'] == 'estimated'
    assert row['level_source'] == 'lateral_spatial_level_ranges'
    assert row['confidence_pct'] <= 30
    assert len(ranges) == 2
    stretch, tail = ranges
    assert stretch['method'] == 'spatial_slab_region_reference'
    assert stretch['status'] == 'inferred' and stretch['value'] == 100
    assert stretch['range_start'] == 0 and 49 <= stretch['range_end'] <= 52
    assert stretch['confidence_pct'] > 30
    assert stretch['source_slabs'] == ['L1']
    assert 'slab_contact_reference_without_cut_offset' in stretch['warnings']
    assert tail['status'] == 'estimated' and tail['value'] == 100
    assert tail['method'] == 'lv_cell_estimado'
    assert tail['range_start'] == stretch['range_end'] and abs(tail['range_end'] - 80) < .2
    assert {r['fact_id'].rsplit(':', 1)[-1] for r in ranges} == {'0', '1'}


def test_corner_nick_under_ten_cm_stays_estimated():
    tower, c, _, side = fixture()
    c['state']['slabs'] = [c['state']['slabs'][0]]
    c['marks'] = [dict(value=100, pos=[25, -5], handle='A')]
    lateral = side(1, 47, 90, 100, None)
    lateral['level_source'] = 'lv_cell_estimado'
    c['state']['segmentos'] = {'lateral_b_passa': [lateral]}
    row = next(s for s in beam(merge_sa_levels(tower, c))['segments'] if s['family'] == 'lateral_b_passa')
    ranges = row['level_ranges']
    assert len(ranges) == 1
    assert ranges[0]['status'] == 'estimated' and ranges[0]['value'] == 100
    assert ranges[0]['method'] == 'lv_cell_estimado'
    assert row['level'] == 100 and row['status'] == 'estimated'


def _contact_row(**extra):
    row = dict(value=100, status='inferred', confidence_pct=30, method='lv_cell_slabs',
               warnings=['source_slab_level_not_uniquely_observed', 'missing_independent_level_evidence'],
               fact_id='row', evidence_ids=[], range_start=0, range_end=80, range_unit='cm', fv_segments=[])
    row.update(extra)
    return row


def _apply(ranges, end=80, region_end=50, source_value=100):
    from shapely.geometry import LineString, box
    from portal.app.preprocessamento.segment_levels import inherited, projected_coverage
    from portal.app.preprocessamento.slab_contact_levels import apply_uncovered_range_contacts
    line = LineString([(0, 0), (end, 0)])
    region = box(0, -10, region_end, 0)
    source = dict(value=source_value, status='sa_evidence', confidence_pct=95, fact_id='L1',
                  evidence_ids=['cad'], warnings=[], region_id='principal')
    return apply_uncovered_range_contacts(
        line, ranges, [('L1', region, source)], inherited, projected_coverage, 10)


def test_multipart_penalty_uses_the_single_region_the_stretch_faces():
    ranges = _apply([_contact_row()])
    assert len(ranges) == 2
    stretch, tail = ranges
    assert stretch['value'] == 100 and stretch['method'] == 'spatial_slab_region_reference'
    assert stretch['status'] == 'inferred' and stretch['confidence_pct'] > 30
    assert stretch['source_slabs'] == ['L1'] and stretch['region_ids'] == ['principal']
    assert tail['value'] == 100 and tail['method'] == 'lv_cell_slabs' and tail['confidence_pct'] == 30


def test_inferred_continuity_without_the_penalty_stays_whole():
    row = _contact_row(warnings=['level_continues_within_existing_lateral_segment'], confidence_pct=73.2,
                       method='same_beam_face_pillar_wall_continuity')
    ranges = _apply([row])
    assert ranges == [row]


def test_multipart_penalty_does_not_replace_a_different_altitude():
    ranges = _apply([_contact_row(value=101)], source_value=100)
    assert len(ranges) == 1 and ranges[0]['value'] == 101 and ranges[0]['method'] == 'lv_cell_slabs'


def test_geometric_reference_preserves_human_level():
    tower,c,fund,_=fixture()
    human=fund(1,0,50,103,None);human['level_evidence_fields']=['confirmed']
    human['level_source']='explicit_beam_or_side'
    c['state']['segmentos']={'fundo':[human]}
    fv=beam(merge_sa_levels(tower,c))['segments'][0]
    assert fv['level']==103 and fv['status']=='human_review'
