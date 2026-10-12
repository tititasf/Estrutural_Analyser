import ezdxf
import pytest
from src.core import n5_ini_frames as frames


def setup_frames(monkeypatch, sizes):
    def source(path, cls):
        doc = ezdxf.new()
        width, height = sizes[path]
        doc.modelspace().add_lwpolyline([(0,0),(width,0),(width,height),(0,height)],close=True)
        return doc
    monkeypatch.setattr(frames, 'source', source)
    monkeypatch.setattr(frames, 'template_doc', lambda *_: (ezdxf.new(),None,None))
    monkeypatch.setattr(frames, 'transfer', lambda *_args,**_kwargs: None)
    monkeypatch.setattr(frames, 'finish', lambda _dst,pages,index,*_args: dict(pages=pages,index=index))


def test_oversized_item_is_pending_without_leaking_its_first_segment(monkeypatch,tmp_path):
    setup_frames(monkeypatch, {'a':(100,100),'bad':(5000,100),'b':(100,100)})
    pending=[]
    result=frames.assemble(ezdxf.new(), [('VF1',['a','bad']),('VF2',['b'])], 'FV',
        obra='any',cliente='',pavimento='any',pages_dir=tmp_path,pending=pending)
    assert [p['label'] for p in result['index']] == ['VF2']
    assert pending[0]['item_id'] == 'VF1'
    assert pending[0]['status'] == 'missing'
    assert 'excede folha' in pending[0]['message']
    with pytest.raises(ValueError,match='excede folha'):
        frames.assemble(ezdxf.new(), [('VF1',['bad'])], 'FV',
            obra='any',cliente='',pavimento='any',pages_dir=tmp_path)


def test_tall_unit_that_fits_fresh_sheet_moves_to_new_page(monkeypatch,tmp_path):
    setup_frames(monkeypatch, {'a':(3000,1200),'b':(3000,1800)})
    result=frames.assemble(ezdxf.new(), [('V1',['a']),('V2',['b'])], 'FV',
        obra='any',cliente='',pavimento='any',pages_dir=tmp_path)
    assert [p['page'] for p in result['index']] == [1,2]
