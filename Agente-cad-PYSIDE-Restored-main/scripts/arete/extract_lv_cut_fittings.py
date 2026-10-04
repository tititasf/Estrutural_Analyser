"""Extract LV cut block geometry from a COPY of the original robot mold."""
from pathlib import Path
import subprocess, shutil, json
import ezdxf
from ezdxf.addons import Importer

root=Path(__file__).resolve().parents[2]
out=root/'scripts/arete/relatorios/20261001_lv_cut_fittings'
out.mkdir(parents=True,exist_ok=True)
source=root.parent/'BASE_DWG_PARA_COMANDOS_SCRIPTS.dwg'
dwg=out/'mold_copy.dwg'; dxf=out/'mold_copy.dxf'
if not dxf.exists():
    shutil.copy2(source,dwg)
    scr=out/'export_mold.scr'
    scr.write_text(f'DXFOUT\n{dxf.as_posix()}\n16\nQUIT\nY\n',encoding='ascii')
    proc=subprocess.run([r'C:\Program Files\Autodesk\AutoCAD 2021\accoreconsole.exe','/i',str(dwg),'/s',str(scr)],capture_output=True,timeout=120)
    (out/'export.log').write_bytes(proc.stdout+proc.stderr)
    if not dxf.exists(): raise RuntimeError('DWG export failed; see export.log')
doc=ezdxf.readfile(dxf)
names=['PAR_ESQ','PAR_FUNDO_ESQ','PAR_FUNDO_DIR','par_int_esq','par_int_dir']
summary={name:[e.dxftype() for e in doc.blocks.get(name)] if name in doc.blocks else None for name in names}
print(json.dumps(summary,indent=2))
if any(summary[n] is None for n in names): raise RuntimeError('Missing original LV blocks')
asset=root/'scripts/arete/assets/lv_cut_fittings.dxf'
asset.parent.mkdir(parents=True,exist_ok=True)
target=ezdxf.new('R2018'); importer=Importer(doc,target)
importer.import_blocks(names); importer.finalize()
target.saveas(asset)
(out/'block_inventory.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
print('ASSET',asset,asset.stat().st_size)
