"""Full production-web SA gate on the isolated 14_PAV copy in the VPS."""
from pathlib import Path
import json
import os
import subprocess
import sys

from src.core.database import DatabaseManager
from portal.app.preprocessamento.context_resolver import pin_context
from portal.app.preprocessamento.service import read_floor, read_tower

root = Path('/opt/cad-analyzer/.deploy/preprocess-20260923/ab14')
dxf = root / 'Fase-2_Triagem/recortes/A/torre_1.dxf'
floor = read_floor(root, '14_PAV')
assert floor and floor['coverage']['processed'] == 1
package = read_tower(root, floor, next(iter(floor['towers'])))
assert package['level_inventory']['reference']['height'] == 3.06
db = root / 'sa-test.vision'
project = DatabaseManager(str(db)).create_project(
    '14_PAV', dxf_path=str(dxf), work_name=str(root), pavement_name='14_PAV'
)
context, reason = pin_context(obra_dir=root, obra_id='linux-ab14',
                              pavimento='14_PAV', project_id=project, dxf_path=dxf)
assert reason == 'accepted', reason
payload = json.loads(context.read_text(encoding='utf-8'))
cmd = [sys.executable, '-m', 'scripts.arete.headless_sa_analise',
       '--obra', str(root), '--pav', '14_PAV', '--db', str(db),
       '--project-id', project, '--context-manifest', str(context),
       '--context-hash', payload['context_hash'], '--production-web',
       '--visual-mode', 'NOVA', '--persist-db', '--wait']
env = os.environ.copy()
env.update(QT_QPA_PLATFORM='offscreen', PYTHONPATH='/opt/cad-analyzer',
           PYTHONDONTWRITEBYTECODE='1')
log = root / 'headless-full-v3.log'
with log.open('w', encoding='utf-8') as stream:
    result = subprocess.run(cmd, cwd='/opt/cad-analyzer', env=env,
                            stdout=stream, stderr=subprocess.STDOUT, timeout=900)
print('exit', result.returncode, 'project', project, 'log', log, flush=True)
assert result.returncode == 0
manifests = sorted((root / 'Fase-6_Execucao_CAD/production_sa/14_PAV').glob('*/production_manifest.json'),
                   key=lambda path: path.stat().st_mtime)
assert manifests
manifest = json.loads(manifests[-1].read_text(encoding='utf-8'))
n3 = manifest['n3']
print('n1', manifest['n1_counts'], 'pl_generated', len(n3['pl_generated']),
      'pl_failed', len(n3['pl_failed']), 'context', manifest['preprocess_context']['status'],
      'manifest', manifests[-1], flush=True)
assert len(n3['pl_generated']) == 70 and not n3['pl_failed']
