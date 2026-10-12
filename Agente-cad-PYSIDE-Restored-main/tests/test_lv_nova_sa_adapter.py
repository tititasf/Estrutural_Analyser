from copy import deepcopy
import ezdxf
import pytest
from src.core.lv_nova_sa_adapter import ab_runs, generate_ab


def source(assembly='sarrafeadas'):
    return dict(beam_name='V9', side='B', assembly_variant=assembly,
                panels=[dict(width=244, height1=75, height2=75, body_height_cm=60,
                             structural_segment_index=1),
                        dict(width=16, height1=75, height2=75, body_height_cm=60,
                             structural_segment_index=1,
                             holes=[dict(active=True, width=16, height=42, position=0, corner='TR')]),
                        dict(width=260, height1=75, height2=75, body_height_cm=60,
                             structural_segment_index=2)])


def test_corner_openings_survive_regrouping_and_source_is_immutable():
    sa=source(); before=deepcopy(sa)
    run=ab_runs(sa)[0]
    assert [s['length'] for s in run['segments']]==[260,260]
    assert run['segments'][0]['beam_openings']==[(244,260,18)]
    assert sa==before


@pytest.mark.parametrize('assembly',['gradeadas','sarrafeadas'])
def test_pipeline_exports_editable_approved_geometry(tmp_path,assembly):
    sa=source(assembly)
    generate_ab(sa,tmp_path/'view.dxf')
    doc=ezdxf.readfile(tmp_path/'view.dxf')
    assert not doc.audit().has_errors
    assert not doc.modelspace().query('IMAGE PDFUNDERLAY')
    assert doc.modelspace().query('DIMENSION HATCH LINE')
    dimensions=list(doc.modelspace().query('DIMENSION'))
    assert dimensions and all(len(list(d.virtual_entities()))>=5 for d in dimensions)
    text=[e.dxf.text for e in doc.modelspace().query('TEXT')]
    assert text.count('V9')==1 and not any(' S' in t for t in text)
    assert any('PONTALETE' in t.upper() for t in text)==(assembly=='gradeadas')


def test_column_interval_is_preserved_and_unmeasured_void_fails_closed():
    sa=source()
    sa['structural_segments']=[dict(segment_index=1,lv_cell=dict(
        pillar_openings=[dict(name='P1',pos_inicio=40,pos_fim=80)]))]
    assert ab_runs(sa)[0]['segments'][0]['column_openings']==[(40,80)]
    sa['structural_segments'][0]['lv_cell']['pillar_openings'][0].pop('pos_inicio')
    with pytest.raises(ValueError,match='intervalo medido'): ab_runs(sa)


def test_distinct_heights_remain_adjacent_with_local_mounting():
    sa=source();sa['panels'][-1].update(height1=90,height2=90,body_height_cm=70)
    runs=ab_runs(sa)
    assert len(runs)==1
    assert [(s['total_cm'],s['body_cm']) for s in runs[0]['segments']]==[(75,60),(90,70)]


@pytest.mark.parametrize('assembly',['gradeadas','sarrafeadas'])
@pytest.mark.parametrize('level_step',[0., .05])
def test_adjacent_panels_follow_sa_elevation_not_bottom(tmp_path,assembly,level_step):
    sa=source(assembly)
    sa['panels'][1].pop('holes')
    sa['panels'][-1].update(height1=90,height2=90,body_height_cm=75)
    sa['structural_segments']=[dict(segment_index=i,section_contract=dict(
        base_level_m=base,top_level_m=top,mounting={'B':{'panel_base_cm':0}}))
        for i,base,top in [(1,99.25,100),(2,99.10+level_step,100+level_step)]]
    before=deepcopy(sa)
    run=ab_runs(sa)[0]
    assert run['segments'][1]['y_offset_cm']==pytest.approx(-15+level_step*100)
    assert sa==before
    generate_ab(sa,tmp_path/'level.dxf')
    doc=ezdxf.readfile(tmp_path/'level.units/AB_001.dxf')
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    slab=unary_union([Polygon([(v[0],v[1]) for v in p.vertices])
        for e in doc.modelspace().query('HATCH') for p in e.paths])
    # Both real slab tops follow their SA level, despite different depths.
    from shapely.geometry import LineString
    assert slab.intersection(LineString([(100,-100),(100,200)])).bounds[3]==pytest.approx(75)
    assert slab.intersection(LineString([(400,-100),(400,200)])).bounds[3]==pytest.approx(75+level_step*100)
    assert not doc.audit().has_errors


