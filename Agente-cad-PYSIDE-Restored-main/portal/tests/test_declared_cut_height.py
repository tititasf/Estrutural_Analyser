from copy import deepcopy

from shapely.geometry import box, mapping

from portal.app.preprocessamento.segment_levels import cut_matches_fund, inherited, sync
from portal.app.preprocessamento.beam_cut_continuity import propagate


def proof():
    return dict(source='declared_section_bound_to_physical_run',
        binding_method='own_label_two_source_walls_aligned_section',
        height_cm=55, width_cm=14, geometry_depth_cm=60, axis_deg=0,
        source_text=dict(handle='dimension', text='14/55', pos=[150,7], rotation=0),
        run_footprint=list(box(0,0,290,14).exterior.coords),
        stem_footprint=list(box(110,0,170,14).exterior.coords))


def test_declared_height_does_not_require_rescaling_original_cut():
    stem = mapping(box(110,0,170,14))
    fund = box(100,0,190,14)
    assert not cut_matches_fund(stem, fund, 55)
    assert cut_matches_fund(stem, fund, 55, proof())
    assert stem == mapping(box(110,0,170,14))


def test_numeric_authority_requires_same_text_dimensions_and_physical_stem():
    stem = mapping(box(110,0,170,14))
    fund = box(100,0,190,14)
    for mutation in ('height', 'width', 'depth', 'axis', 'remote_run', 'remote_stem', 'pillar', 'untraced'):
        evidence = proof()
        if mutation == 'height': evidence['height_cm'] = 66
        if mutation == 'width': evidence['width_cm'] = 19
        if mutation == 'depth': evidence['geometry_depth_cm'] = 53
        if mutation == 'axis': evidence['axis_deg'] = 90
        if mutation == 'remote_run': evidence['run_footprint'] = list(box(0,100,290,114).exterior.coords)
        if mutation == 'remote_stem': evidence['stem_footprint'] = list(box(210,0,270,14).exterior.coords)
        if mutation == 'pillar': evidence['source_text']['text'] = '24/66'
        if mutation == 'untraced': evidence['source_text']['handle'] = None
        assert not cut_matches_fund(stem, fund, 55, evidence), mutation
    assert not cut_matches_fund(mapping(box(110,0,170,12)), fund, 55, proof())


def test_numeric_proof_enables_continuity_but_preserves_change_and_fill_blocks():
    for blocker in (None, 'height', 'paint'):
        funds = [dict(segment_id=str(n), height_cm=55) for n in range(3)]
        shapes = {str(n): box(n*100,0,n*100+90,14) for n in range(3)}
        from shapely.geometry import LineString
        shapes['side'] = LineString([(0,0),(290,0)])
        records = {str(n): dict(fact_id=str(n), value=852.12, confidence_pct=80,
            evidence_ids=['cad:level'], warnings=[], status='sa_evidence',
            method='highest_touching_slab') for n in range(3)}
        records['1'].update(value=852.19, method='cut_geometry_on_fv',
            cut_profile_geometry=mapping(box(110,0,170,14)), cut_height_evidence=proof())
        if blocker == 'height': funds[2]['height_cm'] = 60
        paints = [box(200,0,290,14)] if blocker == 'paint' else []
        before = deepcopy(records)
        propagate(funds,[dict(segment_id='side')],records,shapes,paints,inherited,sync)
        if blocker:
            assert records == before
        else:
            assert all(record['value'] == 852.19 for record in records.values())
            assert records['0']['confidence_pct'] == 76
            assert records['0']['measured_depth_cm'] == 60
            assert records['0']['declared_height_cm'] == 55
