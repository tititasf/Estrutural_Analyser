"""NIV-LAJE-CAMADAS: slab level from slabs facing it across a beam, by layers."""
from copy import deepcopy

from portal.app.preprocessamento.segment_levels import geometry, inherited
from portal.app.preprocessamento.slab_level_layers import resolve


def box(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


# Target T in the middle; beams on three sides; neighbours A (top), B (right), C (bottom).
SLABS = {'T': box(0, 0, 100, 100), 'A': box(0, 119, 100, 219),
         'B': box(119, 0, 219, 100), 'C': box(0, -119, 100, -19)}
FUNDS = [box(0, 100, 100, 119), box(100, 0, 119, 100), box(0, -19, 100, 0)]


def slab_fact(name, value, status='sa_evidence', handle=None, pct=95, method='cad_level_inside_slab', sources=None):
    return dict(item_id=name, fact_id=name+':slab_level:0', field='slab_level', value=value, unit='m',
                status=status, method=method, confidence_pct=pct, confidence_components={}, warnings=[],
                evidence_ids=['cad:'+(handle or name)] if status != 'inferred' else ['sa'],
                source_fact_ids=sources or [])


def run(values, target_value=852.12, handles=None):
    handles = handles or {}
    slab_items = {'T': dict(item_id='T', display_name='T', item_class='slab', levels=[
        slab_fact('T', target_value, status='inferred', pct=55, method='normal_neighbor_level_consensus')])}
    for name, v in values.items():
        fact = slab_fact(name, v) if not isinstance(v, dict) else slab_fact(name, **v)
        if name in handles:
            fact['evidence_ids'] = ['cad:'+handles[name]]
        slab_items[name] = dict(item_id=name, display_name=name, item_class='slab', levels=[fact])
    items = list(slab_items.values()) + [dict(item_id='V%d' % k, item_class='beam', segments=[
        dict(family='fundo', points=p)]) for k, p in enumerate(FUNDS)]
    context = {'state': {'slabs': [dict(name=n, points=p) for n, p in SLABS.items() if n in slab_items]}}
    tower = {}
    resolve(slab_items, items, context, geometry, inherited, tower)
    return slab_items['T']['levels'][0], tower['slab_level_layers']


def test_unanimous_neighbors_layer2():
    t, rep = run({'A': 852.12, 'B': 852.12, 'C': 852.12})
    assert t['method'] == 'slab_neighbor_continuity_without_step_cut'
    assert t['value'] == 852.12 and t['confidence_pct'] == 85      # 95 x .95 capped at 85
    assert t['level_basis'] == 'owner_convention' and set(t['source_fact_ids']) == {
        'A:slab_level:0', 'B:slab_level:0', 'C:slab_level:0'}


def test_majority_vote_layer4_scaled_by_agreement():
    t, rep = run({'A': 852.12, 'B': 852.12, 'C': 852.19})
    assert t['method'] == 'slab_neighbor_majority_vote'
    assert t['confidence_pct'] == round(95*.95*2/3, 1) <= 75
    assert 'neighbor_levels_disagree_majority_vote' in t['warnings']


def test_tie_abstains():
    t, rep = run({'A': 852.12, 'C': 852.19})
    assert t['method'] == 'normal_neighbor_level_consensus' and rep['not_applied'][0]['reason'] == 'tie'


def test_same_cad_origin_is_one_vote():
    # A and B carry the same CAD mark: one origin, so 852.19 (C) ties it.
    t, rep = run({'A': 852.12, 'B': 852.12, 'C': 852.19}, handles={'A': 'h1', 'B': 'h1'})
    assert t['method'] == 'normal_neighbor_level_consensus' and rep['not_applied'][0]['reason'] == 'tie'


def test_inferred_or_self_derived_neighbors_do_not_vote():
    inferred = dict(value=852.19, status='inferred', pct=55, method='normal_neighbor_level_consensus')
    self_derived = dict(value=852.19, status='sa_evidence', method='scoped_cut_wing_relative_delta_cm',
                        sources=['T:slab_level:0'])
    t, rep = run({'A': 852.12, 'B': inferred, 'C': self_derived})
    assert t['method'] == 'slab_neighbor_continuity_without_step_cut'
    assert t['source_fact_ids'] == ['A:slab_level:0']


def test_layer_value_differing_from_sa_is_reported_not_applied():
    t, rep = run({'A': 852.19, 'B': 852.19, 'C': 852.19})
    assert t['value'] == 852.12 and t['method'] == 'normal_neighbor_level_consensus'
    assert rep['not_applied'][0]['reason'] == 'differs_from_sa_value'


def test_narrow_fund_inside_corridor_still_associates(monkeypatch):
    # FV narrower than the gap (drawn at the beam axis): still the beam between them.
    monkeypatch.setitem(globals(), 'FUNDS', [box(0, 104, 100, 115)])
    t, rep = run({'A': 852.12})
    assert t['method'] == 'slab_neighbor_continuity_without_step_cut'


def test_diagonal_across_beam_crossing_is_not_a_neighbor():
    from shapely.geometry import Polygon
    from portal.app.preprocessamento.slab_level_layers import _across_beam
    funds = [('V0', Polygon(FUNDS[0])), ('V1', Polygon(FUNDS[1]))]
    assert _across_beam(Polygon(SLABS['A']), Polygon(SLABS['B']), funds) is None


def test_proven_step_line_withholds_votes(monkeypatch):
    # D/E (own CAD levels) differ across the top beam: that beam carries no continuity.
    monkeypatch.setitem(globals(), 'SLABS', {**SLABS, 'D': box(-120, 0, -20, 100), 'E': box(-120, 119, -20, 219)})
    monkeypatch.setitem(globals(), 'FUNDS', [box(-120, 100, 100, 119)] + FUNDS[1:])
    t, rep = run({'A': 852.19, 'B': 852.12, 'C': 852.12, 'D': 852.12, 'E': 852.19})
    assert t['method'] == 'slab_neighbor_continuity_without_step_cut' and t['confidence_pct'] == 85
    assert set(t['source_fact_ids']) == {'B:slab_level:0', 'C:slab_level:0'}
    assert rep['proven_step_lines']['V0'] and rep['applied'][0]['withheld_votes'][0]['slab'] == 'A'


def test_no_beam_in_corridor_no_vote(monkeypatch):
    monkeypatch.setitem(globals(), 'FUNDS', [])
    t, rep = run({'A': 852.12, 'B': 852.12})
    assert t['method'] == 'normal_neighbor_level_consensus' and not rep['applied']


def region_fact(name, rid, value, shape_box, status='sa_evidence', handle=None):
    from shapely.geometry import Polygon, mapping
    return dict(item_id=name, fact_id=name+':region:'+rid, field='slab_region_level', region_id=rid,
                region_geometry=mapping(Polygon(shape_box)), value=value, unit='m', status=status,
                method='cad_level_inside_slab', confidence_pct=95, warnings=[],
                evidence_ids=['cad:'+(handle or name+rid)], source_fact_ids=[])


def run_stepped(b_step_value=852.16, a_value=852.19):
    """T and B stepped at their top corners (like L414 | L413); A plain above T."""
    slabs = {'T': box(0, 0, 100, 100), 'B': box(119, 0, 219, 100), 'A': box(0, 119, 100, 219)}
    steps = {'T': box(0, 60, 40, 100), 'B': box(179, 60, 219, 100)}
    funds = [box(100, 0, 119, 100), box(0, 100, 100, 119)]
    b_principal = None
    slab_items = {
        'T': dict(item_id='T', display_name='T', item_class='slab', levels=[
            dict(item_id='T', fact_id='T:slab_level:0', field='slab_level', value=None, status='unknown',
                 confidence_pct=0, evidence_ids=[], warnings=[])]),
        'B': dict(item_id='B', display_name='B', item_class='slab', levels=[
            slab_fact('B', b_step_value), region_fact('B', 'sB', b_step_value, steps['B'])]),
        'A': dict(item_id='A', display_name='A', item_class='slab', levels=[slab_fact('A', a_value)]),
    }
    items = list(slab_items.values()) + [dict(item_id='V%d' % k, item_class='beam', segments=[
        dict(family='fundo', points=p)]) for k, p in enumerate(funds)]
    context = {'state': {'slabs': [
        dict(name='T', points=slabs['T'], slab_steps=[dict(uid='sT', points=steps['T'])]),
        dict(name='B', points=slabs['B'], slab_steps=[dict(uid='sB', points=steps['B'])]),
        dict(name='A', points=slabs['A'])]}}
    tower = {}
    resolve(slab_items, items, context, geometry, inherited, tower)
    regions = {f['region_id']: f for f in slab_items['T']['levels'] if f['field'] == 'slab_region_level'}
    return slab_items['T']['levels'][0], regions, tower['slab_level_layers']


def test_step_region_never_votes_for_the_rest_of_the_slab():
    # B's beam contact runs mostly along B's principal (no level): no vote from B.
    t, regions, rep = run_stepped()
    assert all(v['slab'] != 'B' for r in rep['applied'] for v in r['votes'])
    assert t['value'] == 852.19 and set(t['source_fact_ids']) == {'A:slab_level:0'}


def test_regions_without_level_are_voted_by_the_beams_they_face():
    t, regions, rep = run_stepped()
    # T's principal faces A along x 40..100; T's step faces A along x 0..40.
    assert regions['principal']['value'] == 852.19
    assert regions['principal']['level_basis'] == 'owner_convention'
    assert regions['principal']['status'] == 'inferred'
    # The step region of T does not face B (B is across the principal).
    assert all(v['slab'] == 'A' for v in regions['sT']['neighbor_votes'])
