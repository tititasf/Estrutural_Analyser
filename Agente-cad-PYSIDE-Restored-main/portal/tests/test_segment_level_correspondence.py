from copy import deepcopy

from portal.app.preprocessamento.sa_levels import merge_sa_levels


def fixture():
    def fund(label, start, end, level, slab):
        return dict(uid='fv'+str(label),beam_name='V1',segment_label=label,
                    points=[[start,0],[end,0],[end,10],[start,10],[start,0]],
                    level=level,level_source='highest_touching_slab',level_slabs=[slab] if slab else [])
    def side(label, start, end, level=100, slab='L1'):
        return dict(uid='lv'+str(label),beam_name='V1',segment_label=label,
                    points=[[start,0],[end,0]],level=level,
                    level_source='lv_cell_slabs',level_slabs=[slab] if slab else [])
    items=[dict(item_id=n,display_name=n,item_class=c,levels=[],segments=[])
           for n,c in [('V1','beam'),('L1','slab'),('L2','slab'),('P1','pillar')]]
    context=dict(evidence_id='collection',marks=[
        dict(value=100,pos=[25,-5],handle='A'),dict(value=101,pos=[75,-5],handle='B')],
        state=dict(slabs=[dict(name='L1',nivel=100,points=[[0,-10],[50,-10],[50,0],[0,0],[0,-10]]),
                          dict(name='L2',nivel=101,points=[[50,-10],[100,-10],[100,0],[50,0],[50,-10]])],
                   pilares=[dict(name='P1',classification='CONTINUA',points=[[0,10],[10,10],[10,20],[0,20],[0,10]])],
                   segmentos={'fundo':[fund(1,0,50,100,'L1'),fund(2,50,100,101,'L2')],
                               'lateral_b_para':[side(17,100,0)]}),tables={})
    return dict(reference=dict(top=101,base=97,datum_id='same-floor'),items=items),context,fund,side


def beam(result):
    return result['items'][0]


def test_reversed_side_number_and_distinct_counts_match_space_not_index():
    tower,c,_,_=fixture()
    result=beam(merge_sa_levels(tower,c))
    lateral=next(s for s in result['segments'] if s['family']=='lateral_b_para')
    ranges=lateral['level_ranges']
    assert {r['value'] for r in ranges}=={100,101}
    assert ranges[0]['value']==101  # B runs in the opposite direction
    assert ranges[-1]['value']==100
    assert lateral['level'] is None  # no fake single level / no average
    assert {str(v) for r in ranges for v in r.get('fv_segments',[])}=={'1','2'}


def test_missing_fv_uses_full_spatial_lv_independent_support_once():
    tower,c,fund,side=fixture()
    c['state']['segmentos']={'fundo':[fund(1,0,50,None,None)],
                            'lateral_a_para':[side(9,0,50)],'lateral_a_passa':[side(10,0,50)]}
    result=beam(merge_sa_levels(tower,c))
    fv=result['segments'][0]
    assert fv['level']==100
    assert fv['level_source']=='lv_independent_evidence_fills_fv'
    assert fv['confidence_pct'] < result['segments'][1]['native_level_evidence']['confidence_pct']
    assert result['segments'][1]['confidence_pct'] < fv['confidence_pct']
    assert fv['native_level_evidence']['value'] is None


def test_para_passa_duplicates_never_inflate_coverage_or_confidence():
    tower,c,fund,side=fixture()
    c['state']['segmentos']={'fundo':[fund(1,0,100,None,None)],
                            'lateral_a_para':[side(9,0,30)],'lateral_a_passa':[side(10,0,30)]}
    result=beam(merge_sa_levels(tower,c))
    assert result['segments'][0]['level'] is None


