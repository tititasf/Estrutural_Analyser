from copy import deepcopy
from portal.tests.test_preprocessamento_sa_levels import fixture
from portal.app.preprocessamento.sa_levels import merge_sa_levels
from portal.app.preprocessamento.canonical_inventory import coverage


def test_unlabelled_slab_collected_without_inventing_level():
    tower, context = fixture()
    tower['items'] = [i for i in tower['items'] if i['item_class'] != 'slab']
    context['marks'] = []
    tower['reference'] = {'unit': 'm'}
    result = merge_sa_levels(tower, context)
    slab = next(i for i in result['items'] if i['item_class'] == 'slab')
    assert slab['geometry']['points'] == context['state']['slabs'][0]['points']
    assert slab['levels'][0]['value'] is None
    assert slab['levels'][0]['status'] == 'unknown'
    assert coverage(result['items']) == {'pillars': 1, 'slabs': 1, 'beams': 1}
    assert merge_sa_levels(result, context)['items'][-1]['item_id'] == slab['item_id']
    context['floor'] = 'other-floor'
    other = next(i for i in merge_sa_levels(tower, context)['items'] if i['item_class'] == 'slab')
    assert other['item_id'] != slab['item_id']


def test_repeated_survey_labels_retained_but_not_counted_as_geometry():
    tower, context = fixture()
    duplicate = deepcopy(tower['items'][2]); duplicate['item_id'] = 'other-label'
    tower['items'].append(duplicate)
    context['state']['pilares'][0]['classification'] = 'INDETERMINADO'
    tower['reference'] = {'unit': 'm'}
    result = merge_sa_levels(tower, context)
    assert len(result['items']) == 4
    assert coverage(result['items'])['pillars'] == 1
    assert all(f['status'] == 'unknown' for f in result['items'][2]['levels'])
    assert result['items'][3]['levels'] == []


def test_zero_contained_level_on_implicit_slab_preserved():
    tower, context = fixture()
    tower['items'] = []
    context['marks'][0]['value'] = 0
    result = merge_sa_levels(tower, context)
    slab = next(i for i in result['items'] if i['item_class'] == 'slab')
    assert slab['levels'][0]['value'] == 0
    assert slab['levels'][0]['method'] == 'cad_level_inside_slab'
