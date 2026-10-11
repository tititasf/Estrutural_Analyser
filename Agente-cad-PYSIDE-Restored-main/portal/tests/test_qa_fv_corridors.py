import math
from portal.app.qa_fv_corridors import measure_polygon


def fixture(points=None,angle=0):
    points=points or [(0,0),(200,0),(200,19),(0,19),(0,0)]
    r=math.radians(angle)
    def p(z):x,y=z;return(x*math.cos(r)-y*math.sin(r),x*math.sin(r)+y*math.cos(r))
    row=dict(beam_name='V1',segment_label='1',points=[p(z) for z in points])
    texts=[dict(text='V1',position=p((10,25)),rotation=angle,handle='N'),dict(text='19/55',position=p((100,25)),rotation=angle,handle='S')]
    strokes=[dict(a=p(a),b=p(b),handle=f'W{i}') for i,(a,b) in enumerate(zip(points,points[1:]))]
    return row,texts,strokes


def test_complete_rotated_corridor_sections_and_caps_are_independently_measured():
    for angle in (0,43,90):
        rows=measure_polygon(*fixture(angle=angle),'/fund/0')
        assert all(r['status']=='measured' for r in rows if r['guards']!=['inventario_segmentos'])
        assert any(r['guards']==['inventario_segmentos'] and r['status']=='uncertain' for r in rows)
        assert any(r.get('height_cm')==55 for r in rows)


def test_gap_remains_pending_despite_original_section_label():
    row,texts,strokes=fixture()
    strokes=strokes[1:]
    rows=measure_polygon(row,texts,strokes,'/fund/0')
    assert any(r['status']=='uncertain' and r['guards']==['identidade_contorno'] for r in rows)
    assert not any(r.get('height_cm')==55 for r in rows)


def test_real_sliver_is_not_removed_by_epsilon_or_box_replacement():
    points=[(0,0),(200,0),(200,18.99),(219,18.99),(219,19),(0,19),(0,0)]
    rows=measure_polygon(*fixture(points),'/fund/0')
    sliver=[r for r in rows if r.get('local_span_cm')==[200.0,219.0]]
    assert sliver
    assert any(r['status']=='uncertain' and r['guards']==['dimensoes'] for r in sliver)
    assert any(r.get('height_cm')==55 for r in rows)


def test_oblique_cap_does_not_block_proven_straight_section_or_get_bbox_approval():
    points=[(-6,0),(200,0),(200,19),(0,19),(-6,0)]
    rows=measure_polygon(*fixture(points),'/fund/0')
    assert any(r.get('height_cm')==55 for r in rows)
    assert any(r['aspect']=='extremo início' and r['status']=='uncertain' for r in rows)


def test_proven_oblique_boundary_keeps_support_and_section_pending():
    rows=measure_polygon(*fixture([(-6,0),(200,0),(200,19),(0,19),(-6,0)]),'/fund/0')
    proof=next(r for r in rows if 'original_boundary_proof' in r)
    assert proof['status']=='measured' and proof['guards']==['identidade_contorno']
    assert proof['original_boundary_proof']['caps_approved'] is False
    span=proof['local_span_cm']
    assert any(r['status']=='uncertain' and 'apoios_limites' in r['guards']
               and r.get('local_span_cm')==span for r in rows)
    assert not any(r.get('height_cm') for r in rows if r.get('local_span_cm')==span)


def test_missing_diagonal_source_wall_remains_pending():
    row,texts,strokes=fixture([(-6,0),(200,0),(200,19),(0,19),(-6,0)])
    rows=measure_polygon(row,texts,strokes[:-1],'/fund/0')
    proof=next(r for r in rows if 'original_boundary_proof' in r)
    assert proof['status']=='uncertain'


def test_wrong_rotated_section_and_missing_own_name_fail_closed():
    for failure in ('rotation','name'):
        row,texts,strokes=fixture(angle=43)
        if failure=='rotation':texts[1]['rotation']=90
        else:texts[0]['text']='V2'
        rows=measure_polygon(row,texts,strokes,'/fund/0')
        assert any(r['status']=='uncertain' for r in rows)
        assert not any(r.get('height_cm')==55 for r in rows)


