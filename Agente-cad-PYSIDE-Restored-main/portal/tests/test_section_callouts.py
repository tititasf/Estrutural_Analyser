import ezdxf
from portal.app.preprocessamento.adapters.section_callouts import triangles, pair_callouts


def arrow(handle, x, y):
    return {'handle': handle, 'tip': [x-10, y], 'base': [x, y],
            'direction': [-1, 0], 'size': 20}


def label(handle, x, y, name='A'):
    return {'handle': handle, 'position': [x-15, y], 'height': 10, 'label': name}


def test_unique_pair_has_geometry_without_level_or_item_claim():
    pair = pair_callouts([label('t1', 0, 0), label('t2', 0, 100)],
                         [arrow('a1', 0, 0), arrow('a2', 0, 100)])[0]
    assert pair['status'] == 'unique_plan_callout_pair'
    assert pair['bounded_axis'] == [[0, 0], [0, 100]]
    assert pair['numeric_authority'] == 'none'
    assert pair['item_association_status'] == 'unresolved'
    assert 'value' not in pair


def test_three_aligned_callouts_are_ambiguous():
    pairs = pair_callouts([label(str(y), 0, y) for y in (0, 100, 200)],
                          [arrow(str(y), 0, y) for y in (0, 100, 200)])
    assert pairs[0]['status'] == 'ambiguous_pairs'


def test_unaligned_or_opposite_arrows_are_not_a_pair():
    for b in [arrow('b', 20, 100), {**arrow('b', 0, 100), 'direction': [1, 0]}]:
        pairs = pair_callouts([label('t1', 0, 0), label('t2', *b['base'])], [arrow('a', 0, 0), b])
        assert pairs[0]['status'] == 'no_aligned_pair'


def test_plain_dimension_text_and_ambiguous_nearby_triangles_do_not_link():
    assert not pair_callouts([label('t', 0, 0)], [])
    assert not pair_callouts([label('t', 0, 0)], [arrow('a', 0, 0), arrow('b', 1, 0)])


def test_degenerate_solids_are_ignored_and_triangle_tip_is_geometric():
    doc = ezdxf.new()
    doc.modelspace().add_solid([(0, -10), (0, 10), (-10, 0), (-10, 0)])
    doc.modelspace().add_solid([(0, 0), (0, 0), (0, 0), (0, 0)])
    rows = triangles(doc)
    assert len(rows) == 1
    assert rows[0]['tip'] == [-10, 0] and rows[0]['direction'] == [-1, 0]


def test_real_documents_require_same_source_revision_and_handle_geometry(tmp_path):
    import hashlib
    from types import SimpleNamespace
    import pytest
    from portal.app.preprocessamento.sources import SourceKind
    from portal.app.preprocessamento.adapters.section_callouts import enrich_plan_callouts
    doc = ezdxf.new()
    for y in (0, 100):
        doc.modelspace().add_text('A', dxfattribs={'insert': (-15, y), 'height': 10})
        doc.modelspace().add_solid([(0, y-10), (0, y+10), (-10, y), (-10, y)])
    raw, plan = tmp_path/'raw.dxf', tmp_path/'plan.dxf'
    doc.saveas(raw); doc.saveas(plan)
    revision = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    ref = {'relative_path': 'raw.dxf', 'source_id': 'raw', 'revision': revision(raw), 'bruto_id': 'b'}
    source = SimpleNamespace(relative_path='plan.dxf', source_id='tower', revision=revision(plan),
                             bruto_id='b', kind=SourceKind.TOWER)
    auxiliary = lambda: [{'section_title_links': [{'title': 'CORTE A-A', 'title_handle': 'title'}]}]
    entries = auxiliary()
    enrich_plan_callouts(tmp_path, [source], ref, entries)
    assert entries[0]['plan_callout_links'][0]['status'] == 'unique_plan_callout_pair'
    assert entries[0]['plan_callout_links'][0]['origin_revision'] == ref['revision']
    duplicate = auxiliary() + auxiliary()
    enrich_plan_callouts(tmp_path, [source], ref, duplicate)
    assert all(e['plan_callout_links'][0]['status'] == 'ambiguous_section_titles' for e in duplicate)
    second = SimpleNamespace(**{**vars(source), 'source_id': 'second-tower'})
    multi = auxiliary()
    enrich_plan_callouts(tmp_path, [source, second], ref, multi)
    assert all(p['status'] == 'ambiguous_plan_towers' for p in multi[0]['plan_callout_links'])
    other = auxiliary()
    source.bruto_id = 'another-raw'
    enrich_plan_callouts(tmp_path, [source], ref, other)
    assert 'plan_callout_links' not in other[0]
    source.bruto_id = 'b'
    with pytest.raises(ValueError, match='raw_revision_changed'):
        enrich_plan_callouts(tmp_path, [source], {**ref, 'revision': 'stale'}, auxiliary())
    source.revision = 'stale'
    with pytest.raises(ValueError, match='tower_revision_changed'):
        enrich_plan_callouts(tmp_path, [source], ref, auxiliary())
    moved = ezdxf.readfile(plan)
    for entity in moved.modelspace().query('TEXT'):
        entity.dxf.insert += ezdxf.math.Vec3(50, 0, 0)
    moved.saveas(plan)
    source.revision = revision(plan)
    entries = auxiliary()
    enrich_plan_callouts(tmp_path, [source], ref, entries)
    assert 'plan_callout_links' not in entries[0]


