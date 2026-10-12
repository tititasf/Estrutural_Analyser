"""Exercise the actual GUI method without loading Qt or production data."""
import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Dict


def read_source(slab, include_neighbor_context=True):
    tree = ast.parse((Path(__file__).parents[1] / 'main.py').read_text(encoding='utf8'))
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                  and n.name == '_slab_level_source')
    namespace = {'Dict': Dict}
    exec(compile(ast.Module(body=[method], type_ignores=[]), 'main.py', 'exec'), namespace)
    ctx = SimpleNamespace(
        _ensure_slab_level_links=lambda s: s.get('own_links', {}),
        _ensure_slab_neighbor_level_links=lambda s: s.get('neighbor_links', {}),
        _parse_slab_level_value=lambda raw: float(raw) if raw not in (None, '') else None,
    )
    return namespace['_slab_level_source'](ctx, slab, include_neighbor_context)


def test_neighbor_dimension_or_altitude_does_not_become_own_level():
    for token in ('6', '852.19'):
        slab = {'neighbor_links': {'neighbor_north': [{'text': token, 'validated': True}]}}
        assert read_source(slab) is None


def test_explicit_resolved_own_inference_and_zero_remain_available():
    for token in ('0', '-3', '852.19'):
        slab = {'fields': {'laje_nivel': token},
                'level_inference': {'status': 'inferred', 'reason': 'cut_view_delta'}}
        assert read_source(slab)['value'] == float(token)


def test_rejected_own_candidate_cannot_confirm_itself_from_neighbor():
    slab = {'fields': {'laje_nivel': '6'}, 'level_inference': {'status': 'needs_review'},
            'neighbor_links': {'neighbor_north': [{'text': '6'}]}}
    assert read_source(slab) is None
