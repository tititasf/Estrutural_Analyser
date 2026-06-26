
import os
import sys
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

# --- Configuração com paths absolutos ---
DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
STORAGE_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")

# Canonical category names (devem bater com ProjectStorageManager.PHASE_CLASSES)
CAT_BRUTO    = "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)"
CAT_ATAS     = "Documentos e Atas de Reunioes(.PDF/.MD)"
CAT_DETALHES = "Detalhes Estruturais (.DWG/.PDF/.DXF/.MD)"
CAT_REVERSA  = "Projetos Finais Para Engenharia Reversa (suporte a dwg e dxf)"
CAT_LIMPOS   = "Estruturais Pavimentos Limpos"  # Fase 2
CAT_OUTROS   = "📁 Outros / Não Classificados"

# Mapeamento de TODOS os nomes de subpastas encontrados no filesystem real
# (incluindo variantes legadas + nomes atuais)
PHASE_CLASSES_MAP = {
    # --- Categoria: Bruto ---
    "Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF": CAT_BRUTO,
    "Estruturais_Pavimentos_Brutos":                   CAT_BRUTO,
    "DXF_Bruto":                                       CAT_BRUTO,

    # --- Categoria: Atas ---
    "Documentos_e_Atas_de_Reunioes_PDF_MD":            CAT_ATAS,
    "Documentos_e_Atas_de_ReunioesPDF_MD":             CAT_ATAS,
    "Documentos_Atas_de_Reunioes":                     CAT_ATAS,

    # --- Categoria: Detalhes ---
    "Detalhes_Estruturais_DWG_PDF_DXF_MD":             CAT_DETALHES,
    "Detalhes_Estruturais":                            CAT_DETALHES,

    # --- Categoria: Engenharia Reversa ---
    "Projetos_Finalizados_para_Engenharia_Reversa":    CAT_REVERSA,
    "Projetos_Finais_Para_Engenharia_Reversa_suporte_a_dwg_e_dxf": CAT_REVERSA,

    # --- Fase 2 ---
    "Estruturais_Pavimentos_Limpos":                   CAT_LIMPOS,
}

# Heurística de fallback por keyword (cobre novas variantes futuras)
def _infer_category_by_keyword(folder_name: str) -> str:
    if "Bruto" in folder_name or "DXF_Bruto" in folder_name:
        return CAT_BRUTO
    if "Atas" in folder_name or "Reunioes" in folder_name or "Reunião" in folder_name:
        return CAT_ATAS
    if "Detalhe" in folder_name:
        return CAT_DETALHES
    if "Reversa" in folder_name or "Finalizado" in folder_name or "Final" in folder_name:
        return CAT_REVERSA
    if "Limpo" in folder_name:
        return CAT_LIMPOS
    return CAT_OUTROS


def connect_db():
    return sqlite3.connect(str(DB_PATH))


def scan_and_index(filter_work: str | None = None):
    label = f"obra='{filter_work}'" if filter_work else "todas as obras"
    print(f"🚀 Iniciando Auto-Indexação em '{STORAGE_ROOT}' ({label})...")
    print(f"   DB: {DB_PATH}")

    if not DB_PATH.exists():
        print(f"❌ ERRO: DB não encontrado em {DB_PATH}")
        sys.exit(1)

    conn = connect_db()
    cursor = conn.cursor()

    # Carregar docs existentes (mapeamento path → {id, category})
    cursor.execute("SELECT file_path, id, category FROM project_documents")
    existing_docs = {row[0]: {'id': row[1], 'category': row[2]} for row in cursor.fetchall()}
    print(f"📋 {len(existing_docs)} documentos já no DB")

    updates = []
    inserts = []

    # Varrer obras (ou só a obra solicitada)
    for work_name in sorted(os.listdir(STORAGE_ROOT)):
        if filter_work and work_name != filter_work:
            continue

        work_path = STORAGE_ROOT / work_name
        if not work_path.is_dir():
            continue

        print(f"\n📂 Obra: {work_name}")

        for root, dirs, files in os.walk(work_path):
            root_path = Path(root)
            parent_folder = root_path.name

            # Ignorar a pasta raiz da obra (sem categoria definida)
            if root_path == work_path:
                continue

            category = PHASE_CLASSES_MAP.get(parent_folder)
            if category is None:
                category = _infer_category_by_keyword(parent_folder)

            for file in files:
                file_lower = file.lower()
                if not file_lower.endswith(('.dwg', '.dxf', '.pdf', '.md')):
                    continue

                full_path = str((root_path / file).resolve())

                if full_path in existing_docs:
                    current_cat = existing_docs[full_path]['category']
                    doc_id = existing_docs[full_path]['id']
                    if current_cat != category and category != CAT_OUTROS:
                        print(f"  🔄 Corrigindo categoria: {file}\n     {current_cat}\n  -> {category}")
                        updates.append((category, doc_id))
                    continue

                # Inferir fase pela pasta Fase-N_*
                phase = 1
                for part in root_path.parts:
                    if part.startswith("Fase-"):
                        try:
                            phase = int(part.split("-")[1].split("_")[0])
                        except Exception:
                            pass

                doc_id = str(uuid.uuid4())
                now = datetime.now().isoformat()

                print(f"  ➕ {file} | fase={phase} | {category}")
                inserts.append((
                    doc_id,
                    file,
                    full_path,
                    os.path.splitext(file)[1],
                    now,
                    work_name,
                    phase,
                    category,
                ))

    if updates:
        print(f"\n🔄 Corrigindo {len(updates)} categorias...")
        cursor.executemany("UPDATE project_documents SET category = ? WHERE id = ?", updates)

    if inserts:
        print(f"\n💾 Inserindo {len(inserts)} novos documentos...")
        cursor.executemany(
            "INSERT INTO project_documents (id, name, file_path, extension, created_at, work_name, phase, category) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            inserts,
        )

    conn.commit()
    conn.close()

    print(f"\n✅ Indexação concluída — {len(inserts)} inseridos, {len(updates)} corrigidos")


if __name__ == "__main__":
    # Uso: python auto_indexer.py [nome_da_obra]
    work_filter = sys.argv[1] if len(sys.argv) > 1 else None
    scan_and_index(filter_work=work_filter)
