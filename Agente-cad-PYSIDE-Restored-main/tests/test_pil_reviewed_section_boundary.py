import hashlib
import json
import pytest
from src.core.pil_qa_section_boundaries import reviewed_section_span, proved_section_cells


@pytest.mark.parametrize('failure', ['none', 'hash', 'authority', 'handle',
                                   'partial', 'closed', 'section', 'label_handle',
                                   'rotation', 'conflict', 'duplicate', 'anchor',
                                   'extended', 'reviewed_edge', 'unknown_kind',
                                   'partial_reviewed_edge'])
def test_human_boundary_requires_unchanged_original_and_bilateral_numbers(tmp_path, failure):
    source=tmp_path/'original.dxf';source.write_bytes(b'unchanged-original')
    review={'schema':'cad.original_beam_section_review/v1','authority':'human',
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'boundaries':[{'id':'local-review','verdict':'accepted','axis':'x',
                'boundary_handle':'cap','before':{'section':'19/120','section_handles':['left']},
                'after':{'section':'19/55','section_handles':['right']}}]}
    data={'axis':'x','positions':(10,29),'span':(20,120),'anchor':20,
          'closed_handles':set(),'tolerance_cm':.05,
          'walls':[dict(axis='y',pos=70,lo=10,hi=29,handle='cap')],
          'labels':[dict(text=s,handle=h,x=x,y=31,rotation=0,margin=4)
                    for s,h,x in [('19/120','left',40),('19/55','right',90)]]}
    if failure=='hash':review['source_sha256']='0'*64
    if failure=='authority':review['authority']='agent'
    if failure=='handle':review['boundaries'][0]['boundary_handle']='other'
    if failure=='partial':data['walls'][0]['lo']=15
    if failure=='closed':data['closed_handles']={'cap'}
    if failure=='section':review['boundaries'][0]['after']['section']='19/50'
    if failure=='label_handle':review['boundaries'][0]['before']['section_handles']=['other']
    if failure=='rotation':data['labels'][1]['rotation']=90
    if failure=='conflict':data['labels'].append(dict(text='19/80',handle='conflict',x=50,y=31,rotation=0,margin=4))
    if failure=='duplicate':review['boundaries'].append(dict(review['boundaries'][0]))
    if failure=='anchor':data['anchor']=50
    if failure in {'extended', 'reviewed_edge', 'unknown_kind', 'partial_reviewed_edge'}:
        data['walls'][0].update(lo=-20, hi=80)
    if failure in {'reviewed_edge', 'partial_reviewed_edge'}:
        review['boundaries'][0]['boundary_kind']='reviewed_region_edge'
    if failure=='unknown_kind':review['boundaries'][0]['boundary_kind']='anything'
    if failure=='partial_reviewed_edge':data['walls'][0]['lo']=15
    source.with_suffix('.beam-section-review.json').write_text(json.dumps(review))
    result=reviewed_section_span(source,**data)
    if failure in {'none', 'reviewed_edge'}:assert result['span']==(20,70) and result['authority']=='human'
    else:assert result is None
    if failure=='none':
        # Dimension/detail caps with empty cells must not become changes.
        walls=data['walls']+[dict(axis='y',pos=x,lo=10,hi=29,handle=str(x)) for x in (80,85)]
        cells=proved_section_cells(walls,data['labels'],axis='x',positions=(10,29),
            span=(20,120),closed_handles=set(),tolerance_cm=.05,source_path=source)
        assert cells['authority']=='human' and cells['handles']==['cap']
        assert [(c['span'],c['section']) for c in cells['cells']]==[((20,70),'19/120'),((70,120),'19/55')]
        assert proved_section_cells(walls,data['labels'],axis='x',positions=(10,29),
            span=(20,120),closed_handles=set(),tolerance_cm=.05) is None


@pytest.mark.parametrize('review', [[], None, {'boundaries': {}},
    {'boundaries': [None]}, {'boundaries': [{'before': []}]}])
def test_malformed_review_cannot_raise_or_approve(tmp_path, review):
    source=tmp_path/'original.dxf';source.write_bytes(b'original')
    if isinstance(review, dict):
        review.update(schema='cad.original_beam_section_review/v1', authority='human',
                      source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    source.with_suffix('.beam-section-review.json').write_text(json.dumps(review))
    assert reviewed_section_span(source, [], [], axis='x', positions=(0,19),
        span=(0,100), anchor=0, closed_handles=set(), tolerance_cm=.05) is None
