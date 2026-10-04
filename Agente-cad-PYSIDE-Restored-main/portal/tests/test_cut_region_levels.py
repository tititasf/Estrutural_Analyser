from portal.app.preprocessamento.segment_levels import resolve_missing_slab_cut_regions
from portal.app.preprocessamento.segment_levels import add_slab_region_facts
from src.core.slab_steps import apply_region_reviews
from shapely.geometry import Polygon,mapping,shape
from copy import deepcopy
import pytest


def test_broken_stem_preserves_relative_wings_and_uses_actual_region():
    source=dict(fact_id='region',field='slab_region_level',region_id='inner',
        region_geometry=mapping(Polygon([(0,0),(30,0),(30,40),(0,40)])),
        value=852.16,status='sa_evidence',confidence_pct=95,evidence_ids=['cad:level'],warnings=[])
    target=dict(fact_id='target',field='slab_level',value=None,status='unknown')
    items={'S':dict(levels=[source]),'T':dict(levels=[target])}
    cut=[[0,0],[80,0],[80,13],[50,13],[50,70],[30,65],[30,10],[0,10],[0,0]]
    context=dict(state=dict(slabs=[dict(name='S',points=[[0,0],[30,0],[30,40],[0,40],[0,0]],
        slab_steps=[dict(uid='inner',height_cm=10)],fields={}),
        dict(name='T',points=[[50,0],[80,0],[80,40],[50,40],[50,0]],fields={'laje_dim':'h=13'},
        cut_links={'cut_view_geom':[dict(original_pts=cut,points=cut,ficha={'side_a_laje_name':'WRONG'})]})]))
    resolve_missing_slab_cut_regions(items,context)
    assert target['value']==852.19
    assert target['source_fact_ids']==['region']
    assert target['cut_region_evidence'][0]['delta_cm']==3
    assert target['confidence_pct']==85.5
    assert Polygon(context['state']['slabs'][1]['points']).equals(
        shape(target['target_geometry']))
    # Distorted wing thickness is not an accepted geometric delta.
    target.update(value=None,status='unknown')
    context['state']['slabs'][1]['fields']['laje_dim']='h=12'
    resolve_missing_slab_cut_regions(items,context)
    assert target['value'] is None


def wing_fixture(status='inferred', value=852.19, confidence=55):
    source=dict(fact_id='source',field='slab_level',value=852.16,
        status='sa_evidence',confidence_pct=95,evidence_ids=['cad:A'],warnings=[])
    target=dict(fact_id='target',field='slab_level',value=value,status=status,
        confidence_pct=confidence,evidence_ids=['collection'],warnings=['source_slab_requires_review'])
    cut=[[0,0],[80,0],[80,13],[50,13],[50,70],[30,65],[30,10],[0,10],[0,0]]
    context=dict(state=dict(slabs=[
        dict(name='S',points=[[0,0],[30,0],[30,40],[0,40],[0,0]],fields={'laje_dim':'h=10'}),
        dict(name='T',points=[[50,0],[80,0],[80,40],[50,40],[50,0]],fields={'laje_dim':'h=13'},
             cut_links={'cut_view_geom':[dict(original_pts=cut)]})]))
    return {'S':dict(levels=[source]),'T':dict(levels=[target])},context,target


def test_existing_inference_reproved_by_independent_measured_wings():
    items,context,target=wing_fixture()
    resolve_missing_slab_cut_regions(items,context)
    assert target['value']==852.19 and target['confidence_pct']==85.5
    assert target['source_fact_ids']==['source']
    assert target['previous_level_evidence']['confidence_pct']==55
    assert target['warnings']==[]


@pytest.mark.parametrize('status,value,confidence', [
    ('human_review',852.19,100), ('conflict',852.19,20),
    ('sa_evidence',852.19,75), ('inferred',852.12,55), ('inferred',852.19,90)])
def test_reproof_preserves_protected_competing_or_stronger_values(status,value,confidence):
    items,context,target=wing_fixture(status,value,confidence)
    before=deepcopy(target)
    resolve_missing_slab_cut_regions(items,context)
    assert target==before


def test_inferred_source_cannot_bootstrap_reproof_or_form_cycle():
    items,context,target=wing_fixture()
    items['S']['levels'][0]['status']='inferred'
    before=deepcopy(target)
    resolve_missing_slab_cut_regions(items,context)
    assert target==before
    items['S']['levels'][0].update(status='sa_evidence',source_fact_ids=['target'])
    resolve_missing_slab_cut_regions(items,context)
    assert target==before


