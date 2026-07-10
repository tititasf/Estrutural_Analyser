import re
path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\drive_poller.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

replacement = '''
                import uuid
                import datetime
                import shutil
                
                obra_id = repo.criar_obra(
                    conn, membro_id=membro["id"], nome=slug,
                    pasta_drive_id=pasta_id, arquivo_drive_id=None,
                    arquivo_nome=None, arquivo_hash=None,
                    estado="aguardando_ingestao",
                    local_path=str(dest.parent.parent),  # .../<slug>/
                )
                
                doc_id = str(uuid.uuid4())
                now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
                conn.execute(
                    """INSERT INTO portal_documentos (
                        id, obra_id, arquivo_nome, arquivo_drive_id, arquivo_hash, status, 
                        pavimento_sugerido, tipo_documento_sugerido, local_path,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'pendente', ?, ?, ?, ?, ?)""",
                    (
                        doc_id, obra_id, arq.name, arq.file_id, md5,
                        'Pavimento unico', 'Bruto', str(dest.parent.parent), now, now
                    )
                )
                
                doc_dir = dest.parent.parent / 'docs' / doc_id
                doc_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dest), str(doc_dir / arq.name))
'''

content = re.sub(r'obra_id = repo\.criar_obra\([^)]+\)', replacement, content, count=1, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
