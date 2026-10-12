from scripts.arete.headless_sa_analise import _preserve_unrequested_fundo


def test_lv_preserves_fv_geometry_dimensions_and_mirror_without_stale_slots():
    old = {'name':'B', 'fv_is_h':True, 'fields':{'viga_fundo_seg_1_dim':'19/65'},
           'links':{'viga_fundo_seg_1_area_segs':{'contour':[{'points':[[1,2],[3,4]]}]},
                    'viga_segs':{'seg_bottom':[{'source':'canonical'}]}},
           'validated_fields':['viga_fundo_seg_1_dim']}
    new = {'name':'B', 'fv_is_h':False,
           'fields':{'viga_fundo_seg_2_dim':'bad','viga_a_seg_1_altura':'40'},
           'links':{'viga_fundo_seg_2_area_segs':{},'viga_segs':{'seg_bottom':[],'seg_a':[1]}},
           'validated_fields':['viga_a_seg_1_altura']}
    _preserve_unrequested_fundo([old],[new])
    assert new['fv_is_h'] is True
    assert new['fields']=={'viga_fundo_seg_1_dim':'19/65','viga_a_seg_1_altura':'40'}
    assert new['links']['viga_fundo_seg_1_area_segs']==old['links']['viga_fundo_seg_1_area_segs']
    assert 'viga_fundo_seg_2_area_segs' not in new['links']
    assert new['links']['viga_segs']=={'seg_bottom':[{'source':'canonical'}],'seg_a':[1]}
    assert set(new['validated_fields'])=={'viga_fundo_seg_1_dim','viga_a_seg_1_altura'}
    new['links']['viga_fundo_seg_1_area_segs']['contour'][0]['points'].append([5,6])
    assert len(old['links']['viga_fundo_seg_1_area_segs']['contour'][0]['points'])==2


def test_lv_preserves_classified_fv_geometry_without_preserving_lv():
    old={'name':'B','geometry':{'classified':{'merged_bottom_groups_coords':[1], 'merged_bottom_lengths':[2]}}}
    new={'name':'B','geometry':{'classified':{'merged_bottom_groups_coords':[9], 'merged_bottom_lengths':[9], 'lateral':[3]}}}
    _preserve_unrequested_fundo([old],[new])
    assert new['geometry']['classified']=={'merged_bottom_groups_coords':[1], 'merged_bottom_lengths':[2], 'lateral':[3]}
