import sqlite3

conn = sqlite3.connect('project_data.vision')
cur = conn.cursor()

project_id = '43b93bed-8af8-473f-9d27-0d99b4d0764a'

print("="*60)
print("STATUS DO PROJETO P-1")
print("="*60)

# 1. Documentos
cur.execute('SELECT COUNT(*) FROM project_documents WHERE project_id = ?', (project_id,))
print(f"\nDOCUMENTOS: {cur.fetchone()[0]}")

cur.execute('SELECT name, file_path, extension FROM project_documents WHERE project_id = ?', (project_id,))
for doc in cur.fetchall():
    print(f"  - {doc[0]}")
    print(f"    Path: {doc[1]}")
    print(f"    Ext: {doc[2]}")

# 2. DXF Path do projeto
cur.execute('SELECT dxf_path FROM projects WHERE id = ?', (project_id,))
result = cur.fetchone()
dxf_path = result[0] if result and result[0] else "NULL"
print(f"\nDXF_PATH NO PROJETO: {dxf_path}")

# 3. Pilares/Vigas/Lajes
cur.execute('SELECT COUNT(*) FROM pillars WHERE project_id = ?', (project_id,))
pillars = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM beams WHERE project_id = ?', (project_id,))
beams = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM slabs WHERE project_id = ?', (project_id,))
slabs = cur.fetchone()[0]

print(f"\nDADOS PROCESSADOS:")
print(f"  Pilares: {pillars}")
print(f"  Vigas: {beams}")
print(f"  Lajes: {slabs}")

conn.close()
print("\n" + "="*60)
