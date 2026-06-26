import sqlite3, json

def run():
    try:
        conn = sqlite3.connect('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/data/db/projeto.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT obj_name, obj_data FROM general_analysis WHERE obj_name LIKE '%V302%'")
        rows = c.fetchall()
        
        found = False
        for r in rows:
            data = json.loads(r['obj_data'])
            name = r['obj_name']
            
            # Print specifically the area_segs for the segments
            keys = [k for k in data.keys() if 'area_segs' in k]
            if keys:
                print(f"=============================")
                print(f"FOUND IN: {name}")
                for k in sorted(keys):
                    print(f"\n{k}:")
                    print(json.dumps(data[k], indent=2))
                found = True
                
        if not found:
            print("Nenhum vinculo de area_segs encontrado em V302.")
            
    except Exception as e:
        print("Erro:", e)

if __name__ == '__main__':
    run()
