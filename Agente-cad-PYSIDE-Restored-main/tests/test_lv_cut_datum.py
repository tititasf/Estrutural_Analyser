from copy import deepcopy
from src.core.lv_cut_datum import apply_original_datums
from src.core.lv_cut_datum import connected_soffit_beams
from src.core.lv_n3_cut_contract import build_cut_contract


def sources():
    original = dict(id='measured', beam='V1', kind='identified', source_cut=dict(
        beam_w=19, beam_h=55, own_laje='L1', ficha=dict(direction='norte',
        side_a_laje_name='L1', own_slab_height=13, own_dist_top=0,
        own_dist_bottom=42, beam_lajes_side_b='0')))
    slab = dict(name='L1', height=13, nivel=852.19,
                points=[[0,0],[100,0],[100,100],[0,100]])
    profile = dict(width_cm=19, height_cm=55, level=852.16,
                   level_source='paired_touching_slabs',
                   slabs=[dict(name='L1',height_cm=10,level=852.16)])
    section = dict(id='local',beam='V1',kind='calculated',width_cm=19,
                   beam_height_cm=55,profiles={'A':profile,'B':deepcopy(profile)},pairs=[])
    return section, original, slab


def test_lowered_regions_do_not_lower_the_measured_beam_top():
    section, original, slab = sources()
    before = deepcopy(section)
    derived = apply_original_datums([section], [original], [slab])[0]
    contract = build_cut_contract(derived)
    assert section == before
    assert contract['top_level_m'] == 852.19
    assert contract['slabs']['A'][0]['drop_cm'] == 3
    assert derived['beam_datum_evidence_ids'] == ['measured']


def test_no_original_evidence_does_not_guess_a_beam_top():
    section, original, slab = sources()
    derived = apply_original_datums([section], [], [slab])[0]
    assert 'beam_top_level_m' not in derived


def test_conflicting_measured_datums_are_flagged_instead_of_guessed():
    section, original, slab = sources()
    other = deepcopy(original)
    other['id'] = 'other'
    other['source_cut']['ficha'].update(own_dist_top=7,own_dist_bottom=35)
    derived = apply_original_datums([section], [original,other], [slab])[0]
    assert 'beam_top_level_m' not in derived
    assert 'diferentes' in derived['attention']


def test_connected_neighbor_datum_requires_same_local_slab_level_and_height():
    section, original, slab = sources()
    original['beam'] = 'V2'
    # Measured beam top 852.19, slab 852.12: preserve the recess locally.
    original['source_cut']['ficha'].update(own_dist_top=7, own_dist_bottom=35)
    slab['nivel'] = 852.12
    section['profiles']['B']['slabs'][0].update(height_cm=13, level=852.12)
    derived = apply_original_datums([section], [], [slab], neighboring_originals=[original])[0]
    assert derived['beam_top_level_m'] == 852.19
    assert build_cut_contract(derived)['slabs']['B'][0]['drop_cm'] == 7
    original['source_cut']['beam_w'] = 14
    assert 'beam_top_level_m' not in apply_original_datums([section], [], [slab], neighboring_originals=[original])[0]
    original['source_cut']['beam_w'] = 19
    section['profiles']['B']['slabs'][0]['level'] = 852.16
    derived = apply_original_datums([section], [], [slab], neighboring_originals=[original])[0]
    assert 'beam_top_level_m' not in derived


def test_neighbor_is_direct_geometric_continuity_despite_clipped_width():
    segments = [dict(beam_name='V1',width=14,points=[[0,0],[10,0],[10,14],[0,14]]),
                dict(beam_name='V2',width=14,points=[[10,0],[20,0],[20,14],[10,14]]),
                dict(beam_name='V3',width=14,points=[[21,0],[30,0],[30,14],[21,14]]),
                dict(beam_name='V4',width=19,points=[[10,0],[20,0],[20,19],[10,19]])]
    assert connected_soffit_beams('V1', segments) == {'V2', 'V4'}
    segments[0]['width'] = 12.847
    assert 'V2' in connected_soffit_beams('V1', segments)