def test_default_does_not_suppress_stronger_independent_lateral_support(monkeypatch):
    from portal.app.preprocessamento import standard_beam_level
    def weak_convention(geom, native, *args):
        result=deepcopy(native)
        result.update(method='standard_beam_top_principal_slab', value=100,
                      confidence_pct=60, status='inferred')
        return result
    monkeypatch.setattr(standard_beam_level, 'level', weak_convention)
    tower,c,fund,side=fixture()
    c['state']['segmentos']={'fundo':[fund(1,0,50,None,None)],
                            'lateral_a_para':[side(9,0,50)]}
    fv=beam(merge_sa_levels(tower,c))['segments'][0]
    assert fv['level']==100
    assert fv['level_source']=='lv_independent_evidence_fills_fv'
    assert fv['confidence_pct']>60


def test_every_fact_and_segment_has_score_and_calculation():
    tower,c,_,_=fixture()
    result=merge_sa_levels(tower,c)
    for item in result['items']:
        for fact in item['levels']:
            assert 0 <= fact['confidence_pct'] <= 100
            assert fact['confidence_components']
        for seg in item.get('segments',[]):
            assert 0 <= seg['confidence_pct'] <= 100
            assert all(r['confidence_pct']<=100 for r in seg.get('level_ranges',[]))


def test_pillar_top_is_highest_actual_face_contact_not_floor_top():
    tower,c,_,_=fixture()
    tower['reference']['top']=110
    result=merge_sa_levels(tower,c)
    top=next(f for f in result['items'][-1]['levels'] if f['field']=='top')
    assert top['value']==100
    assert top['faces']==['A']  # horizontal pillar: bottom long face
    assert top['method']=='highest_touching_face_level'
    assert top['confidence_pct']<95


def test_cut_footprint_and_slab_offset_determine_fv_not_wrong_beam_name():
    tower,c,_,_=fixture()
    c['state']['slabs'][0]['cut_links']={'cut_view_geom':[dict(
        points=[[20,-2],[30,-2],[30,12],[20,12],[20,-2]],
        ficha=dict(beam_name='HALLUCINATED',own_dist_top=7))]}
    result=beam(merge_sa_levels(tower,c))
    first=next(s for s in result['segments'] if s['segment_id']=='fv1')
    assert first['level']==100.07
    assert first['level_source']=='cut_geometry_on_fv'
    assert first['confidence_pct']<=95*.9*.95


def test_contradictory_cuts_not_averaged_or_sent_to_side():
    tower,c,_,_=fixture()
    cut=dict(points=[[20,-2],[30,-2],[30,12],[20,12],[20,-2]],ficha=dict(own_dist_top=7))
    other=deepcopy(cut);other['points']=[[35,-2],[40,-2],[40,12],[35,12],[35,-2]];other['ficha']['own_dist_top']=9
    c['state']['slabs'][0]['cut_links']={'cut_view_geom':[cut,other]}
    result=beam(merge_sa_levels(tower,c))
    fv=next(s for s in result['segments'] if s['segment_id']=='fv1')
    assert fv['level'] is None and fv['status']=='conflict'
    assert fv['confidence_pct']==0
    lateral=next(s for s in result['segments'] if s['family']=='lateral_b_para')
    assert any(r['status']=='conflict' for r in lateral['level_ranges'])


def test_no_evidence_cannot_bootstrap_between_fv_and_lv():
    tower,c,fund,side=fixture()
    lv=side(3,0,50,None,None)
    c['state']['segmentos']={'fundo':[fund(1,0,50,None,None)],'lateral_a_para':[lv]}
    result=beam(merge_sa_levels(tower,c))
    assert all(s['level'] is None and s['confidence_pct']==0 for s in result['segments'])