def test_no_second_arrow_cannot_supply_section_authority(tmp_path):
    # Pair recognizer cannot pick an unmarked drawing simply by text proximity.
    doc = ezdxf.new()
    doc.modelspace().add_solid([(0, 0), (10, 0), (5, 8), (5, 8)])
    assert not pair_callouts([label('t1', 0, 0), label('t2', 0, 100)], triangles(doc))


def axis_candidates(items, status='unique_plan_callout_pair', source='tower', axis=None):
    from portal.app.preprocessamento.adapters.section_callouts import enrich_pillar_axis_candidates
    link = {'status': status, 'plan_source_id': source,
            'bounded_axis': axis or [[0, 0], [0, 100]], 'numeric_authority': 'none'}
    enrich_pillar_axis_candidates([{'plan_callout_links': [link]}],
                                 {'source_id': 'tower', 'items': items})
    return link


def footprint(geometry, name='pillar', status='linked'):
    return {'item_id': name, 'display_name': name, 'status': status,
            'source_entity_handles': ['wall'], 'geometry': geometry}


def test_axis_candidates_are_bounded_and_do_not_authorize_levels():
    polygon = lambda y: {'type': 'Polygon', 'coordinates': [[(-5,y),(5,y),(5,y+10),(-5,y+10),(-5,y)]]}
    link = axis_candidates([footprint(polygon(20)), footprint(polygon(120), 'outside'),
                            footprint(polygon(50), 'ambiguous', 'ambiguous')])
    candidates = link['pillar_axis_candidates']
    assert len(candidates) == 1
    assert candidates[0]['axis_intervals'] == [[.2,.3]]
    assert candidates[0]['numeric_authority'] == 'none'
    assert candidates[0]['section_identity_status'] == 'unresolved'
    assert 'value' not in candidates[0]


def test_native_circle_uses_exact_chord_and_tangency_is_not_a_cut():
    import pytest
    link = axis_candidates([footprint({'type':'Circle','center':[0,50],'radius':10}),
                            footprint({'type':'Circle','center':[10,70],'radius':10}, 'tangent')])
    assert len(link['pillar_axis_candidates']) == 1
    assert link['pillar_axis_candidates'][0]['axis_intervals'][0] == pytest.approx([.4,.6])


def test_axis_along_polygon_wall_does_not_establish_interior_cut():
    polygon = {'type':'Polygon','coordinates': [[(0,20),(10,20),(10,30),(0,30),(0,20)]]}
    assert axis_candidates([footprint(polygon)])['pillar_axis_candidates'] == []


def test_wrong_source_and_ambiguous_cut_cannot_associate_items():
    item = footprint({'type':'Circle','center':[0,50],'radius':10})
    assert 'pillar_axis_candidates' not in axis_candidates([item], source='other')
    assert 'pillar_axis_candidates' not in axis_candidates([item], status='ambiguous_section_titles')


def test_nonconvex_footprint_preserves_disconnected_intersections():
    # C-shaped footprint: the empty space between arms is not pillar material.
    polygon = {'type':'Polygon','coordinates': [[(-5,10),(5,10),(5,20),(-2,20),
                (-2,80),(5,80),(5,90),(-5,90),(-5,10)]]}
    intervals = axis_candidates([footprint(polygon)])['pillar_axis_candidates'][0]['axis_intervals']
    assert intervals == [[.1,.2],[.8,.9]]
