from copy import deepcopy

import pytest
from shapely.geometry import Polygon, box

from src.core.lv_beam_scene import LvScene, _attach_context
from src.core.lv_short_support_composition import compose_short_support_runs
from src.core.beam_interpreters.lateral_viga_cells import segment_cell


def fixture(horizontal):
    runs = [LvScene('VX', horizontal, 0, 19, 0, 500),
            LvScene('VX', horizontal, 0, 19, 519, 900)]
    poly = box(500, 0, 519, 154) if horizontal else box(0, 500, 154, 519)
    pillars = [('PX', 'SEGUE', poly)]
    for run in runs:
        run.sections = [dict(start=run.start, end=run.end, dim='19/50', width=19, depth=50)]
        run.provenance = dict(band_source='dxf_edges_from_own_label')
        run.face_coverage = {'A': [[0, 500], [519, 900]], 'B': [[0, 500], [519, 900]]}
        _attach_context(run, pillars, runs, [])
        run.slabs['B'] = [dict(name='LX', level='537.86', height=12)]
    return runs, pillars


@pytest.mark.parametrize('horizontal', [True, False])
@pytest.mark.parametrize('behavior', ['para', 'passa'])
def test_short_support_is_once_in_composed_exterior_wall(horizontal, behavior):
    runs, pillars = fixture(horizontal)
    before = deepcopy(runs)
    joined = compose_short_support_runs(runs, pillars)
    assert runs == before
    assert len(joined) == 1
    scene = joined[0]
    assert scene.provenance['context_rebuild_required']
    _attach_context(scene, pillars, joined, [])
    cells = segment_cell(scene, 'A', behavior)
    assert len(cells) == 1
    assert sorted((cells[0].start, cells[0].end)) == [0, 900]
    assert len(cells[0].pillar_openings) == 1
    opening = cells[0].pillar_openings[0]
    assert opening['comprimento'] == 19
    assert opening['abertura'] == 41
    assert opening['dist_face_inicio'] + opening['comprimento'] + opening['dist_face_fim'] == 900
    # The opposite wall crosses the core and must remain interrupted.
    assert len(segment_cell(scene, 'B', behavior)) == 2


@pytest.mark.parametrize('guard', ['section', 'level', 'unknown', 'width', 'diagonal',
                                  'walls', 'dimension', 'long', 'hollow', 'missing', 'source'])
def test_no_composition_without_complete_original_proof(guard):
    runs, pillars = fixture(True)
    if guard == 'section': runs[1].sections[0].update(dim='19/60', depth=60)
    if guard == 'level': runs[1].slabs['B'][0]['level'] = '537.81'
    if guard == 'unknown': runs[1].slabs['B'] = []
    if guard == 'width': runs[1].t_hi = 22
    if guard == 'diagonal': runs[1].angle = 15
    if guard == 'walls': runs[1].face_coverage['B'] = []
    if guard == 'dimension':
        # A dimension with no structural edge underneath cannot prove a wall.
        runs[1].face_coverage['A'] = [[560, 900]]
        runs[1].dimension_coverage['A'] = [[519, 900]]
    if guard == 'long': pillars = [('PX', 'SEGUE', box(500, 0, 519, 19))]
    if guard == 'hollow': pillars = [('PX', 'SEGUE', Polygon([(500,0),(519,0),(519,154),(500,154)],
                                                            [[(505,30),(510,30),(510,100),(505,100)]]))]
    if guard == 'missing': pillars = []
    if guard == 'source': runs[1].provenance = {}
    assert len(compose_short_support_runs(runs, pillars)) == 2


def test_dimension_overlay_does_not_erase_proven_structural_wall():
    runs, pillars = fixture(True)
    runs[1].dimension_coverage['A'] = [[519, 900]]
    assert runs[1].dimension_overlap('A', 519, 900) == 0
    assert len(compose_short_support_runs(runs, pillars)) == 1


@pytest.mark.parametrize('cause', ['gap', 'negative', 'nan_section', 'nan_level'])
def test_incomplete_or_nonfinite_measurements_cannot_prove_composition(cause):
    runs, pillars = fixture(True)
    if cause == 'gap':
        original = runs[1].sections[0]
        runs[1].sections = [dict(original, end=600), dict(original, start=620)]
    elif cause == 'negative':
        for run in runs:
            run.sections[0]['depth'] = -50
    elif cause == 'nan_section':
        runs[1].sections[0]['end'] = float('nan')
    else:
        for run in runs:
            run.slabs['B'][0]['level'] = 'inf'
    assert len(compose_short_support_runs(runs, pillars)) == 2
