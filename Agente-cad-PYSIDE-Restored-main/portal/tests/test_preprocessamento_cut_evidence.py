from types import SimpleNamespace
import ezdxf
from portal.app.preprocessamento.adapters.cuts import inventory_cuts
from portal.app.preprocessamento.service import _tower_dependencies
from portal.app.preprocessamento.sources import SourceKind


def test_cut_call_and_title_are_inventory_evidence_not_invented_geometry(tmp_path):
    doc = ezdxf.new()
    doc.modelspace().add_text('VER CORTE 1-1', dxfattribs={'insert': (1, 1)})
    doc.modelspace().add_text('CORTE 1-1', dxfattribs={'insert': (100, 100)})
    source = tmp_path/'cuts.dxf'
    doc.saveas(source)
    items = inventory_cuts(source, source_id='source')['items']
    assert [i['evidence_kind'] for i in items] == ['plan_call', 'section_title']
    assert all(i['section_label'] == '1-1' for i in items)
    assert all(i['section_geometry'] is None and i['status']=='unlinked' for i in items)


def test_details_dependency_is_bound_to_same_raw_source():
    tower = SimpleNamespace(kind=SourceKind.TOWER, bruto_id='A', source_id='tower')
    local = SimpleNamespace(kind=SourceKind.DETAILS, bruto_id='A', source_id='local')
    foreign = SimpleNamespace(kind=SourceKind.DETAILS, bruto_id='B', source_id='foreign')
    deps, _ = _tower_dependencies([tower, local, foreign], tower)
    assert deps == [tower, local]
