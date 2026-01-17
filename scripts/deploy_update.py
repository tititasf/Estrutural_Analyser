import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load .env file explicitly
load_dotenv()


# --- CONFIGURATION ---
# Add parent dir to path to import src.config
sys.path.append(str(Path(__file__).parent.parent))
from src import config

REPO_DIR = Path("repository")

# Credentials
SUPABASE_URL = config.SUPABASE_URL
SUPABASE_BUCKET = config.SUPABASE_BUCKET_UPDATES
# Deployment requires SERVICE ROLE key to bypass RLS (Row Level Security)
# Do NOT hardcode it in config.py (which goes to client).
SUPABASE_TOKEN = os.getenv("SUPABASE_SERVICE_ROLE", config.SUPABASE_KEY)

def upload_to_supabase():
    print("☁️ Uploading 'repository/' to Supabase Cloud...")
    
    if not REPO_DIR.exists():
        print("❌ Repository not found. Did you run the build script first?")
        sys.exit(1)
        
    headers = {
        "Authorization": f"Bearer {SUPABASE_TOKEN}"
    }
    
    count = 0
    errors = 0
    
    # Walk repository and upload EVERYTHING
    # This syncs the metadata (targets.json, etc) and the new zip bundles.
    MAX_PART_SIZE = 5 * 1024 * 1024 # 5MB for maximum stability against machine-level SSL corruption

    for root, _, files in os.walk(REPO_DIR):
        for file in files:
            file_path = Path(root) / file
            # Flatten structure for Supabase root (metadata and targets in the same bucket root)
            rel_path = file
            file_size = file_path.stat().st_size
            
            # --- STRATEGY 1: NORMAL UPLOAD (Small files) ---
            if file_size < MAX_PART_SIZE:
                with open(file_path, 'rb') as f:
                    data = f.read()
                
                url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{rel_path}"
                print(f"   ⬆️ {rel_path} ({file_size/1024:.1f} KB)...", end="")
                
                headers_upsert = headers.copy()
                headers_upsert["x-upsert"] = "true"
                headers_upsert["Content-Type"] = "application/json" if file.endswith(".json") else "application/octet-stream"

                try:
                    r = requests.post(url, headers=headers_upsert, data=data)
                    if r.status_code in [200, 201]:
                        print(" OK")
                        count += 1
                    else:
                        print(f" FAIL ({r.status_code}) - {r.text}")
                        errors += 1
                except Exception as e:
                    print(f" EXCEPTION: {e}")
                    errors += 1
            
            # --- STRATEGY 2: CHUNKED UPLOAD (Large files) ---
            else:
                print(f"   📦 Large file detected: {rel_path} ({file_size/1024/1024:.1f} MB)")
                print(f"      -> Splitting into {MAX_PART_SIZE/1024/1024:.0f}MB chunks...")
                
                with open(file_path, 'rb') as f:
                    part_num = 0
                    while True:
                        chunk_data = f.read(MAX_PART_SIZE)
                        if not chunk_data:
                            break
                        
                        part_num += 1
                        part_name = f"{rel_path}.part{part_num}"
                        url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{part_name}"
                        
                        print(f"      ⬆️ Use Part {part_num}...", end="")
                        
                        headers_upsert = headers.copy()
                        headers_upsert["x-upsert"] = "true"
                        headers_upsert["Content-Type"] = "application/octet-stream"
                        
                        try:
                            r = requests.post(url, headers=headers_upsert, data=chunk_data)
                            if r.status_code in [200, 201]:
                                print(" OK")
                            else:
                                print(f" FAIL ({r.status_code})")
                                errors += 1
                        except Exception as e:
                            print(f" ERR: {e}")
                            errors += 1
                
                count += 1 # Count the main file as processed

                # --- CLEANUP GHOST PARTS ---
                # Attempt to delete additional parts (76, 77, etc) that might exist from previous larger versions
                print(f"      🧹 Cleaning up potential ghost parts (scanning parts {part_num+1} to {part_num+20})...")
                for ghost_num in range(part_num + 1, part_num + 21):
                    ghost_name = f"{rel_path}.part{ghost_num}"
                    ghost_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{ghost_name}"
                    try:
                        # Supabase DELETE
                        r_del = requests.delete(ghost_url, headers=headers)
                        if r_del.status_code == 200:
                            print(f"         🗑️ Deleted ghost {ghost_name}")
                    except:
                        pass

    if errors == 0:
        print(f"\n✅ Deployment Complete! {count} files synchronized.")
        print("🚀 Clients will detect this update on next launch.")
    else:
        print(f"\n⚠️ Deployment finished with {errors} errors. Please retry.")

if __name__ == "__main__":
    upload_to_supabase()
