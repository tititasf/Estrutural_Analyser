import json,os,tempfile,sys
from pathlib import Path
sys.path.insert(0,'/opt/cad-analyzer/scripts')
sys.path.insert(0,'/opt/cad-analyzer')
from scripts import drawing_mode_config as config
from scripts import gerar_pl_dxf_stog as g
from scripts.pl_panel_drilling import APPID,top_stations
with tempfile.TemporaryDirectory() as temporary:
    os.environ['ARETE_DRAWING_MODE_CONFIG']=str(Path(temporary)/'settings.json')
    value=config.effective('NOVA','PL');value['drilling']['enabled']=True
    config.save('NOVA','PL',value,0,'validation')
    p=json.loads(Path('/tmp/panel_drilling_deploy/P28.json').read_text())
    doc=g.setup_doc();g.generate_pilar_zone(doc.modelspace(),p,'abcd',visual_mode='NOVA')
    holes=[e for e in doc.modelspace() if e.has_xdata(APPID)]
    stations=top_stations(g.__dict__,p,'NOVA')
    assert holes
    assert all(e.get_xdata(APPID)[1].value in stations[e.get_xdata(APPID)[0].value] for e in holes)
    assert not doc.audit().errors
    doc.saveas('/tmp/panel_drilling_deploy/P28_N3_furacoes.dxf')
    print(json.dumps({'pillar':'P28','holes':len(holes),'audit_errors':0,'profile_isolated':True}))
