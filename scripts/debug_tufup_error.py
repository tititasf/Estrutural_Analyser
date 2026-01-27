import traceback
import sys
import os
from pathlib import Path
from tufup.repo import Repository

# Adiciona a raiz do projeto ao path para importar config
project_root = Path(r"c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE")
sys.path.append(str(project_root))
from src import config

def debug_tufup():
    REPO_DIR = project_root / "repository"
    KEYS_DIR = project_root / "keys"
    BUNDLE_DIR = project_root / "dist" / "AgenteCAD"
    
    print(f"Config: {config.APP_NAME} v{config.APP_VERSION}", flush=True)
    print(f"Repo Dir: {REPO_DIR}", flush=True)
    print(f"Bundle Dir: {BUNDLE_DIR}", flush=True)

    if not BUNDLE_DIR.exists():
        print(f"ERROR: Bundle dir does not exist: {BUNDLE_DIR}", flush=True)
        return

    try:
        print("Initializing Repository...", flush=True)
        repo = Repository(app_name=config.APP_NAME, repo_dir=REPO_DIR, keys_dir=KEYS_DIR)
        print("Repository object created. Loading roles (skipping key gen prompts)...", flush=True)
        # USA _load_keys_and_roles com create_keys=False para evitar o input() do initialize()
        # Se as chaves já existem, ele deve carregar corretamente.
        repo._load_keys_and_roles(create_keys=False)
        print("Repository initialized (roles loaded).", flush=True)
        
        # Inspeciona se repo.targets existe
        print(f"Repo internal targets: {getattr(repo, 'targets', 'MISSING')}", flush=True)

        # Verifica versão atual no repo
        latest_archive = repo.roles.get_latest_archive()
        if latest_archive:
            print(f"Latest archive in repo: {latest_archive.version}", flush=True)
            if latest_archive.version == config.APP_VERSION:
                print(f"Version {config.APP_VERSION} already exists. Removing to overwrite...", flush=True)
                repo.remove_latest_bundle()
                print("Old bundle removed.", flush=True)
        
        print("Calling add_bundle with skip_patch=True...", flush=True)
        repo.add_bundle(new_bundle_dir=BUNDLE_DIR, new_version=config.APP_VERSION, skip_patch=True)
        print("Success!", flush=True)
    except Exception:
        print("\n--- TRACEBACK ---", flush=True)
        traceback.print_exc()
        print("-----------------\n", flush=True)

if __name__ == "__main__":
    debug_tufup()
