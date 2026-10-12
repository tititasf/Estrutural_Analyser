"""Evidence-path explanation: traceable roots, no circular or duplicated support."""
from copy import deepcopy

from shapely.geometry import Polygon, mapping

from portal.app.preprocessamento import level_provenance as lp
from portal.app.preprocessamento.sa_levels import merge_sa_levels
from portal.app.preprocessamento.segment_levels import cut_matches_fund
from portal.tests.test_segment_level_correspondence import fixture


def facts(result):
    return lp.collect(result)


def scores(result):
    return {k: (f.get('value'), f.get('confidence_pct')) for k, f in facts(result).items()}


def test_named_section_wings_share_one_verified_cad_origin():
    root = dict(fact_id='left', value=537.86, unit='m', status='sa_evidence', confidence_pct=75,
                method='named_section_marker_and_plan_region', section_source_id='pre-src-v1:section',
                section_revision='a'*64, marker_handle='M', evidence_ids=['pre-src-v1:section','cad:M'],
                projection=mapping(Polygon([(0,0),(1,0),(1,1),(0,1)])),
                region_geometry=mapping(Polygon([(0,0),(1,0),(1,1),(0,1)])))
    right = dict(root, fact_id='right', independent_confirmations=[{'fact_id':'left'}])
    result = lp.explain(right, {'left':root,'right':right})
    assert result['primary_source']['origin_kind'] == 'cad_named_section_level'
    assert result['gates']['origem'] == 'pass'
    assert result['independent_origin_count'] == 1
    assert result['confirmations'] == []
    for field in ('section_source_id','section_revision','marker_handle','region_geometry','projection'):
        missing = dict(root); missing.pop(field)
        assert lp.origin_kind(missing) == 'sa_field_without_traced_root'
    assert lp.origin_kind(dict(root, status='conflict')) == 'sa_field_without_traced_root'
    assert lp.origin_kind(dict(root, evidence_ids=['cad:unrelated'])) == 'sa_field_without_traced_root'


def test_every_fact_is_explained_acyclic_and_never_raised_by_transfer():
    tower, c, _, _ = fixture()
    result = merge_sa_levels(tower, c)
    summary = result['evidence_provenance']
    assert summary['cycles'] == 0 and summary['support_increase_violations'] == 0
    explained = [f for f in facts(result).values() if f.get('status') != 'not_applicable']
    assert explained and all('support_explanation' in f for f in explained)
    for f in explained:
        e = f['support_explanation']
        assert e['meaning'] == 'suporte_de_evidencia_nao_probabilidade'
        assert e['calculation'][-1]['fact_id'] == f['fact_id']
        assert e['gates']['sem_ciclo'] == 'pass'


def test_lateral_range_traces_to_the_slab_cad_mark_through_fv():
    tower, c, _, _ = fixture()
    result = merge_sa_levels(tower, c)
    beam = result['items'][0]
    lateral = next(s for s in beam['segments'] if s['family'] == 'lateral_b_para')
    for row in lateral['level_ranges']:
        e = row['support_explanation']
        assert e['primary_source']['origin_kind'] in ('cad_direct_level', 'sa_field_without_traced_root')
        assert [s['fact_id'] for s in e['calculation']][-1] == row['fact_id']
        assert e['independent_origin_count'] == 1


def test_duplicated_lateral_sources_do_not_raise_support():
    tower, c, fund, side = fixture()
    base = scores(merge_sa_levels(deepcopy(tower), deepcopy(c)))
    c2 = deepcopy(c)
    c2['state']['segmentos']['lateral_a_para'] = [side(30, 0, 100)]
    c2['state']['segmentos']['lateral_a_passa'] = [side(31, 0, 100)]
    dup = scores(merge_sa_levels(deepcopy(tower), c2))
    for key, (value, pct) in base.items():
        if key in dup and dup[key][0] == value:
            assert dup[key][1] <= pct + 1e-9, key


def test_processing_order_does_not_change_levels_or_support():
    tower, c, _, _ = fixture()
    first = scores(merge_sa_levels(deepcopy(tower), deepcopy(c)))
    c2 = deepcopy(c)
    c2['state']['slabs'].reverse()
    c2['state']['segmentos']['fundo'].reverse()
    second = scores(merge_sa_levels(deepcopy(tower), c2))
    # Fact ids are positional; compare by physical identity instead.
    def physical(result):
        return sorted(repr((f.get('item_id'), f.get('field'), str(f.get('segment_id')), f.get('region_id'),
                            f.get('range_start'), f.get('face'), f.get('linked_item'),
                            f.get('value'), f.get('confidence_pct'))) for f in facts(result).values()
                      if not f['fact_id'].endswith(':independent_seed'))
    assert physical(merge_sa_levels(deepcopy(tower), deepcopy(c))) == physical(
        merge_sa_levels(deepcopy(tower), c2))
    assert len(first) == len(second)


def test_cycle_and_missing_source_fail_their_gates():
    a = dict(fact_id='a', value=1., unit='m', status='inferred', confidence_pct=50, source_fact_ids=['b'])
    b = dict(fact_id='b', value=1., unit='m', status='inferred', confidence_pct=50, source_fact_ids=['a'])
    m = dict(fact_id='m', value=1., unit='m', status='inferred', confidence_pct=50, source_fact_ids=['gone'])
    index = {f['fact_id']: f for f in (a, b, m)}
    assert lp.explain(a, index)['gates']['sem_ciclo'] == 'fail'
    assert lp.explain(m, index)['gates']['fontes_presentes'] == 'fail'


