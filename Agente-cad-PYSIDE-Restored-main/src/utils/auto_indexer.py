
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

# Configuração
DB_PATH = "project_data.vision"
STORAGE_ROOT = "DADOS-OBRAS"

PHASE_CLASSES_MAP = {
    "Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF": "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)",
    "Documentos_e_Atas_de_Reunioes_PDF_MD": "Documentos e Atas de Reunioes(.PDF/.MD)",
    "Detalhes_Estruturais_DWG_PDF_DXF_MD": "Detalhes Estruturais (.DWG/.PDF/.DXF/.MD)",
    "Projetos_Finais_Para_Engenharia_Reversa_suporte_a_dwg_e_dxf": "Projetos Finais Para Engenharia Reversa (suporte a dwg e dxf)",
    # Fase 2
    "Estruturais_Pavimentos_Limpos": "Estruturais Pavimentos Limpos" 
}

def connect_db():
    return sqlite3.connect(DB_PATH)


def scan_and_index():
    print(f"🚀 Iniciando Auto-Indexação e Correção em '{STORAGE_ROOT}'...")
    conn = connect_db()
    cursor = conn.cursor()
    
    # Mapeamento reverso de paths para ID (para poder atualizar)
    cursor.execute("SELECT file_path, id, category FROM project_documents")
    existing_docs = {row[0]: {'id': row[1], 'category': row[2]} for row in cursor.fetchall()}
    print(f"📋 Analisando {len(existing_docs)} documentos existentes...")

    updates = []
    inserts = []
    
    # 2. Varrer diretórios
    for work_name in os.listdir(STORAGE_ROOT):
        work_path = os.path.join(STORAGE_ROOT, work_name)
        if not os.path.isdir(work_path):
            continue
            
        print(f"Checking work: {work_name}")
        
        for root, dirs, files in os.walk(work_path):
            for file in files:
                file_lower = file.lower()
                if file_lower.endswith(('.dwg', '.dxf', '.pdf', '.md')):
                    full_path = str(Path(os.path.join(root, file)).resolve())
                    
                    # Inferir categoria pela pasta pai
                    parent_folder = os.path.basename(root)
                    category = PHASE_CLASSES_MAP.get(parent_folder, "📁 Outros / Não Classificados")
                    
                    # Heurística de fallback
                    if category == "📁 Outros / Não Classificados":
                        if "Bruto" in parent_folder: category = "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)"
                        elif "Atas" in parent_folder: category = "Documentos e Atas de Reunioes(.PDF/.MD)"
                        elif "Detalhes" in parent_folder: category = "Detalhes Estruturais (.DWG/.PDF/.DXF/.MD)"
                        elif "Reversa" in parent_folder: category = "Projetos Finais Para Engenharia Reversa (suporte a dwg e dxf)"
                        elif "Limpos" in parent_folder: category = "Estruturais Pavimentos Limpos" # Fase 2

                    if full_path in existing_docs:
                        # Verifica se precisa atualizar
                        current_cat = existing_docs[full_path]['category']
                        doc_id = existing_docs[full_path]['id']
                        
                        # Se a categoria atual estiver errada (não classificada) e agora temos uma melhor
                        if current_cat != category and category != "📁 Outros / Não Classificados":
                            print(f"  🔄 Updating: {file} | {current_cat} -> {category}")
                            updates.append((category, doc_id))
                        continue

                    # Criar novo registro
                    doc_id = str(uuid.uuid4())
                    now = datetime.now().isoformat()
                    
                    phase = 1
                    for part in root.split(os.sep):
                        if part.startswith("Fase-"):
                            try:
                                phase = int(part.split("-")[1].split("_")[0])
                            except: pass

                    print(f"  ➕ Indexing: {file} -> {category}")
                    
                    inserts.append((
                        doc_id, # id
                        file, # name
                        full_path, # file_path
                        os.path.splitext(file)[1], # extension
                        now, # created_at
                        work_name, # work_name
                        phase, # phase
                        category # category
                    ))

    # 3. Aplicar Updates
    if updates:
        print(f"🔄 Corrigindo categorias de {len(updates)} documentos...")
        cursor.executemany("UPDATE project_documents SET category = ? WHERE id = ?", updates)
        
    # 4. Aplicar Inserts
    if inserts:
        print(f"💾 Salvando {len(inserts)} novos documentos...")
        cursor.executemany("""
            INSERT INTO project_documents (id, name, file_path, extension, created_at, work_name, phase, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, inserts)
        
    conn.commit()
    conn.close()
    print("✅ Processo de Indexação e Correção Finalizado!")

if __name__ == "__main__":
    scan_and_index()
