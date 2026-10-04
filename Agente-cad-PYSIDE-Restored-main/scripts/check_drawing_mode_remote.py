"""Read portal settings, generate in a new isolated folder; never mutate source."""
import functools
import json
import os
from pathlib import Path
import runpy
import sys
ROOT = Path('/opt/cad-analyzer')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from src.core import artifact_governance as governance
from scripts import drawing_mode_config as config
import ezdxf
out = ROOT / 'portal_runtime/drawing_config_validation_20261001_v2'
out.mkdir(exist_ok=False)
governance.guarded_saveas = functools.partial(governance.guarded_saveas, db_path=out / 'governance.sqlite')
sys.argv = ['gerar_lv_dxf_stog.py', '--obra', str(out / 'isolated_obra'), '--item', 'V301', '--behavior', 'Para', '--view', 'A', '--visual-mode', 'NOVA', '--input-dir', str(ROOT / 'DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/production_sa/13_PAV/20260928_165837_3895120/n3/contracts_lv/LV-PARA'), '--output-dir', str(out / 'dxf')]
runpy.run_path(str(ROOT / 'scripts/gerar_lv_dxf_stog.py'), run_name='__main__')
doc = ezdxf.readfile(next((out / 'dxf').glob('*.dxf')))
assert not doc.audit().errors
profile = config.effective('NOVA', 'LV_PARA')
assert profile['appearance']['text_scale'] == 1.2
assert doc.header['$USERI1'] == config.read_store()['revision']
revision = doc.header['$USERI1']
custom_heights = [entity.dxf.height for entity in doc.modelspace().query('TEXT')]
os.environ['ARETE_DRAWING_MODE_CONFIG'] = str(out / 'empty-settings.json')
sys.argv[-1] = str(out / 'baseline')
runpy.run_path(str(ROOT / 'scripts/gerar_lv_dxf_stog.py'), run_name='__main__')
baseline = ezdxf.readfile(next((out / 'baseline').glob('*.dxf')))
heights = [entity.dxf.height for entity in baseline.modelspace().query('TEXT')]
assert custom_heights and len(custom_heights) == len(heights)
assert all(abs(a - b * 1.2) < 1e-8 for a,b in zip(custom_heights, heights))
assert not baseline.audit().errors
print(json.dumps({'verified_text_scale': 1.2, 'text_count': len(heights), 'revision': revision, 'audit_errors': 0}))
