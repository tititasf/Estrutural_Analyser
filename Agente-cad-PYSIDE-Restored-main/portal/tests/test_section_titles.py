from portal.app.preprocessamento.adapters.section_titles import associate_titles


def title(x=50, y=121, height=10):
    return {'position': [x, y], 'height': height, 'title_handle': 'A', 'title': 'CORTE 1-1'}


def test_header_just_outside_crop_is_linked_without_claiming_item():
    links = associate_titles([title()], [{'file': 'one.dxf', 'bbox': [0, 0, 100, 100]}])
    assert links[0]['candidate_files'] == ['one.dxf']
    assert links[0]['status'] == 'unique_island'
    assert links[0]['item_association_status'] == 'unresolved'


def test_nearby_islands_are_ambiguous_not_nearest_wins():
    links = associate_titles([title()], [{'file': 'one', 'bbox': [0, 0, 100, 100]},
                                        {'file': 'two', 'bbox': [0, 130, 100, 200]}])
    assert links[0]['status'] == 'ambiguous_islands'


def test_containing_island_owns_its_title():
    links = associate_titles([title()], [{'file': 'one', 'bbox': [0, 0, 100, 100]},
                                        {'file': 'two', 'bbox': [0, 110, 100, 200]}])
    assert links[0]['candidate_files'] == ['two']


def test_far_or_sideways_title_does_not_link():
    islands = [{'file': 'one', 'bbox': [0, 0, 100, 100]}]
    for t in [title(y=200), title(x=120), title(height=0)]:
        links = associate_titles([t], islands)
        assert not links or links[0]['status'] == 'no_island'


def test_real_source_link_preserves_geometry_and_revision_boundary(tmp_path):
    import hashlib
    import json
    from types import SimpleNamespace
    import ezdxf
    import pytest
    from portal.app.preprocessamento.sources import SourceKind
    from portal.app.preprocessamento.adapters.section_titles import enrich_section_titles
    raw = tmp_path / 'raw.dxf'
    doc = ezdxf.new()
    header = doc.modelspace().add_text('CORTE 1-1', dxfattribs={'insert': (50, 121), 'height': 10})
    doc.saveas(raw)
    original = raw.read_bytes()
    revision = hashlib.sha256(original).hexdigest()
    directory = tmp_path / 'crops'; directory.mkdir()
    (directory / 'islands.json').write_text(json.dumps({'source_sha256': revision,
        'islands': [{'file': 'one.dxf', 'bbox': [0, 0, 100, 100]}]}))
    source = SimpleNamespace(source_id='crop', relative_path='crops/one.dxf',
                             bruto_id='raw', kind=SourceKind.OTHER, revision='crop-revision')
    ref = {'relative_path': 'raw.dxf', 'revision': revision, 'source_id': 'raw', 'bruto_id': 'raw'}
    auxiliary = [{'source_id': 'crop', 'status': 'observed_unreviewed', 'texts': []}]
    enrich_section_titles(tmp_path, [source], ref, auxiliary)
    link = auxiliary[0]['section_title_links'][0]
    assert link['title_handle'] == header.dxf.handle and not link['title_present_in_crop']
    assert link['origin_revision'] == revision and link['crop_revision'] == 'crop-revision'
    assert link['manifest_revision'] and 'level' not in link
    assert raw.read_bytes() == original
    with pytest.raises(ValueError, match='revision_changed'):
        enrich_section_titles(tmp_path, [source], {**ref, 'revision': 'stale'}, auxiliary)
    (directory / 'islands.json').write_text(json.dumps({'source_sha256': 'stale', 'islands': []}))
    fresh = [{'source_id': 'crop'}]
    enrich_section_titles(tmp_path, [source], ref, fresh)
    assert 'section_title_links' not in fresh[0]
