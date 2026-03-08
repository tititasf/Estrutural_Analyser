
import sys
import os
import logging
from pathlib import Path

# Setup path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from src.core.database import DatabaseManager

def audit_works():
    db = DatabaseManager()
    works = db.get_all_works()
    print(f"Works in DB ({len(works)}):")
    for w in works:
        print(f" - {w}")
        
    documents = db.get_all_project_documents_debug() if hasattr(db, 'get_all_project_documents_debug') else []
    # Helper to count docs
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM project_documents")
    count = cursor.fetchone()[0]
    print(f"Total documents in DB: {count}")
    conn.close()

if __name__ == "__main__":
    audit_works()
