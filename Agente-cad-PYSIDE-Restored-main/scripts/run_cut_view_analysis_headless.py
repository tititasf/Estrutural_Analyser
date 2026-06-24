"""
Roda _auto_link_slab_cut_views headless para PAV 13 e salva de volta no DB.
Usa Qt offscreen para evitar GUI real.
"""
from __future__ import annotations
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
PROJ_ID = '4869be2b-f17c-410b-a9c8-98a887ec1c95'
DXF_PATH = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-1_Ingestao/Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF/TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA.dxf"


def main():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    # Import after QApplication exists
    from main import MainWindow

    win = MainWindow.__new__(MainWindow)
    win.slabs_found = []
    win.dxf_data = None
    win._log_lines = []

    def _log(msg):
        print(msg)
    win.log = _log

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT name, points_json, links_json, extra_data_json FROM slabs WHERE project_id=? ORDER BY name",
        (PROJ_ID,)
    )
    rows = cur.fetchall()
    print(f"Carregadas {len(rows)} lajes")

    print(f"DXF: {DXF_PATH}")
    if Path(DXF_PATH).exists():
        from src.core.dxf_loader import DXFLoader
        win.dxf_data = DXFLoader.load_dxf(DXF_PATH)
        print(f"DXF: {len(win.dxf_data.get('polylines', []))} polylines, {len(win.dxf_data.get('texts', []))} textos")
    else:
        print("AVISO: DXF não encontrado")

    # Reconstruct slabs list preserving full extra data for slab_height
    slabs = []
    for name, pts_json, links_json, extra_json in rows:
        pts = json.loads(pts_json) if pts_json else []
        links = json.loads(links_json) if links_json else {}
        extra = json.loads(extra_json) if extra_json else {}
        slab = {'name': name, 'points': pts, 'links': links}
        slab.update(extra)
        slabs.append(slab)

    win.slabs_found = slabs

    poly_map = win._slab_polygon_map(slabs)
    print(f"poly_map: {len(poly_map)} entradas")

    print("\nRodando _auto_link_slab_cut_views...")
    added_cuts, added_pillars = win._auto_link_slab_cut_views(slabs)
    print(f"Novos: {added_cuts} cortes, {added_pillars} pilares")

    n_saved = 0
    for slab in slabs:
        name = slab.get('name')
        links = slab.get('links') or {}
        cur.execute(
            "UPDATE slabs SET links_json=? WHERE project_id=? AND name=?",
            (json.dumps(links), PROJ_ID, name)
        )
        n_saved += 1
    con.commit()
    print(f"Salvas {n_saved} lajes no DB")
    con.close()
    print("Concluído.")


if __name__ == '__main__':
    main()
