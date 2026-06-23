import sqlite3

conn = sqlite3.connect('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/data/database.db')
c = conn.cursor()
c.execute("""
    SELECT f.element_name, COUNT(s.id), SUM(s.length) 
    FROM reverse_eng_fichas f 
    JOIN reverse_eng_fichas_segments s ON s.ficha_id = f.id 
    WHERE f.obra_name='Obra_TREINO_1' AND f.pavimento='13'
    GROUP BY f.element_name;
""")
rows = c.fetchall()
for r in rows:
    print(r)
