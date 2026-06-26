import sqlite3

db_path = 'project_data.vision'
project_id = '43b93bed-8af8-473f-9d27-0d99b4d0764a'
dxf_path = r'C:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\projects_repo\P-1.dxf'

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("="*60)
print("CORRIGINDO DXF_PATH DO P-1")
print("="*60)

# Verificar antes
cur.execute('SELECT dxf_path FROM projects WHERE id = ?', (project_id,))
before = cur.fetchone()
print(f"\nANTES: {before[0] if before and before[0] else 'NULL'}")

# Atualizar
cur.execute('UPDATE projects SET dxf_path = ? WHERE id = ?', (dxf_path, project_id))
rows_affected = cur.rowcount
print(f"Linhas afetadas: {rows_affected}")

# Commit
conn.commit()
print("✅ COMMIT realizado")

# Verificar depois
cur.execute('SELECT dxf_path FROM projects WHERE id = ?', (project_id,))
after = cur.fetchone()
print(f"\nDEPOIS: {after[0] if after and after[0] else 'NULL'}")

# Verificar documento
cur.execute('SELECT name, file_path FROM project_documents WHERE project_id = ?', (project_id,))
docs = cur.fetchall()
print(f"\nDOCUMENTOS REGISTRADOS: {len(docs)}")
for doc_name, doc_path in docs:
    print(f"  - {doc_name}")
    print(f"    {doc_path}")

conn.close()
print("\n" + "="*60)
print("✅ REPARO CONCLUÍDO")
print("="*60)
