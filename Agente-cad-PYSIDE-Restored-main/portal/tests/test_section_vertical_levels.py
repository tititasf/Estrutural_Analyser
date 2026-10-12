import hashlib
from types import SimpleNamespace

import ezdxf
import pytest

from portal.app.preprocessamento.adapters.auxiliary import inventory_auxiliary
from portal.app.preprocessamento.adapters.section_vertical_levels import (
    calibrate_vertical_levels, enrich_section_vertical_levels, level_at_y)


def anchor(handle, y, value, x=0):
    return {'marker_handle': handle, 'position': [x, y], 'width': 10, 'value_m': value}


def test_bounded_affine_datum_preserves_levels_without_item_authority():
    p = calibrate_vertical_levels([anchor('a', 100, 534.94), anchor('b', 392, 537.86)])
    assert p['status'] == 'calibrated_section_only'
    assert p['meters_per_drawing_unit'] == pytest.approx(.01)
    assert level_at_y(p, 246) == pytest.approx(536.4)
    assert level_at_y(p, 99) is None and level_at_y(p, 393) is None
    assert p['item_numeric_authority'] == 'none' and p['independent_vote_count'] == 0


@pytest.mark.parametrize('rows,reason', [
    ([anchor('a', 0, 1)], 'insufficient_explicit_markers'),
    ([anchor('a', 0, 1), anchor('a', 100, 2)], 'duplicate_marker_ownership'),
    ([anchor('a', 0, 1), anchor('b', 100, 2, 20)], 'multiple_marker_columns'),
    ([anchor('a', 0, 2), anchor('b', 100, 1)], 'non_increasing_vertical_datum'),
    ([anchor('a', 0, 1), anchor('b', 100, 2.1), anchor('c', 200, 3)], 'inconsistent_vertical_scale'),
    ([anchor('a', 0, float('nan')), anchor('b', 100, 2)], 'invalid_marker_geometry_or_value'),
    ([anchor('a', 0, 1), anchor('b', 0, 2)], 'non_increasing_vertical_datum'),
])
def test_contradictory_or_insufficient_datums_remain_unresolved(rows, reason):
    p = calibrate_vertical_levels(rows)
    assert p['status'] == 'unresolved' and p['reason'] == reason
    assert level_at_y(p, 50) is None


def fixture(tmp_path, unit='METROS'):
    doc = ezdxf.new()
    model = doc.modelspace()
    model.add_text('COTAS EM '+unit)
    for i, y in enumerate((0, 292), 1):
        model.add_text(f'{i}º PAVIMENTO', dxfattribs={'insert': (0, y-3), 'height': 2})
        model.add_text(str(534.94 if i == 1 else 537.86),
                       dxfattribs={'insert': (0, y+13), 'height': 2})
        model.add_lwpolyline([(0, y), (-5, y+10), (5, y+10)], close=True)
    path = tmp_path/'section.dxf'
    doc.saveas(path)
    source = SimpleNamespace(source_id='section', revision=hashlib.sha256(path.read_bytes()).hexdigest(),
                             relative_path=path.name, kind=SimpleNamespace(value='other'))
    entry = inventory_auxiliary(path, source)
    entry['section_title_links'] = [{'title_handle': 'title', 'title': 'CORTE 1-1'}]
    entry['plan_callout_links'] = [{'status': 'unique_plan_callout_pair', 'title_handle': 'title',
                                  'plan_source_id': 'plan', 'plan_revision': 'revision'}]
    return source, entry, path


def test_actual_markers_use_tip_and_never_text_insertion(tmp_path):
    source, entry, _ = fixture(tmp_path)
    enrich_section_vertical_levels(tmp_path, [source], [entry])
    p = entry['section_vertical_levels']
    assert p['status'] == 'calibrated_section_only'
    assert p['y_bounds'] == [0, 292]
    assert p['anchors'][0]['position'][1] != 13
    assert p['datum_id'] == 'source-local-section:section'


@pytest.mark.parametrize('change,reason', [
    ('hash', 'source_content_changed'), ('row', 'unverified_marker_or_unit'),
    ('unit', 'unverified_marker_or_unit'), ('aggregate', 'ambiguous_section_extent'),
    ('revision', 'stale_source_revision'), ('bulge', 'unverified_marker_or_unit')])
def test_source_and_semantic_contraprovations(tmp_path, change, reason):
    source, entry, path = fixture(tmp_path)
    if change == 'hash':
        source.revision = entry['source_revision'] = 'changed'
    elif change == 'revision':
        entry['source_revision'] = 'changed'
    elif change == 'aggregate':
        entry['section_title_links'].append({'title': 'CORTE A-A'})
    elif change == 'unit':
        entry['level_convention']['direct_floor_levels'][0]['selected']['unit'] = None
    elif change == 'row':
        entry['level_convention']['direct_floor_levels'][0]['selected']['value'] = 600
    else:
        doc = ezdxf.readfile(path)
        marker = next(iter(doc.modelspace().query('LWPOLYLINE')))
        points = list(marker.get_points())
        points[0] = (*points[0][:4], .1)
        marker.set_points(points)
        doc.saveas(path)
        source.revision = entry['source_revision'] = hashlib.sha256(path.read_bytes()).hexdigest()
    enrich_section_vertical_levels(tmp_path, [source], [entry])
    assert entry['section_vertical_levels']['reason'] == reason
    assert entry['section_vertical_levels']['status'] == 'unresolved'
