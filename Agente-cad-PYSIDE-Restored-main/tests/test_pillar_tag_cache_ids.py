import json

from portal.app import pillar_tag_cache as cache


def test_ids_aleatorios_de_vinculo_nao_entram_no_fingerprint():
    def row(uid):
        links = {'viga_a_seg_1_lajes': {'laje': [{'id': uid, 'text': 'L401'}]}}
        return ['b_1', json.dumps(links), 'V301']

    a = [cache._canonical_cell(c) for c in row('3f2b8c1e-0a4d-4e8f-9b1c-2d3e4f5a6b7c')]
    b = [cache._canonical_cell(c) for c in row('9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d')]
    assert a == b
    # Ids that are not uuid4 (row keys, names) still change the fingerprint.
    assert cache._without_random_ids({'id': 'b_1'}) == {'id': 'b_1'}
    assert cache._canonical_cell('{nao json') == '{nao json'
