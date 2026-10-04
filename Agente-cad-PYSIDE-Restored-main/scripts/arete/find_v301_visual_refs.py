from pathlib import Path
root=Path('scripts/arete/relatorios')
rows=[]
for p in root.rglob('*'):
    if p.is_file() and p.suffix.lower() in ('.html','.png','.dxf') and 'v301' in p.name.lower():
        rows.append((p.stat().st_mtime,p))
for _,p in sorted(rows,reverse=True)[:65]: print(p)