@pytest.mark.parametrize('blocked', [False,True])
def test_flat_bottom_region_tracks_measured_counterpart_without_self_confirmation(blocked):
    step=dict(uid='inner',points=[[0,0],[10,0],[10,10],[0,10],[0,0]],
        height_cm=10,owner_height_cm=13,level_m=852.16,owner_level_m=852.19,
        evidence_handles=['height','level','section'],sections=[{'handle':'section'}],
        method='scoped_level_and_flat_bottom_section',status='same_bottom',
        evidence_checks={'direct_internal_level':True,'direct_principal_level':False})
    if blocked:step['review_conflict']={'principal_level_m':853.19}
    context=dict(evidence_id='drawing',state=dict(slabs=[dict(name='S',
        points=[[0,0],[30,0],[30,30],[0,30],[0,0]],slab_steps=[step])]))
    item=dict(item_id='S',levels=[])
    add_slab_region_facts({'S':item},context)
    source,target=item['levels']
    assert source['confidence_pct']==95
    if blocked:
        assert target['confidence_pct']==65 and not target.get('source_fact_ids')
    else:
        assert target['confidence_pct']==85.5
        assert target['source_fact_ids']==[source['fact_id']]
        assert target['delta_cm']==3


@pytest.mark.parametrize('decision', ['D64-user-confirmation', None])
def test_owner_confirmed_flat_bottom_ties_principal_to_measured_step(decision):
    step=dict(uid='inner',points=[[0,0],[10,0],[10,10],[0,10],[0,0]],
        height_cm=10,owner_height_cm=13,level_m=852.16,owner_level_m=852.19,
        evidence_handles=['height','level'],sections=[],
        method='owner_confirmed_scoped_same_bottom',status='same_bottom',
        owner_review=dict(same_bottom=True,principal_level_m=852.19,decision_id=decision),
        evidence_checks={'direct_internal_level':True,'direct_principal_level':False})
    context=dict(evidence_id='drawing',state=dict(slabs=[dict(name='S',
        points=[[0,0],[30,0],[30,30],[0,30],[0,0]],slab_steps=[step])]))
    item=dict(item_id='S',levels=[])
    add_slab_region_facts({'S':item},context)
    source,target=item['levels']
    assert target['confidence_pct']==(85.5 if decision else 65)


def test_owner_same_bottom_fills_only_scoped_region_and_preserves_direct_conflict():
    step=dict(uid='region',height_cm=10,owner_height_cm=13,level_m=852.16,
        owner_level_m=None,evidence_checks={'direct_internal_level':True},evidence_handles=['A'])
    review={'region':dict(same_bottom=True,principal_level_m=852.19,decision_id='user-decision')}
    apply_region_reviews([step],review)
    assert step['owner_level_m']==852.19 and step['bottom_delta_m']==0
    review['region']['principal_level_m']=853.19
    apply_region_reviews([step],review)
    assert step['owner_level_m']==852.19 and step['review_conflict']


def rotated(points, sign):
    """sign=+1 rotates 90 deg counter-clockwise; -1 clockwise."""
    return [[-y, x] if sign > 0 else [y, -x] for x, y in points]


def rotated_fixture(section, sign, value=852.19):
    source=dict(fact_id='source',field='slab_level',value=852.16,
        status='sa_evidence',confidence_pct=95,evidence_ids=['cad:A'],warnings=[])
    target=dict(fact_id='target',field='slab_level',value=value,status='inferred' if value else 'unknown',
        confidence_pct=55 if value else 0,evidence_ids=['collection'],warnings=['source_slab_requires_review'])
    s=[[0,0],[30,0],[30,100],[0,100],[0,0]]; t=[[50,0],[80,0],[80,100],[50,100],[50,0]]
    cut=rotated(section,sign)
    context=dict(state=dict(slabs=[
        dict(name='S',points=rotated(s,sign),fields={'laje_dim':'h=10'}),
        dict(name='T',points=rotated(t,sign),fields={'laje_dim':'h=13'},
             cut_links={'cut_view_geom':[dict(original_pts=cut)]})]))
    return {'S':dict(levels=[source]),'T':dict(levels=[target])},context,target


# Normal beam: wings at the top, stem hanging below; T wing 3 cm above S.
NORMAL=[[0,60],[30,60],[30,18],[50,18],[50,60],[80,60],[80,73],[30,73],[30,70],[0,70],[0,60]]
# Inverted beam with a flat bottom (stem up): ambiguous once rotated.
INVERTED=[[0,0],[80,0],[80,13],[50,13],[50,70],[30,65],[30,10],[0,10],[0,0]]


@pytest.mark.parametrize('sign', [1, -1])
def test_rotated_section_reproves_existing_level_with_stem_orientation(sign):
    items,context,target=rotated_fixture(NORMAL,sign)
    resolve_missing_slab_cut_regions(items,context)
    assert target['value']==852.19 and target['confidence_pct']==85.5
    assert target['source_fact_ids']==['source']
    assert target['cut_region_evidence'][0]['section_drawing']=='rotated'
    assert target['cut_region_evidence'][0]['delta_cm']==pytest.approx(3)


@pytest.mark.parametrize('sign', [1, -1])
def test_rotated_ambiguous_or_new_value_abstains(sign):
    items,context,target=rotated_fixture(INVERTED,sign)
    before=deepcopy(target)
    resolve_missing_slab_cut_regions(items,context)
    assert target==before  # reading disagrees with the existing value: abstain
    items,context,target=rotated_fixture(NORMAL,sign,value=None)
    before=deepcopy(target)
    resolve_missing_slab_cut_regions(items,context)
    assert target==before  # a rotated drawing never introduces a new altitude
