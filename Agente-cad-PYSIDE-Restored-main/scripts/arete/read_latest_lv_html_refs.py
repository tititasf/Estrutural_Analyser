from pathlib import Path
from bs4 import BeautifulSoup
root=Path('scripts/arete/relatorios/g2v')
rows=[]
for p in root.rglob('*.html'):
    if 'lv' not in str(p).lower() and 'v301' not in str(p).lower():continue
    rows.append((p.stat().st_mtime,p))
for _,p in sorted(rows,reverse=True)[:10]:
    print('\nHTML',p)
    soup=BeautifulSoup(p.read_text(encoding='utf8',errors='replace'),'html.parser')
    print(soup.get_text(' ',strip=True)[:1200])
    print('sources',[(e.name,str(e.get('src') or e.get('data') or e.get('href'))[:120]) for e in soup.find_all(['iframe','object','img','a'])][:12])
