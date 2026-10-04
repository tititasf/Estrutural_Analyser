from pathlib import Path


def test_fresh_local_cell_replaces_only_its_own_stale_derived_level():
    from portal.app.lv_ficha import _segment
    item = dict(item_id='A|beam|9|1', points=[[0,0],[100,0]],
                level_source='lv_cell_slabs',
                campos={'Segmento':9, 'Largura':'14/55', 'Nível':'852.15'},
                lv_cell={'level':'852.19', 'slabs':[{'name':'L317','level':'852.19','height':'h=13'}]})
    result = _segment(Path('.'), '13_PAV', 'lateral_a_para', item, include_svgs=False)
    assert result['level'] == 852.19
    assert item['campos']['Nível'] == '852.15'
    item['level_source'] = 'human_review'
    assert _segment(Path('.'), '13_PAV', 'lateral_a_para', item, include_svgs=False)['level'] == 852.15
import copy
from portal.app import lv_ficha


def test_current_link_cell_supersedes_stale_export_only_for_matching_span():
    item = dict(points=[[0, 0], [100, 0]], level_source='lv_cell_slabs',
                campos={'Segmento': 9, 'Largura': '14/55', 'Nível': '852.15'},
                lv_cell={'level': '852.15', 'slabs': [{'name': 'old', 'level': '852.15'}]})
    fresh = {'level': '852.19', 'slabs': [{'name': 'L317', 'level': '852.19', 'height': 'h=13'}]}
    row = {'points': [[100, 0], [0, 0]], 'lv_cell': fresh}
    record = {'links': {'viga_a_seg_9_comprimento_total': {'seg_side_a': [row]}}}
    before = copy.deepcopy((item, record))
    def project():
        return lv_ficha._segment(Path('.'), '13_PAV', 'lateral_a_para', item,
                                 include_svgs=False, beam_record=record)
    assert project()['level'] == 852.19
    assert project()['slabs'] == fresh['slabs']
    assert (item, record) == before
    row['points'] = [[100, 0], [200, 0]]
    assert project()['level'] == 852.15
    row['points'] = [[0, 0], [100, 0]]
    item['level_source'] = 'human_review'
    assert project()['level'] == 852.15
    assert project()['slabs'][0]['name'] == 'old'


def test_portal_projects_cell_slab_region_without_reversing_side(monkeypatch):
    monkeypatch.setattr(lv_ficha,'_touching_slabs',lambda *args,**kwargs:[{'name':'opposite','level':'852.12'}])
    item={'campos':{'Segmento':'1','Largura':'19/55','Comprimento':'100','Nível':'852.19'},
          'points':[[0,0],[100,0]],'lv_cell':{'level':'852.19',
          'slabs':[{'name':'own','level':'852.19','region_id':'principal'}]}}
    before=copy.deepcopy(item)
    data=lv_ficha._segment(Path('.'),'13_PAV','lateral_a_passa',item,include_svgs=False)
    assert data['level']==852.19
    assert data['slabs']==item['lv_cell']['slabs']
    assert item==before


def test_explicit_empty_cell_slab_set_is_not_replaced_by_other_side(monkeypatch):
    monkeypatch.setattr(lv_ficha,'_touching_slabs',lambda *args,**kwargs:[{'name':'opposite','level':'852.12'}])
    item={'campos':{'Segmento':'1','Largura':'19/55','Comprimento':'100'},
          'points':[[0,0],[100,0]],'lv_cell':{'slabs':[]}}
    data=lv_ficha._segment(Path('.'),'13_PAV','lateral_a_para',item,include_svgs=False)
    assert data['slabs']==[] and data['level'] is None
