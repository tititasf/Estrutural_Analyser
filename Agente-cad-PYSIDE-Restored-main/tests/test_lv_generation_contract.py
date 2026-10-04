from src.core.lv_generation_contract import (
    build_lv_generation_contracts,
    distribute_lv_panels,
)


def _entry(length, dim="14/50"):
    entry = {"points": [[0, 0], [length, 0]], "len": length}
    if dim:
        entry["lv_dimensao"] = dim
    return entry


def _inverted_context(end=100):
    return {'physical_entries': [{
        'beam': 'V330', 'pairs': [{'start': [0, 0], 'end': [end, 0]}],
        'section_contract': {
            'beam_type': 'inverted', 'form_role': 'top_cap',
            'section_semantics': {'confirmed': True, 'beam_type': 'inverted'},
            'width_cm': 19., 'height_cm': 71.,
            'base_level_m': 851.99, 'top_level_m': 852.70,
            'mounting': {
                'A': {'panel_base_cm': 15., 'panel_top_cm': 71., 'h1_cm': 56.},
                'B': {'panel_base_cm': 22., 'panel_top_cm': 71., 'h1_cm': 49.},
            },
        },
    }]}


def test_inverted_lateral_uses_local_mounting_instead_of_common_depth():
    beam = {'name': 'V330', 'links': {
        f'viga_{s}_seg_1_comprimento_total': {f'seg_side_{s}': [_entry(100, '19/71')]}
        for s in ('a', 'b')
    }}
    beam['links']['viga_b_seg_1_comprimento_total']['seg_side_b'][0]['points'] = [[100,19],[0,19]]
    result = build_lv_generation_contracts(beam, section_context=_inverted_context())
    for side, height in [('A', 56.), ('B', 49.)]:
        contract = result['Para'][side]
        assert contract['generation_ready']
        assert contract['geometry_length'] == 100.
        assert [p['height1'] for p in contract['panels']] == [height]
        assert contract['panels'][0]['section_contract']['top_level_m'] == 852.70


def test_inverted_lateral_gap_blocks_common_depth_fallback():
    beam = {'name': 'V330', 'links': {
        'viga_a_seg_1_comprimento_total': {'seg_side_a': [_entry(100, '19/71')]}
    }}
    contract = build_lv_generation_contracts(beam, section_context=_inverted_context(80))['Para']['A']
    assert not contract['generation_ready']
    assert contract['panels'] == []
    assert contract['geometry_length'] == 100.
    assert contract['vertical_pending']


def test_inverted_pending_inventory_retains_every_uncovered_segment():
    from copy import deepcopy
    rows = [_entry(100, '19/71'), _entry(20, '19/71')]
    rows[1]['points'] = [[120, 0], [140, 0]]
    beam = {'name': 'V330', 'links': {
        f'viga_a_seg_{i}_comprimento_total': {'seg_side_a': [row]}
        for i, row in enumerate(rows, 1)
    }}
    before = deepcopy(beam)
    contract = build_lv_generation_contracts(beam, section_context=_inverted_context(80))['Para']['A']
    assert beam == before
    assert not contract['generation_ready'] and not contract['panels']
    pending = contract['vertical_pending_segments']
    assert [p['segment_index'] for p in pending] == [1, 2]
    assert [p['points'] for p in pending] == [[[80., 0.], [100., 0.]], rows[1]['points']]
    assert sum(p['length_cm'] for p in pending) == 40.
    assert contract['geometry_length'] == 120.


def test_inverted_pending_partition_retains_known_islands_and_both_gaps():
    from copy import deepcopy
    from src.core.beam_vertical_context import partition_inverted_lateral, split_inverted_lateral
    import pytest
    context = _inverted_context(30)['physical_entries']
    second = deepcopy(context[0])
    second['pairs'] = [{'start': [60, 0], 'end': [80, 0]}]
    context.append(second)
    before = deepcopy(context)
    pieces = partition_inverted_lateral([[100, 0], [0, 0]], context, 'A')
    assert context == before
    assert sum(p['width'] for p in pieces) == 100.
    assert [(p['points'], p['width']) for p in pieces if p.get('pending')] == [
        ([[100., 0.], [80., 0.]], 20.), ([[60., 0.], [30., 0.]], 30.)]
    assert sum(p['width'] for p in pieces if not p.get('pending')) == 50.
    with pytest.raises(ValueError, match='sem intervalo vertical confirmado'):
        split_inverted_lateral([[100, 0], [0, 0]], context, 'A')


