from copy import deepcopy
from types import SimpleNamespace

import pytest

from portal.app.structural_cut_overlay import (
    collect_sections, compare_sections, slab_section_drawing, viewer_groups,
)


def test_inverted_soffit_highlight_requires_full_local_confirmed_coverage():
    contract = dict(beam_type='inverted', form_role='top_cap', width_cm=19,
                    height_cm=120, base_level_m=852.06, top_level_m=853.26,
                    section_semantics=dict(confirmed=True))
    other = dict(contract, height_cm=71, top_level_m=852.77)
    entries = [dict(beam='VX', section_contract=c,
                    pairs=[dict(start=[a,0], end=[b,0])])
               for a,b,c in [(0,60,contract), (60,100,other)]]
    items = [dict(beam_name='VX', pontos_dxf=p)
             for p in [[[0,0],[100,0],[100,19],[0,19]],
                       [[0,200],[100,200],[100,219],[0,219]],
                       [[0,0],[120,0],[120,19],[0,19]]]]
    groups = [dict(grupo='fundos', itens=items)]
    inventory = dict(entries=[], physical_entries=entries, blocked=[])
    result = viewer_groups(None, 'floor', {}, None, groups, inventory=inventory)
    rendered = result[0]['itens']
    assert rendered[0]['highlight_color'] == '#ff4545'
    assert rendered[0]['form_role'] == 'top_cap'
    assert all('highlight_color' not in i for i in rendered[1:])
    assert 'highlight_color' not in items[0]
    entries[0]['section_contract']['section_semantics']['confirmed'] = False
    result = viewer_groups(None, 'floor', {}, None, groups, inventory=inventory)
    assert 'highlight_color' not in result[0]['itens'][0]


def data(vertical=False):
    pair = dict(start=[0,0],end=[100,0],length_cm=100,b_id='B',a_id='A',a_index=1,b_index=2)
    b = [[100,19],[0,19]]
    if vertical:
        pair.update(end=[0,100]); b=[[-19,100],[-19,0]]
    cut = dict(id='cut',kind='calculated',beam='V1',width_cm=19,beam_height_cm=55,
               profiles={s:dict(level=852,slabs=[]) for s in ('A','B')},pairs=[pair],
               layers={'n3_cut':dict(fingerprint='profile-19x55')})
    return dict(cut_views=[cut],sides={'B':dict(segments=[dict(id='B',points=b)])})


@pytest.mark.parametrize('vertical', [False, True])
def test_shared_inventory_deduplication_and_orange_geometry(tmp_path, monkeypatch, vertical):
    monkeypatch.setattr('portal.app.lv_ficha.montar_ficha_lv', lambda *a, **k: data(vertical))
    state = dict(segmentos={f'lateral_a_{m}':[dict(beam_name='V1')] for m in ('para','passa')})
    inventory = collect_sections(tmp_path, 'floor', state)
    assert inventory['total'] == inventory['calculated'] == 1
    assert len(inventory['physical_entries'])==2
    assert inventory['entries'][0]['behaviors'] == ['passa', 'para']
    transform = SimpleNamespace(dxf_para_px=lambda x,y: [2*x, -2*y])
    groups = viewer_groups(tmp_path,'floor',state,transform,[],inventory=inventory)
    group = next(g for g in groups if g['grupo']=='cortes_interpretados')
    assert group['total']==1
    drawing = group['itens'][0]['section_drawing']
    assert drawing['primitives'][0]['color']=='#ff9a1f'
    # Mapping keeps the exact A->B normal and full physical dimensions.
    expected = inventory['entries'][0]['drawing']['primitives'][0]['points']
    assert drawing['primitives'][0]['points']==[[2*x,-2*y] for x,y in expected]
    assert inventory['entries'][0]['drawing']['primitives'][0]['color']=='#a8fff0'


