from copy import deepcopy
from types import SimpleNamespace

import pytest

from portal.app.structural_cut_overlay import (
    collect_sections, compare_sections, slab_section_drawing, viewer_groups,
)


def test_bad_item_does_not_stop_other_beam_sections(tmp_path, monkeypatch):
    calls = []
    def assemble(root, floor, name, mode, state, **kwargs):
        calls.append(name)
        if name == 'VER CORTE 1-1':
            raise ValueError('nome de viga lateral inválido')
        return dict(cut_views=[], sides={s: dict(segments=[]) for s in ('A','B')}, physical_cut_views=[])
    monkeypatch.setattr('portal.app.structural_cut_overlay.lv_ficha.montar_ficha_lv', assemble)
    inventory = collect_sections(tmp_path, 'floor', dict(segmentos={
        'lateral_a_passa': [dict(beam_name=n) for n in ('VER CORTE 1-1', 'VF1')]}), behavior='passa')
    assert calls == ['VER CORTE 1-1', 'VF1']
    assert inventory['blocked'][0]['beam'] == 'VER CORTE 1-1'
    assert inventory['blocked'][0]['stage'] == 'assemble_lateral_sections'


def test_inverted_lateral_red_white_requires_confirmed_local_mounting():
    contract = dict(beam_type='inverted', form_role='top_cap', width_cm=19, height_cm=120,
                    base_level_m=852.06, top_level_m=853.26,
                    section_semantics=dict(confirmed=True),
                    mounting=dict(A=dict(panel_base_cm=15, panel_top_cm=120, h1_cm=105)))
    entry = dict(beam='VX', section_contract=contract,
                 pairs=[dict(start=[0,0], end=[100,0])])
    original = dict(beam_name='VX', lado='A', rotulo='VX SEG1', pontos_dxf=[[0,0],[100,0]])
    groups = [dict(grupo='lateral_a_passa', itens=[original])]
    inventory = dict(entries=[], physical_entries=[entry], blocked=[])
    transform = SimpleNamespace(dxf_para_px=lambda x,y: [x,y])
    rendered = viewer_groups(None, 'floor', {}, transform, groups, inventory=inventory)[0]['itens'][0]
    assert 'highlight_pattern' not in rendered
    assert rendered['highlight_color'] == '#ff4545'
    assert 'highlight_pattern' not in original
    repeated = [dict(grupo='lateral_a_passa', itens=[original, deepcopy(original)])]
    alternating = viewer_groups(None, 'floor', {}, transform, repeated, inventory=inventory)[0]['itens']
    assert [p['highlight_color'] for p in alternating] == ['#ff4545', '#ffffff']
    contract['mounting'] = {}
    pending = viewer_groups(None, 'floor', {}, transform, groups, inventory=inventory)[0]['itens'][0]
    assert 'highlight_pattern' not in pending


def test_inverted_step_segments_keep_local_profiles_through_measured_terminal_pillar():
    contract = dict(beam_type='inverted', form_role='top_cap', width_cm=19, height_cm=120,
                    base_level_m=852.06, top_level_m=853.26,
                    section_semantics=dict(confirmed=True),
                    mounting=dict(A=dict(panel_base_cm=13, panel_top_cm=120, h1_cm=107)))
    lower = deepcopy(contract)
    lower.update(base_level_m=852.03, top_level_m=853.23)
    lower['mounting']['A'].update(panel_base_cm=10, h1_cm=110)
    entries = [dict(beam='VX', section_contract=c, pairs=[dict(start=[a,0], end=[b,0])])
               for a,b,c in [(0,40,contract), (40,80,lower)]]
    items = [dict(item_id=str(i), beam_name='VX', lado='A', rotulo=f'VX SEG{i}',
                  pontos_dxf=p) for i,p in enumerate([[[0,0],[40,0]], [[40,0],[100,0]]],1)]
    state = dict(pilares=[dict(name='PX',points=[[80,-1],[100,-1],[100,20],[80,20]])],
                 segmentos={'lateral_a_passa':[dict(uid='2',lv_cell=dict(depth=120,
                     pillar_openings=[dict(name='PX')]))]})
    inventory = dict(entries=[],physical_entries=entries,blocked=[])
    groups = [dict(grupo='lateral_a_passa',itens=items)]
    transform = SimpleNamespace(dxf_para_px=lambda x,y:[x,y])
    original = deepcopy((state,groups,inventory))
    result = viewer_groups(None,'floor',state,transform,groups,inventory=inventory)[0]['itens']
    assert {p['item_id'] for p in result} == {'1','2'}
    assert all(p['highlight_color']=='#ff4545' for p in result if p['item_id']=='1')
    assert all(p['highlight_color']=='#ffffff' for p in result if p['item_id']=='2')
    assert (state,groups,inventory) == original
    # Continuity covers the named solid pillar, never unmeasured free span.
    items[1]['pontos_dxf'][-1][0] = 110
    result = viewer_groups(None,'floor',state,transform,groups,inventory=inventory)[0]['itens']
    assert all('highlight_color' not in p for p in result if p['item_id']=='2')


