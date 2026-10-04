"""Read archived LV sources without restoring or executing them."""
from pathlib import Path
import zipfile
root=Path(__file__).resolve().parents[2]
out=root/'scripts/arete/relatorios/20261001_lv_cut_fittings/archive_rules.txt'
chunks=[]
for p in root.parent.glob('*.zip'):
    with zipfile.ZipFile(p) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(('.py','.md','.json','.lsp')):continue
            if not any(k in name.lower() for k in ('viga','lateral','lv','corte')):continue
            raw=archive.read(name);s=raw.decode('utf8',errors='replace')
            lines=s.splitlines()
            hits=[i for i,l in enumerate(lines) if any(k in l.lower() for k in ('par_fundo','par_int','gerar_script_visao_corte'))]
            if hits:
                print('HITS',p.name,name,len(hits))
                chunks.append(f'FILE {p}:{name}')
                for i in hits:
                    chunks.extend(f'{j+1}: {lines[j]}' for j in range(max(0,i-12),min(len(lines),i+18)))
out.write_text('\n'.join(chunks),encoding='utf8')
print('LINES',len(chunks))
