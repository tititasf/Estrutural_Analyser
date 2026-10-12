from shapely.geometry import Polygon
from shapely.ops import unary_union
from src.core.composite_cut_contours import partition_cut_contours,source_section_drawing
from portal.app.source_section_overlay import original_groups


def rect(x,y,w,h,layer='sections'):
    return dict(layer=layer,points=[[x,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y]])


def dim(x,y,text):return dict(pos=[x,y],text=text,layer='beam dimensions')


def test_two_beams_sharing_a_slab_bridge_remain_two_complete_source_parts():
    pieces=[rect(0,100,120,19),rect(75,19,12,81),rect(70,5,50,14),rect(70,-45,12,50)]
    records=partition_cut_contours(pieces,[dim(100,125,'19/120'),dim(100,24,'14/50')])
    assert len(records)==2 and all(r['section_kind']=='beam' for r in records)
    original=unary_union([Polygon(p['points']) for p in pieces])
    partition=unary_union([Polygon(r['points']) for r in records])
    assert original.symmetric_difference(partition).area<1e-6
    assert Polygon(records[0]['points']).intersection(Polygon(records[1]['points'])).area<1e-6
    assert {tuple(Polygon(r['body_points']).bounds) for r in records}=={(0,100,120,119),(70,5,120,19)}
    for record in records:
        shared=[p for p in record['measured_pieces'] if p['shared_for_display']]
        assert shared
        assert any(abs(Polygon(p['points']).bounds[3]-Polygon(p['points']).bounds[1]-81)<1e-6 for p in shared)
        labels={p.get('text') for p in source_section_drawing(record)['primitives']}
        assert '81' not in labels and '12' in labels


def test_beam_and_step_have_distinct_colors_without_losing_a_piece():
    pieces=[rect(100,0,19,120),rect(0,35,50,15),rect(50,35,50,10)]
    records=partition_cut_contours(pieces,[dim(90,70,'19/120')])
    assert {r['section_kind'] for r in records}=={'beam','slab_step'}
    colors={r['section_kind']:source_section_drawing(r)['primitives'][0]['color'] for r in records}
    assert colors=={'beam':'#a8fff0','slab_step':'#ffe033'}
    assert unary_union([Polygon(r['points']) for r in records]).equals(unary_union([Polygon(r['points']) for r in pieces]))
    step=next(r for r in records if r['section_kind']=='slab_step')
    labels=[p['text'] for p in source_section_drawing(step)['primitives'] if p['kind']=='text']
    assert '10' in labels and '15' in labels


def test_original_is_never_mirrored_stretched_or_replaced_by_a_schematic():
    pieces=[rect(70,0,19,120),rect(20,50,50,12)]
    records=partition_cut_contours(pieces,[dim(90,65,'19/120')])
    record=records[0]
    drawing=source_section_drawing(record)
    assert drawing['primitives'][0]['points']==record['points']
    assert Polygon(drawing['primitives'][0]['points']).equals(unary_union([Polygon(p['points']) for p in pieces]))
    assert {p['text'] for p in drawing['primitives'] if p['kind']=='text'}>={'19','120','12'}


def test_gap_and_pillar_dimension_do_not_create_a_connected_cut():
    records=partition_cut_contours([rect(0,0,19,120),rect(-50.1,90,50,12)], [dim(20,50,'19/120')])
    assert len(records)==1
    assert Polygon(records[0]['points']).area==19*120
    assert partition_cut_contours([rect(0,0,22,150,'pillars')],[dict(pos=[0,0],text='22/150',layer='pillar dimensions')])==[]


def test_wall_intervals_and_title_follow_rotated_source_without_changing_it():
    for rotated in (False,True):
        pieces=[rect(70,0,19,120),rect(20,50,50,12)]
        text=dim(90,65,'19/120')
        if rotated:
            for piece in pieces:piece['points']=[[y,-x] for x,y in piece['points']]
            text['pos']=[65,-90]
        record=partition_cut_contours(pieces,[text])[0]
        drawing=source_section_drawing(record,'V1')
        assert drawing['primitives'][0]['points']==record['points']
        walls=[p for p in drawing['primitives'] if p.get('role')=='wall_dimension']
        assert sorted(float(p['text']) for p in walls)==[50,58]
        title=next(p for p in drawing['primitives'] if p.get('role')=='section_title')
        a,b=title['points'];x,y,X,Y=Polygon(record['points']).bounds
        if rotated:
            assert b==[a[0],a[1]+1] and a[0]<x-20
        else:
            assert b==[a[0]+1,a[1]] and a[1]>Y+20


def test_disconnected_arm_does_not_invent_wall_contacts():
    record=partition_cut_contours([rect(70,0,19,120),rect(19,50,50,12)],
                                  [dim(90,65,'19/120')])[0]
    assert not any(p.get('role')=='wall_dimension' for p in source_section_drawing(record)['primitives'])


