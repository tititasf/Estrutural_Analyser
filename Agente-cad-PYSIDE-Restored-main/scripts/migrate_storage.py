
import sys
import os
import shutil
import logging
from pathlib import Path

# Ensure src is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from src.core.database import DatabaseManager
from src.core.storage.project_storage import ProjectStorageManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate_storage():
    logging.info("Starting storage migration...")
    
    db_path = os.path.join(project_root, "project_data.vision")
    db = DatabaseManager(db_path)
    
    # Force base_dir to be project root
    base_dir = project_root
    storage = ProjectStorageManager(base_dir)
    
    files_moved = 0
    errors = 0
    
    # 1. Migrar Obras (Criar estrutura de pastas)
    works = db.get_all_works()
    for work_name in works:
        try:
            storage.initialize_work_structure(work_name)
        except Exception as e:
            logging.error(f"Failed to initialize structure for work '{work_name}': {e}")
            
    # 2. Migrar Documentos
    conn = db._get_conn()
    conn.row_factory = None # We want tuples or dicts, wait. default is tuple.
    cursor = conn.cursor()
    
    # Fetch all project documents
    # Join with projects to get work_name if missing in document?
    # project_documents usually has project_id. projects has work_name.
    
    query = """
    SELECT pd.id, pd.file_path, pd.phase, pd.category, p.work_name, pd.name, pd.extension
    FROM project_documents pd
    JOIN projects p ON pd.project_id = p.id
    """
    
    cursor.execute(query)
    documents = cursor.fetchall()
    
    for doc in documents:
        doc_id, old_path_str, phase, category, work_name, doc_name, ext = doc
        
        if not old_path_str:
            continue
            
        old_path = Path(old_path_str)
        if not old_path.exists():
            logging.warning(f"File not found for doc {doc_id} ({doc_name}): {old_path}")
            continue
            
        if not work_name:
            logging.warning(f"Doc {doc_id} has no associated work. Skipping.")
            continue
            
        # Determine expected path
        # If phase is missing, default to 1?
        phase_id = phase if phase else 1
        class_name = category if category else "Geral"
        
        # Calculate new path using storage manager logic
        try:
            work_path = storage.get_work_path(work_name)
            phase_folder = storage.get_phase_folder_name(phase_id)
            class_folder = storage.get_class_folder_name(class_name)
            
            target_dir = work_path / phase_folder / class_folder
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Use original filename
            filename = old_path.name
            new_path = target_dir / filename
            
            # Check if already in correct place
            if old_path.resolve() == new_path.resolve():
                # Already migrated
                continue
            
            # Move file
            logging.info(f"Moving {old_path} -> {new_path}")
            if new_path.exists():
                # Handle conflict
                stem = new_path.stem
                new_path = target_dir / f"{stem}_migrated{ext}"
            
            shutil.move(old_path, new_path)
            
            # Update DB
            cursor.execute("UPDATE project_documents SET file_path = ? WHERE id = ?", (str(new_path), doc_id))
            conn.commit()
            
            files_moved += 1
            
        except Exception as e:
            logging.error(f"Error migrating doc {doc_id}: {e}")
            errors += 1
            
    conn.close()
    logging.info(f"Migration complete. Moved: {files_moved}, Errors: {errors}")

if __name__ == "__main__":
    migrate_storage()
