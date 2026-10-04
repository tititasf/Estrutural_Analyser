from copy import deepcopy

from shapely.geometry import Polygon

from portal.app.structural_cut_overlay import viewer_groups, align_highlight_dividers


class Transform:
    def dxf_para_px(self, x, y):
        return [2*x, -2*y]


def test_highlight_draws_each_confirmed_height_without_changing_owner():
    def entry(lo, hi, height):
        return dict(beam='BEAM', pairs=[dict(start=[9.5,lo], end=[9.5,hi])],
            section_contract=dict(width_cm=19, height_cm=height,
                base_level_m=852.06, top_level_m=852.06+height/100,
                beam_type='inverted', form_role='top_cap',
                section_semantics=dict(confirmed=True)))
    groups=[dict(grupo='fundo', total=1, itens=[dict(item_id='source',
        beam_name='BEAM', rotulo='BEAM SEG 1',
        pontos_dxf=[[0,0],[19,0],[19,200],[0,200],[0,0]],
        pontos_px=[], fora_do_frame=False)])]
    before=deepcopy(groups)
    inventory=dict(physical_entries=[entry(0,120,120),entry(120,200,71)],
                   entries=[], blocked=[])
    result=viewer_groups(None,None,{},Transform(),groups,inventory=inventory)
    rows=result[0]['itens']
    assert len(rows)==result[0]['total']==2
    assert {r['rotulo'] for r in rows}=={'BEAM SEG 1 · 19/120','BEAM SEG 1 · 19/71'}
    assert {r['highlight_color'] for r in rows}=={'#ff4545'}
    assert {r['item_id'] for r in rows}=={'source'}
    assert sum(Polygon(r['pontos_dxf']).area for r in rows)==3800
    assert Polygon(rows[0]['pontos_dxf']).intersection(Polygon(rows[1]['pontos_dxf'])).area==0
    assert all(r['pontos_px']==[Transform().dxf_para_px(*p) for p in r['pontos_dxf']] for r in rows)
    assert groups==before


def test_measured_full_width_divider_replaces_midpoint_without_losing_area():
    spans=[dict(geometry=[[0,0],[19,0],[19,120],[0,120],[0,0]],
                length=120,vertical_partition=dict(start_cm=0,end_cm=120)),
           dict(geometry=[[0,120],[19,120],[19,200],[0,200],[0,120]],
                length=80,vertical_partition=dict(start_cm=120,end_cm=200))]
    before=deepcopy(spans)
    aligned=align_highlight_dividers(spans,[(0,140,19,140),(2,150,17,150)])
    assert [r['length'] for r in aligned]==[140,60]
    assert aligned[0]['vertical_partition']['end_cm']==140
    assert aligned[1]['vertical_partition']['start_cm']==140
    polygons=[Polygon(r['geometry']) for r in aligned]
    assert sum(p.area for p in polygons)==3800
    assert polygons[0].intersection(polygons[1]).area==0
    assert spans==before
    assert align_highlight_dividers(spans,[(0,140,19,140),(0,150,19,150)])==before
    spans[0]['dim_text']='19/120'
    spans[1]['dim_text']='19/71'
    # A second full-width line belongs to the same-height run; CAD labels
    # bracket the actual transition and exclude it.
    aligned=align_highlight_dividers(spans,[(0,100,19,100),(0,140,19,140)],
        [dict(text='19/120',pos=[-4,110]),dict(text='19/71',pos=[-4,170])])
    assert aligned[0]['vertical_partition']['end_cm']==140
