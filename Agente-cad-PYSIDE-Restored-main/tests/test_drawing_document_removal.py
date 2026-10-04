import io
import pytest
import ezdxf
from portal.app import drawing_frame as frames

@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('ARETE_DRAWING_MODE_CONFIG', str(tmp_path/'profiles.json'))
    doc=ezdxf.new();doc.modelspace().add_line((0,0),(10,10));stream=io.StringIO();doc.write(stream)
    return stream.getvalue().encode()

def test_remove_frame_preserves_original_and_other_mode(isolated):
    a=frames.store('NOVA','PL','a.dxf',isolated)
    b=frames.store('INI','PL','b.dxf',isolated)
    frames.remove_frame('NOVA','PL',a['id'])
    assert frames.metadata('NOVA','PL') is None
    assert frames.metadata('INI','PL')==b
    assert (frames.directory('NOVA','PL')/(a['id']+'.dxf')).exists()

def test_remove_older_document_preserves_current(isolated):
    a=frames.store('NOVA','PL','a.dxf',isolated)
    b=frames.store('NOVA','PL','b.dxf',isolated)
    frames.remove_frame('NOVA','PL',a['id'])
    assert frames.documents('NOVA','PL')==[b]
    with pytest.raises(RuntimeError):frames.remove_frame('NOVA','PL',a['id'])
    assert frames.metadata('NOVA','PL')==b

def test_remove_selected_example_only(isolated):
    a=frames.add_example('NOVA','FV','a.dxf',isolated)[0]
    b=frames.add_example('NOVA','FV','b.dxf',isolated)[1]
    assert frames.remove_example('NOVA','FV',a['id'])==[b]
    assert frames.remove_example('NOVA','FV',b['id'])==[]

@pytest.mark.parametrize('token',['../current.json','z'*32])
def test_invalid_removal_token(isolated,token):
    with pytest.raises(ValueError):frames.remove_frame('NOVA','PL',token)

@pytest.mark.parametrize('collection', [frames.FRAMES, frames.LEGENDS])
def test_multiple_documents_and_legacy_migration(isolated, collection):
    a=frames.store('NOVA','PL','a.dxf',isolated,collection)
    root=frames.directory('NOVA','PL',collection)
    (root/'index.json').unlink()  # existing single-document storage
    assert frames.documents('NOVA','PL',collection)==[a]
    b=frames.store('NOVA','PL','b.dxf',isolated,collection)
    assert frames.documents('NOVA','PL',collection)==[a,b]
    with pytest.raises(ValueError):
        frames.store('NOVA','PL','bad.dxf',b'invalid',collection)
    assert frames.documents('NOVA','PL',collection)==[a,b]
    assert frames.documents('NOVA','FV',collection)==[]
    assert frames.documents('INI','PL',collection)==[]
    frames.remove_frame('NOVA','PL',b['id'],collection)
    assert frames.metadata('NOVA','PL',collection)==a
    assert frames.documents('NOVA','PL',collection)==[a]
    frames.remove_frame('NOVA','PL',a['id'],collection)
    assert frames.documents('NOVA','PL',collection)==[]
    assert frames.metadata('NOVA','PL',collection) is None
