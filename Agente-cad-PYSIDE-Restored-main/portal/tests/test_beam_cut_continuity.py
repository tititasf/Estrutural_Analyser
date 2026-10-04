from copy import deepcopy

from shapely.geometry import box, LineString, mapping

from portal.app.preprocessamento.beam_cut_continuity import propagate, scoped_cut_profile, fund_section
from portal.app.preprocessamento.segment_levels import inherited, sync


def fixture(reverse=False):
    funds = [dict(segment_id=str(n), height_cm=55) for n in range(3)]
    shapes = {str(n): box(n*100, 0, n*100+90, 14) for n in range(3)}
    shapes['side'] = LineString([(0, 0), (290, 0)][::-1] if reverse else [(0, 0), (290, 0)])
    records = {str(n): dict(fact_id=str(n), value=852.12, confidence_pct=80,
        evidence_ids=['cad:level'], warnings=[], status='sa_evidence',
        method='highest_touching_slab') for n in range(3)}
    records['1'].update(value=852.19, method='cut_geometry_on_fv',
                        cut_profile_geometry=mapping(box(110, 0, 165, 14)))
    return funds, [dict(segment_id='side')], records, shapes


def test_measured_cut_replaces_flush_slab_assumption_in_both_directions():
    for reverse in (False, True):
        funds, sides, records, shapes = fixture(reverse)
        propagate(funds, sides, records, shapes, [], inherited, sync)
        assert all(r['value'] == 852.19 for r in records.values())
        assert records['0']['source_fact_ids'] == ['1']
        assert records['0']['confidence_pct'] == 76
        assert records['0']['previous_level_evidence']['value'] == 852.12


def test_cut_dimensions_must_match_fund_and_slab_wing():
    funds, sides, records, shapes = fixture()
    records['1']['cut_profile_geometry'] = mapping(box(110, 0, 158, 14))
    before = deepcopy(records)
    propagate(funds, sides, records, shapes, [], inherited, sync)
    assert records == before
    cut = dict(points=[[0,0],[55,0],[55,14],[0,14],[0,0]],
               ficha=dict(own_slab_height='10'))
    assert scoped_cut_profile(cut, dict(fields=dict(laje_dim='h=12'))) is None
    assert scoped_cut_profile(cut, dict(fields=dict(laje_dim='h=10')))


def test_real_changes_human_decisions_and_paint_block_transfer():
    for blocker in ('cut', 'depth', 'width', 'human', 'paint', 'unreadable'):
        funds, sides, records, shapes = fixture()
        paints = []
        if blocker == 'cut': records['2'].update(method='cut_geometry_on_fv', value=852.22)
        if blocker == 'depth': funds[2]['height_cm'] = 60
        if blocker == 'width': shapes['2'] = box(200, 0, 290, 19)
        if blocker == 'human': records['2']['status'] = 'human_review'
        if blocker == 'paint': paints = [box(200, 0, 290, 14)]
        if blocker == 'unreadable': paints = None
        before = deepcopy(records)
        propagate(funds, sides, records, shapes, paints, inherited, sync)
        assert records == before, blocker


def test_unrelated_fund_is_not_changed_and_inferred_anchor_does_not_bootstrap():
    funds, sides, records, shapes = fixture()
    shapes['2'] = box(200, 100, 290, 114)
    propagate(funds, sides, records, shapes, [], inherited, sync)
    assert records['0']['value'] == 852.19 and records['2']['value'] == 852.12
    funds, sides, records, shapes = fixture()
    records['1']['method'] = 'cut_anchored_constant_beam_section'
    before = deepcopy(records)
    propagate(funds, sides, records, shapes, [], inherited, sync)
    assert records == before


def test_section_rejects_pillar_dimension_and_scopes_lateral_depth():
    fund = dict(points=[[100,0],[190,0],[190,14],[100,14],[100,0]], segment_label='2')
    side = dict(uid='side', points=[[0,0],[290,0]], details=dict(lv_cell=dict(sections=[
        dict(start=0,end=90,dim='14/60'), dict(start=100,end=190,dim='14/55')])))
    peers = [('lateral_a_para',side)]
    result = fund_section(fund, {'viga_fundo_seg_2_dim':'19/66'}, peers)
    assert result['height_cm'] == 55 and result['section_segment_ids'] == ['side']
    assert fund_section(fund, {'viga_fundo_seg_2_dim':'14/60'}, peers)['height_cm'] == 60
    side['details']['lv_cell']['sections'].append(dict(start=100,end=190,dim='14/60'))
    assert fund_section(fund, {}, peers) is None
    side['points'] = [[0,100],[290,100]]
    assert fund_section(fund, {}, peers) is None
