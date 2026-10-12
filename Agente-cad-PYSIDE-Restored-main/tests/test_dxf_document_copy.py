import io
import importlib.util
from pathlib import Path
import ezdxf
from src.core.n5_ini_frames import clone


def test_copy_preserves_resources_dimensions_hatches_and_isolation(tmp_path):
    doc = ezdxf.new('R2018')
    doc.appids.new('TEST_PROVENANCE')
    block = doc.blocks.new('manufacturing')
    block.add_circle((0, 0), 4)
    msp = doc.modelspace()
    inserted = msp.add_blockref('manufacturing', (30, 40))
    inserted.set_xdata('TEST_PROVENANCE', [(1000, 'original')])
    hatch = msp.add_hatch()
    hatch.paths.add_polyline_path([(0, 0), (40, 0), (40, 20), (0, 20)], is_closed=True)
    dim = msp.add_linear_dim(base=(0, -10), p1=(0, 0), p2=(40, 0))
    dim.render()
    msp.add_mline([(0, 0), (40, 0)])
    stream = io.StringIO()
    doc.write(stream)
    legacy = ezdxf.read(io.StringIO(stream.getvalue()))
    copied = clone(doc)
    assert all(e.doc is copied for e in copied.entitydb.values() if e.is_alive)
    assert all(e.dxf._entity is e for e in copied.entitydb.values() if e.is_alive)
    spec = importlib.util.spec_from_file_location('clone_parity', Path(__file__).resolve().parents[1] /
        'scripts/arete/relatorios/20261008_n3_performance/compare_dxf.py')
    parity = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parity)
    for name, value in [('legacy', legacy), ('copy', copied)]:
        value.saveas(tmp_path / f'{name}.dxf')
    assert parity.canonical(tmp_path/'legacy.dxf') == parity.canonical(tmp_path/'copy.dxf')
    copied.blocks.get('manufacturing').query('CIRCLE')[0].dxf.radius = 99
    copied.modelspace().query('INSERT')[0].set_xdata('TEST_PROVENANCE', [(1000, 'changed')])
    assert block.query('CIRCLE')[0].dxf.radius == 4
    assert inserted.get_xdata('TEST_PROVENANCE')[0].value == 'original'
    assert not copied.audit().errors
