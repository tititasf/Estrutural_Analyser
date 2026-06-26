import sqlite3

conn = sqlite3.connect('project_data.vision')
cur = conn.cursor()

print("="*60)
print("BUSCANDO PROJETO P-1 DA OBRA-TESTE1")
print("="*60)

# Buscar por nome e obra
cur.execute('''
    SELECT id, name, work_name, pavement_name, dxf_path, created_at 
    FROM projects 
    WHERE name = ? AND work_name = ?
''', ('P-1', 'OBRA-TESTE1'))

results = cur.fetchall()

print(f"\nResultados encontrados: {len(results)}")

if results:
    for row in results:
        pid, name, work, pav, dxf, created = row
        print(f"\nPROJETO ENCONTRADO:")
        print(f"  ID: {pid}")
        print(f"  Nome: {name}")
        print(f"  Obra: {work}")
        print(f"  Pavimento: {pav}")
        print(f"  DXF: {dxf if dxf else 'NULL'}")
        print(f"  Criado: {created}")
        
        # Verificar documentos
        cur.execute('SELECT COUNT(*) FROM project_documents WHERE project_id = ?', (pid,))
        doc_count = cur.fetchone()[0]
        print(f"  Documentos: {doc_count}")
        
        # Verificar pilares/vigas/lajes
        cur.execute('SELECT COUNT(*) FROM pillars WHERE project_id = ?', (pid,))
        pil_count = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM beams WHERE project_id = ?', (pid,))
        beam_count = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM slabs WHERE project_id = ?', (pid,))
        slab_count = cur.fetchone()[0]
        print(f"  Dados: {pil_count}P, {beam_count}V, {slab_count}L")
else:
    print("\nPROJETO NAO ENCONTRADO!")
    print("\nBuscando projetos similares...")
    cur.execute("SELECT id, name, work_name FROM projects WHERE name LIKE '%P-1%' OR work_name LIKE '%TESTE%'")
    similares = cur.fetchall()
    for s in similares:
        print(f"  - {s[1]} (Obra: {s[2]}, ID: {s[0]})")

conn.close()
print("\n" + "="*60)
