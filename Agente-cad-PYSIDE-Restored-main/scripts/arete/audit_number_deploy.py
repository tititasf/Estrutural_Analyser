"""Read-only comparison: never overwrite remote drift or run Git."""
from pathlib import Path
import subprocess
import difflib
import sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
FILES = ['portal/app/static/decimal_display.js', 'portal/app/static/fv_ficha.js',
    'portal/app/static/lv_ficha.js', 'portal/app/static/laje_ficha.js',
    'portal/app/static/pillar_ficha.js', 'portal/app/dxf_preview.py',
    'src/core/n5_assembler.py', 'scripts/arete/headless_sa_analise.py',
    'portal/app/templates/obra_detalhe.html']

for relative in FILES:
    response = subprocess.run(['ssh', 'root@62.238.111.147',
        'cat /opt/cad-analyzer/' + relative], capture_output=True, check=True)
    remote = response.stdout.decode('utf-8').splitlines()
    local = (ROOT / relative).read_text(encoding='utf-8').splitlines()
    print('\n'.join(difflib.unified_diff(remote, local,
        fromfile='VPS/' + relative, tofile='local/' + relative, n=2)))
