"""Exercise the canonical pass and snapshot expressions without starting Qt."""
import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Dict

ROOT = Path(__file__).parents[1]


def method(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding='utf8'))
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


def nivel_report(slabs):
    node = method('main.py', '_build_nivel_report')
    namespace = {'Dict': Dict}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'main.py', 'exec'), namespace)
    context = SimpleNamespace(
        _slab_level_source=lambda s, **kw: (
            {'value': float(s['fields']['laje_nivel']), 'kind': 'field',
             'human': s.get('human', False)} if s.get('fields', {}).get('laje_nivel') else None),
        _slab_has_cut_view=lambda s: bool(s.get('level_inference')),
        _ensure_slab_neighbor_level_links=lambda s: {},
        _format_slab_level_value=lambda v: f'{v:.2f}',
        _infer_slab_levels_from_context=lambda s: None,
    )
    return namespace[node.name](context, slabs)


def test_report_preserves_cut_and_neighbor_provenance_after_field_persistence():
    for reason, expected in [('cut_view_paired_geometry_delta', 'cut_view_delta'),
                             ('cut_view_delta', 'cut_view_delta'),
                             ('neighbor_consensus', 'neighbor_inferred')]:
        report = nivel_report([{'name': 'own', 'fields': {'laje_nivel': '537.86'},
                              'level_inference': {'status': 'inferred', 'reason': reason,
                                                  'confidence': .55}}])
        assert report['lajes']['own']['source_type'] == expected
        assert report['lajes']['own']['confidence'] == .55
        assert report['summary']['confirmed'] == 0
    report = nivel_report([{'name': 'direct', 'fields': {'laje_nivel': '537.86'}}])
    assert report['lajes']['direct']['source_type'] == 'text_label'
    assert report['lajes']['direct']['confidence'] == .9


def test_report_never_repairs_rejected_altitude_with_nearest_slab():
    slabs = [{'name': name, 'fields': {'laje_nivel': level}, 'pos': (x, 0)}
             for name, level, x in [('one', '537.86', 0), ('two', '537.86', 10),
                                    ('bad', '999.99', 1)]]
    report = nivel_report(slabs)
    bad = report['lajes']['bad']
    assert bad['level'] is None and bad['level_str'] == ''
    assert bad['source_type'] == 'unknown' and bad['confidence'] == 0
    assert bad['warnings']
    assert 'laje_nivel' not in slabs[-1]['fields']


def test_secondary_pass_preserves_paired_result_without_promoting_it_to_source():
    node = method('main.py', '_infer_slab_level_from_cut_deltas')
    namespace = {'Dict': Dict}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'main.py', 'exec'), namespace)
    slab = {'name': 'own', 'fields': {'laje_nivel': '537.86'},
            'level_inference': {'status': 'inferred', 'reason': 'cut_view_paired_geometry_delta'}}
    context = SimpleNamespace(
        _slab_has_human_level=lambda s: False,
        _slab_level_source=lambda s, **kw: {'value': 537.86},
        _slab_cut_links=lambda s: (_ for _ in ()).throw(AssertionError('recomputed accepted result')),
    )
    sources = {'other': {'value': 537.86}}
    assert namespace[node.name](context, [slab], sources, {}) == 0
    assert slab['level_inference']['status'] == 'inferred'
    assert set(sources) == {'other'}


def test_snapshot_publishes_report_level_and_never_rejected_raw_candidate():
    node = method('src/ui/widgets/pre_validation_dialog.py', '_save_analysis_state')
    row = next(n for n in ast.walk(node) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == 'row' for t in n.targets)
               and isinstance(n.value, ast.Dict)
               and any(isinstance(k, ast.Constant) and k.value == 'nivel' for k in n.value.keys))
    expression = next(v for k, v in zip(row.value.keys, row.value.values)
                      if isinstance(k, ast.Constant) and k.value == 'nivel')
    code = compile(ast.Expression(body=expression), 'snapshot', 'eval')
    slab = {'name': 'own', 'fields': {'laje_nivel': '852.19'}, 'nivel': '852.19'}
    for approved in ('', '0.00', '537.86', '⚠'):
        assert eval(code, {'s': slab, 'accepted_slab_levels': {'own': approved}}) == approved
    assert eval(code, {'s': slab, 'accepted_slab_levels': {}}) == ''


def test_pillar_ficha_height_keeps_absolute_metres_and_unknown_levels(monkeypatch):
    from src.core import niveis_extractor
    calls = []
    monkeypatch.setattr(niveis_extractor, 'get_pavimento_niveis_abs',
                        lambda obra, pav: calls.append((obra, pav)) or {})
    tree = ast.parse((ROOT / 'src/ui/widgets/pre_validation_dialog.py').read_text(encoding='utf8'))
    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
             and n.name == '_pillar_height_detail']
    assert len(nodes) == 2
    for node in nodes:
        namespace = {'self': SimpleNamespace(_obra_name='actual', _pavimento='TIPO'),
                     'pilar_n3': {'nivel_saida_abs': 534.94, 'nivel_chegada_abs': 537.86}}
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'ficha', 'exec'), namespace)
        text = namespace[node.name]()
        assert '534.94m' in text and '537.86m' in text and '292.0cm' in text
        namespace['pilar_n3'] = {}
        text = namespace[node.name]()
        assert '848.98' not in text and '852.19' not in text
        assert calls[-1] == ('actual', 'TIPO')