def test_slab_symbol_extent_never_changes_engineering_dimensions():
    for rotated in (False,True):
        for extent in (37,81):
            pieces=[rect(100,0,19,120),rect(100-extent,50,extent,12)]
            text=dim(120,65,'19/120')
            if rotated:
                for piece in pieces:piece['points']=[[y,-x] for x,y in piece['points']]
                text['pos']=[65,-120]
            record=partition_cut_contours(pieces,[text])[0]
            drawing=source_section_drawing(record)
            assert drawing['source_points']==record['points']
            dimensions=[p for p in drawing['primitives'] if p['kind']=='text' and p.get('role')!='section_title']
            assert {p['text'] for p in dimensions}=={'19','120','12','50','58'}
            assert [p['text'] for p in dimensions if p.get('role')=='slab_thickness']==['12']


def test_current_source_replaces_old_partial_highlights(tmp_path):
    import ezdxf
    doc=ezdxf.new();msp=doc.modelspace()
    for p in [rect(70,0,19,120),rect(20,50,50,12)]:msp.add_lwpolyline(p['points'],close=True,dxfattribs={'layer':'sections'})
    msp.add_text('19/120',dxfattribs={'insert':(90,65),'layer':'beam dimensions'})
    path=tmp_path/'test.dxf';doc.saveas(path)
    class Transform:
        def dxf_para_px(self,x,y):return [x,-y]
    groups=[dict(grupo='cortes',itens=[dict(pontos_dxf=rect(70,0,19,60)['points'],fora_do_frame=False)])]
    result=original_groups(groups,path,{},Transform())[0]
    assert result['total']==1
    item=result['itens'][0]
    assert item['measured_height_cm']==120 and item['measured_width_cm']==19
    assert item['section_drawing']['primitives'][0]['points']==[[p[0],-p[1]] for p in item['pontos_dxf']]
    interpreted=next(g for g in original_groups(groups,path,{},Transform()) if g['grupo']=='cortes_interpretados')
    assert interpreted['total']==0
    assert interpreted['itens']==[]
    from portal.app.source_section_overlay import measured_items
    listed = measured_items(path, {})
    assert listed[0]['item_id'] == item['item_id']
    assert listed[0]['classe_sa'] == 'cortes'
    assert '19/120 cm' in listed[0]['titulo']


def test_source_measurements_do_not_duplicate_or_remove_generated_cuts(tmp_path):
    import ezdxf
    doc=ezdxf.new()
    doc.modelspace().add_lwpolyline(rect(0,0,19,120)['points'],close=True,
                                  dxfattribs={'layer':'sections'})
    doc.modelspace().add_text('19/120',dxfattribs={'insert':(20,60),'layer':'beam dimensions'})
    path=tmp_path/'source.dxf';doc.saveas(path)
    generated=dict(item_id='interpreted:generated',section_drawing={'primitives':[]})
    stale=dict(item_id='interpreted:source-section:old',interpretation_scope='measured_source_geometry')
    groups=[dict(grupo='cortes_interpretados',itens=[generated,stale])]
    class Transform:
        def dxf_para_px(self,x,y):return [x,y]
    result=original_groups(groups,path,{},Transform())
    interpreted=next(g for g in result if g['grupo']=='cortes_interpretados')
    assert interpreted['itens']==[generated] and interpreted['total']==1
    original=next(g for g in result if g['grupo']=='cortes')
    assert original['total']==1
    assert original['itens'][0]['measured_height_cm']==120
    assert groups[0]['itens']==[generated,stale]


def test_measured_geometry_cannot_validate_an_absolute_level(monkeypatch):
    import pytest
    from fastapi import HTTPException
    from portal.app.routers import item_geometry_routes as routes
    monkeypatch.setattr(routes, 'context', lambda *args: ({}, None))
    with pytest.raises(HTTPException) as error:
        routes.review_interpreted('work', 'interpreted:source-section:abc', None,
                                 'floor', {}, None, 'validate')
    assert error.value.status_code == 422
    assert 'não possui referência de nível' in error.value.detail


def test_selection_uses_viewer_inventory_even_without_current_sa(monkeypatch):
    from portal.app.routers import item_geometry_routes as routes, viewer_routes
    items = [dict(item_id='interpreted:calculated', rotulo='V1', review_status='validated'),
             dict(item_id='interpreted:source-section:a', rotulo='V2',
                  interpretation_scope='measured_source_geometry', measured_width_cm=19,
                  measured_height_cm=120, absolute_level=None)]
    monkeypatch.setattr(viewer_routes, 'viewer_pavimento_endpoint',
                        lambda *args: dict(grupos=[dict(grupo='cortes_interpretados', itens=items)]))
    listed = routes.interpreted_items('work', None, 'floor', {}, None)['itens']
    assert [item['item_id'] for item in listed] == [item['item_id'] for item in items]
    assert listed[0]['review_status'] == 'validated'
    assert '19/120 cm' in listed[1]['titulo']
    assert listed[1]['absolute_level'] is None
