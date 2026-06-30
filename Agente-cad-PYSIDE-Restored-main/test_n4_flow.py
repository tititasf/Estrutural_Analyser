import json, sys, os
from pathlib import Path
sys.path.insert(0, 'scripts')
sys.path.insert(0, 'src/core')

item_id = 'L312'
temp_item = f'{item_id}_n4er'
obra_dir = Path(r'D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1')
json_dir = obra_dir / 'Fase-4_Sincronizacao' / 'JSON_Lajes'

# Read the existing JSON as the script would
ficha = json.loads((json_dir / f'{item_id}.json').read_text(encoding='utf-8'))
# Write temp JSON
temp_json = json_dir / f'{temp_item}.json'
temp_json.write_text(json.dumps(ficha, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Wrote temp JSON: {temp_json}')
print(f'nome in JSON: {ficha.get("nome")}')
print(f'_stog_pose: {ficha.get("_stog_pose")}')
print(f'Coords: {ficha.get("coordenadas")}')

# Run script
import subprocess
result = subprocess.run(
    [sys.executable, 'scripts/gerar_lj_dxf_stog.py', '--obra', str(obra_dir), '--item', temp_item],
    capture_output=True, text=True
)
print('STDOUT:', result.stdout[-500:] if result.stdout else 'EMPTY')
print('STDERR:', result.stderr[-300:] if result.stderr else 'EMPTY')
print('Return code:', result.returncode)

# Check output
fase6 = obra_dir / 'Fase-6_Execucao_CAD'
expected = fase6 / f'LJ_preview_{temp_item}.dxf'
print(f'Expected DXF: {expected} exists={expected.exists()}')

# Check extents
if expected.exists():
    import ezdxf
    from ezdxf import bbox
    doc = ezdxf.readfile(str(expected))
    msp = doc.modelspace()
    ext = bbox.extents(msp)
    print(f'extmin={ext.extmin}, extmax={ext.extmax}')
    print(f'entities={len(msp)}')
else:
    # Try finding it in n4
    n4 = fase6 / 'n4' / f'LJ_preview_{temp_item}.dxf'
    print(f'n4 path: {n4} exists={n4.exists()}')
    # Glob fallback
    for p in fase6.glob(f'*{temp_item}*'):
        print(f'  found: {p}')

# Cleanup
temp_json.unlink(missing_ok=True)
if expected.exists():
    expected.unlink(missing_ok=True)