def _crossing_context(top=852.19, base=851.64):
    context = _inverted_context()
    context['physical_entries'].append({'beam':'V301',
        'pairs':[{'start':[40,-30], 'end':[40,30],
                  'footprint':[[40,-30],[40,30],[59,30],[59,-30]]}],
        'section_contract': {'base_level_m':base, 'top_level_m':top}})
    return context


def _inverted_crossing_beam():
    entry = _entry(100, '19/71')
    entry['lv_cell'] = {'beam_openings':[{'name':'V301', 'pos_inicio':40.,
        'largura':19., 'abertura_largura':27., 'abertura_altura':59.}]}
    return {'name':'V330', 'links':{
        f'viga_{s}_seg_1_comprimento_total':{f'seg_side_{s}':[entry]}
        for s in ('a','b')}}


def test_inverted_crossing_has_only_real_contact_at_bottom_of_a_wall():
    result = build_lv_generation_contracts(_inverted_crossing_beam(),
                                           section_context=_crossing_context())['Para']
    for c in result.values():
        assert c['generation_ready'] and c['total_length'] == 100.
    holes = [h for p in result['A']['panels'] for h in p.get('holes', [])]
    assert len(holes) == 1
    assert holes[0]['height'] == 5.
    assert holes[0]['position'] == 51.  # from top of the 56 cm local wall
    assert holes[0]['corner'] == 'TL'
    assert not any(p.get('holes') for p in result['B']['panels'])


def test_inverted_crossing_preserves_interior_contact_height_and_offset():
    result = build_lv_generation_contracts(_inverted_crossing_beam(),
        section_context=_crossing_context(top=852.64, base=852.24))['Para']['A']
    holes = [h for p in result['panels'] for h in p.get('holes', [])]
    assert result['generation_ready']
    assert [(h['height'],h['position']) for h in holes] == [(40.,6.)]


def test_unknown_incident_levels_block_instead_of_using_old_depth_plus_four():
    context = _crossing_context()
    context['physical_entries'][-1]['section_contract'].pop('top_level_m')
    result = build_lv_generation_contracts(_inverted_crossing_beam(), section_context=context)['Para']['A']
    assert not result['generation_ready'] and not result['panels']
    assert 'V301' in result['vertical_pending']
    assert result['geometry_length'] == 100.


def test_inverted_partition_keeps_original_opening_station_and_total_length():
    from copy import deepcopy
    context = _crossing_context()
    second = deepcopy(context['physical_entries'][0])
    second['pairs'] = [{'start':[50,0], 'end':[100,0]}]
    context['physical_entries'][0]['pairs'][0]['end'] = [50,0]
    context['physical_entries'].append(second)
    result = build_lv_generation_contracts(_inverted_crossing_beam(), section_context=context)['Para']['A']
    assert result['generation_ready'] and result['total_length'] == 100.
    holes = [h for p in result['panels'] for h in p.get('holes', [])]
    assert sum(h['width'] for h in holes) == 27.
    assert len(holes) == 2
    assert len({p['physical_segment_index'] for p in result['panels']}) == 2


def test_builds_four_isolated_lv_generation_contracts():
    beam = {
        "name": "V327",
        "fields": {"viga_fundo_seg_1_dim": "99/999"},
        "links": {
            "viga_a_seg_1_comprimento_total": {"seg_side_a": [_entry(96.5)]},
            "viga_a_seg_2_comprimento_total": {"seg_side_a": [_entry(100)]},
            "viga_b_seg_1_comprimento_total": {"seg_side_b": [_entry(196.5)]},
            "viga_a_seg_1_comp_total_passa": {"seg_side_a": [_entry(204)]},
            "viga_b_seg_1_comp_total_passa": {"seg_side_b": [_entry(204)]},
        },
    }

    contracts = build_lv_generation_contracts(beam, floor="13_PAV")

    assert [p["width"] for p in contracts["Para"]["A"]["panels"]] == [96.5, 100]
    assert [p["width"] for p in contracts["Passa"]["A"]["panels"]] == [204]
    assert contracts["Para"]["A"]["contract_id"] == "LV_A_PARA"
    assert contracts["Passa"]["B"]["contract_id"] == "LV_B_PASSA"
    assert contracts["Para"]["A"]["total_width"] == 14
    assert contracts["Para"]["A"]["h_section"] == 50
    assert contracts["Para"]["A"]["total_height"] == 54
    assert contracts["Para"]["A"]["behavior_distinct_from_other"] is True


