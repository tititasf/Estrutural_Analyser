import sqlite3
import uuid
import os

conn = sqlite3.connect('project_data.vision')
cur = conn.cursor()

project_id = 'c987bcdb-270b-49f1-ad55-9feba6b6d2e3'
dxf_path = r'C:/Users/Ryzen/Desktop/Treinos-Projetos-Dxf/P-1.dxf'

print("="*60)
print("REGISTRANDO DOCUMENTO P-1.dxf")
print("="*60)

# Verificar se já existe
cur.execute('SELECT id FROM project_documents WHERE project_id = ? AND file_path = ?', 
            (project_id, dxf_path))
exists = cur.fetchone()

if exists:
    print("\nDocumento JA EXISTE!")
else:
    # Registrar documento
    doc_id = str(uuid.uuid4())
    cur.execute('''
        INSERT INTO project_documents (id, project_id, name, file_path, extension, sync_status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (doc_id, project_id, 'P-1.dxf (Principal)', dxf_path, '.dxf', 'synced'))
    
    conn.commit()
    print(f"\nDOCUMENTO REGISTRADO!")
    print(f"  ID: {doc_id}")
    print(f"  Nome: P-1.dxf (Principal)")
    print(f"  Path: {dxf_path}")
    print(f"  Existe no disco: {os.path.exists(dxf_path)}")

# Verificar resultado final
cur.execute('''
    SELECT name, file_path, extension, created_at 
    FROM project_documents 
    WHERE project_id = ?
''', (project_id,))

docs = cur.fetchall()
print(f"\n TOTAL DE DOCUMENTOS: {len(docs)}")
for doc_name, doc_path, ext, created in docs:
    print(f"  - {doc_name} ({ext})")
    print(f"    {doc_path}")
    print(f"    Criado: {created}")

conn.close()
print("\n" + "="*60)
print("CONCLUIDO!")
print("="*60)
