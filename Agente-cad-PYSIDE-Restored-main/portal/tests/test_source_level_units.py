import hashlib
from types import SimpleNamespace

import ezdxf
import pytest

from portal.app.preprocessamento.adapters.auxiliary import inventory_auxiliary, crosscheck_reference
from portal.app.preprocessamento.adapters.source_level_units import enrich_source_level_units


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(tmp_path, declaration='DIMENSÕES EM CM E COTAS EM METROS'):
    doc = ezdxf.new()
    model = doc.modelspace()
    note = model.add_text(declaration, dxfattribs={'insert': (100, 100), 'height': 2})
    label = model.add_text('2º PAVIMENTO', dxfattribs={'insert': (0, -3), 'height': 2})
    value = model.add_text('537.86', dxfattribs={'insert': (0, 13), 'height': 2})
    marker = model.add_lwpolyline([(0, 0), (-5, 10), (5, 10)], close=True)
    raw_path, crop_path = tmp_path/'raw.dxf', tmp_path/'crop.dxf'
    doc.saveas(raw_path)
    model.delete_entity(note)
    doc.saveas(crop_path)
    source = SimpleNamespace(source_id='crop', revision=sha(crop_path), relative_path='crop.dxf',
                             obra_id='work', pavimento_id='floor', bruto_id='raw',
                             kind=SimpleNamespace(value='other'))
    raw = {'source_id': 'parent', 'revision': sha(raw_path), 'relative_path': 'raw.dxf',
           'obra_id': 'work', 'pavimento_id': 'floor', 'bruto_id': 'raw'}
    entry = inventory_auxiliary(crop_path, source)
    return source, raw, entry, marker.dxf.handle, label.dxf.handle, value.dxf.handle


def test_explicit_parent_unit_confirms_floor_without_independent_vote(tmp_path):
    source, raw, entry, *_ = fixture(tmp_path)
    enrich_source_level_units(tmp_path, [source], raw, [entry])
    row = entry['level_convention']['direct_floor_levels'][0]
    assert row['selected']['unit'] == 'm'
    assert row['unit_provenance']['independent_vote_count'] == 0
    assert row['unit_provenance']['item_numeric_authority'] == 'none'
    result = crosscheck_reference({'floor_selection': {'representative_floor': 2},
                                  'unit': 'm', 'top': 537.86}, [entry])
    assert result['status'] == 'consistent' and result['independent_vote_count'] == 0


@pytest.mark.parametrize('changed', ['raw_hash', 'crop_hash', 'scope', 'entry_revision', 'marker', 'label', 'value'])
def test_changed_provenance_or_geometry_never_inherits_unit(tmp_path, changed):
    source, raw, entry, marker, label, value = fixture(tmp_path)
    if changed == 'raw_hash':
        raw['revision'] = 'stale'
    elif changed == 'crop_hash':
        source.revision = entry['source_revision'] = 'stale'
    elif changed == 'scope':
        source.bruto_id = 'another_raw'
    elif changed == 'entry_revision':
        entry['source_revision'] = 'stale'
    else:
        crop_path = tmp_path/'crop.dxf'
        crop = ezdxf.readfile(crop_path)
        entity = crop.entitydb.get({'marker': marker, 'label': label, 'value': value}[changed])
        if changed == 'marker':
            entity.translate(0, 1, 0)
        else:
            entity.dxf.insert = (1, entity.dxf.insert.y)
        crop.saveas(crop_path)
        source.revision = entry['source_revision'] = sha(crop_path)
    enrich_source_level_units(tmp_path, [source], raw, [entry])
    assert entry['level_convention']['direct_floor_levels'][0]['selected']['unit'] is None


@pytest.mark.parametrize('declaration', ['DIMENSÕES EM CENTÍMETROS',
                                       'COTAS EM M; NÍVEIS EM CM'])
def test_generic_or_conflicting_units_are_not_inherited(tmp_path, declaration):
    source, raw, entry, *_ = fixture(tmp_path, declaration)
    enrich_source_level_units(tmp_path, [source], raw, [entry])
    assert entry['level_convention']['direct_floor_levels'][0]['selected']['unit'] is None


def test_numeric_conflict_remains_conflicting_after_unit_resolution(tmp_path):
    source, raw, entry, *_ = fixture(tmp_path)
    enrich_source_level_units(tmp_path, [source], raw, [entry])
    qa = crosscheck_reference({'floor_selection': {'representative_floor': 2},
                              'unit': 'm', 'top': 500}, [entry])
    assert qa['status'] == 'conflicting' and qa['independent_vote_count'] == 0
