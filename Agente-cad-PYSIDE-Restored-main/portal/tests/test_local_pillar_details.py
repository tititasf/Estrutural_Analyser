from copy import deepcopy
from portal.app.preprocessamento.adapters.local_pillar_details import bind_region, crosscheck_sa_details


def fixture():
    points=[[0,0],[165,0],[165,19],[19,19],[19,218],[0,218],[0,0]]
    pillars=[dict(name=n,points=points) for n in ('P26','P27')]
    contour=dict(handle='original',points=[[x*2+1000,y*2+2000] for x,y in points])
    texts=[dict(handle='caption',text='P26=P27',position=[1100,2500]),
           dict(handle='scale',text='ESC.:1:25',position=[1100,2470])]
    texts += [dict(handle=str(i),text=str(v),position=[0,0]) for i,v in enumerate((165,19,146,199,19,218))]
    return dict(bbox=[900,1900,1400,2600]),[contour],texts,pillars


def test_detail_inventory_candidate_does_not_certify_dimensions_or_create_pillar():
    region,contours,texts,pillars=fixture();before=deepcopy(pillars)
    record=bind_region(region,contours,texts,pillars)
    assert record['status']=='candidate'
    assert record['pillar_names']==['P26','P27']
    assert record['candidate_drawing_to_physical_factor']==2
    assert record['canonical_correspondence_dimensions_cm']['width']==165
    assert record['canonical_correspondence_dimensions_cm']['height']==218
    assert record['creates_plan_pillar'] is False
    assert record['dimension_chain_bound'] is False
    assert record['consumer_authorized'] is False
    assert pillars==before
    texts[1]['text']='ESC.:1:500'
    assert bind_region(region,contours,texts,pillars)['candidate_drawing_to_physical_factor']==2


def test_candidate_requires_numeric_copresence_unique_caption_and_correct_canonical_shape():
    for blocker in ('dimension','caption','ambiguous','contour','owner','duplicate'):
        region,contours,texts,pillars=fixture()
        if blocker=='dimension':texts.pop()
        if blocker=='caption':texts[0]['text']='P26'
        if blocker=='ambiguous':texts.append(dict(handle='another',text='P26=P27',position=[0,0]))
        if blocker=='contour':contours[0]['points'][1][0]+=5
        if blocker=='owner':pillars.pop()
        if blocker=='duplicate':contours.append(deepcopy(contours[0]))
        assert bind_region(region,contours,texts,pillars)['status']=='unresolved',blocker


def test_incidental_numbers_and_duplicate_labels_never_authorize_binding():
    region,contours,texts,pillars=fixture()
    # These numeric labels are deliberately unrelated and outside any chain.
    texts += [dict(t,handle='incidental-'+t['handle']) for t in texts[2:]]
    record=bind_region(region,contours,texts,pillars)
    assert record['status']=='candidate'
    assert record['dimension_chain_bound'] is False
    assert record['consumer_authorized'] is False


def test_two_matching_figures_remain_ambiguous():
    region,contours,texts,pillars=fixture()
    second=deepcopy(contours[0]);second['handle']='second-original'
    second['points']=[[x+400,y] for x,y in second['points']]
    assert bind_region(region,contours+[second],texts,pillars)['status']=='unresolved'


def dimension_fixture():
    points=[[0,0],[20,0],[20,40],[0,40]]
    pillars=[dict(name=n,points=[[x/2,y/2] for x,y in points]) for n in ('P26','P27')]
    texts=[dict(handle='caption',text='P26=P27',position=[0,0])];lines=[]
    for index,(a,b) in enumerate(zip(points,points[1:]+points[:1])):
        axis=0 if a[1]==b[1] else 1;perp=1-axis
        offset=-5 if index in (0,3) else 5
        ends=[]
        for j,vertex in enumerate((a,b)):
            end=list(vertex);end[perp]+=offset;ends.append(end)
            near=list(vertex);near[perp]+=1 if offset>0 else -1
            far=list(end);far[perp]+=1 if offset>0 else -1
            lines.extend([dict(handle=f'{index}-{j}-ext',start=near,end=far),
                dict(handle=f'{index}-{j}-tick',start=[end[0]-1,end[1]-1],end=[end[0]+1,end[1]+1]),
                dict(handle=f'{index}-{j}-marker',start=vertex,end=vertex)])
        lines.append(dict(handle=f'{index}-spine',start=ends[0],end=ends[1]))
        pos=[(ends[0][k]+ends[1][k])/2 for k in (0,1)];pos[perp]+=1
        texts.append(dict(handle=f'{index}-label',text=str(abs(a[axis]-b[axis])/2),position=pos,height=4,rotation=axis*90))
    return dict(bbox=[-10,-10,30,50]),[dict(handle='contour',points=points)],texts,pillars,lines


