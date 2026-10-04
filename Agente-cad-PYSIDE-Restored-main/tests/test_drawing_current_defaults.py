import json
import ezdxf
import pytest
from scripts import drawing_mode_config as cfg
from scripts.drawing_semantics import APPID

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setenv('ARETE_DRAWING_MODE_CONFIG',str(tmp_path/'profiles.json'))

def text(doc,name,height):
    if APPID not in doc.appids: doc.appids.new(APPID)
    item=doc.modelspace().add_text(name,dxfattribs={'height':height})
    item.set_xdata(APPID,[(1000,'fundo'),(1000,'texts'),(1000,name)])
    return item

def test_actual_defaults_and_mixed_values_are_not_guessed():
    actual=cfg.current_catalog()['modes']['NOVA']['FV']['texts']['nome']
    value=cfg.defaults('NOVA','FV')['texts']['nome']
    assert value['height']==actual['height'][0]==12
    assert value['style']=='Standard' and value['color']==256
    heights=cfg.current_catalog()['modes']['NOVA']['PL']['texts']['nome']['height']
    assert len(heights)>1
    assert cfg.defaults('NOVA','PL')['texts']['nome']['height']==-1

def test_changed_generator_invalidates_measured_catalog(tmp_path,monkeypatch):
    import hashlib
    (tmp_path/'config').mkdir()
    source=tmp_path/'current.py';source.write_text('version = 1\n')
    data={'sources':{'current.py':hashlib.sha256(source.read_text().encode()).hexdigest()},'modes':{}}
    (tmp_path/'config/drawing_mode_current_catalog.json').write_text(json.dumps(data))
    monkeypatch.setattr(cfg,'ROOT',tmp_path)
    assert cfg.current_catalog()['verified']
    source.write_text('version = 2\n')
    assert not cfg.current_catalog()['verified']

@pytest.mark.parametrize('mode',cfg.MODES)
@pytest.mark.parametrize('cls',cfg.CLASSES)
def test_save_actual_defaults_is_inert(mode,cls):
    value=cfg.defaults(mode,cls)
    assert cfg.validate(mode,cls,value)=={}
    cfg.save(mode,cls,value,0,'test')
    doc=ezdxf.new();a=text(doc,'nome',17);b=text(doc,'referencias',5)
    before=[e.dxf.all_existing_dxf_attribs() for e in doc.modelspace()]
    cfg.apply_config(doc,mode,cls)
    assert before==[e.dxf.all_existing_dxf_attribs() for e in doc.modelspace()]

def test_absolute_height_and_relative_factor_only_change_target():
    value=cfg.defaults('NOVA','FV');value['texts']['nome'].update(height=18,scale=1.5,color=2)
    cfg.save('NOVA','FV',value,0,'test')
    doc=ezdxf.new();a=text(doc,'nome',12);b=text(doc,'referencias',5)
    cfg.apply_config(doc,'NOVA','FV')
    assert a.dxf.height==27 and a.dxf.color==2
    assert b.dxf.height==5

def test_existing_relative_override_remains_relative():
    cfg.storage_path().write_text(json.dumps({'schema_version':1,'revision':3,'profiles':{'NOVA':{'FV':{'texts':{'nome':{'scale':2}}}}}}))
    doc=ezdxf.new();a=text(doc,'nome',7)
    cfg.apply_config(doc,'NOVA','FV')
    assert a.dxf.height==14
    value=cfg.effective('NOVA','FV');cfg.save('NOVA','FV',value,3,'test')
    assert cfg.overrides('NOVA','FV')=={'texts':{'nome':{'scale':2}}}

def test_absolute_hatch_scale_and_dimension_size():
    from scripts.drawing_semantics import roles
    doc=ezdxf.new();doc.appids.new(APPID)
    h=doc.modelspace().add_hatch();h.set_pattern_fill('ANSI31',scale=2,angle=45)
    h.set_xdata(APPID,[(1000,'fundo'),(1000,'hatches'),(1000,'paineis')])
    dim=doc.modelspace().add_linear_dim(base=(0,5),p1=(0,0),p2=(10,0))
    dim.render();d=dim.dimension;d.set_xdata(APPID,[(1000,'fundo'),(1000,'dimensions'),(1000,'fundo')])
    value=cfg.defaults('NOVA','FV');value['hatches']['paineis'].update(pattern_scale=3,scale=2)
    value['dimensions']['fundo'].update(text_height=4,arrow_size=2,scale=1.5,arrow_scale=1.5)
    cfg.save('NOVA','FV',value,0,'test');cfg.apply_config(doc,'NOVA','FV')
    assert h.dxf.pattern_scale==6
    assert d.override().get('dimtxt')==6 and d.override().get('dimasz')==3
    assert not doc.audit().errors
