import sqlite3, json, ezdxf, re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = sqlite3.connect('project_data.vision')
DADOS_DIR = Path('DADOS-OBRAS')

obras_diag = ['Obra_TREINO_3', 'Obra_TREINO_10', 'Obra_TREINO_14', 'Obra_TREINO_18', 'Obra_TREINO_22']

for obra in obras_diag:
    projs = conn.execute('SELECT p.name, p.dxf_path FROM projects p WHERE p.work_name=? LIMIT 1', (obra,)).fetchall()
    if not projs:
        print(f'{obra}: no projects'); continue
    pav, dbpath = projs[0]
    fname = Path(dbpath).name if dbpath else None
    dxf = DADOS_DIR / obra / 'Fase-2_Triagem' / 'Estruturais_Pavimentos_Limpos' / fname if fname else None

    print(f'=== {obra} / {pav} ===')
    if not dxf or not dxf.exists():
        print(f'  DXF not found: {fname}'); print(); continue

    doc = ezdxf.readfile(str(dxf))
    msp = doc.modelspace()
    all_texts = []
    for e in msp:
        try:
            if e.dxftype() == 'TEXT':
                t = (getattr(e.dxf,'text','') or '').strip()
                if t: all_texts.append(t)
            elif e.dxftype() == 'MTEXT':
                for attr in ['plain_text']:
                    try:
                        fn = getattr(e, attr, None)
                        t = fn() if callable(fn) else ''
                        if t:
                            t2 = re.sub(r'\\[A-Za-z][^;]*;','',str(t)).strip()
                            all_texts.extend(t2.split('\n'))
                            break
                    except: pass
                else:
                    try:
                        t = str(e.dxf.text or '').strip()
                        t2 = re.sub(r'\\[A-Za-z][^;]*;','',t).strip()
                        if t2: all_texts.extend(t2.split('\n'))
                    except: pass
        except: pass

    all_texts = [t.strip() for t in all_texts if t.strip()]
    laje_pat = re.compile(r'^[LYXZW]\d+[A-Za-z]?$', re.I)
    laje_texts = [t for t in all_texts if laje_pat.match(t)]
    unique_texts = list(set(all_texts))[:8]

    # Slab
    s = conn.execute('SELECT s.name, s.points_json FROM slabs s JOIN projects p ON s.project_id=p.id WHERE p.work_name=? AND (s.points_json IS NOT NULL AND s.points_json != "[]") LIMIT 1', (obra,)).fetchone()
    slab_info = ''
    if s:
        pts = json.loads(s[1] or '[]')
        if pts:
            xs,ys = [p[0] for p in pts],[p[1] for p in pts]
            slab_info = f'slab={s[0]} x=[{min(xs):.0f},{max(xs):.0f}] y=[{min(ys):.0f},{max(ys):.0f}]'

    # Laje_pat matches
    if laje_texts:
        lx = [e.dxf.insert.x for e in msp if e.dxftype()=='TEXT' and laje_pat.match((getattr(e.dxf,'text','')).strip())][:3]
        ly = [e.dxf.insert.y for e in msp if e.dxftype()=='TEXT' and laje_pat.match((getattr(e.dxf,'text','')).strip())][:3]
        coord_info = f'  Text coords: x={lx} y={ly}'
    else:
        coord_info = ''

    print(f'  All texts: {len(all_texts)}, L/Y/other pattern: {len(laje_texts)}')
    print(f'  Unique sample: {unique_texts}')
    if laje_texts: print(f'  Laje names: {laje_texts[:8]}')
    if coord_info: print(coord_info)
    if slab_info: print(f'  {slab_info}')
    print()

conn.close()
