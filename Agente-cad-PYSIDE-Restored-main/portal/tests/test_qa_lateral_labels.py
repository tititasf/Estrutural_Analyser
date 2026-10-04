import copy
import xml.etree.ElementTree as ET
from portal.app.qa_versions import _lateral_label, NS


def test_segment_caption_fits_own_span_and_preserves_identity_and_cad():
    group=ET.Element('{'+NS+'}g')
    polygon=ET.SubElement(group,'{'+NS+'}polygon',{'points':'0,0 100,0 100,10 0,10'})
    before=ET.tostring(polygon)
    points=[[0,0],[100,0],[100,10],[0,10]]; original=copy.deepcopy(points)
    label=_lateral_label(group,points,'B','V301 SEG14-B',1000)
    assert label.text=='B14'
    assert label.find('{'+NS+'}title').text=='B V301 SEG14-B'
    assert label.get('text-anchor')=='middle'
    assert float(label.get('font-size')) > 3
    assert points==original and ET.tostring(polygon)==before


def test_adjacent_short_segment_labels_have_separate_horizontal_spans():
    group=ET.Element('{'+NS+'}g'); spans=[]
    for n in (14,15):
        x=(n-14)*10
        label=_lateral_label(group,[[x,0],[x+10,0],[x+10,2],[x,2]],'A',f'V301 SEG{n}-A',1000)
        half=float(label.get('font-size'))*.65*len(label.text)/2
        centre=float(label.get('x'))
        spans.append((centre-half,centre+half))
    assert spans[0][1]<spans[1][0]
