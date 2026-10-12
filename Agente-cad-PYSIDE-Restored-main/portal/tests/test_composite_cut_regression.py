from copy import deepcopy
import xml.etree.ElementTree as ET

import pytest

from src.core.composite_cut_contours import composite_cut_contours
from src.core.lv_cut_datum import apply_original_datums
from src.core.lv_n3_cut_contract import build_cut_contract, CutContractError
from portal.app.dxf_preview import svg_viewer_compactar_tracos


def rectangle(x, y, w, h, layer='section'):
    return dict(layer=layer, points=[[x,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y]])


def test_touching_rectangles_form_section_but_gaps_layers_and_pillars_do_not():
    stem = rectangle(0,0,19,65)
    flange = rectangle(-50,53,50,12)
    result = composite_cut_contours([stem, flange])
    assert len(result) == 1 and result[0]['source_piece_count'] == 2
    assert len(result[0]['points']) == 7
    assert composite_cut_contours([stem, rectangle(-50.1,53,50,12)]) == []
    assert composite_cut_contours([stem, rectangle(-50,53,50,12,'pillar')]) == []
    assert composite_cut_contours([stem, rectangle(19,0,20,65)]) == []


def original(drop=5):
    return dict(id='CAD-1', beam='V1', kind='identified', source_cut=dict(
        beam_w=19, beam_h=65, own_laje='L1', ficha=dict(
            direction='Leste', side_a_laje_name='L1', side_b_laje_name='nulo',
            beam_lajes_side_a='1', beam_lajes_side_b='0', own_slab_height=12,
            own_dist_top=drop, own_dist_bottom=65-12-drop)))


def calculated(name='L1', height=65):
    profiles = {'A':dict(level=None,slabs=[dict(name=name,height_cm=12,level=None)]),
                'B':dict(level=None,slabs=[])}
    return dict(id='calc-1',beam='V1',kind='calculated',width_cm=19,
                beam_height_cm=height, profiles=profiles,
                pairs=[dict(profiles=deepcopy(profiles))])


def test_relative_profile_uses_measured_original_without_fabricating_absolute_level():
    cut = apply_original_datums([calculated()], [original()], [])[0]
    contract = build_cut_contract(cut)
    assert contract['slabs']['A'][0]['drop_cm'] == 5
    assert contract['vertical_datum_source'] == 'original_cut_relative_profile'
    assert 'base_level_m' not in contract and 'top_level_m' not in contract
    assert contract['evidence_ids'] == ['CAD-1']
    assert cut['pairs'][0]['profiles']['A']['slabs'][0]['measured_drop_cm'] == 5


@pytest.mark.parametrize('cut, originals', [
    (calculated('L2'), [original()]),
    (calculated(height=120), [original()]),
    (calculated(), [original(), dict(original(10), id='CAD-2')]),
])
def test_relative_evidence_cannot_cross_slab_height_or_conflicting_measurements(cut, originals):
    derived = apply_original_datums([cut], originals, [])[0]
    with pytest.raises(CutContractError, match=r'profiles\.level'):
        build_cut_contract(derived)


def test_dash_batch_retains_exact_subpaths_clips_and_fills():
    ns = 'http://www.w3.org/2000/svg'
    svg = f'''<svg xmlns="{ns}"><g id="LineCollection_1">
    <path d="M 0 0 L 1 0" style="fill: none; stroke: #fff" clip-path="url(#c)"/>
    <path d="M 2 0 L 3 0" style="fill: none; stroke: #fff" clip-path="url(#c)"/>
    <path d="M 3 0 L 4 0" style="fill: #fff"/></g></svg>'''.encode()
    output = ET.fromstring(svg_viewer_compactar_tracos(svg))
    paths = list(output.iter(f'{{{ns}}}path'))
    assert len(paths) == 2
    assert paths[0].get('d') == 'M 0 0 L 1 0 M 2 0 L 3 0'
    assert paths[0].get('clip-path') == 'url(#c)'
    faded = svg.replace(b'<g id=', b'<g opacity=".5" id=')
    assert len(list(ET.fromstring(svg_viewer_compactar_tracos(faded)).iter(f'{{{ns}}}path'))) == 3
    unknown = svg.replace(b'<g id=', b'<style>g > path {stroke:red}</style><g id=')
    assert svg_viewer_compactar_tracos(unknown) == unknown


def test_source_reader_keeps_current_snapshot_slabs_when_database_names_are_stale(tmp_path):
    import sqlite3
    from portal.app.lv_cut_sources import load_sources
    db_path = tmp_path / 'project.vision'
    with sqlite3.connect(db_path) as db:
        db.execute('CREATE TABLE slabs (name, project_id, links_json, extra_data_json, points_json)')
        db.execute("INSERT INTO slabs VALUES ('LAUTO_1', 'project', '{}', '{}', '[]')")
    slabs = [dict(name='L1_TIPO_TESTE', points=[[0,0],[10,0],[10,10]], links={})]
    result, _, _ = load_sources(tmp_path, 'TIPO_TESTE', dict(db_path=str(db_path), slabs=slabs), {'x':dict(project_id='project')})
    assert [s['name'] for s in result] == ['L1_TIPO_TESTE']
    assert result[0]['points'] == slabs[0]['points']


def test_relative_profile_follows_named_slabs_across_cuts_without_absolute_level():
    def link(uid, a, b, da, db):
        return dict(id=uid, beam='V2', kind='identified', source_cut=dict(
            beam_w=19, beam_h=120, own_laje=a, ficha=dict(
                direction='Leste', side_a_laje_name=a, side_b_laje_name=b,
                beam_lajes_side_a='1', beam_lajes_side_b='1',
                own_slab_height=12, neigh_slab_height=12,
                own_dist_top=da, own_dist_bottom=108-da,
                neighbor_dist_top=db, neighbor_dist_bottom=108-db)))
    section = calculated('L2',120)
    anchor = original(75)
    anchor['source_cut']['beam_h'] = 120
    anchor['source_cut']['ficha']['own_dist_bottom'] = 33
    links = [link('L1-L4','L1','L4',0,0), link('L4-L2','L4','L2',75,0)]
    cut = apply_original_datums([section],[anchor],[],regional_originals=links)[0]
    contract = build_cut_contract(cut)
    assert contract['slabs']['A'][0]['drop_cm'] == 0
    assert set(contract['evidence_ids']) == {'CAD-1','L1-L4','L4-L2'}
    assert 'top_level_m' not in contract
    conflicts = [*links,link('conflict','L1','L2',20,0)]
    pending = apply_original_datums([section],[anchor],[],regional_originals=conflicts)[0]
    with pytest.raises(CutContractError,match=r'profiles\.level'):
        build_cut_contract(pending)
