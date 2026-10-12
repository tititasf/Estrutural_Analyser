import ezdxf
import pytest
from scripts import drawing_mode_config as config
from scripts.drawing_semantics import LayoutProxy, roles
from scripts.visual_modes import apply_visual_mode


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('ARETE_DRAWING_MODE_CONFIG', str(tmp_path/'profiles.json'))


def test_moldes_snapshot_nova_once_and_remain_independent():
    nova=config.effective('NOVA','PL')
    nova['texts']['nome']['scale']=1.5
    config.save('NOVA','PL',nova,0,'test')
    # Simulate an existing pre-Molde store at the migration boundary.
    import json
    stored=json.loads(config.storage_path().read_text())
    for m in config.MODES[2:]: stored['profiles'].pop(m)
    config.storage_path().write_text(json.dumps(stored))
    catalog=config.catalog()
    assert len(catalog['modes'])==5
    assert all(catalog['modes'][m]['PL']['texts']['nome']['scale']==1.5 for m in config.MODES[2:])
    nova['texts']['nome']['scale']=2
    config.save('NOVA','PL',nova,1,'test')
    molde=config.effective('MOLDE_1','PL')
    molde['human_notes']='Anotação de teste'
    config.save('MOLDE_1','PL',molde,2,'test')
    assert config.effective('MOLDE_2','PL')['texts']['nome']['scale']==1.5
    assert config.effective('MOLDE_1','PL')['human_notes']=='Anotação de teste'
    assert config.effective('NOVA','PL')['human_notes'] == nova['human_notes']


def add_cima(msp):
    msp.add_text('A',dxfattribs={'height':10})
    msp.add_text('P1',dxfattribs={'height':10})
    dim=msp.add_linear_dim(base=(0,-10),p1=(0,0),p2=(40,0))
    dim.render()
    return dim.dimension


def add_face(msp,fid):
    return msp.add_text('P1.'+fid,dxfattribs={'height':10})


def test_roles_isolate_view_components_texts_and_dimension_style(tmp_path):
    doc=ezdxf.new()
    msp=LayoutProxy(doc.modelspace(),'PL')
    dim=add_cima(msp)
    a,c=add_face(msp,'A'),add_face(msp,'C')
    assert roles(c)==('cd','texts','faces')
    settings=config.effective('MOLDE_2','PL')
    settings['texts']['faces_cima'].update(scale=2,color=3)
    settings['view_components']['cd']['textos']=False
    settings['dimensions']['cima'].update(scale=1.5,arrow_scale=2,color=2,style='CIMA_TEST',precision=3,gap=2)
    config.save('MOLDE_2','PL',settings,0,'test')
    apply_visual_mode(doc,'MOLDE_2','PL')
    texts=list(doc.modelspace().query('TEXT'))
    assert [(t.dxf.text,t.dxf.height) for t in texts]==[('A',20),('P1',10),('P1.A',10)]
    assert dim.dxf.dimstyle=='CIMA_TEST'
    assert dim.override().get('dimdec')==3
    assert dim.override().get('dimclrd')==2
    doc.saveas(tmp_path/'granular.dxf')
    assert not ezdxf.readfile(tmp_path/'granular.dxf').audit().errors


def test_hatch_role_changes_only_requested_pattern():
    doc=ezdxf.new();msp=LayoutProxy(doc.modelspace(),'PL')
    def draw_laje():
        h=msp.add_hatch();h.set_pattern_fill('AR-CONC');return h
    def draw_void_hatches():
        h=msp.add_hatch();h.set_pattern_fill('ANSI31');return h
    laje,opening=draw_laje(),draw_void_hatches()
    settings=config.effective('NOVA','PL')
    settings['hatches']['aberturas'].update(pattern='ANSI32',scale=2,angle=30,color=1)
    config.save('NOVA','PL',settings,0,'test')
    apply_visual_mode(doc,'NOVA','PL')
    assert laje.dxf.pattern_name=='AR-CONC'
    assert opening.dxf.pattern_name=='ANSI32'
    assert opening.dxf.pattern_scale==2 and opening.dxf.pattern_angle==30


def test_plain_dimension_text_is_not_generic_text():
    doc=ezdxf.new();msp=LayoutProxy(doc.modelspace(),'FV')
    def add_plain_dim_h(): return msp.add_text('120',dxfattribs={'height':5})
    text=add_plain_dim_h()
    assert roles(text)==('fundo','dimensions','fundo')
    settings=config.effective('NOVA','FV')
    settings['texts']['referencias']['scale']=3
    settings['dimensions']['fundo']['scale']=2
    config.save('NOVA','FV',settings,0,'test')
    apply_visual_mode(doc,'NOVA','FV')
    assert text.dxf.height==10


def test_real_plain_cut_dimensions_support_ticks_gap_style_and_disable():
    from scripts.gerar_lv_dxf_stog import add_plain_dim_h
    doc=ezdxf.new(); msp=LayoutProxy(doc.modelspace(),'LV')
    add_plain_dim_h(msp,0,100,-20,'100',extension_to_y=0)
    settings=config.effective('NOVA','LV_PARA')
    settings['dimensions']['corte'].update(scale=2,arrow_scale=2,gap=10,precision=2,style='CORTE_TXT',color=2)
    config.save('NOVA','LV_PARA',settings,0,'test')
    config.apply_config(doc,'NOVA','LV','PARA')
    text=doc.modelspace().query('TEXT')[0]
    assert text.dxf.text=='100.00' and text.dxf.height==14 and text.dxf.style=='CORTE_TXT'
    assert text.dxf.insert.y==-30
    ticks=[e for e in doc.modelspace().query('LINE') if e.dxf.start.x!=e.dxf.end.x and e.dxf.start.y!=e.dxf.end.y]
    assert all(abs(e.dxf.end.x-e.dxf.start.x)==10 for e in ticks)
    settings['view_components']['corte']['cotas']=False
    config.save('NOVA','LV_PARA',settings,1,'test')
    config.apply_config(doc,'NOVA','LV','PARA')
    assert not list(doc.modelspace())
