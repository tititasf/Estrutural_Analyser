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


def test_unknown_inner_region_uses_its_own_wing_without_changing_principal():
    items,context,target=wing_fixture('unknown',None,0)
    original=deepcopy(context['state']['slabs'][1]['points'])
    target.update(field='slab_region_level',region_id='thin',region_height_cm=13,
                  region_geometry=mapping(Polygon(original)))
    slab=context['state']['slabs'][1]
    slab.update(points=[[50,0],[120,0],[120,80],[50,80],[50,0]],
                slab_steps=[dict(uid='thin',height_cm=13,points=original)])
    slab['fields']['laje_dim']='h=12'
    principal=dict(fact_id='principal',field='slab_level',value=852.25,status='sa_evidence')
    items['T']['levels'].append(principal)
    resolve_missing_slab_cut_regions(items,context)
    assert target['value']==852.19 and target['source_fact_ids']==['source']
    assert shape(target['target_geometry']).equals(Polygon(original))
    assert principal['value']==852.25
    assert 'level_review' not in items['T']
    assert items['T']['region_level_reviews']['thin']['value']==852.19


def test_unknown_region_fact_is_retained_without_inventing_level():
    step=dict(uid='thin',points=[[0,0],[10,0],[10,10],[0,10],[0,0]],
              height_cm=10,owner_height_cm=12,level_m=None,owner_level_m=None,
              evidence_handles=[],evidence_checks={})
    context=dict(evidence_id='collection',state=dict(slabs=[dict(name='T',
        points=[[0,0],[20,0],[20,20],[0,20],[0,0]],slab_steps=[step])]))
    item=dict(item_id='T',levels=[])
    add_slab_region_facts({'T':item},context)
    assert len(item['levels'])==1
    fact=item['levels'][0]
    assert fact['value'] is None and fact['status']=='unknown'
    assert fact['region_height_cm']==10 and fact['region_id']=='thin'
    assert step['level_m'] is None


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


@pytest.mark.parametrize('dependency', ['source_fact_ids', 'derived_from'])
def test_relative_wing_rejects_transitive_self_confirmation(dependency):
    items,context,target=wing_fixture()
    source=items['S']['levels'][0]
    source[dependency]=['bridge']
    items['T']['levels'].append(dict(fact_id='bridge',field='audit', **{dependency:['target']}))
    before=deepcopy(target)
    resolve_missing_slab_cut_regions(items,context)
    assert target==before


def test_relative_wing_rejects_existing_cycle_in_source_chain():
    items,context,target=wing_fixture()
    items['S']['levels'][0]['source_fact_ids']=['bridge']
    items['T']['levels'].append(dict(fact_id='bridge',field='audit',source_fact_ids=['source']))
    before=deepcopy(target)
    resolve_missing_slab_cut_regions(items,context)
    assert target==before


def test_relative_wing_rejects_cycle_through_other_class():
    items,context,target=wing_fixture()
    items['S']['levels'][0]['source_fact_ids']=['beam']
    resolve_missing_slab_cut_regions(items,context, {
        'beam':dict(fact_id='beam',source_fact_ids=['target'])})
    assert target['confidence_pct']==55 and target['status']=='inferred'


def test_relative_wing_preserves_acyclic_derived_source():
    items,context,target=wing_fixture()
    items['S']['levels'][0]['source_fact_ids']=['root']
    resolve_missing_slab_cut_regions(items,context, {
        'root':dict(fact_id='root',evidence_ids=['cad:A'])})
    assert target['value']==852.19 and target['confidence_pct']==85.5
    assert target['source_fact_ids']==['source']


def test_bounded_measured_wing_corrects_only_unmeasured_convention_with_traced_root():
    items, context, target = wing_fixture(value=852.16, confidence=70)
    target['method'] = 'slab_neighbor_continuity_without_step_cut'
    items['S']['levels'][0].update(status='inferred', source_fact_ids=['root'])
    root = dict(fact_id='root', field='slab_level', value=852.16, unit='m',
                method='cad_level_inside_slab', status='sa_evidence', evidence_ids=['cad:A'])
    resolve_missing_slab_cut_regions(items, context, {'root':root}, allow_traced_inferred=True)
    assert target['value'] == 852.19
    assert target['previous_level_evidence']['value'] == 852.16
    assert 'measured_wing_supersedes_neighbor_convention' in target['warnings']


@pytest.mark.parametrize('blocker', ['cycle', 'missing', 'estimate', 'human_target', 'measured_target'])
def test_bounded_reconciliation_rejects_unrooted_or_self_confirming_feedback(blocker):
    items, context, target = wing_fixture(value=852.16, confidence=70)
    target['method'] = 'slab_neighbor_continuity_without_step_cut'
    source = items['S']['levels'][0]
    source.update(status='inferred', source_fact_ids=['root'])
    root = dict(fact_id='root', field='slab_level', value=852.16, unit='m',
                method='cad_level_inside_slab', status='sa_evidence', evidence_ids=['cad:A'])
    if blocker == 'cycle': root['source_fact_ids'] = ['target']
    if blocker == 'estimate': root['status'] = 'estimated'
    if blocker == 'human_target': target['status'] = 'human_review'
    if blocker == 'measured_target': target['method'] = 'scoped_cut_wing_relative_delta_cm'
    before = deepcopy(target)
    resolve_missing_slab_cut_regions(items, context, {} if blocker=='missing' else {'root':root},
                                    allow_traced_inferred=True)
    assert target == before


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
