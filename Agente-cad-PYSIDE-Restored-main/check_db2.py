import sqlite3
import sys
import json

def list_tables(db_path):
    print(f"\n--- Banco: {db_path} ---")
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        c.execute("SELECT id, name, links_json, data_json FROM beams WHERE name LIKE '%V302%'")
        for row in c.fetchall():
            print("== VIGA ENCONTRADA:", row[1], "==")
            links = json.loads(row[2]) if row[2] else {}
            # Mostrar os vínculos de "area_segs"
            area_links = {k: v for k, v in links.items() if 'area_segs' in k}
            if area_links:
                print("VINCULOS DE AREA_SEGS:")
                print(json.dumps(area_links, indent=2))
            else:
                print("Sem vínculos de area_segs.")
                
            data = json.loads(row[3]) if row[3] else {}
            area_data = {k: v for k, v in data.items() if 'area_segs' in k}
            if area_data:
                print("DADOS JSON DE AREA_SEGS:")
                print(json.dumps(area_data, indent=2))
                
    except Exception as e:
        print("Erro ao acessar:", e)

if __name__ == "__main__":
    list_tables('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/project_data.vision')
