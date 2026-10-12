"""Recorte não pode descartar tipos estruturais do DXF clássico."""
import ezdxf
import pytest

from scripts.obra_crop_engine import _entity_center, crop_dxf, crop_dxf_multi, crop_dxf_complement


@pytest.mark.parametrize('multi', [False, True])
def test_crop_preserves_classic_geometry_and_excludes_outside(tmp_path, multi):
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_polyline2d([(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)])
    msp.add_solid([(1, 1), (3, 1), (1, 3), (3, 3)])
    msp.add_point((2, 2))
    hatch = msp.add_hatch()
    hatch.paths.add_polyline_path([(1, 1), (3, 1), (3, 3), (1, 3)], is_closed=True)
    msp.add_polyline2d([(20, 20), (22, 22)])
    source, target = tmp_path / 'raw.dxf', tmp_path / 'crop.dxf'
    doc.saveas(source)
    if multi:
        result = crop_dxf_multi(source, target, [(0, 0, 5, 5)])
    else:
        result = crop_dxf(source, target, (0, 0, 5, 5))
    assert result['error'] is None
    cropped = ezdxf.readfile(target)
    assert [e.dxftype() for e in cropped.modelspace()] == ['POLYLINE', 'SOLID', 'POINT', 'HATCH']
    poly = next(iter(cropped.modelspace().query('POLYLINE')))
    assert list(poly.points()) == list(next(iter(msp.query('POLYLINE'))).points())


def test_classic_polyline_center_uses_world_coordinates():
    doc = ezdxf.new()
    poly = doc.modelspace().add_polyline2d([(1, 1), (3, 1), (3, 3), (1, 3)])
    assert _entity_center(poly) == (2, 2)
    solid = doc.modelspace().add_solid([(1, 1), (3, 1), (1, 3), (3, 3)])
    assert _entity_center(solid) == (2, 2)


def test_partition_retains_noise_and_referenced_resources(tmp_path):
    doc = ezdxf.new()
    doc.layers.new('STRUCTURE', dxfattribs={'color': 3, 'linetype': 'CONTINUOUS'})
    block = doc.blocks.new('COLUMN')
    block.add_lwpolyline([(0, 0), (2, 0), (2, 2), (0, 2)], close=True)
    doc.modelspace().add_blockref('COLUMN', (1, 1), dxfattribs={'layer': 'STRUCTURE'})
    doc.modelspace().add_text('CORTE 1-1', dxfattribs={'insert': (9000, 9000)})
    doc.modelspace().add_ellipse((12000, 12000), (3, 0))
    raw, tower, details = [tmp_path / n for n in ('raw.dxf', 'tower.dxf', 'details.dxf')]
    doc.saveas(raw)
    assert crop_dxf(raw, tower, (0, 0, 5, 5))['error'] is None
    cropped = ezdxf.readfile(tower)
    assert len(list(next(iter(cropped.modelspace())).virtual_entities())) == 1
    assert cropped.layers.get('STRUCTURE').dxf.color == 3
    result = crop_dxf_complement(raw, details, [tower])
    assert result['error'] is None
    assert result['uncovered_entities'] == 0
    source_handles = {e.dxf.handle for e in ezdxf.readfile(raw).modelspace()}
    tower_handles = {e.dxf.handle for e in cropped.modelspace()}
    other_handles = {e.dxf.handle for e in ezdxf.readfile(details).modelspace()}
    assert tower_handles.isdisjoint(other_handles)
    assert source_handles == tower_handles | other_handles
    assert [e.dxftype() for e in ezdxf.readfile(details).modelspace()] == ['TEXT', 'ELLIPSE']


def test_contained_selection_does_not_shift_after_entity_without_bbox(tmp_path):
    doc = ezdxf.new()
    doc.modelspace().add_point((99, 99))
    doc.modelspace().add_line((1, 1), (2, 2))
    raw, target = tmp_path / 'raw.dxf', tmp_path / 'target.dxf'
    doc.saveas(raw)
    result = crop_dxf(raw, target, (0, 0, 5, 5), selection_mode='contained')
    assert result['error'] is None
    assert [e.dxftype() for e in ezdxf.readfile(target).modelspace()] == ['LINE']


def test_r12_without_exported_handles_keeps_provenance_in_both_crops(tmp_path):
    doc = ezdxf.new('R12')
    doc.header['$HANDLING'] = 0
    doc.modelspace().add_line((99, 99), (100, 100))
    doc.modelspace().add_solid([(1, 1), (3, 1), (1, 3), (3, 3)])
    raw, tower, details = [tmp_path/n for n in ('raw.dxf', 'tower.dxf', 'details.dxf')]
    doc.saveas(raw)
    assert crop_dxf(raw, tower, (0, 0, 5, 5))['error'] is None
    assert crop_dxf_complement(raw, details, [tower])['error'] is None
    original = {e.dxf.handle: e.dxftype() for e in ezdxf.readfile(raw).modelspace()}
    a = {e.dxf.handle: e.dxftype() for e in ezdxf.readfile(tower).modelspace()}
    b = {e.dxf.handle: e.dxftype() for e in ezdxf.readfile(details).modelspace()}
    assert a | b == original and a.keys().isdisjoint(b)
