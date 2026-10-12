from src.core.slab_level_graph import resolve_cut_level_graph


def edge(a, b, delta):
    return {'source': a, 'target': b, 'delta_m': delta, 'evidence_id': a+b}


def test_chain_retains_root_confidence_and_simple_path():
    roots = {'a': {'value': 537.86, 'confidence': .65, 'evidence_ids': ['cad:1']}}
    result, rejected = resolve_cut_level_graph(roots, [edge('a','b',-.05), edge('b','c',.02)])
    assert not rejected
    assert abs(result['c']['value']-537.83) < 1e-8
    assert result['c']['confidence'] == .65
    assert result['c']['path'] == ['a','b','c']
    assert result['c']['root_source']['evidence_ids'] == ['cad:1']


def test_unanchored_consistent_cycle_cannot_self_confirm():
    result, rejected = resolve_cut_level_graph({}, [edge('a','b',.05),edge('b','c',-.05),edge('c','a',0)])
    assert not result and set(rejected.values()) == {'no_independent_root'}


def test_inconsistent_cycle_rejects_component_but_keeps_independent_one():
    roots = {'a': {'value': 100}, 'x': {'value': 200}}
    edges = [edge('a','b',.05),edge('b','c',-.05),edge('c','a',.02),edge('x','y',.03)]
    result, rejected = resolve_cut_level_graph(roots, edges)
    assert set(result) == {'y'}
    assert rejected == {'b':'inconsistent_cut_cycle','c':'inconsistent_cut_cycle'}


def test_disagreeing_roots_do_not_majority_vote():
    result, rejected = resolve_cut_level_graph({'a':{'value':100},'c':{'value':101}},
                                              [edge('a','b',0),edge('b','c',0)])
    assert not result and rejected['b'] == 'conflicting_independent_roots'


def test_order_and_direction_do_not_change_altitudes():
    roots = {'a': {'value': 100, 'confidence': 1}}
    one, _ = resolve_cut_level_graph(roots, [edge('a','b',.02),edge('b','c',-.05)])
    two, _ = resolve_cut_level_graph(roots, [edge('c','b',.05),edge('b','a',-.02)])
    assert {n:r['value'] for n,r in one.items()} == {n:r['value'] for n,r in two.items()}
    assert one['c']['confidence'] == .8


def test_canonical_consumer_requires_bound_root_and_preserves_known_fields():
    from types import SimpleNamespace
    from src.core.slab_level_graph import infer_measured_cut_network
    contour = [(0,0),(2,0),(2,2),(0,2)]
    def slab(name, level=None):
        return {'name':name, 'fields':{'laje_dim':'12', **({'laje_nivel':level} if level else {})},
                'cuts':[]}
    root, one, two = slab('root','100'), slab('one'), slab('two')
    root['preprocess_level_evidence'] = {'unit':'m','value':100,'evidence_ids':['cad:1']}
    root['level_inference'] = {'confidence_pct':75}
    for source, target in [(root, one), (one, two)]:
        points=[(x+len(target['name'])*10,y) for x,y in contour]
        for own, other, top in [(target,source,5),(source,target,0)]:
            own['cuts'].append({'points':points, 'ficha':{'side_a_laje_name':own['name'],
                'side_b_laje_name':other['name'],'own_dist_top':top,'neighbor_dist_top':5-top,
                'own_slab_height':12,'neigh_slab_height':12}})
    def source(s, **kw):
        return {'value':float(s['fields']['laje_nivel'])} if 'laje_nivel' in s['fields'] else None
    def apply(s, value, reason, sources):
        s['fields']['laje_nivel'] = value
        s['level_inference'] = {'status':'inferred','reason':reason,'sources':sources}
    runner = SimpleNamespace(_slab_level_source=source,_slab_cut_links=lambda s:s['cuts'],
                             _apply_inferred_slab_level=apply)
    assert infer_measured_cut_network(runner,[root,one,two]) == 2
    assert abs(two['fields']['laje_nivel']-99.90)<1e-8
    assert two['level_inference']['confidence'] == .75
    assert two['level_inference']['path'] == ['root','one','two']
    assert root['fields']['laje_nivel'] == '100'
    # A previous inferred field, even with a matching number, is not a root.
    root.pop('preprocess_level_evidence')
    one['fields'].pop('laje_nivel');two['fields'].pop('laje_nivel')
    assert infer_measured_cut_network(runner,[root,one,two]) == 0
    assert set(runner._sa_cut_level_graph_qa['rejected'].values()) == {'no_independent_root'}
