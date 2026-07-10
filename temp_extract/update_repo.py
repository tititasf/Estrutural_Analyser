import re
path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\db\repository.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

new_mover = '''def mover_documento_para_indeterminado(conn: sqlite3.Connection, doc_id: str) -> None:
    conn.execute(
        """UPDATE portal_documentos
           SET pavimento_confirmado = '', tipo_documento_confirmado = '',
               updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
           WHERE id = ?""",
        (doc_id,),
    )
    conn.commit()'''

content = re.sub(r'def mover_documento_para_indeterminado\(.*?\).*?conn\.commit\(\)', new_mover, content, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