def test_sa_column_allowance_is_not_replaced_by_concrete_width():
    sa=source()
    sa['structural_segments']=[dict(segment_index=1,lv_cell=dict(pillar_openings=[
        dict(pos_inicio=40,pos_fim=80,dist_abertura_inicio=29,abertura=62)]))]
    assert ab_runs(sa)[0]['segments'][0]['column_openings']==[(29,91)]


@pytest.mark.parametrize('points,origin', [
    ([[140, 0], [400, 0]], [[100, 0], [400, 0]]),
    ([[0, 260], [0, 0]], [[0, 300], [0, 0]]),
])
def test_partitioned_column_openings_use_physical_origin_and_clip(points, origin):
    sa=source()
    sa['panels']=sa['panels'][:2]
    sa['structural_segments']=[dict(segment_index=1,points=points,
        opening_source_points=origin,lv_cell=dict(pillar_openings=[
            dict(dist_abertura_inicio=29,abertura=62),
            dict(pos_inicio=290,pos_fim=330)]))]
    before=deepcopy(sa)
    assert ab_runs(sa)[0]['segments'][0]['column_openings']==[(0,51),(250,260)]
    assert sa==before


def test_start_trim_moves_column_opening_without_affecting_later_segments():
    sa=source()
    sa['start_adjustment']=-10
    sa['structural_segments']=[dict(segment_index=i,lv_cell=dict(
        pillar_openings=[dict(pos_inicio=40,pos_fim=80)])) for i in (1,2)]
    segments=ab_runs(sa)[0]['segments']
    assert segments[0]['column_openings']==[(30,70)]
    assert segments[1]['column_openings']==[(40,80)]


def test_local_cut_sheet_retains_dimension_graphics(tmp_path):
    from src.core.lv_n3_cut_contract import build_cut_contract
    from scripts.arete.lv_n3_cut_draw import generate_local_sections
    c=build_cut_contract(dict(kind='calculated',id='c',beam='V9',width_cm=19,
        beam_height_cm=55,profiles={s:dict(level=852.19,slabs=[]) for s in 'AB'}))
    sides={s:dict(assembly_variant='gradeadas',structural_segments=[dict(section_contract=c)]) for s in 'AB'}
    generate_local_sections(sides,tmp_path/'cuts.dxf')
    doc=ezdxf.readfile(tmp_path/'cuts.dxf')
    assert all(len(list(d.virtual_entities()))>=5 for d in doc.modelspace().query('DIMENSION'))
    assert not doc.audit().has_errors


def test_nova_multiple_slab_contract_preserves_profiles_and_aliases():
    from src.core.lv_n3_cut_contract import build_cut_contract,CutContractError
    cut=dict(kind='calculated',id='c',beam='V9',width_cm=25,beam_height_cm=90,
        profiles=dict(A=dict(level=852.19,slabs=[dict(name='L1',height_cm=14,level=852.19),
            dict(name='L2',height_cm=12,level=851.87)]), B=dict(level=852.19,slabs=[])),
        slab_aliases=dict(A=['L1','L2']))
    with pytest.raises(CutContractError,match='mais de um perfil'): build_cut_contract(cut)
    c=build_cut_contract(cut,allow_multiple_slabs=True)
    assert len(c['slabs']['A'])==2
    assert c['mounting']['A']['h1_cm']==48


def test_dimension_graphics_preserve_fractional_centimetres():
    from src.core.lv_nova_design import draw_ab
    doc=draw_ab(dict(beam='V1', side='A', assembly_variant='gradeadas',
        body_cm=49, total_cm=63, segments=[dict(length=305.5)]))
    text=[e.dxf.text for d in doc.modelspace().query('DIMENSION')
          for e in d.virtual_entities() if e.dxftype() in ('TEXT','MTEXT')]
    assert '305,5' in text and '61,5' in text
    assert '306' not in text and '62' not in text


@pytest.mark.parametrize('assembly', ['gradeadas', 'sarrafeadas'])
def test_confirmed_inverted_cut_retains_neighbor_slab_below_web(assembly):
    from src.core.lv_nova_design import draw_cut
    from ezdxf import bbox
    c = dict(beam='V9', width_cm=19, height_cm=120,
             assembly_variant=assembly, beam_type='inverted', form_role='top_cap',
             slabs={'A': [dict(height_cm=13, drop_cm=114)],
                    'B': [dict(height_cm=13, drop_cm=107)]})
    doc = draw_cut(c)
    assert not doc.audit().has_errors
    # The concrete neighbor reaches -7 while the web base remains at 0.
    bounds = bbox.extents(doc.modelspace().query('LWPOLYLINE[layer=="CONCRETO"]'))
    assert bounds.extmin.y == pytest.approx(-7)
    assert bounds.extmax.y == pytest.approx(120)
    assert len(list(doc.modelspace().query('DIMENSION'))) >= 6
    c.pop('beam_type'); c.pop('form_role')
    with pytest.raises(ValueError, match='slab outside beam profile'):
        draw_cut(c)
    c.update(beam_type='inverted', form_role='top_cap')
    c['slabs']['A'][0]['drop_cm'] = 120
    with pytest.raises(ValueError, match='slab outside beam profile'):
        draw_cut(c)


