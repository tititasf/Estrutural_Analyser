from portal.app.preprocessamento.sa_levels import resolved_inventory_item
from portal.app.preprocessamento.segment_levels import add_slab_region_facts


def test_inventory_points_to_collected_facts_not_obsolete_survey_ids():
    item=dict(item_id='x',level_fact_ids=['old'],segment_ids=['old-seg'],
              pre_sa_levels=[dict(fact_id='old')],levels=[dict(fact_id='new')],
              segments=[dict(segment_id='new-seg')])
    result=resolved_inventory_item(item)
    assert result['level_fact_ids']==['new']
    assert result['segment_ids']==['new-seg']
    assert result['pre_sa_levels']==item['pre_sa_levels']


def test_principal_region_does_not_conflict_with_inner_step_altitude():
    item=dict(item_id='slab',levels=[dict(fact_id='stored',field='slab_level',
        value=852.19,status='conflict',method='scoped_slab_principal_region',
        confidence_pct=20,warnings=['sa_differs_from_contained_plan_level']),
        dict(fact_id='inner-mark',field='slab_level',value=852.16,
             status='sa_evidence',method='cad_level_inside_slab',confidence_pct=95)])
    context=dict(evidence_id='collection',state=dict(slabs=[dict(name='L',
        points=[[0,0],[20,0],[20,20],[0,20],[0,0]],slab_steps=[dict(uid='step',
        points=[[0,0],[10,0],[10,10],[0,10],[0,0]],level_m=852.16,
        owner_level_m=852.19,evidence_handles=['h'],evidence_checks=dict(
            direct_internal_level=True,direct_principal_level=False))])]))
    add_slab_region_facts({'L':item},context)
    principal=item['levels'][0]
    assert principal['value']==852.19 and principal['status']=='inferred'
    assert principal['confidence_pct']==65
    assert principal['source_fact_ids']==['slab:region:principal']
    assert item['levels'][1]['value']==852.16
    # An actually disagreeing principal altitude remains a conflict.
    item['levels'][0].update(value=852.30,status='conflict',method='scoped_slab_principal_region')
    add_slab_region_facts({'L':item},context)
    assert item['levels'][0]['status']=='conflict'


def test_scoped_cut_level_reaches_sa_with_geometry_and_source_gates():
    from copy import deepcopy
    from shapely.geometry import Polygon,mapping
    from portal.app.preprocessamento.sa_levels import item_level_input,consume_item_levels
    points=[[0,0],[10,0],[10,10],[0,10],[0,0]]
    source=dict(fact_id='source',item_id='other',field='slab_region_level',value=852.16,status='sa_evidence',
                method='cad_level_inside_slab', evidence_ids=['cad:source-level'])
    target=dict(fact_id='target',item_id='slab',field='slab_level',value=852.19,unit='m',
        status='sa_evidence',method='scoped_cut_wing_relative_delta_cm',confidence_pct=85.5,
        evidence_ids=['cad:cut'],source_fact_ids=['source'],target_geometry=mapping(Polygon(points)),
        cut_region_evidence=[dict(source_fact_id='source',delta_cm=3)])
    package=dict(level_inventory=dict(items=[dict(item_id='slab',display_name='L',item_class='slab')]),levels=[source,target])
    levels=item_level_input(package)
    slab=dict(name='L',points=points,fields={})
    protected=deepcopy(slab); protected['validated_fields']=['laje_nivel']
    changed=deepcopy(slab); changed['points']=[[0,0],[11,0],[11,10],[0,10],[0,0]]
    assert consume_item_levels([protected,changed],levels)==[]
    assert consume_item_levels([slab],levels)
    assert slab['fields']['laje_nivel']=='852.19'
    assert slab['level_inference']['status']=='inferred'
    assert slab['level_inference']['confidence_pct']==85.5
    assert slab['level_inference']['source_fact_ids']==['source']
    source['status']='estimated'
    assert item_level_input(package)=={}
    source['status']='sa_evidence'; target['cut_region_evidence'][0]['delta_cm']=30
    assert item_level_input(package)=={}

