from copy import deepcopy
from shapely.geometry import box, mapping, shape
from portal.app.preprocessamento.beam_junction_continuity import propagate_junctions
from portal.app.preprocessamento.segment_levels import inherited, sync


def fixture():
    target=dict(segment_id='short',beam_name='V1',height_cm=55,points=list(box(0,0,19,5).exterior.coords))
    anchor=dict(segment_id='long',beam_name='V1',height_cm=55,points=list(box(0,24,19,124).exterior.coords))
    cross=dict(segment_id='cross',beam_name='V2',height_cm=55,points=list(box(-100,5,100,24).exterior.coords))
    shapes={f['segment_id']:shape({'type':'Polygon','coordinates':[f['points']]}) for f in (target,anchor)}
    walls=[]
    for x in (0,19):
        walls += [dict(a=(x,0),b=(x,5),handle=f's{x}'),dict(a=(x,24),b=(x,124),handle=f'l{x}')]
        for y in (5,24):walls.append(dict(a=(x,y),b=(-100 if x==0 else 100,y),handle=f'c{x}-{y}'))
    records={f['segment_id']:dict(fact_id=f['segment_id'],value=855.25,status='estimated',method='estimated',
        confidence_pct=30,evidence_ids=[],warnings=[],unit='m',datum_id='datum') for f in (target,anchor)}
    cuts=[]
    for fund,profile in ((anchor,box(0,30,19,85)),(cross,box(-80,5,-25,24))):
        proof=dict(height_cm=55,beam_name=fund['beam_name'])
        fact=dict(fact_id='cut-'+fund['segment_id'],value=855.25,status='sa_evidence',method='cut_geometry_on_fv',
            confidence_pct=95,evidence_ids=['original'],warnings=[],unit='m',datum_id='datum',
            cut_profile_geometry=mapping(profile),cut_height_evidence=proof)
        cuts.append((profile,fact))
    return [target,anchor],[target,anchor,cross],records,shapes,cuts,walls


def test_measured_junction_requires_two_independent_anchors_and_original_corners(tmp_path,monkeypatch):
    source=tmp_path/'source';source.write_text('source')
    funds,all_funds,records,shapes,cuts,walls=fixture()
    from portal.app.preprocessamento import oriented_beam_section
    monkeypatch.setattr(oriented_beam_section,'_source_evidence',lambda *args:([],walls))
    propagate_junctions(funds,all_funds,records,shapes,cuts,source,[],inherited,sync)
    assert records['short']['method']=='measured_four_corner_beam_junction'
    assert records['short']['source_fact_ids']==['cut-cross','cut-long']
    assert records['short']['status']=='sa_evidence'
    assert records['short']['previous_level_evidence']['status']=='estimated'


def test_junction_blocks_missing_corner_disagreeing_datum_depth_and_paint(tmp_path,monkeypatch):
    source=tmp_path/'source';source.write_text('source')
    from portal.app.preprocessamento import oriented_beam_section
    for blocker in ('corner','value','datum','unit','depth','paint','missing_anchor','cut_conflict','numeric_depth'):
        funds,all_funds,records,shapes,cuts,walls=fixture();paints=[]
        if blocker=='corner':walls.pop()
        if blocker=='value':cuts[1][1]['value']+=.03
        if blocker=='datum':cuts[1][1]['datum_id']='other'
        if blocker=='unit':cuts[1][1]['unit']='cm'
        if blocker=='depth':all_funds[-1]['height_cm']=60
        if blocker=='paint':paints=[box(-50,5,50,24)]
        if blocker=='missing_anchor':cuts.pop()
        if blocker=='cut_conflict':cuts[1][1].update(value=None,status='conflict')
        if blocker=='numeric_depth':cuts[1][1]['cut_height_evidence']['height_cm']=60
        monkeypatch.setattr(oriented_beam_section,'_source_evidence',lambda *args:([],walls))
        before=deepcopy(records)
        propagate_junctions(funds,all_funds,records,shapes,cuts,source,paints,inherited,sync)
        assert records==before,blocker
