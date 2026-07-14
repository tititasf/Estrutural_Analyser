"""Contrato de persistência mínima dos microciclos headless."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.arete.headless_sa_analise import (  # noqa: E402
    _beam_topology_coverage,
    _changed_canonical_beam_names,
    _fast_context_cache_path,
    _non_regressive_beam_dependencies,
    _partial_collections_for_sections,
)


def test_fast_context_cache_key_tracks_source_identity():
    first = _fast_context_cache_path(str(Path(__file__)))
    second = _fast_context_cache_path(str(ROOT / 'main.py'))

    assert first != second
    assert first.parent.name == 'n1_context'


def test_pil_microcycle_persists_only_reconciled_beam_dependency():
    collections = {
        'pillars': [{'name': 'P35'}, {'name': 'P1'}],
        'slabs': [{'name': 'L301'}],
        'beams': [{'name': 'V308'}, {'name': 'V327'}],
    }
    result = _partial_collections_for_sections(
        collections,
        {'pilares'},
        {'P35'},
        beam_dependencies={'V308'},
    )
    assert [item['name'] for item in result['pillars']] == ['P35']
    assert [item['name'] for item in result['beams']] == ['V308']
    assert result['slabs'] == []


def test_unchanged_canonical_beam_is_not_a_partial_dependency():
    old = [{'name': 'V308', 'dim': '19/55', 'fields': {'dimensao': '19/55'}}]
    new = [{
        'name': 'V308', 'dim': '19/55',
        'fields': {'dimensao': '19/55'},
        '_section_dimension_source': 'fundo_ficha_geometrica',
    }]
    assert _changed_canonical_beam_names(old, new, {'V308'}) == set()


def test_partial_dependency_rejects_loss_of_second_beam_span():
    def lateral(index, x1, x2):
        return {
            f'viga_a_seg_{index}_comprimento_total': {
                'seg_side_a': [{'points': [[x1, 10], [x2, 10]]}],
            },
        }

    old_links = {}
    old_links.update(lateral(1, 0, 100))
    old_links.update(lateral(2, 130, 300))
    old = [{'name': 'V308', 'links': old_links}]
    new = [{'name': 'V308', 'links': lateral(1, 0, 100)}]

    accepted, rejected = _non_regressive_beam_dependencies(old, new, {'V308'})

    assert accepted == set()
    assert rejected == {'V308': {'old': (2, 270.0), 'new': (1, 100.0)}}


def test_topology_coverage_does_not_triple_count_fv_and_two_laterals():
    contour = {
        'contour': [{'points': [[0, 0], [100, 0], [100, 19], [0, 19], [0, 0]]}],
    }
    beam = {'links': {
        'viga_fundo_seg_1_area_segs': contour,
        'viga_a_seg_1_comprimento_total': {
            'seg_side_a': [{'points': [[0, 19], [100, 19]]}],
        },
        'viga_b_seg_1_comprimento_total': {
            'seg_side_b': [{'points': [[0, 0], [100, 0]]}],
        },
    }}

    assert _beam_topology_coverage(beam) == (1, 100.0)
