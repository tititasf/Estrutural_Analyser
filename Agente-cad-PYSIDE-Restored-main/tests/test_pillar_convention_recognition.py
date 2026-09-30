from src.core.pillar_convention_recognition import recognize

P = [(0,0),(20,0),(20,100),(0,100),(0,0)]
C = {'birth': {'sig':'CROSS','label':'birth'},
     'continuation': {'sig':'DIAG','label':'continuation'},
     'end': {'sig':'EMPTY','label':'end'}}

def line(a,b,layer='fill'):
    return {'start':a,'end':b,'layer':layer}

def test_complete_parallel_and_cross():
    assert recognize(P, {'lines':[line((0,10),(20,30)),line((0,40),(20,60))]}, C)[0] == 'continuation'
    assert recognize(P, {'lines':[line((0,0),(20,100)),line((20,0),(0,100))]}, C)[0] == 'birth'

def test_regular_clipped_fill():
    lines=[line((-1,y-1),(21,y+21)) for y in (10,40,70)]
    value,evidence=recognize(P,{'lines':lines},C)
    assert value=='continuation'
    assert evidence['path']=='regular_clipped_fill'

def test_empty_requires_original_closed_outline():
    assert recognize(P, {}, C)[0]=='INDETERMINADO'
    assert recognize(P, {'polylines':[{'points':P,'closed':True}]}, C)[0]=='end'

def test_concave_outline_excludes_neighbor():
    points=[(0,0),(100,0),(100,20),(20,20),(20,100),(0,100),(0,0)]
    data={'lines':[line((40,40),(60,60)),line((40,60),(60,40))],
          'polylines':[{'points':points,'closed':True}]}
    assert recognize(points,data,C)[0]=='end'

def test_conflict_and_single_leader_stay_unknown():
    conflict={**C,'other':{'sig':'DIAG','label':'other'}}
    data={'lines':[line((0,10),(20,30)),line((0,40),(20,60))]}
    assert recognize(P,data,conflict)[0]=='INDETERMINADO'
    assert recognize(P,{'lines':[line((0,10),(20,30))]},C)[0]=='INDETERMINADO'

def test_overlapping_neighbor_cross_does_not_change_empty_outline():
    data={'lines':[line((-15,0),(35,19)),line((-15,19),(35,0))],
          'polylines':[{'points':P,'closed':True},
                       {'points':[(-15,0),(35,0),(35,19),(-15,19),(-15,0)],'closed':True}]}
    assert recognize(P,data,C)[0]=='end'
    data['polylines'].pop()
    assert recognize(P,data,C)[0]=='INDETERMINADO'

def test_inventory_classifies_geometry_found_by_name():
    import ast
    from pathlib import Path
    tree=ast.parse((Path(__file__).parents[1]/'main.py').read_text(encoding='utf-8-sig'))
    method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)
                and n.name=='_build_complete_pillar_report')
    namespace={'Dict':dict}
    exec(compile(ast.Module(body=[method],type_ignores=[]),'inventory','exec'),namespace)
    class Runner:
        dxf_data={'lines':[line((0,10),(20,30)),line((0,40),(20,60))]}
        pavimento_preprocess={'convention':C}
        _build_pillar_report=lambda self,slabs:{}
        _collect_plan_pillar_names=lambda self:{'P_TEST':[(0,0)]}
        _find_pillar_geom_near_text=lambda self,*args:(P,1)
        _pillar_laje_entries=lambda self,*args:[]
        _reconcile_canonical_pillar_links=lambda self,*args:None
    report=namespace['_build_complete_pillar_report'](Runner(),[])
    assert report['P_TEST']['classification']=='continuation'
    assert report['P_TEST']['geometry_source']=='name_proximity'

def test_boundary_dimension_tick_requires_two_axes():
    data={'lines':[line((-5,45),(5,55)),line((-30,50),(0,50)),line((0,35),(0,65))],
          'polylines':[{'points':P,'closed':True}]}
    assert recognize(P,data,C)[0]=='end'
    data['lines'].pop()
    assert recognize(P,data,C)[0]=='INDETERMINADO'
