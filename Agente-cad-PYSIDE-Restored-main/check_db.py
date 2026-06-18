import sqlite3
import sys

def list_tables(db_path):
    print(f"\n--- Banco: {db_path} ---")
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in c.fetchall()]
        print("Tabelas:", tables)
        
        # Se 'obra_triagem' existir, vamos mostrar as linhas da V302
        if 'obra_triagem' in tables:
            print(">> obra_triagem encontrada!")
            c.execute("SELECT * FROM obra_triagem WHERE obj_name LIKE '%V302%'")
            for row in c.fetchall():
                print(row)
                
        # Se 'beams' existir, mostrar tbm
        if 'beams' in tables:
            print(">> beams encontrada!")
            c.execute("SELECT id_obj, name FROM beams WHERE name LIKE '%V302%'")
            for row in c.fetchall():
                print(row)
                
    except Exception as e:
        print("Erro ao acessar:", e)

if __name__ == "__main__":
    list_tables('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/project_data.vision')
    list_tables('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/.brv/blobs/storage.db')
