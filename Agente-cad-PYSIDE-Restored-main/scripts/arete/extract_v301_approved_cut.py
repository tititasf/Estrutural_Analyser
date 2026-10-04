from pathlib import Path
from bs4 import BeautifulSoup
import base64
root=Path('scripts/arete/relatorios')
soup=BeautifulSoup((root/'g2v/lv_debug/LV_DEBUG.html').read_text(encoding='utf8'),'html.parser')
for panel in soup.select('[data-folha]'):
    if panel['data-folha']=='V301|CORTE|N4-Corte' or ('V301' in panel['data-folha'] and 'N4' in panel['data-folha'] and 'Corte' in panel['data-folha']):
        print(panel['data-folha'],panel.get_text(' ',strip=True)[:700])
        im=panel.find('img')
        if im and im.get('src','').startswith('data:image/png;base64,'):
            out=root/'20261001_lv_n3_cortes/v301_html_approved_cut.png'
            out.write_bytes(base64.b64decode(im['src'].split(',',1)[1]))
            print(out)
