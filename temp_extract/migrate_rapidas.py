import sqlite3
from pathlib import Path
import shutil
import uuid
import datetime

DB_PATH = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal_data.db'

def migrate_obras_rapidas():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    obras = conn.execute('SELECT * FROM portal_obras WHERE arquivo_nome IS NOT NULL AND arquivo_nome != \'\'').fetchall()
    
    print(f'Found {len(obras)} obras rapidas.')
    for o in obras:
        docs = conn.execute('SELECT * FROM portal_documentos WHERE obra_id=?', (o['id'],)).fetchall()
        print(f"Obra {o['nome']} (ID: {o['id']}) tem {len(docs)} documentos.")
        if len(docs) == 0:
            doc_id = str(uuid.uuid4())
            now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
            
            local_path = Path(o['local_path']) if o['local_path'] else None
            
            # Insert the document
            conn.execute('''
                INSERT INTO portal_documentos (
                    id, obra_id, arquivo_nome, arquivo_drive_id, arquivo_hash, status, 
                    pavimento_sugerido, tipo_documento_sugerido, local_path,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                doc_id, o['id'], o['arquivo_nome'], o['arquivo_drive_id'], o['arquivo_hash'], o['estado'],
                'Pavimento unico', 'Bruto', o['local_path'], now, now
            ))
            
            # Clear the legacy fields
            conn.execute('''
                UPDATE portal_obras
                SET arquivo_nome = NULL, arquivo_drive_id = NULL
                WHERE id = ?
            ''', (o['id'],))
            
            # Move the file on disk
            if local_path and local_path.exists():
                entrada_file = local_path / "entrada" / o['arquivo_nome']
                doc_dir = local_path / "docs" / doc_id
                doc_file = doc_dir / o['arquivo_nome']
                
                if entrada_file.exists():
                    doc_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(entrada_file), str(doc_file))
                    print(f"Moved {entrada_file} to {doc_file}")
                else:
                    print(f"Warning: {entrada_file} does not exist!")
            else:
                print(f"Warning: local_path {local_path} does not exist!")
                
    conn.commit()
    conn.close()
    print("Done.")

if __name__ == '__main__':
    migrate_obras_rapidas()
