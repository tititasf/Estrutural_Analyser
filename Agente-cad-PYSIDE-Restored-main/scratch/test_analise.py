import sys
import os
import sqlite3
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from main import MainWindow

def test_fundo_viga():
    try:
        app = QApplication(sys.argv)
        window = MainWindow()

        db_path = "D:/Agente-cad-PYSIDE/project_data.vision"
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT id FROM projects WHERE name='RDD-EST-EXE-301-R00_R2018_ASCII_ODA' LIMIT 1")
        row = c.fetchone()
        if not row:
            print("Project not found")
            sys.exit(1)
        project_id = row[0]
        conn.close()
        
        print(f"Loading project {project_id}...")
        window.current_project_id = project_id
        try:
            window.load_project_action()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("Failed to load project action, but continuing...")
        
        # Mock dialogs so the script doesn't hang!
        window._show_preprocess_dialog = lambda x: print("Mocked _show_preprocess_dialog")
        window._run_pre_validation_dialog = lambda: True
        if hasattr(window, '_compare_fv_n1_n2'):
            window._compare_fv_n1_n2 = lambda x: print("Mocked _compare_fv_n1_n2")
        
        print("Running Analise Geral...")
        try:
            window.process_pillars_action()
        except Exception as e:
            import traceback
            print("Failed to run process_pillars_action, stopping.")
            print(traceback.format_exc())
            return
            
        print("Analise Geral finished!")
        
        # Check DB for Fundo de Viga geometries
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name, data_json FROM beams WHERE project_id=?", (project_id,))
        beams = c.fetchall()
        
        found_fv_with_contour = 0
        total_fv = 0
        
        for name, data_json in beams:
            b = json.loads(data_json)
            if name == 'V403':
                print(f"DEBUG V403 links: {b.get('links', {}).keys()}")
            has_fundo = any(k.startswith('viga_fundo_seg_') for k in b.get('links', {}).keys())
            if has_fundo:
                total_fv += 1
                has_contour = False
                for k, v in b.get('links', {}).items():
                    if k.startswith('viga_fundo_seg_') and k.endswith('_area_segs'):
                        if 'contour' in v and len(v['contour']) > 0:
                            has_contour = True
                if has_contour:
                    found_fv_with_contour += 1
                else:
                    print(f"Beam {name} has Fundo segments but NO contour in DB!")
                    
        print(f"\n--- TEST RESULTS ---")
        print(f"Total Beams with Fundo segments: {total_fv}")
        print(f"Beams with Fundo segments AND populated contours: {found_fv_with_contour}")
        
        conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fundo_viga()