def test_original_dimension_chains_authorize_only_when_complete_and_consistent():
    region,contours,texts,pillars,lines=dimension_fixture()
    record=bind_region(region,contours,texts,pillars,lines)
    assert record['status']=='proved'
    assert record['consumer_authorized'] and record['dimension_chain_bound']
    assert record['drawing_to_physical_factor']==2
    assert len(record['dimension_chain_proof']['chains'])==4
    no_markers=[l for l in lines if not l['handle'].endswith('marker')]
    assert bind_region(region,contours,texts,pillars,no_markers)['status']=='candidate'
    # Both parallel vertical dimensions conflict with the horizontal ratio.
    for text in texts:
        if text.get('rotation')==90:text['text']='10'
    assert bind_region(region,contours,texts,pillars,lines)['status']!='proved'


def test_actual_sa_crosscheck_blocks_revision_owner_and_geometry_conflicts_without_mutation():
    region,contours,texts,pillars,lines=dimension_fixture()
    record=bind_region(region,contours,texts,pillars,lines);record['source_revision']='exact'
    inventory=dict(records=[record]);report={p['name']:deepcopy(p) for p in pillars};before=deepcopy(report)
    receipt=crosscheck_sa_details(inventory,report,'exact')
    assert receipt['status']=='checked' and len(receipt['consumer_calls'])==2
    assert report==before
    assert len(crosscheck_sa_details(inventory,report,'stale')['blocked'])==2
    report.pop('P27')
    assert crosscheck_sa_details(inventory,report,'exact')['blocked'][0]['reason']=='actual_sa_owner_missing_or_ambiguous'
    report['P26']['points'][1][0]+=1
    assert len(crosscheck_sa_details(inventory,report,'exact')['blocked'])==2


def test_detector_dependency_failure_is_a_blocking_issue_not_an_empty_success(tmp_path):
    from portal.app.preprocessamento.adapters.local_pillar_details import inventory_local_details
    source=tmp_path/'untouched.dxf';source.write_bytes(b'original source')
    inventory=inventory_local_details(source,[],detection={'error':'required detector dependency unavailable'})
    assert inventory['status']=='unavailable'
    receipt=crosscheck_sa_details(inventory,{},inventory['source_revision'])
    assert receipt['status']=='blocked'
    assert receipt['blocked'][0]['reason']=='detail_region_detection_unavailable'
    assert source.read_bytes()==b'original source'


def chain_fixture():
    region,contours,texts,pillars=fixture()
    texts=texts[:2];lines=[];points=contours[0]['points']
    for i,(a,b) in enumerate(zip(points,points[1:])):
        axis=0 if a[1]==b[1] else 1;perp=1-axis
        ends=[]
        for j,v in enumerate((a,b)):
            end=list(v);end[perp]+=20;ends.append(end)
            near=list(v);near[perp]+=1
            far=list(end);far[perp]+=2
            lines += [dict(handle=f'm{i}{j}',start=list(v),end=list(v)),
                      dict(handle=f'e{i}{j}',start=near,end=far),
                      dict(handle=f't{i}{j}',start=[end[0]-2,end[1]-2],end=[end[0]+2,end[1]+2])]
        lines.append(dict(handle=f's{i}',start=ends[0],end=ends[1]))
        pos=[(ends[0][0]+ends[1][0])/2,(ends[0][1]+ends[1][1])/2];pos[perp]+=1
        texts.append(dict(handle=f'n{i}',text=str(abs(a[axis]-b[axis])/2),position=pos,height=4,rotation=axis*90))
    return region,contours,texts,pillars,lines


def test_complete_original_chains_measure_scale_independently_and_preserve_state():
    args=chain_fixture();before=deepcopy(args)
    record=bind_region(*args)
    assert record['status']=='proved'
    assert record['dimension_chain_bound'] is True
    assert record['drawing_to_physical_factor']==2
    assert len(record['dimension_chain_proof']['chains'])==6
    assert record['consumer_authorized'] is True
    assert record['creates_plan_pillar'] is False
    assert args==before


def test_missing_tick_extension_marker_wrong_rotation_or_incidental_duplicate_blocks_proof():
    for blocker in ('tick','extension','marker','rotation','duplicate','displaced','conflict'):
        args=list(chain_fixture());texts=args[2];lines=args[4]
        if blocker in ('tick','extension','marker'):
            prefix={'tick':'t','extension':'e','marker':'m'}[blocker]
            target=next(l for l in lines if l['handle']==prefix+'00')
            if blocker=='marker':
                lines[:]=[l for l in lines if not (l['start']==target['start'] and l['end']==target['end'])]
            else:
                lines[:]=[l for l in lines if l['handle']!=prefix+'00']
        elif blocker=='rotation':texts[2]['rotation']=90
        elif blocker=='duplicate':texts.append(dict(texts[2],handle='duplicate-numeric'))
        elif blocker=='displaced':texts[2]['position'][1]+=100
        elif blocker=='conflict':texts[2]['text']='164'
        record=bind_region(*args)
        assert record['status']!='proved',blocker
        if record['status']=='candidate':assert record['dimension_chain_bound'] is False
