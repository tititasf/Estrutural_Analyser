import ezdxf

from src.core.dxf_loader import DXFLoader
from portal.app.preprocessamento.sa_levels import plan_marks


def test_plan_marks_preserve_real_text_and_mtext_handles(tmp_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    text = msp.add_text('855.25', dxfattribs={'insert': (10, 20)})
    mtext = msp.add_mtext('855.22', dxfattribs={'insert': (30, 40)})
    msp.add_text('402.5', dxfattribs={'insert': (50, 60)})
    path = tmp_path / 'levels.dxf'
    doc.saveas(path)

    marks = plan_marks(path, {'top': 855.25, 'height': 3.21, 'unit': 'm'})
    assert {(row['value'], row['handle']) for row in marks} == {
        (855.25, text.dxf.handle), (855.22, mtext.dxf.handle)}
    restored = ezdxf.readfile(path)
    for row in marks:
        entity = restored.entitydb[row['handle']]
        assert list(entity.dxf.insert)[:2] == row['pos']


def test_transformed_block_text_keeps_source_handle(tmp_path):
    doc = ezdxf.new()
    block = doc.blocks.new('LEVEL')
    text = block.add_text('855.25', dxfattribs={'insert': (1, 2)})
    doc.modelspace().add_blockref('LEVEL', (100, 200))
    path = tmp_path / 'block.dxf'
    doc.saveas(path)
    tokens = DXFLoader.load_dxf(str(path))['texts']
    assert len(tokens) == 1
    assert tokens[0]['handle'] == text.dxf.handle
    assert tokens[0]['pos'] == (101, 202)