def test_inverted_soffit_highlight_requires_full_local_confirmed_coverage():
    contract = dict(beam_type='inverted', form_role='top_cap', width_cm=19,
                    height_cm=120, base_level_m=852.06, top_level_m=853.26,
                    section_semantics=dict(confirmed=True))
    other = dict(contract, height_cm=71, top_level_m=852.77)
    entries = [dict(beam='VX', section_contract=c,
                    pairs=[dict(start=[a,0], end=[b,0])])
               for a,b,c in [(0,60,contract), (60,100,other)]]
    items = [dict(beam_name='VX', rotulo='VX SEG1', pontos_dxf=p)
             for p in [[[0,0],[100,0],[100,19],[0,19]],
                       [[0,200],[100,200],[100,219],[0,219]],
                       [[0,0],[120,0],[120,19],[0,19]]]]
    groups = [dict(grupo='fundos', itens=items)]
    inventory = dict(entries=[], physical_entries=entries, blocked=[])
    transform = SimpleNamespace(dxf_para_px=lambda x,y: [x,y])
    result = viewer_groups(None, 'floor', {}, transform, groups, inventory=inventory)
    rendered = result[0]['itens']
    assert rendered[0]['highlight_color'] == '#ff4545'
    assert rendered[0]['form_role'] == 'top_cap'
    assert rendered[1]['highlight_color'] == '#ff4545'
    assert all('highlight_color' not in i for i in rendered[2:])
    assert 'highlight_color' not in items[0]
    entries[0]['section_contract']['section_semantics']['confirmed'] = False
    result = viewer_groups(None, 'floor', {}, transform, groups, inventory=inventory)
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


def test_local_step_profiles_from_same_source_cut_have_distinct_stable_viewer_ids(tmp_path, monkeypatch):
    monkeypatch.setattr('portal.app.lv_ficha.montar_ficha_lv', lambda *a, **k: data(True))
    inventory = collect_sections(tmp_path, 'floor', dict(segmentos={'lateral_a_passa':[dict(beam_name='V1')]}))
    first = inventory['entries'][0]
    first['fundo_id'] = 'same-bottom'
    first['section_contract']['slabs']['A'] = [dict(height_cm=13, drop_cm=0)]
    second = deepcopy(first)
    second['section_contract']['slabs']['A'][0]['drop_cm'] += 3
    inventory['entries'] = [first, second]
    transform = SimpleNamespace(dxf_para_px=lambda *p:list(p))
    rendered = viewer_groups(tmp_path, 'floor', {}, transform, [], inventory=inventory)[-1]['itens']
    assert len(rendered) == 2
    assert len({item['item_id'] for item in rendered}) == 2
    reordered = dict(inventory, entries=[second, first])
    again = viewer_groups(tmp_path, 'floor', {}, transform, [], inventory=reordered)[-1]['itens']
    assert {item['item_id'] for item in again} == {item['item_id'] for item in rendered}


def test_displayed_coverage_tracks_merged_owner_and_each_height_interval():
    from portal.app.structural_cut_overlay import displayed_soffit_coverage
    def item(uid, start, end, index=None):
        return dict(item_id=uid, beam_name='V1', display_segment_index=index,
                    pontos_dxf=[[start,0],[end,0],[end,19],[start,19]])
    groups = [dict(grupo='fundos', itens=[item('merged',0,100),
                    item('split',100,150,1), item('split',150,200,2)])]
    entries = [dict(beam='V1',kind='calculated',cut_index=i,drawing=dict(anchor=[x,9.5]))
               for i,x in enumerate((25,75,125))]
    state = dict(segmentos=dict(fundo=[dict(uid='merged',merged_source_uids=['merged','old']),
                                       dict(uid='split')]))
    rows = displayed_soffit_coverage(groups,entries,state)
    assert len(rows) == 3
    assert rows[0]['source_fundo_ids'] == ['merged','old']
    assert rows[0]['interpreted_cut_indexes'] == [0,1]
    assert rows[1]['status'] == 'interpreted' and rows[2]['status'] == 'pending'
    assert rows[1]['display_id'] != rows[2]['display_id']
    assert all(row['fundo_id'] != 'old' for row in rows)


@pytest.mark.parametrize('has_original,region,inverted,expected', [
    (False, 'step', False, '#7dd3fc'),
    (True, 'step', False, '#7dd3fc'),
    (False, 'principal', False, '#7dd3fc'),
    (False, 'step', True, '#ff4545'),
])
def test_missing_slab_step_original_is_local_and_preserves_inverted_priority(
        tmp_path, monkeypatch, has_original, region, inverted, expected):
    monkeypatch.setattr('portal.app.lv_ficha.montar_ficha_lv', lambda *a, **k: data(True))
    inventory = collect_sections(tmp_path, 'floor', dict(segmentos={'lateral_a_passa':[dict(beam_name='V1')]}))
    entry = inventory['entries'][0]
    entry['drawing']['confidence'] = 'high'
    entry['section_contract']['beam_type'] = 'inverted' if inverted else 'normal'
    entry['pairs'][0]['profiles'] = {'A': dict(slabs=[dict(name='LX', region_id=region)])}
    entry['section_contract']['pairs'][0]['profiles'] = deepcopy(entry['pairs'][0]['profiles'])
    # Presentation pairs can include other regions; the local contract wins.
    entry['pairs'].append(dict(profiles={'B': dict(slabs=[dict(name='OTHER', region_id='other-step')])}))
    state = dict(slabs=[dict(name='LX', slab_steps=[dict(uid='step', sections=[dict(points=[])] if has_original else [])])])
    before = deepcopy((inventory, state))
    item = viewer_groups(tmp_path, 'floor', state, SimpleNamespace(dxf_para_px=lambda *p:list(p)), [], inventory=inventory)[-1]['itens'][0]
    assert item['highlight_color'] == expected
    assert item['confidence'] == 'high'
    assert (inventory, state) == before
