from portal.app.preprocessamento.adapters.auxiliary import semantic_roles


def labels(scale=1, offset=(0, 0)):
    return [{'text': name, 'handle': str(i), 'height': height*scale,
             'position': [offset[0]+x*scale, offset[1]+y*scale]}
            for i, (name, x, y, height) in enumerate([
                ('CONVENÇÕES :', 0, 100, 20), ('NASCE', 40, 50, 12),
                ('SEGUE', 200, 50, 12), ('MORRE', 360, 50, 12)])]


def test_generic_legend_is_scoped_candidate_not_classification():
    for scale in (.01, 1, 100):
        roles = semantic_roles(labels(scale, (1000, -2000)))
        assert len(roles) == 1
        assert roles[0]['role'] == 'pillar_legend_candidate'
        assert roles[0]['label_handles'] == ['1', '2', '3']
        assert roles[0]['classification_authority'] == 'none'
        assert roles[0]['symbol_association_status'] == 'unresolved'


def test_partial_distant_duplicate_or_unscaled_terms_do_not_make_legend():
    data = labels()
    assert semantic_roles(data[:-1]) == []
    data[-1]['position'] = [1000, 0]
    assert semantic_roles(data) == []
    data = labels()
    assert semantic_roles(data + [dict(data[1], handle='duplicate')]) == []
    data[0]['height'] = 0
    assert semantic_roles(data) == []
