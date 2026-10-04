from math import cos, sin

import pytest

from src.core.lv_cut_inventory import collect_explicit_cuts, pair_sections, section_svg


def seg(uid, index, points, level=852.16, height=55):
    return dict(id=uid,index=index,points=points,width_cm=19,beam_height_cm=height,level=level)


def sides(a,b):
    return {'A':{'segments':a},'B':{'segments':b}}


@pytest.mark.parametrize('angle', [0, .6, 1.5707963268])
def test_pairing_is_spatial_reversed_and_groups_same_section(angle):
    def rotate(points):
        return [[x*cos(angle)-y*sin(angle),x*sin(angle)+y*cos(angle)] for x,y in points]
    a=[seg('a1',1,rotate([[0,0],[70,0]])),seg('a2',2,rotate([[70,0],[100,0]]))]
    b=[seg('b1',1,rotate([[100,19],[50,19]])),seg('b2',2,rotate([[50,19],[0,19]]))]
    cuts,report=pair_sections('V1','passa',sides(a,b))
    assert len(cuts)==1
    assert {(p['a_index'],p['b_index']) for p in cuts[0]['pairs']}=={(1,2),(1,1),(2,1)}
    assert sum(p['length_cm'] for p in cuts[0]['pairs'])==pytest.approx(100,abs=.002)
    assert not report['unpaired']
    assert '19 × 55' in section_svg(cuts[0])


def test_gap_and_remote_parallel_face_do_not_create_pairs():
    a=[seg('a1',1,[[0,0],[40,0]]),seg('a2',2,[[60,0],[100,0]])]
    b=[seg('b1',1,[[45,19],[55,19]]),seg('b2',2,[[0,500],[100,500]])]
    cuts,report=pair_sections('V1','para',sides(a,b))
    assert not cuts and len(report['unpaired'])==4


@pytest.mark.parametrize('policy,covered', [
    ({'classification': 'NASCE'}, 100),
    ({'ignore_in_beams': True}, 100),
    ({'classification': 'SEGUE'}, 80),
])
def test_section_support_exclusions_follow_sa_floor_policy(policy, covered):
    pillar = dict(points=[[40,0],[60,0],[60,19],[40,19]], **policy)
    cuts, report = pair_sections('V1', 'passa', sides(
        [seg('a',1,[[0,0],[100,0]])],
        [seg('b',1,[[100,19],[0,19]])]), pillars=[pillar])
    assert sum(p['length_cm'] for c in cuts for p in c['pairs']) == covered
    assert bool(report['pillar_exclusions']) == (covered < 100)


def test_partial_coverage_and_duplicate_pairs_are_reported():
    a=[seg('a',1,[[0,0],[100,0]])]
    b=[seg('b',1,[[70,19],[20,19]])]
    _,report=pair_sections('V1','passa',sides(a,b))
    assert report['coverage_gaps'][0]['length_cm']==50
    b.append(seg('b2',2,[[70,19],[20,19]]))
    _,report=pair_sections('V1','passa',sides(a,b))
    assert report['conflicts'][0]['overlap_cm']==50


def test_section_levels_and_dimensions_change_count_not_pair_index():
    a=[seg('a1',1,[[0,0],[50,0]]),seg('a2',2,[[50,0],[100,0]],852.19)]
    b=[seg('b1',1,[[100,19],[0,19]])]
    cuts,_=pair_sections('V1','passa',sides(a,b))
    assert len(cuts)==2
    a[1]['beam_height_cm']=60
    cuts,_=pair_sections('V1','passa',sides(a,b))
    assert cuts[1]['beam_height_cm'] is None
    assert section_svg(cuts[1]) is None


def test_slab_transition_splits_pair_then_equivalent_slabs_group():
    a=[seg('a1',1,[[0,0],[100,0]])]
    b=[seg('b1',1,[[100,19],[0,19]])]
    slabs=[dict(name='L1',height=12,nivel=852.16,points=[[0,0],[50,0],[50,-30],[0,-30]]),
           dict(name='L2',height=12,nivel=852.16,points=[[50,0],[100,0],[100,-30],[50,-30]])]
    cuts,_=pair_sections('V1','passa',sides(a,b),slabs)
    assert len(cuts)==1
    assert sum(p['length_cm'] for p in cuts[0]['pairs'])==pytest.approx(100,abs=.002)
    assert {name for p in cuts[0]['pairs'] for name in p['a_slabs']}=={'L1','L2'}
    slabs[1]['height']=14
    cuts,_=pair_sections('V1','passa',sides(a,b),slabs)
    assert len(cuts)==2