def test_broken_section_cannot_create_false_absolute_beam_offset(tmp_path):
    import ezdxf
    tower,c,_,_=fixture()
    doc=ezdxf.new()
    doc.modelspace().add_line((18,4),(32,6),dxfattribs={'color':1})
    doc.modelspace().add_line((18,7),(32,9),dxfattribs={'color':1})
    path=tmp_path/'broken.dxf';doc.saveas(path)
    c['tower_path']=str(path)
    c['state']['slabs'][0]['cut_links']={'cut_view_geom':[dict(
        points=[[20,-2],[30,-2],[30,12],[20,12],[20,-2]],ficha=dict(own_dist_top=72.1))]}
    result=merge_sa_levels(tower,c)
    assert next(s for s in beam(result)['segments'] if s['segment_id']=='fv1')['level']==100
    assert result['rejected_cut_level_evidence'][0]['reason']=='shortened_section_break'


def test_human_segment_level_is_preserved_even_when_cut_disagrees():
    tower,c,_,_=fixture()
    c['state']['segmentos']['fundo'][0].update(level=103,level_source='explicit_beam_or_side',
        level_slabs=[],level_evidence_fields=['human_level_field'])
    c['state']['slabs'][0]['cut_links']={'cut_view_geom':[dict(
        points=[[20,-2],[30,-2],[30,12],[20,12],[20,-2]],ficha=dict(own_dist_top=7))]}
    first=beam(merge_sa_levels(tower,c))['segments'][0]
    assert first['level']==103 and first['confidence_pct']==100


def test_weak_fv_contact_keeps_independent_slab_evidence_without_floor_fallback():
    from portal.app.preprocessamento.segment_levels import resolve_pillars
    top=dict(fact_id='p:top',field='top',value=None,status='unknown',confidence_pct=0,evidence_ids=[],warnings=[])
    source=dict(fact_id='s:level',value=100,status='inferred',confidence_pct=55,evidence_ids=['cad:A'],warnings=[])
    fund=dict(segment_id='fv',segment_label=1,family='fundo',level=100,status='inferred',confidence_pct=30,level_slabs=['L1'],points=[[0,0],[50,0],[50,10],[0,10],[0,0]])
    fact=dict(fact_id='fv:level',field='fundo',segment_id='fv',value=100,status='inferred',confidence_pct=30,evidence_ids=['collection'],warnings=[])
    pillar=dict(display_name='P1',item_class='pillar',levels=[top])
    beam=dict(display_name='V1',item_class='beam',segments=[fund],levels=[fact])
    context=dict(state=dict(pilares=[dict(name='P1',points=[[0,10],[10,10],[10,20],[0,20],[0,10]])],slabs=[dict(name='L1',points=[[20,-20],[40,-20],[40,-10],[20,-10],[20,-20]])]))
    resolve_pillars([pillar,beam],context,{'L1':source})
    assert top['value']==100
    assert 0 < top['confidence_pct'] < 30
    assert 'cad:A' in top['evidence_ids']
    assert 'weak_contact_level_requires_review' in top['warnings']
    top.update(value=None,status='unknown'); fund['level_slabs']=[]
    resolve_pillars([pillar,beam],context,{'L1':source})
    assert top['value'] is None


def test_weak_fv_cannot_use_conflicting_or_missing_slab_source():
    # Existing no-evidence fixture must remain unresolved even if FV holds a value.
    tower,c,fund,_=fixture()
    c['state']['segmentos']={'fundo':[fund(1,0,50,101,None)]}
    result=merge_sa_levels(tower,c)
    top=next(f for i in result['items'] if i['display_name']=='P1' for f in i['levels'] if f['field']=='top')
    assert top['value'] is None


def regional_fixture(inner_level=99):
    tower, c, _, _ = fixture()
    c['state']['segmentos'] = {}
    c['state']['slabs'] = [dict(name='L1', nivel=100,
        points=[[0,0],[100,0],[100,100],[0,100],[0,0]],
        slab_steps=[dict(uid='inner', points=[[20,20],[80,20],[80,80],[20,80],[20,20]],
            level_m=inner_level, owner_level_m=100, evidence_handles=['A','B'],
            evidence_checks=dict(direct_internal_level=True,direct_principal_level=True))])]
    c['marks'] = [dict(value=100,pos=[5,5],handle='A')]
    if inner_level is not None:
        c['marks'].append(dict(value=inner_level,pos=[50,50],handle='B'))
    c['state']['pilares'][0]['points']=[[30,30],[40,30],[40,40],[30,40],[30,30]]
    return tower,c


