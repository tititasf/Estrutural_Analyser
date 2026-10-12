import math
from shapely.geometry import Polygon
from src.core.pillar_geometry_association import reassociate, circular_measurements, annotate_circular_state
from src.core.pillar_sa_review import eligible
from src.core.perspective_mapper import PillarPerspectiveMapper


def rectangle(x, y, w, h, layer):
    return dict(points=[(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)], layer=layer)


def predicate(poly, points):
    return poly.is_valid and poly.area >= 80


def test_independent_dimensions_replace_nearest_beam_and_section():
    pillar = rectangle(10, 0, 19, 170, 'COLUMN')
    for layer in ('FACE-BEAM', 'SECTION'):
        wrong = rectangle(29, 50, 71, 15, layer)
        data = dict(polylines=[wrong, pillar], texts=[
            dict(text='P1', pos=(50,80), height=10), dict(text='19/170',pos=(50,65),height=10)])
        found = reassociate(data, {'P1':[(50,80)]}, {'P1':wrong['points']}, predicate)
        assert found['P1']['points'] == pillar['points']
        assert found['P1']['evidence']['dimension_match']


def test_recurrence_does_not_discard_dimensioned_minority_and_no_duplicate_owner():
    polys = [rectangle(300*i,0,20,100,'STYLE_MAIN') for i in range(3)]
    polys += [rectangle(900,0,20,100,'STYLE_MAIN'), rectangle(930,0,30,60,'STYLE_MINORITY')]
    names = {f'P{i+1}':[(300*i-10,40)] for i in range(4)}
    names['P5']=[(970,40)]
    texts = [dict(text=name,pos=ps[0],height=10) for name,ps in names.items()]
    texts += [dict(text='20/100' if name!='P5' else '30/60',pos=(ps[0][0],25),height=10) for name,ps in names.items()]
    result = reassociate(dict(polylines=polys,texts=texts), names, {}, predicate)
    assert len(result)==5
    assert len({v['source_id'] for v in result.values()})==5
    assert result['P5']['evidence']['source_layer']=='STYLE_MINORITY'


def test_ambiguous_candidates_are_not_arbitrarily_owned():
    data=dict(polylines=[rectangle(-40,-20,20,40,'X'),rectangle(20,-20,20,40,'X')],texts=[])
    assert reassociate(data, {'P1':[(0,0)]}, {}, predicate)=={}


def test_u_preserves_notch_and_circle_is_sa_only_with_true_contact_angle():
    u=[(0,0),(100,0),(100,100),(80,100),(80,20),(20,20),(20,100),(0,100),(0,0)]
    assert PillarPerspectiveMapper.identify_shape(u)[0]=='Em U'
    points=[(30*math.cos(i*math.tau/64),30*math.sin(i*math.tau/64)) for i in range(64)]
    circle=dict(name='P1',points=points,classification='SEGUE')
    assert PillarPerspectiveMapper.identify_shape(points)[0]=='Circular'
    assert circular_measurements(points)['diameter']==60
    assert not eligible(circle)
    assert eligible(dict(points=u,classification='SEGUE'))
    state=dict(pilares=[circle],segmentos=dict(fundo=[dict(points=rectangle(30,-5,40,10,'')['points'],beam_name='V1')]))
    annotate_circular_state(state)
    contacts=circle['circular_geometry']['beam_contacts']
    assert len(contacts)==1 and contacts[0]['angle_deg']==0
    state['segmentos']['fundo'][0]['points']=rectangle(31,-5,40,10,'')['points']
    annotate_circular_state(state)
    assert not circle['circular_geometry']['beam_contacts']
