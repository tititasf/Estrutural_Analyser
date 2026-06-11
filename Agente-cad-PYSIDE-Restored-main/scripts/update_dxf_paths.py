#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Atualiza dxf_path de todos os projetos no banco para o DXF estrutural correto."""
import sqlite3, pathlib

ROOT = pathlib.Path(__file__).parent.parent
DADOS_OBRAS = pathlib.Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')
DB_PATH = ROOT / 'project_data.vision'


def _find_dxf_for_pav(obra_path, pav_name):
    pav_upper = pav_name.upper().replace(' ', '').replace('-', '')

    def _best_from(dxfs):
        if not dxfs:
            return ''
        for d in dxfs:
            stem = d.stem.upper().replace(' ', '').replace('-', '')
            if pav_upper in stem or pav_name.upper() in d.stem.upper():
                return str(d)
        return str(dxfs[0])

    f1 = obra_path / 'Fase-1_Ingestao'
    if f1.exists():
        for sub in f1.iterdir():
            if sub.is_dir() and 'estruturai' in sub.name.lower():
                dxfs = list(sub.rglob('*.dxf')) + list(sub.rglob('*.DXF'))
                r = _best_from(dxfs)
                if r:
                    return r

    f2 = obra_path / 'Fase-2_Triagem'
    if f2.exists():
        dxfs = list(f2.rglob('*.dxf')) + list(f2.rglob('*.DXF'))
        r = _best_from(dxfs)
        if r:
            return r

    if f1.exists():
        dxfs = list(f1.rglob('*.dxf')) + list(f1.rglob('*.DXF'))
        r = _best_from(dxfs)
        if r:
            return r

    return ''


con = sqlite3.connect(str(DB_PATH))
cur = con.cursor()
rows = cur.execute('SELECT id, work_name, pavement_name FROM projects').fetchall()
updated = 0

for pid, work_name, pav_name in rows:
    obra_dir = DADOS_OBRAS / work_name
    if obra_dir.exists():
        new_dxf = _find_dxf_for_pav(obra_dir, pav_name)
        cur.execute('UPDATE projects SET dxf_path=? WHERE id=?', (new_dxf, pid))
        dxf_short = pathlib.Path(new_dxf).name if new_dxf else '(nao encontrado)'
        print(f'  {work_name}: {dxf_short}')
        updated += 1

con.commit()
con.close()
print(f'\nAtualizado {updated} projetos.')