def test_obstacles_and_measured_gaps_separate_runs():
    sa=source('gradeadas')
    sa['panels'][1]['holes'][0]['height']=60
    before=deepcopy(sa)
    runs=ab_runs(sa)
    assert len(runs)==2
    assert runs[0]['segments'][0]['length']==244
    assert not runs[0]['segments'][0]['beam_openings']
    assert sa==before
    sa=source()
    sa['structural_segments']=[dict(segment_index=1,points=[[0,0],[260,0]]),
        dict(segment_index=2,points=[[280,0],[540,0]])]
    assert len(ab_runs(sa))==2


def test_height_step_uses_local_panel_top(tmp_path):
    sa=source('gradeadas')
    sa['panels'][-1].update(height1=90,height2=90,body_height_cm=70)
    generate_ab(sa,tmp_path/'step.dxf')
    doc=ezdxf.readfile(tmp_path/'step.dxf')
    labels=[e for e in doc.modelspace().query('TEXT') if e.dxf.text=='V9']
    assert len(labels)==1 and labels[0].dxf.insert.x==5
    assert labels[0].dxf.insert.y==80
    assert not doc.audit().has_errors


@pytest.mark.parametrize('assembly',['gradeadas','sarrafeadas'])
def test_connected_run_has_one_total_aligned_dimensions_and_one_void(assembly):
    from src.core.lv_nova_design import draw_ab
    c=dict(beam='V9',side='A',assembly_variant=assembly,body_cm=60,total_cm=75,
        segments=[dict(length=260,body_cm=60,total_cm=75,
                       beam_openings=[(220,260,20)]),
                  dict(length=300,body_cm=90,total_cm=105,y_offset_cm=-30)])
    d=draw_ab(c);ms=d.modelspace()
    granular=[e for e in ms.query('DIMENSION') if abs(e.dxf.defpoint.y+56.54)<1e-6]
    assert len(granular)==4
    assert min(e.dxf.defpoint2.y for e in granular)==-30
    assert max(e.dxf.defpoint2.y for e in granular)==0
    totals=[e for e in ms.query('DIMENSION') if abs(e.dxf.defpoint.y+100)<1e-6]
    assert len(totals)==1
    assert totals[0].dxf.defpoint2.x==0 and totals[0].dxf.defpoint3.x==560
    assert [e.dxf.text for e in ms.query('TEXT') if e.dxf.text.startswith('V9')]==['V9']
    hatches=list(ms.query('HATCH'))
    assert len(hatches)==1 and hatches[0].dxf.layer=='COTA'
    assert not any(e.dxf.layer=='COTA' and abs(e.dxf.start.x-260)<1e-6
                   and abs(e.dxf.end.x-260)<1e-6 for e in ms.query('LINE'))
    assert any(e.dxf.layer=='COTA' and abs(e.dxf.start.y-75)<1e-6
               and abs(e.dxf.end.x-e.dxf.start.x)==560 for e in ms.query('LINE'))


@pytest.mark.parametrize('face',list('ABCDEFGH'))
def test_column_openings_follow_pillar_faces(face):
    sa=source()
    sa['structural_segments']=[dict(segment_index=1,lv_cell=dict(pillar_openings=[
        dict(name='P1',pos_inicio=40,pos_fim=80,pillar_face=face)]))]
    openings=ab_runs(sa)[0]['segments'][0]['column_openings']
    assert openings == ([] if face in 'CD' else [(40,80)])


def test_sa_geometry_identifies_short_face_without_mutating_sources():
    from src.core.lv_nova_sa_adapter import attach_pillar_faces
    sa=source();sa['structural_segments']=[dict(segment_index=1,points=[[0,80],[260,80]],
        lv_cell=dict(pillar_openings=[dict(name='P1',pos_inicio=40,pos_fim=59)]))]
    original=deepcopy(sa)
    result=attach_pillar_faces({'B':sa},[dict(name='P1',points=[[40,0],[59,0],[59,80],[40,80]])])
    assert result['B']['structural_segments'][0]['lv_cell']['pillar_openings'][0]['pillar_face']=='C'
    assert ab_runs(result['B'])[0]['segments'][0]['column_openings']==[]
    assert sa==original
