import sqlite3
import os
import sys
import logging

# Adicionar caminho do projeto ao sys.path para importar os módulos internos
PROJECT_ROOT = r"c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE"
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from src.core.cad_utils import get_cad_version_info

DB_PATH = os.path.join(PROJECT_ROOT, "project_data.vision")

def migrate_missing_versions():
    logging.basicConfig(level=logging.INFO)
    if not os.path.exists(DB_PATH):
        print(f"Banco de dados não encontrado em {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Atualizar Projects
        cursor.execute("SELECT id, dxf_path FROM projects WHERE (file_version IS NULL OR file_version = '') AND dxf_path IS NOT NULL AND dxf_path != ''")
        projects = cursor.fetchall()
        print(f"Escaneando {len(projects)} projetos...")
        for p_id, dxf_path in projects:
            if os.path.exists(dxf_path):
                version = get_cad_version_info(dxf_path)
                cursor.execute("UPDATE projects SET file_version = ? WHERE id = ?", (version, p_id))
                print(f"Projeto {p_id}: {version}")

        # 2. Atualizar Documents
        cursor.execute("SELECT id, file_path FROM project_documents WHERE (file_version IS NULL OR file_version = '') AND (extension LIKE '.dwg' OR extension LIKE '.dxf')")
        docs = cursor.fetchall()
        print(f"Escaneando {len(docs)} documentos...")
        for d_id, f_path in docs:
            if f_path and os.path.exists(f_path):
                version = get_cad_version_info(f_path)
                cursor.execute("UPDATE project_documents SET file_version = ? WHERE id = ?", (version, d_id))
                print(f"Documento {d_id}: {version}")

        conn.commit()
        print("Migração concluída com sucesso!")
    except Exception as e:
        print(f"Erro durante a migração: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_missing_versions()