def test_preprocessing_slab_drawing_works_before_production_sa():
    pts=[[0,0],[100,0],[100,20],[50,20],[50,12],[0,12]]
    slab=dict(name='L1')
    step=dict(points=[[50,-50],[110,-50],[110,50],[50,50]],height_cm=20,owner_height_cm=12)
    drawing=slab_section_drawing(slab,step,dict(points=pts))
    frozen=dict(entries=[],blocked=[],slab_sections=[dict(slab='L1',points=pts,drawing=drawing)])
    result=viewer_groups(None,'floor',{},SimpleNamespace(dxf_para_px=lambda x,y:[x,-y]),[],inventory=frozen)
    originals=next(g for g in result if g['grupo']=='cortes')['itens']
    assert len(originals)==1 and originals[0]['detail_status']=='dimensioned'
    assert {p['text'] for p in originals[0]['section_drawing']['primitives'] if p['kind']=='text'} >= {'12','20'}


def test_ephemeral_second_pass_uses_its_own_beam_records():
    from portal.app.lv_ficha import _beam_records
    record=dict(id='local',project_id='same-source',fields={'viga_largura':'19'})
    assert _beam_records({'_section_beam_records':{'local':record}},[]) == {'local':record}


def test_grouped_shapes_keep_each_physical_pairs_absolute_level(tmp_path, monkeypatch):
    source = data()
    cut = source['cut_views'][0]
    cut['pairs'][0]['profiles'] = {s:dict(level=852.12, level_source='lv_cell_slabs', slabs=[])
                                  for s in ('A','B')}
    second = deepcopy(cut['pairs'][0])
    second.update(start=[100,0], end=[200,0])
    second['profiles'] = {s:dict(level=852.19, level_source='lv_cell_slabs', slabs=[])
                          for s in ('A','B')}
    cut['pairs'].append(second)
    source['sides']['B']['segments'][0]['points'] = [[200,19],[0,19]]
    monkeypatch.setattr('portal.app.lv_ficha.montar_ficha_lv', lambda *a, **k: deepcopy(source))
    inventory = collect_sections(tmp_path,'floor',dict(segmentos={'lateral_a_passa':[dict(beam_name='V1')]}))
    contracts = [e['section_contract'] for e in inventory['physical_entries']]
    assert [(c['base_level_m'],c['top_level_m']) for c in contracts] == [(851.57,852.12),(851.64,852.19)]
    assert [len(e['pairs']) for e in inventory['physical_entries']] == [1,1]


def test_ephemeral_records_take_precedence_over_existing_database(tmp_path):
    from portal.app.lv_ficha import _beam_records
    existing = tmp_path/'unrelated.sqlite'
    existing.touch()
    record = dict(id='local', project_id='current-source')
    assert _beam_records(dict(db_path=str(existing),
        _section_beam_records={'local':record}),[]) == {'local':record}


def test_second_pass_compares_anchor_and_profile_without_database_ids(tmp_path, monkeypatch):
    monkeypatch.setattr('portal.app.lv_ficha.montar_ficha_lv', lambda *a, **k: data())
    state=dict(segmentos={'lateral_a_passa':[dict(beam_name='V1')]})
    frozen=collect_sections(tmp_path,'floor',state)
    current=deepcopy(frozen)
    current['entries'][0]['pairs'][0]['a_id']='other-database'
    frozen['entries'][0]['section_contract']['section_semantics']=dict(beam_type='inverted',
        source_section_id='old',symbol_handles=['old'],frame=dict(base_center=[0,0]))
    current['entries'][0]['section_contract']['section_semantics']=dict(beam_type='inverted',
        source_section_id='new',symbol_handles=['new'],frame=dict(base_center=[100,0]))
    assert compare_sections(frozen,current)['status']=='matches'
    changed_levels=deepcopy(current)
    changed_levels['entries'][0]['section_contract']['top_level_m']=853.26
    assert compare_sections(frozen,changed_levels)['status']=='divergent'
    changed=deepcopy(current)
    changed['entries'][0]['drawing']['primitives'][0]['points'][0][0] += 2
    assert compare_sections(frozen,changed)['status']=='divergent'
    current['entries'][0]['drawing']['anchor'][0]+=1
    result=compare_sections(frozen,current)
    assert result['status']=='divergent' and result['only_sa']==result['only_preprocessing']==1