def test_same_root_agreement_is_not_an_independent_confirmation():
    root = dict(fact_id='mark', value=1., unit='m', status='sa_evidence', confidence_pct=95,
                method='cad_level_inside_slab', evidence_ids=['cad:AA'])
    other = dict(root, fact_id='mark-copy')  # same CAD handle seen by another class
    third = dict(root, fact_id='mark-b', evidence_ids=['cad:BB'])
    cuts = [dict(fact_id=f'cut{i}', value=1.03, unit='m', status='inferred', confidence_pct=85.5,
                 source_fact_ids=[s]) for i, s in enumerate(('mark', 'mark-copy', 'mark-b'))]
    fv = dict(fact_id='fv', value=1.03, unit='m', status='sa_evidence', confidence_pct=81.2,
              source_fact_ids=['cut0'], independent_confirmations=[
                  dict(fact_id='cut1'), dict(fact_id='cut2')])
    index = {f['fact_id']: f for f in (root, other, third, fv, *cuts)}
    e = lp.explain(fv, index)
    assert [c['fact_id'] for c in e['confirmations']] == ['cut2']
    assert e['support_pct'] == 81.2  # confirmation lists, never adds score
    assert e['gates']['concordancia'] == 'confirmed'


def test_self_confirmation_and_legacy_derivation_cycles_are_not_roots():
    for dependency in ('source_fact_ids', 'derived_from'):
        fact = dict(fact_id='self', value=1., unit='m', status='inferred', confidence_pct=90)
        fact[dependency] = ['self']
        explanation = lp.explain(fact, {'self': fact})
        assert explanation['gates']['sem_ciclo'] == 'fail'
        assert explanation['independent_origin_count'] == 0


def test_confirmation_cannot_reuse_any_primary_origin_or_a_cyclic_path():
    roots = [dict(fact_id=k, value=1., unit='m', status='sa_evidence', confidence_pct=95,
                  method='cad_level_inside_slab', evidence_ids=['cad:'+k]) for k in ('A', 'B')]
    fact = dict(fact_id='FV', value=1., unit='m', status='inferred', confidence_pct=80,
                source_fact_ids=['A', 'B'], independent_confirmations=[{'fact_id':'B'}, {'fact_id':'loop'}])
    loop = dict(fact_id='loop', value=1., unit='m', status='inferred', confidence_pct=80,
                source_fact_ids=['A', 'loop'])
    index = {f['fact_id']: f for f in [*roots, fact, loop]}
    assert lp.explain(fact, index)['confirmations'] == []
    assert lp.explain(fact, index)['support_pct'] == 80


def test_independent_origin_does_not_confirm_disagreeing_value_or_datum():
    own = dict(fact_id='own', value=852., unit='m', datum_id='tower:A',
               status='sa_evidence', confidence_pct=90, method='cad_level_inside_slab',
               evidence_ids=['cad:A'], independent_confirmations=[{'fact_id':'other'}])
    for changes in ({'value': 851.8}, {'datum_id': 'tower:B'}, {'unit': 'cm'}):
        other = dict(own, fact_id='other', evidence_ids=['cad:B'], independent_confirmations=[])
        other.update(changes)
        explanation = lp.explain(own, {'own': own, 'other': other})
        assert explanation['confirmations'] == []
        assert explanation['gates']['concordancia'] == 'conflict'
        assert explanation['confirmation_conflicts'][0]['fact_id'] == 'other'
        assert explanation['support_pct'] == 90


def test_compound_cad_origin_cannot_confirm_one_of_its_own_marks():
    fact = dict(fact_id='combined', value=852., unit='m', status='sa_evidence',
                confidence_pct=90, method='cad_level_inside_slab', evidence_ids=['cad:A', 'cad:B'],
                independent_confirmations=[{'fact_id': 'partial'}])
    partial = dict(fact, fact_id='partial', evidence_ids=['cad:B'], independent_confirmations=[])
    assert lp.explain(fact, {'combined':fact, 'partial':partial})['confirmations'] == []


def test_cut_is_associated_by_stem_section_not_by_contact():
    fund = Polygon([(0, 0), (300, 0), (300, 19), (0, 19)])
    stem = mapping(Polygon([(100, 0), (160, 0), (160, 19), (100, 19)]))
    assert cut_matches_fund(stem, fund, 60)
    assert not cut_matches_fund(stem, fund, 55)          # different depth
    wide = mapping(Polygon([(100, -5), (160, -5), (160, 30), (100, 30)]))
    assert cut_matches_fund(wide, fund, 60)              # clipped to the FV strip
    narrow = mapping(Polygon([(100, 0), (160, 0), (160, 12), (100, 12)]))
    assert not cut_matches_fund(narrow, fund, 60)        # another beam width
    assert not cut_matches_fund(stem, fund, None)


def test_cut_hop_is_a_traceable_fact():
    tower, c, _, _ = fixture()
    c['state']['slabs'][0]['cut_links'] = {'cut_view_geom': [dict(
        points=[[10, -5], [30, -5], [30, 12], [10, 12], [10, -5]], ficha=dict(own_dist_top=3))]}
    result = merge_sa_levels(tower, c)
    fv = next(f for f in result['items'][0]['levels'] if f['field'] == 'fundo' and f['segment_label'] == 1)
    assert fv['method'] == 'cut_geometry_on_fv'
    assert fv['cut_association'] == 'contact_only'  # no stem profile: weakest-of-all kept
    cut = next(f for f in result['cut_level_facts'] if f['fact_id'] in fv['source_fact_ids'])
    assert cut['field'] == 'cut_beam_reference' and cut['cut_id'] in fv['cut_ids']
    assert fv['support_explanation']['calculation'][0]['fact_id'] != cut['fact_id']
