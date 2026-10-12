import ast
from pathlib import Path
from types import SimpleNamespace
import math
from shapely.geometry import Polygon


def finder():
    # Test the real method without starting the desktop window.
    tree = ast.parse((Path(__file__).parents[1] / 'main.py').read_text(encoding='utf8'))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                and n.name == '_find_pillar_geom_near_text')
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'main.py', 'exec'), namespace)
    return namespace[node.name]


def test_circular_pillar_uses_actual_circle_and_excludes_grid_dots():
    circle = {'center': (100, 100), 'radius': 30, 'layer': 'STRUCT-PILAR'}
    runner = SimpleNamespace(dxf_data={'circles': [circle,
        {'center': (105, 105), 'radius': 1, 'layer': 'STRUCT-PILAR'}]})
    points, claimed = finder()(runner, [(150, 100)], set())
    assert claimed == id(circle)
    assert abs(Polygon(points).area - math.pi*900) / (math.pi*900) < .005
    assert all(abs(math.dist(p, circle['center']) - 30) < 1e-8 for p in points)
    assert finder()(runner, [(150, 100)], {id(circle)}) == (None, None)


def test_circular_pillar_does_not_guess_when_candidates_are_ambiguous():
    runner = SimpleNamespace(dxf_data={'circles': [
        {'center': (100, 100), 'radius': 30, 'layer': 'PILAR'},
        {'center': (200, 100), 'radius': 30, 'layer': 'PILAR'}]})
    assert finder()(runner, [(150, 100)], set()) == (None, None)
