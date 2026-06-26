import os
import sys
import shutil
from pathlib import Path
from tufup.repo import Repository

# --- CONFIGURATION ---
# Add parent dir to path to import src.config
sys.path.append(str(Path(__file__).parent.parent))
from src import config

DIST_DIR = Path("dist")
REPO_DIR = Path("repository")
KEYS_DIR = Path("keys")
FINAL_BUNDLE_DIR = DIST_DIR / config.APP_NAME

def update_repo():
    print("🛡️ Finishing Tufup Packaging...")
    
    if not FINAL_BUNDLE_DIR.exists():
        print(f"❌ Error: Compiled bundle not found at {FINAL_BUNDLE_DIR}")
        print("   Did the Nuitka build finish successfully?")
        sys.exit(1)
    

    # 1. Clean existing broken metadata (Safety First)
    metadata_dir = REPO_DIR / "metadata"
    if metadata_dir.exists():
        print("   🧹 Cleaning old/broken metadata...")
        shutil.rmtree(metadata_dir)
    
    # 2. Initialize FRESH Repository
    print("   ✨ Initializing new Tufup repository...")
    repo = Repository(app_name=config.APP_NAME, repo_dir=REPO_DIR, keys_dir=KEYS_DIR)
    
    # Check if we need to initialize (if metadata missing)
    # Since we deleted metadata, we MUST initialize.
    repo.initialize() 

    # 3. CRITICAL: Inject NEW public key into the Bundle
    # We must ensure the client (inside the bundle) has the key that matches this new repo.
    print("   🔑 Syncing new keys to bundle...")
    src_key = KEYS_DIR / "timestamp.pub"
    dest_key_dir = FINAL_BUNDLE_DIR / "keys"
    dest_key_dir.mkdir(parents=True, exist_ok=True)
    
    if src_key.exists():
        shutil.copy(src_key, dest_key_dir / "timestamp.pub")
    else:
        print("❌ CRITICAL: New timestamp.pub not found!")
        sys.exit(1)

    # 4. Add Bundle
    print(f"   📦 Adding bundle for {config.APP_NAME} v{config.APP_VERSION}...")
    repo.add_bundle(
        new_bundle_dir=FINAL_BUNDLE_DIR,
        new_version=config.APP_VERSION
    )
    
    repo.publish_changes(private_key_dirs=[KEYS_DIR])
    print("✅ Repository Updated successfully.")
    print("\n👉 Now you can run: python scripts/deploy_update.py")

if __name__ == "__main__":
    update_repo()
