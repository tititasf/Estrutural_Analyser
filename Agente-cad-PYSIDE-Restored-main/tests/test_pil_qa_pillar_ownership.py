from src.core.pil_qa_pillar_ownership import foreign_named_contour


def binding(contour='pillar',dimensions=('number',)):
    return {'contour_handle':contour,'name_handles':['name'],
            'dimension_handles':list(dimensions)}


def test_original_name_and_numeric_section_bind_another_contour():
    labels=[{'handle':'name'}]
    assert foreign_named_contour('slab',labels,[binding()])
    assert not foreign_named_contour('pillar',labels,[binding()])


def test_no_unproved_or_competing_pillar_is_removed():
    labels=[{'handle':'name'}]
    assert not foreign_named_contour('slab',labels,[])
    assert not foreign_named_contour('slab',labels,[binding(dimensions=())])
    assert not foreign_named_contour('slab',labels,[binding(),binding('other')])
    assert not foreign_named_contour('slab',labels+[{'handle':'unknown'}],[binding()])
    assert not foreign_named_contour('slab',[],[binding()])
