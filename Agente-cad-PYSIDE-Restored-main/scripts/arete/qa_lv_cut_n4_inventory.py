"""Inventário de seções do N4 e extração live N2, apenas leitura."""
import sys, json, sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from gerar_lv_n4_fichas import _entry_from_live_recorte, N4_OUT
import ezdxf
beams=['V'+str(i) for i in range(301,333)]+['V309A','VF202','VF203','VF301']
rows=[]
for beam in beams:
    entry=_entry_from_live_recorte(beam)
    path=N4_OUT/f'LV_preview_{beam}_CORTE.dxf'
    row={'beam':beam,'n2_live_available':bool(entry),'n4_path':str(path),'n4_exists':path.exists()}
    if entry:
        row['section_views']=entry.get('section_views',[])
        row['n2_section_count']=len(row['section_views'])
        row['n2_heights']=entry.get('h_section_all')
    if path.exists():
        doc=ezdxf.readfile(path)
        texts=[e.dxf.text for e in doc.modelspace().query('TEXT')]
        row['section_titles']=[t for t in texts if beam in t]
        row['n4_drawn_count']=texts.count('a')
        row['n4_anatomy_counts']={t:texts.count(t) for t in ('a','b','c')}
        row['n4_modified']=path.stat().st_mtime
    rows.append(row)
    print(beam,row.get('n2_section_count'),row.get('section_titles'),flush=True)
Path(sys.argv[1]).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