@pytest.mark.parametrize('vertical', [False, True])
def test_slab_step_measures_both_regions_and_preserves_cad(vertical):
    pts=[[0,0],[100,0],[100,20],[50,20],[50,12],[0,12]]
    region=[[50,-50],[110,-50],[110,50],[50,50]]
    if vertical:
        pts=[[y,x] for x,y in pts]; region=[[y,x] for x,y in region]
    section=dict(points=pts)
    step=dict(points=region,height_cm=20,owner_height_cm=12)
    drawing=slab_section_drawing(dict(name='L1'),step,section)
    assert drawing['primitives'][0]['points']==pts
    assert sorted(p['text'] for p in drawing['primitives'] if p.get('size')==5)==['12','20']
    title=next(p for p in drawing['primitives'] if p.get('size')==8)
    assert title['points'][0][1]>max(p[1] for p in pts)


def test_original_is_upgraded_once_and_pending_has_external_label(tmp_path):
    raw = dict(pts=[[0,0],[19,0],[19,55],[0,55]])
    drawing = dict(primitives=[dict(kind='polygon',points=raw['pts'],color='#a8fff0')])
    inventory = dict(entries=[dict(kind='identified',beam='V1',source_cut=raw,drawing=drawing)],blocked=[])
    groups=[dict(grupo='cortes',itens=[dict(pontos_dxf=raw['pts'],rotulo='V1',fora_do_frame=False),
                dict(pontos_dxf=[[100,0],[119,0],[119,55],[100,55]],rotulo='V2',fora_do_frame=False)])]
    result=viewer_groups(tmp_path,'floor',{},SimpleNamespace(dxf_para_px=lambda *p: list(p)),groups,inventory=inventory)
    assert result[0]['total']==2 and result[-1]['total']==0
    pending=result[0]['itens'][1]
    assert pending['detail_status']=='pending'
    label=pending['section_drawing']['primitives'][-1]
    assert label['points'][0][1]>55
    assert not groups[0]['itens'][0].get('section_drawing')


@pytest.mark.parametrize('vertical', [False, True])
def test_para_passa_same_section_with_different_midpoint_is_drawn_once(tmp_path, monkeypatch, vertical):
    def build(*args, **kwargs):
        result = data(vertical)
        if args[3] == 'para':
            pair = result['cut_views'][0]['pairs'][0]
            pair['end'] = [0, 60] if vertical else [60, 0]
            pair['length_cm'] = 60
        return result
    monkeypatch.setattr('portal.app.lv_ficha.montar_ficha_lv', build)
    state = dict(segmentos={f'lateral_a_{m}':[dict(beam_name='V1')] for m in ('para','passa')})
    inventory = collect_sections(tmp_path, 'floor', state)
    assert inventory['total'] == 1
    entry = inventory['entries'][0]
    assert entry['behaviors'] == ['passa', 'para']
    assert entry['alternate_presentations'][0]['anchor'] != entry['drawing']['anchor']


def test_frozen_duplicates_are_coalesced_but_distinct_stations_and_dimensions_remain(tmp_path, monkeypatch):
    from portal.app.structural_cut_overlay import deduplicate_sections
    monkeypatch.setattr('portal.app.lv_ficha.montar_ficha_lv', lambda *a, **k: data(True))
    inventory = collect_sections(tmp_path, 'floor', dict(segmentos={'lateral_a_passa':[dict(beam_name='V1')]}))
    first = inventory['entries'][0]
    second = deepcopy(first)
    second.update(behavior='para', behaviors=['para'])
    second['drawing']['anchor'][1] -= 20
    for p in second['drawing']['primitives']:
        for q in p['points']:
            q[1] -= 20
    assert len(deduplicate_sections([first, second])) == 1
    frozen = dict(entries=[first, second], blocked=[])
    groups = viewer_groups(tmp_path, 'floor', {}, SimpleNamespace(dxf_para_px=lambda *p:list(p)), [], inventory=frozen)
    assert groups[-1]['total'] == 1
    different = deepcopy(second)
    different['drawing']['primitives'][0]['points'][0][0] += 1
    assert len(deduplicate_sections([first, different])) == 2
    distant = deepcopy(second)
    distant['pairs'][0].update(start=[0, 200], end=[0, 300])
    assert len(deduplicate_sections([first, distant])) == 2
