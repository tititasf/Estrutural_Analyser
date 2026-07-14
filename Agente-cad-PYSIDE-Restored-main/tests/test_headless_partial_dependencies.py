"""Contrato de persistência mínima dos microciclos headless."""
from __future__ import annotations

import sys
from pathlib import Path

import scripts.arete.headless_sa_analise as headless

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.arete.headless_sa_analise import (  # noqa: E402
    _headless_lock_plan,
    _beam_topology_coverage,
    _changed_canonical_beam_names,
    _fast_context_cache_path,
    _fresh_laj_geometry_for_readonly_preview,
    _non_regressive_beam_dependencies,
    _partial_collections_for_sections,
)


def test_headless_lock_plan_isolates_single_class_item():
    locks, scope = _headless_lock_plan({'pilares'}, {'P35'}, False)
    assert locks == ['headless_sa_pil']
    assert scope == 'classe:PIL'


def test_headless_lock_plan_keeps_global_for_dangerous_runs():
    expected = [
        'headless_sa_global', 'headless_sa_pil', 'headless_sa_laj',
        'headless_sa_fv', 'headless_sa_lv',
    ]
    assert _headless_lock_plan(None, None, False)[0] == expected
    assert _headless_lock_plan({'pilares'}, None, False)[0] == expected
    assert _headless_lock_plan({'pilares', 'lajes'}, {'P1'}, False)[0] == expected
    assert _headless_lock_plan({'pilares'}, {'P1'}, True)[0] == expected


def test_fast_context_cache_key_tracks_source_identity():
    first = _fast_context_cache_path(str(Path(__file__)))
    second = _fast_context_cache_path(str(ROOT / 'main.py'))

    assert first != second
    assert first.parent.name == 'n1_context'


def test_fast_context_cache_key_is_invalidated_by_dxf_and_fv_owner_content(
    tmp_path: Path, monkeypatch,
):
    """O atalho FV não pode reaproveitar N1 ao mudar DXF ou interpretador."""
    source = tmp_path / 'source.dxf'
    source.write_bytes(b'DXF-A')
    engine = tmp_path / 'src' / 'core' / 'beam_interpreters' / 'fundo_viga.py'
    engine.parent.mkdir(parents=True)
    engine.write_text('owner=A', encoding='utf-8')
    contract = tmp_path / 'src' / 'core' / 'fv_generation_contract.py'
    contract.write_text('contract=A', encoding='utf-8')

    monkeypatch.setattr(headless, '_REPO_ROOT', tmp_path)
    monkeypatch.setattr(headless, '_FAST_CONTEXT_ENGINE_FILES', (
        'src/core/beam_interpreters/fundo_viga.py',
        'src/core/fv_generation_contract.py',
    ))
    first = headless._fast_context_cache_path(str(source))
    source.write_bytes(b'DXF-B')
    after_dxf = headless._fast_context_cache_path(str(source))
    engine.write_text('owner=B', encoding='utf-8')
    after_owner = headless._fast_context_cache_path(str(source))

    assert first != after_dxf
    assert after_dxf != after_owner


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


def test_readonly_laj_preview_uses_fresh_geometry_without_losing_human_seal():
    merged = [{
        'name': 'L318',
        'points': [[0, 0], [1, 0], [1, 1], [0, 0]],
        'area': 1.0,
        'is_validated': True,
        'validated_fields': ['laje_outline_segs'],
        'links': {'laje_outline_segs': {'contour': [{'points': [[0, 0]]}]}},
    }]
    fresh = [{
        'name': 'L318',
        'points': [[10, 10], [30, 10], [30, 20], [10, 10]],
        'area': 100.0,
        'method': 'motor_geom',
        'trace_diagnostics': {'outline_source': 'polygonize'},
        'links': {'laje_outline_segs': {'contour': [{'points': [[10, 10]]}]}},
    }]

    assert _fresh_laj_geometry_for_readonly_preview(merged, fresh) == 1
    assert merged[0]['is_validated'] is True
    assert merged[0]['validated_fields'] == ['laje_outline_segs']
    assert merged[0]['points'] == fresh[0]['points']
    assert merged[0]['links']['laje_outline_segs'] == fresh[0]['links']['laje_outline_segs']
    assert merged[0]['n1_geometry_preview_source'] == 'fresh_dxf_readonly'


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