def test_missing_measurements_do_not_assert_equivalence_or_render():
    a=[seg('a1',1,[[0,0],[50,0]],None),seg('a2',2,[[50,0],[100,0]],None)]
    cuts,_=pair_sections('V1','passa',sides(a,[seg('b1',1,[[100,19],[0,19]])]))
    assert len(cuts)==2 and all(section_svg(c) is None for c in cuts)


def test_identical_section_at_different_absolute_elevation_groups():
    a=[seg('a1',1,[[0,0],[50,0]]),seg('a2',2,[[50,0],[100,0]],852.19)]
    b=[seg('b1',1,[[50,19],[0,19]]),seg('b2',2,[[100,19],[50,19]],852.19)]
    cuts,_=pair_sections('V1','passa',sides(a,b))
    assert len(cuts)==1 and len(cuts[0]['pairs'])==2
    assert [p['profiles']['A']['level'] for p in cuts[0]['pairs']] == [852.16, 852.19]
    assert cuts[0]['pairs'][1]['footprint'] == [[50.,0.],[100.,0.],[100.,19.],[50.,19.]]


def test_explicit_union_preserves_sa_assignment_ficha_and_preprocess_provenance():
    pts=[[0,0],[30,0],[30,55],[0,55],[0,0]]
    state=[dict(uid='sa-cut',beam_name='V1',pts=pts,status='Válido')]
    slabs=[dict(name='L1',links={'laje_visao_corte':{'cut_view_geom':[
        dict(id='raw-cut',points=pts,ficha={'beam_name':'V2','beam_height':55,'own_dist_top':0})]}})]
    pre=[dict(item_id='pre-cut',beam_id='V1',section_geometry={'points':list(reversed(pts))})]
    rows=collect_explicit_cuts(state,slabs,pre)
    assert len(rows)==1 and rows[0]['beam_name']=='V1'
    assert rows[0]['ficha']['own_dist_top']==0
    assert rows[0]['origins']==['sa','sa_links','preprocessamento']
    assert 'pre-cut' in rows[0]['evidence_ids']


def test_rejected_sa_geometry_is_not_resurrected_by_other_source():
    pts=[[0,0],[10,0],[10,20],[0,20]]
    rows=collect_explicit_cuts([dict(uid='bad',pts=pts,status='NÃO É VISÃO CORTE — Errada Apenas Visual')],
        preprocessing=[dict(item_id='pre',beam_id='V1',section_geometry={'points':pts})])
    assert rows==[]


def test_unlinked_preprocessing_label_remains_in_inventory_without_guess():
    rows=collect_explicit_cuts([],preprocessing=[dict(item_id='p1',raw_text='CORTE A-A',position=[10,20])])
    assert len(rows)==1 and not rows[0]['beam_name'] and not rows[0]['pts']

@pytest.mark.parametrize('source,expected', [('lv_cell_estimado',852.19),('lv_cell_slabs',852.19),('sa_beam_segment',852.12)])
def test_local_slab_replaces_only_borrowed_cell_level(source, expected):
    from src.core.lv_n3_cut_contract import build_cut_contract, CutContractError
    a=seg('a',1,[[0,0],[100,0]],852.12)
    a['level_source']=source
    b=seg('b',1,[[100,19],[0,19]],852.12)
    slabs=[dict(name='L1',height=13,nivel=852.19,points=[[0,0],[100,0],[100,-30],[0,-30]])]
    cuts,_=pair_sections('V1','passa',sides([a],[b]),slabs)
    assert cuts[0]['profiles']['A']['level']==expected
    assert a['level']==852.12
    if source in ('lv_cell_estimado', 'lv_cell_slabs'):
        contract=build_cut_contract(cuts[0])
        assert contract['slabs']['A'][0]['drop_cm']==0
        assert contract['slabs']['A'][0]['height_cm']==13
    else:
        with pytest.raises(CutContractError, match='laje fora'):
            build_cut_contract(cuts[0])
