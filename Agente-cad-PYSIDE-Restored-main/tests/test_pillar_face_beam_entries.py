"""Face annotations must agree with the newly measured beam topology."""
from src.core.pillar_face_beams import enrich_pillar_report_with_beams
import pytest


@pytest.mark.parametrize('horizontal', [True, False])
def test_verified_fundo_subset_does_not_erase_original_bilateral_contact(horizontal):
    def pts(x0,y0,x1,y1):
        points=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
        return points if horizontal else [(y,x) for x,y in points]
    report={'P900':{'points':pts(100,100,220,119),'lajes':[]}}
    beam={'name':'V900','dim':'19/55','is_h':horizontal,
          'geometry':{'classified':{'seg_bottom':[
              {'points':pts(0,100,100,119)},
              {'points':pts(220,100,300,119)}]}},
          '_verified_wall_runs':[((0,100,100,119) if horizontal else
                                  (100,0,119,100),'19/55')]}
    enrich_pillar_report_with_beams(report,[beam])
    for face in ('C','D'):
        assert any(r['name']=='V900' and r['dim']=='19/55'
                   for r in report['P900']['face_beams'][face]['interior'])


def test_axial_contact_without_parallel_wall_hit_is_not_a_null_slab():
    report = {'P900': {'points': [(100, 100), (220, 100), (220, 119), (100, 119)],
                      'lajes': []}}
    beam = {'name': 'V900', 'dim': '19/55', 'is_h': True,
            'geometry': {'classified': {'seg_bottom': [
                {'points': [(0, 100), (100, 100), (100, 119), (0, 119)]},
                {'points': [(220, 100), (300, 100), (300, 119), (220, 119)]}]}}}
    enrich_pillar_report_with_beams(report, [beam])
    entries = {entry['side']: entry for entry in report['P900']['lajes']}
    for face in ('C', 'D'):
        assert entries[face]['content_type'] == 'viga'
        assert entries[face]['viga'] == {'name': 'V900', 'dim': '19/55'}


@pytest.mark.parametrize('horizontal', [True, False])
def test_bilateral_trace_uses_local_wall_section_at_each_cap(horizontal):
    def pts(x0, y0, x1, y1):
        points = [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
        return points if horizontal else [(y,x) for x,y in points]
    def box(x0,y0,x1,y1):
        return (x0,y0,x1,y1) if horizontal else (y0,x0,y1,x1)
    report = {'PX': {'points': pts(100,100,160,119), 'lajes': []}}
    beam = {'name':'VX', 'dim':'14/55', 'is_h':horizontal,
            'geometry':{'classified':{'seg_bottom':[
                {'points':pts(0,100,100,119)},
                {'points':pts(160,100,300,119)}]}},
            '_verified_wall_runs':[(box(50,100,100,119),'19/55'),
                                   (box(160,100,230,119),'19/65')]}
    enrich_pillar_report_with_beams(report, [beam])
    expected = {'C':'19/55','D':'19/65'} if horizontal else {'D':'19/55','C':'19/65'}
    for face, dim in expected.items():
        entries = report['PX']['face_beams'][face]['interior']
        assert [(e['name'], e['dim']) for e in entries] == [('VX', dim)]
        for long_face in ('A', 'B'):
            corners = [report['PX']['face_beams'][long_face][slot]
                       for slot in ('passa_esq', 'passa_dir')]
            assert [e['dim'] for e in corners if face in e['corner']] == [dim]


@pytest.mark.parametrize('horizontal', [True, False])
def test_bilateral_contact_does_not_borrow_section_from_distant_wall(horizontal):
    def pts(x0, y0, x1, y1):
        points = [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
        return points if horizontal else [(y,x) for x,y in points]
    def box(x0,y0,x1,y1):
        return (x0,y0,x1,y1) if horizontal else (y0,x0,y1,x1)
    report = {'PX': {'points': pts(100,100,160,119), 'lajes': []}}
    beam = {'name':'VX', 'dim':'19/55', 'is_h':horizontal,
            'geometry':{'classified':{'seg_bottom':[
                {'points':pts(0,100,100,119)},
                {'points':pts(160,100,300,119)}]}},
            '_verified_wall_runs':[(box(250,100,280,119),'19/90')]}
    enrich_pillar_report_with_beams(report, [beam])
    for face in ('C','D'):
        assert [e['dim'] for e in report['PX']['face_beams'][face]['interior']] == ['19/55']


def test_bilateral_contact_conflicting_local_sections_remain_unresolved():
    report = {'PX': {'points': [(100,100),(160,100),(160,119),(100,119)], 'lajes': []}}
    beam = {'name':'VX', 'dim':'19/55', 'is_h':True,
            'geometry':{'classified':{'seg_bottom':[
                {'points':[(0,100),(100,100),(100,119),(0,119)]},
                {'points':[(160,100),(300,100),(300,119),(160,119)]}]}},
            '_verified_wall_runs':[((50,100,100,119),'19/55'),
                                   ((70,100,100,119),'19/65')]}
    enrich_pillar_report_with_beams(report, [beam])
    assert report['PX']['face_beams']['C']['interior'][0]['dim'] == ''
    assert report['PX']['face_beams']['D']['interior'][0]['dim'] == '19/55'


@pytest.mark.parametrize('wall_shift', [0, 5])
def test_bilateral_contact_rejects_incompatible_global_or_nearby_parallel_section(wall_shift):
    report = {'PX': {'points': [(100,100),(160,100),(160,119),(100,119)], 'lajes': []}}
    beam = {'name':'VX', 'dim':'14/55', 'is_h':True,
            'geometry':{'classified':{'seg_bottom':[
                {'points':[(0,100),(100,100),(100,119),(0,119)]},
                {'points':[(160,100),(300,100),(300,119),(160,119)]}]}}}
    if wall_shift:
        beam['_verified_wall_runs'] = [((50,100+wall_shift,100,119+wall_shift),'19/90')]
    enrich_pillar_report_with_beams(report, [beam])
    for face in ('C','D'):
        assert report['PX']['face_beams'][face]['interior'][0]['dim'] == ''


def test_rejected_automatic_contact_does_not_leave_an_invented_slab():
    report = {'P900': {'points': [(0, 0), (19, 0), (19, 100), (0, 100)],
                      'lajes': [
                          {'side': 'C', 'laje': None, 'content_type': 'viga',
                           'viga': {'name': 'V900', 'dim': '19/55'},
                           'source': 'beam_wall_alignment'},
                          {'side': 'A', 'laje': 'L900', 'content_type': 'both',
                           'viga': {'name': 'V900', 'dim': '19/55'}}]}}
    enrich_pillar_report_with_beams(report, [
        {'name': 'V901', 'dim': '19/55', 'is_h': True,
         'points': [(500, 500), (600, 500), (600, 519), (500, 519)]}])
    entries = report['P900']['lajes']
    assert len(entries) == 1
    assert entries[0]['laje'] == 'L900'
    assert entries[0]['content_type'] == 'laje'
    assert 'viga' not in entries[0]
