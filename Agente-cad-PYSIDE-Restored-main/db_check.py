import sqlite3, json

conn = sqlite3.connect(r'D:\Agente-cad-PYSIDE\project_data.vision')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("SELECT name, data_json FROM beams WHERE name LIKE '%V301%'")
rows = c.fetchall()

if rows:
    for row in rows:
        b = json.loads(row['data_json'])
        print('Viga:', b.get('name'))
        links = {k: v for k, v in b.get('links', {}).items() if 'fundo' in k}
        print('Links Fundo:', json.dumps(links, indent=2)[:1500])
else:
    print("Nenhuma viga V301 encontrada.")
conn.close()
