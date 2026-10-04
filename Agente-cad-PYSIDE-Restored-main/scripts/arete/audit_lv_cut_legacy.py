"""Read-only audit of LV cut SCRs and cached generator function names."""
from pathlib import Path
import json, marshal, types

root = Path(__file__).resolve().parents[2]
legacy = root / '_ROBOS_ABAS/Robo_Laterais_de_Vigas'
records = []
for p in sorted((legacy / 'SCRIPTS').rglob('VC-*.scr')):
    if 'HEADLESS' in str(p):
        continue
    raw = p.read_bytes()
    text = raw.decode('utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf8', errors='replace')
    lines = text.splitlines()
    inserts = []
    for i, line in enumerate(lines):
        if line.strip().upper() == '_INSERT' and i+2 < len(lines):
            inserts.append({'block':lines[i+1], 'xy':lines[i+2], 'line':i+1})
    records.append({'file':str(p.relative_to(root)), 'inserts':inserts})
print(json.dumps(records, ensure_ascii=False, indent=2))
for p in [legacy / '__pycache__/gerador_script_viga.cpython-312.pyc', root.parent / '_ROBOS_ABAS/Robo_Laterais_de_Vigas/__pycache__/gerador_script_viga.cpython-312.pyc']:
    if not p.exists(): continue
    # Inspect code objects only; never import or execute old generator code.
    code = marshal.loads(p.read_bytes()[16:])
    def walk(c):
        for item in c.co_consts:
            if isinstance(item, types.CodeType):
                if any(k in item.co_name.lower() for k in ('corte','parafus','ancor')):
                    print('CACHED FUNCTION', p, item.co_name, item.co_firstlineno)
                walk(item)
    walk(code)
out = root / 'scripts/arete/relatorios/20261001_lv_n3_cortes/legacy_cut_bolt_inventory.json'
out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf8')
