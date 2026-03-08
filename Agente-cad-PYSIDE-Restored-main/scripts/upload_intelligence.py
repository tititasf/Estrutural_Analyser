import os
import json
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def upload_intelligence(db_type="laje"):
    """
    db_type: 'laje' ou 'structural'
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY") # Precisamos do Secret Key para upload manual
    
    if not url or not key:
        print("❌ Supabase URL ou Secret Key não encontrados no .env")
        return

    supabase = create_client(url, key)
    
    db_filename = f"{db_type}_ai.db"
    local_path = Path("data") / db_filename
    version_filename = f"version_{db_type}.json"
    
    if not local_path.exists():
        print(f"❌ Arquivo local não encontrado: {local_path}")
        return

    # 1. Gerar Version Info (simples timestamp ou versão incremental)
    version_data = {
        "version": os.path.getmtime(local_path),
        "filename": db_filename,
        "updated_at": str(os.path.getmtime(local_path))
    }
    
    with open(version_filename, "w") as f:
        json.dump(version_data, f)

    print(f"📤 Subindo {db_filename} para o bucket 'intelligence'...")
    
    # Upload DB
    with open(local_path, "rb") as f:
        supabase.storage.from_("intelligence").upload(
            path=db_filename,
            file=f,
            file_options={"x-upsert": "true"}
        )

    # Upload Version JSON
    with open(version_filename, "rb") as f:
        supabase.storage.from_("intelligence").upload(
            path=version_filename,
            file=f,
            file_options={"x-upsert": "true"}
        )

    print(f"✨ Inteligência '{db_type}' atualizada com sucesso na nuvem!")
    os.remove(version_filename)

if __name__ == "__main__":
    import sys
    db_arg = sys.argv[1] if len(sys.argv) > 1 else "laje"
    upload_intelligence(db_arg)
