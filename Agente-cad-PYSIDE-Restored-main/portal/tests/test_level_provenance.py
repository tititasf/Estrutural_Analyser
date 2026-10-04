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