def test_pillar_inside_step_uses_inner_level_not_outer_slab_scalar():
    tower,c=regional_fixture()
    result=merge_sa_levels(tower,c)
    top=next(f for f in result['items'][-1]['levels'] if f['field']=='top')
    assert top['value']==99
    assert top['status']=='sa_evidence'
    assert {x['region_id'] for x in result['items'][-1]['face_level_contacts']}=={'inner'}


def test_unknown_inner_region_cannot_borrow_principal_level():
    tower,c=regional_fixture(None)
    top=next(f for f in merge_sa_levels(tower,c)['items'][-1]['levels'] if f['field']=='top')
    assert top['value'] is None
    assert top['status']=='unknown'


def test_pillar_touching_both_regions_adopts_highest_contact():
    tower,c=regional_fixture()
    c['state']['pilares'][0]['points']=[[15,30],[25,30],[25,40],[15,40],[15,30]]
    top=next(f for f in merge_sa_levels(tower,c)['items'][-1]['levels'] if f['field']=='top')
    assert top['value']==100


def test_same_beam_estimate_propagates_to_sides_without_becoming_measured():
    tower,c,fund,side=fixture()
    # No independently levelled region touches the estimated segment.
    c['state']['slabs'][1]['points']=[[200,-10],[250,-10],[250,0],[200,0],[200,-10]]
    estimated=fund(2,50,100,98,None)
    estimated['level_source']='estimated_beam_level'
    c['state']['segmentos']={'fundo':[fund(1,0,50,100,'L1'),estimated],
                            'lateral_a_para':[side(9,50,100,98,None)]}
    result=beam(merge_sa_levels(tower,c))
    fv=result['segments'][1]
    lv=result['segments'][2]
    assert fv['level']==lv['level']==100
    assert fv['status']==lv['status']=='estimated'
    assert fv['level_source']=='estimated_from_same_beam_sourced_segment'
    assert lv['confidence_pct']<fv['confidence_pct']
    record=next(f for f in result['levels'] if f['field']=='fundo' and f['segment_id']=='fv2')
    assert record['fact_id'] not in record['source_fact_ids']


def test_distinct_peer_levels_do_not_define_unknown_segment_by_arbitrary_choice():
    tower,c,fund,_=fixture()
    estimated=fund(3,100,150,98,None)
    estimated['level_source']='estimated_beam_level'
    c['state']['segmentos']={'fundo':[fund(1,0,50,100,'L1'),fund(2,50,100,101,'L2'),estimated]}
    fv=beam(merge_sa_levels(tower,c))['segments'][2]
    assert fv['level']==98
    assert fv['status']=='estimated'
    assert fv['level_source']!='estimated_from_same_beam_sourced_segment'


def test_step_without_any_scoped_level_never_certifies_global_scalar():
    tower,c=regional_fixture(None)
    c['state']['slabs'][0]['slab_steps'][0]['owner_level_m']=None
    top=next(f for f in merge_sa_levels(tower,c)['items'][-1]['levels'] if f['field']=='top')
    assert top['value'] is None


def test_lower_side_lateral_does_not_fill_fv_when_opposite_face_reads_higher():
    tower,c,fund,side=fixture()
    c['state']['segmentos']={'fundo':[fund(1,0,50,None,None)],
                            'lateral_a_para':[side(9,0,50)],
                            'lateral_b_para':[side(11,50,0,level=101,slab=None)]}
    fv=beam(merge_sa_levels(tower,c))['segments'][0]
    assert fv.get('level_source')!='lv_independent_evidence_fills_fv'
    assert fv['level']!=100