def test_conflicting_aligned_depths_stay_pending_and_original_inputs_are_unchanged():
    from copy import deepcopy
    row,texts,strokes=fixture()
    texts.append(dict(text='19/60',position=(110,25),rotation=0,handle='S2'))
    before=deepcopy((row,texts,strokes))
    rows=measure_polygon(row,texts,strokes,'/fund/0')
    assert any(r['status']=='measured' and r['guards']==['identidade_contorno'] for r in rows)
    assert any(r['status']=='uncertain' and r['guards']==['dimensoes'] for r in rows)
    assert not any(r.get('height_cm') for r in rows)
    assert (row,texts,strokes)==before


def test_partial_cap_requires_absolute_eps_instead_of_percentage():
    row,texts,strokes=fixture()
    strokes[1]['b']=(200,18.9)  # 99.47% covered: still missing more than .05 cm.
    rows=measure_polygon(row,texts,strokes,'/fund/0')
    cap=next(r for r in rows if r['aspect']=='extremo fim')
    assert cap['status']=='uncertain'
    assert abs(cap['uncovered_cm'][0]-.1)<1e-9
    assert any(r.get('height_cm')==55 for r in rows)


def test_partial_long_wall_also_uses_absolute_uncovered_length():
    row,texts,strokes=fixture()
    strokes[0]['b']=(199.9,0)
    rows=measure_polygon(row,texts,strokes,'/fund/0')
    walls=next(r for r in rows if r['guards']==['identidade_contorno'])
    assert walls['status']=='uncertain'
    assert abs(max(walls['uncovered_cm'])-.1)<1e-9
    assert not any(r.get('height_cm') for r in rows)


def test_changed_branch_count_emits_guard_instead_of_silently_skipping(monkeypatch):
    from shapely.geometry import Polygon
    import portal.app.qa_fv_corridors as helper
    row,texts,strokes=fixture()
    # A true interior opening introduces two branches at the middle sample.
    # The current exterior-only partition cannot certify this topology.
    with_hole=Polygon(row['points'],holes=[[(80,5),(120,5),(120,14),(80,14)]])
    monkeypatch.setattr(helper.affinity,'rotate',lambda *args,**kwargs:with_hole)
    rows=measure_polygon(row,texts,strokes,'/fund/0')
    guard=next(r for r in rows if 'branch_counts' in r)
    assert guard['branch_counts']==[1,2,1]
    assert guard['status']=='uncertain'
    assert guard['guards']==['identidade_contorno','inventario_segmentos']
    assert not any(r.get('height_cm') for r in rows)


def test_only_explicit_own_height_is_compared_and_bbox_width_is_not():
    row,texts,strokes=fixture()
    row['width']='191.24'
    rows=measure_polygon(row,texts,strokes,'/fund/0')
    section=next(r for r in rows if r.get('height_cm')==55)
    assert section['errors']=={}
    assert 'declared_height_fields' not in section
    row['height_cm']=60
    rows=measure_polygon(row,texts,strokes,'/fund/0')
    section=next(r for r in rows if r.get('height_cm')==55)
    assert section['status']=='measured'
    assert section['errors']['dimensoes']
    row['height_cm']=55
    assert all(not r['errors'] for r in measure_polygon(row,texts,strokes,'/fund/0'))


def test_continuation_segment_takes_axis_from_collinear_far_label_only():
    for angle in (0,90):
        row,texts,strokes=fixture(angle=angle)
        r=math.radians(angle)
        far=lambda x,y:(x*math.cos(r)-y*math.sin(r),x*math.sin(r)+y*math.cos(r))
        texts[0]['position']=far(-400,25)
        rows=measure_polygon(row,texts,strokes,'/fund/0')
        assert not any(c['aspect']=='eixo local' for c in rows)
        texts[0]['position']=far(-400,80)
        rows=measure_polygon(row,texts,strokes,'/fund/0')
        assert any(c['aspect']=='eixo local' for c in rows)


def test_sub_eps_cap_slice_is_left_to_end_guards():
    rows=measure_polygon(*fixture([(0,0),(200,0),(200,19),(0.0175,19),(0,0)]),'/fund/0')
    assert not any('oblíquas' in r['aspect'] for r in rows)
    assert any(r.get('height_cm')==55 for r in rows)
