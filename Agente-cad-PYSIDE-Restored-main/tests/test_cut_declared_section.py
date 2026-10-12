from copy import deepcopy
from src.core.cut_declared_section import declared_section_for_cut
from src.core.lv_beam_scene import LvScene


POINTS = [(0,0),(60,0),(60,14),(17,14),(17,44),(7,44),(7,14),(0,14)]


def facts():
    scene = LvScene('V1',True,0,14,-100,200)
    scene.labels = [{'text':'V1','pos':(150,-20)}]
    scene.provenance = {'band_source':'dxf_edges_from_own_label'}
    scene.face_coverage = {'A':[[-100,200]], 'B':[[-100,200]]}
    scene.sections = [{'start':-100,'end':200,'width':14,'depth':55}]
    return {'V1':[scene]}, [{'text':'14/55','pos':(120,-15),'rotation':0,'height':10,'handle':'ref'}]


def test_own_bound_numeric_section_can_disagree_with_drawn_depth():
    runs,texts=facts(); proof=declared_section_for_cut(POINTS,'Sul',14,runs,texts)
    assert proof['height_cm']==55 and proof['geometry_depth_cm']==60
    assert proof['source_text']['handle']=='ref'


def test_pillar_nearest_text_does_not_replace_beam_reference():
    runs,texts=facts();texts += [{'text':'24/66','pos':(20,-10),'rotation':0},
                               {'text':'P9','pos':(20,5)}]
    assert declared_section_for_cut(POINTS,'Sul',14,runs,texts)['height_cm']==55


def test_wing_contact_with_wrong_parallel_run_cannot_bind():
    runs,texts=facts();runs['V1'][0].t_lo=30;runs['V1'][0].t_hi=44
    assert declared_section_for_cut(POINTS,'Sul',14,runs,texts) is None


def test_missing_local_source_wall_cannot_bind():
    runs,texts=facts();runs['V1'][0].face_coverage['B']=[[-100,7],[17,200]]
    assert declared_section_for_cut(POINTS,'Sul',14,runs,texts) is None


def test_other_component_annotation_cannot_bind():
    runs,texts=facts();texts[0]['pos']=(1000,-15)
    assert declared_section_for_cut(POINTS,'Sul',14,runs,texts) is None


def test_wrong_orientation_cannot_bind():
    runs,texts=facts();texts[0]['rotation']=90
    assert declared_section_for_cut(POINTS,'Sul',14,runs,texts) is None


def test_source_without_cad_handle_is_not_authoritative():
    runs,texts=facts();texts[0].pop('handle')
    assert declared_section_for_cut(POINTS,'Sul',14,runs,texts) is None


def test_reanalysis_without_current_source_drops_stale_authority():
    from types import SimpleNamespace
    from src.core.cut_declared_section import apply_declared_section
    link={'points':POINTS,'ficha':{'beam_height_evidence':{'height_cm':55}}}
    window=SimpleNamespace(dxf_data={},beams_found=[])
    assert apply_declared_section(window,link,{'bw':14},'Sul') is None
    assert 'beam_height_evidence' not in link['ficha']


def test_ambiguous_ownership_cannot_bind():
    runs,texts=facts();runs['V2']=deepcopy(runs['V1']);runs['V2'][0].beam_name='V2'
    assert declared_section_for_cut(POINTS,'Sul',14,runs,texts) is None


def test_cut_crossing_different_declared_section_zones_cannot_bind():
    runs,texts=facts();runs['V1'][0].sections=[{'start':-100,'end':30,'width':14,'depth':55},
        {'start':30,'end':200,'width':14,'depth':70}]
    assert declared_section_for_cut(POINTS,'Sul',14,runs,texts) is None


def test_own_fv_geometry_resolves_a_foreign_label_on_same_run():
    runs,texts=facts();runs['V2']=deepcopy(runs['V1']);runs['V2'][0].beam_name='V2'
    beams = [{'name':'V1', 'links':{'viga_fundo_seg_1_area_segs':
             {'contour':[{'points':[(-100,0),(200,0),(200,14),(-100,14)]}]}}},
             {'name':'V2','links':{'viga_fundo_seg_1_area_segs':
             {'contour':[{'points':[(-100,100),(200,100),(200,114),(-100,114)]}]}}}]
    proof = declared_section_for_cut(POINTS,'Sul',14,runs,texts,beams)
    assert proof['beam_name']=='V1'


def test_authoritative_override_preserves_own_measured_offset_and_repairs_source_links(monkeypatch):
    from types import SimpleNamespace
    from src.core.cut_declared_section import apply_declared_section
    runs,texts=facts();texts += [{'text':'V1','pos':(150,-20),'handle':'beam-name'}]
    beams=[{'name':'V1','links':{'viga_fundo_seg_1_area_segs':
             {'contour':[{'points':[(-100,0),(200,0),(200,14),(-100,14)]}]}}}]
    window=SimpleNamespace(dxf_data={'texts':texts,'lines':[]},beams_found=beams,
                           _infer_slab_position=lambda *args:'centro')
    monkeypatch.setattr('src.core.lv_beam_scene.build_scene_runs', lambda *args:runs)
    link={'points':POINTS,'ficha':{'beam_height':'60','beam_name':'V7',
          'own_slab_height':'10','own_dist_top':'7','own_dist_bottom':'43'},
          'ficha_links':{'beam_height':[{'text':'24/66'}]}}
    proof=apply_declared_section(window,link,{'bw':14},'Sul')
    assert proof['geometry_depth_cm']==60
    assert link['ficha']['beam_height']=='55.0'
    assert link['ficha']['own_dist_top']=='7' and link['ficha']['own_dist_bottom']=='38.0'
    assert link['ficha']['beam_name']=='V1'
    assert link['ficha_links']['beam_height'][0]['handle']=='ref'
    assert link['ficha_links']['beam_name'][0]['handle']=='beam-name'


def test_wrapper_includes_polyline_walls_and_cache_follows_source_identity(monkeypatch):
    from types import SimpleNamespace
    from src.core.cut_declared_section import apply_declared_section
    runs,texts=facts()
    beam={'name':'V1','links':{'viga_fundo_seg_1_area_segs':
        {'contour':[{'points':[(-100,0),(200,0),(200,14),(-100,14)]}]}}}
    data={'texts':texts,'lines':[{'layer':'structural','start':(-100,0),'end':(200,0)}],
        'polylines':[{'layer':'structural','points':[(-100,14),(200,14)]}]}
    calls=[]
    def build(beams,texts,lines,pillars):
        calls.append(lines)
        assert any(item.get('points') for item in lines)
        return runs
    monkeypatch.setattr('src.core.lv_beam_scene.build_scene_runs',build)
    window=SimpleNamespace(dxf_data=data,beams_found=[beam],_infer_slab_position=lambda *args:'centro')
    link={'points':POINTS,'ficha':{'beam_height':'60','beam_height_label':'53',
         'own_slab_height':'10','own_dist_top':'7'}}
    apply_declared_section(window,link,{'bw':14},'Sul')
    apply_declared_section(window,link,{'bw':14},'Sul')
    assert len(calls)==1 and link['ficha']['own_dist_bottom']=='38.0'
    assert 'beam_height_label' not in link['ficha']
    assert link['cut_dimension_debug']['overridden_height_label']['drawing_label_cm']=='53'
    window.dxf_data=deepcopy(data)
    apply_declared_section(window,link,{'bw':14},'Sul')
    assert len(calls)==2
