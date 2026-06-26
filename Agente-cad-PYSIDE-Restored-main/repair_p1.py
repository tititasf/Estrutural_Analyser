import sqlite3
import os
import uuid

db_path = 'project_data.vision'
project_id = '43b93bed-8af8-473f-9d27-0d99b4d0764a'
dxf_path = r'C:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\projects_repo\P-1.dxf'

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("="*60)
print("REPARANDO PROJETO P-1")
print("="*60)

# 1. Verificar estado atual
cur.execute('SELECT dxf_path FROM projects WHERE id = ?', (project_id,))
result = cur.fetchone()
current_dxf = result[0] if result and result[0] else "NULL"
print(f"\n1. DXF atual no banco: {current_dxf}")

# 2. Atualizar dxf_path do projeto
cur.execute('UPDATE projects SET dxf_path = ? WHERE id = ?', (dxf_path, project_id))
print(f"2. Atualizando dxf_path para: {dxf_path}")

# 3. Verificar se documento já existe
cur.execute('SELECT COUNT(*) FROM project_documents WHERE project_id = ? AND file_path = ?', 
            (project_id, dxf_path))
doc_exists = cur.fetchone()[0]

if doc_exists == 0:
    # 4. Registrar como documento
    doc_id = str(uuid.uuid4())
    cur.execute('''
        INSERT INTO project_documents (id, project_id, name, file_path, extension, sync_status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (doc_id, project_id, 'P-1.dxf (Principal)', dxf_path, '.dxf', 'synced'))
    print(f"3. Documento registrado: P-1.dxf (ID: {doc_id})")
else:
    print(f"3. Documento já existe ({doc_exists} registros)")

conn.commit()

# 5. Verificar resultado
print("\n" + "="*60)
print("VERIFICAÇÃO FINAL")
print("="*60)

cur.execute('SELECT dxf_path FROM projects WHERE id = ?', (project_id,))
result = cur.fetchone()
print(f"DXF registrado: {result[0] if result else 'NULL'}")

cur.execute('SELECT COUNT(*) FROM project_documents WHERE project_id = ?', (project_id,))
doc_count = cur.fetchone()[0]
print(f"Total de documentos: {doc_count}")

cur.execute('SELECT name, file_path FROM project_documents WHERE project_id = ?', (project_id,))
docs = cur.fetchall()
if docs:
    print("\nDocumentos encontrados:")
    for doc_name, doc_path in docs:
        exists = "EXISTS" if os.path.exists(doc_path) else "NOT FOUND"
        print(f"  - {doc_name} [{exists}]")
        print(f"    Path: {doc_path}")

conn.close()
print("\n" + "="*60)
print("REPARO CONCLUÍDO")
print("="*60)
