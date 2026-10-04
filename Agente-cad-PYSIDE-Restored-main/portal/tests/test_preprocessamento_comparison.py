from portal.app.preprocessamento.sa_comparison import compare_tower


def test_comparacao_exige_torre_revisao_e_identidade_unica():
    scope = {'obra_id': 'a', 'pavimento_id': '14_PAV', 'recorte_id': 'tower-1',
             'source_revision': 'x' * 64}
    package = {'scope': scope, 'pillars': {'items': [
        {'item_id': 'tower-1:P1', 'display_name': 'P1', 'classification_raw': 'SEGUE'}]}}
    snapshot = {'source': dict(scope), 'items': [{'id': 'sa-p1', 'name': 'P1', 'classification': 'NASCE'}]}
    assert compare_tower(package, snapshot)['comparisons'][0]['status'] == 'unavailable_no_exact_link'
    links = {'tower-1:P1': {'sa_item_id': 'sa-p1', 'source_revision': scope['source_revision'],
                           'recorte_id': scope['recorte_id'], 'status': 'confirmed'}}
    assert compare_tower(package, snapshot, correspondence=links)['comparisons'][0]['status'] == 'divergent'
    snapshot['source']['recorte_id'] = 'tower-2'
    assert compare_tower(package, snapshot, correspondence=links)['status'] == 'unavailable'
    snapshot['source'] = scope
    snapshot['items'].append({'id': 'sa-p1', 'name': 'P1', 'classification': 'SEGUE'})
    assert compare_tower(package, snapshot, correspondence=links)['comparisons'][0]['status'] == 'unavailable_no_exact_link'
