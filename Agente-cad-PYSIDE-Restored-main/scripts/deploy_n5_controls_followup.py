"""Apply guarded follow-up patches to the already deployed mode controls."""
import json
from pathlib import Path
import shutil
import sys

if len(sys.argv) == 1:
    core = Path('src/core/n5_assembler.py').read_text(encoding='utf-8')
    addition = core[core.index('    if classe == "PL" and (obra_dir / f"estado_{pavimento}.json").is_file():'):core.index('    missing = []', core.index('def n3_mode_readiness'))]
    edits = [
        {'file':'src/core/n5_assembler.py','old':'    missing = []\n    for item in ids:', 'new':addition+'    missing = []\n    for item in ids:'},
        {'file':'portal/app/templates/obra_detalhe.html','old':"            {% if release %}\n            {% if classe == 'PL' %}", 'new':"            {% if classe == 'PL' %}"},
        {'file':'portal/app/templates/obra_detalhe.html','old':"            {% for group in (['PARA', 'PASSA'] if classe == 'PL' else ['']) %}",'new':"            {% if release %}\n            {% for group in (['PARA', 'PASSA'] if classe == 'PL' else ['']) %}"},
        {'file':'portal/app/templates/obra_detalhe.html','old':"              <button type=\"button\" class=\"drawing-mode-missing-switch\" data-n5-mode-switch>{{ 'Ver Nova' if n5_modo_ativo == 'INI' else 'Ver Ini' }}</button>\n",'new':''},
    ]
    Path('scripts/n5_controls_followup.json').write_text(json.dumps(edits),encoding='utf-8')
else:
    root = Path('/opt/cad-analyzer')
    backup = Path('/root/backup_n5_controls_followup_20260930')
    staged = {}
    for edit in json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')):
        path = root / edit['file']
        value = staged.get(path, path.read_text(encoding='utf-8'))
        assert value.count(edit['old']) == 1, edit['file']
        staged[path] = value.replace(edit['old'],edit['new'],1)
    for path,value in staged.items():
        target = backup / path.relative_to(root)
        target.parent.mkdir(parents=True,exist_ok=True)
        assert not target.exists()
        shutil.copy2(path,target)
        path.write_text(value,encoding='utf-8')
        print(path)