def test_missing_lv_dimension_blocks_generation_and_never_uses_fv_dimension():
    beam = {
        "name": "V327",
        "fields": {"viga_fundo_seg_1_dim": "14/50"},
        "links": {
            "viga_a_seg_1_comprimento_total": {
                "seg_side_a": [_entry(200, dim="")]
            }
        },
    }

    contract = build_lv_generation_contracts(beam)["Para"]["A"]

    assert contract["segment_count"] == 1
    assert contract["dimension_status"] == "missing"
    assert contract["generation_ready"] is False
    assert contract["total_width"] == 0
    assert contract["_sa_meta"]["fv_dimension_fallback"] is False


def test_uses_canonical_lv_segment_field_after_cross_class_autofill():
    beam = {
        "name": "V308",
        "fields": {
            "viga_fundo_seg_1_dim": "19/55",
            "viga_a_seg_1_dim": "100/19",
        },
        "links": {
            "viga_a_seg_1_comprimento_total": {
                "seg_side_a": [_entry(291, dim="")]
            }
        },
    }

    contract = build_lv_generation_contracts(beam)["Para"]["A"]

    assert contract["total_width"] == 19
    assert contract["h_section"] == 100
    assert contract["generation_ready"] is True
    assert contract["_sa_meta"]["dimension_source"] == "sa_lv_segment_field"
    assert contract["_sa_meta"]["fv_dimension_fallback"] is False


def test_uses_beamtracer_lv_dimension_without_fv_fallback():
    beam = {
        "name": "V327",
        "geometry": {"lv_dimension_text": {"text": "14/50"}},
        "fields": {"viga_fundo_seg_1_dim": "24/66"},
        "links": {
            "viga_a_seg_1_comprimento_total": {
                "seg_side_a": [_entry(260, dim="")]
            }
        },
    }

    contract = build_lv_generation_contracts(beam)["Para"]["A"]

    assert contract["total_width"] == 14
    assert contract["h_section"] == 50
    assert contract["total_height"] == 54
    assert contract["generation_ready"] is True


def test_panelizer_avoids_short_residual_after_full_module():
    assert distribute_lv_panels(260) == [122.0, 138.0]
    assert distribute_lv_panels(256) == [122.0, 134.0]
    assert distribute_lv_panels(415) == [244.0, 171.0]


def test_v327_passa_reaches_expected_panels_from_n1_geometry_and_pillar():
    beam = {
        "name": "V327",
        "lv_is_h": False,
        "geometry": {"lv_dimension_text": {"text": "14/50"}},
        "links": {
            "viga_a_seg_1_comp_total_passa": {
                "seg_side_a": [{
                    "points": [[4387.3825, 1982.038], [4387.3825, 2242.038]],
                    "len": 260,
                }]
            },
            "viga_b_seg_1_comp_total_passa": {
                "seg_side_b": [{
                    "points": [[4387.3825, 1982.038], [4387.3825, 2242.038]],
                    "len": 260,
                }]
            },
        },
    }
    pillars = {"P27": (4387.3825, 2242.038, 4552.3825, 2460.038)}

    contracts = build_lv_generation_contracts(
        beam, pillar_bboxes=pillars
    )["Passa"]

    assert [panel["width"] for panel in contracts["A"]["panels"]] == [122.0, 134.0]
    assert [panel["width"] for panel in contracts["B"]["panels"]] == [122.0, 138.0]
    assert contracts["A"]["end_adjustment"] == -4.0
    assert contracts["B"]["end_adjustment"] == 0.0
    assert contracts["A"]["total_length"] == 256.0
    assert contracts["B"]["total_length"] == 260.0


def test_endpoint_labels_use_only_proven_local_lv_fields_not_global_fundo_links():
    beam = {
        "name": "V327",
        "geometry": {"lv_dimension_text": {"text": "14/50"}},
        "fields": {"viga_a_seg_1_end_name": "P27"},
        "links": {
            "apoios": {
                "inicio": [{"name": "V328"}],
                "fim": [{"name": "P27"}],
            },
            "viga_a_seg_1_comprimento_total": {
                "seg_side_a": [_entry(260)]
            },
        },
    }

    contract = build_lv_generation_contracts(beam)["Para"]["A"]

    assert contract["endpoint_labels"] == {"start": "", "end": "P27"}
