import os
import sys
import shutil
import subprocess
from pathlib import Path
from tufup.repo import Repository

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).parent.parent.absolute()
sys.path.append(str(BASE_DIR))
from src import config

DIST_DIR = BASE_DIR / "dist"
REPO_DIR = BASE_DIR / "repository"
KEYS_DIR = BASE_DIR / "keys"
ASSETS_DIR = BASE_DIR / "assets"
ICON_PATH = ASSETS_DIR / "icon.ico"

# --- ROBO PATHS (Dynamic Imports) ---
ROBO_LATERAIS_DIR = BASE_DIR / "_ROBOS_ABAS" / "Robo_Laterais_de_Vigas"
ROBO_LAJES_DIR = BASE_DIR / "_ROBOS_ABAS" / "Robo_Lajes"
ROBO_FUNDOS_DIR = BASE_DIR / "_ROBOS_ABAS" / "Robo_Fundos_de_Vigas" / "compactador-producao"
ROBO_PILARES_DIR = BASE_DIR / "_ROBOS_ABAS" / "Robo_Pilares" / "pilares-atualizado-09-25"

NUITKA_OUTPUT_DIR = DIST_DIR / "main.dist"
FINAL_BUNDLE_DIR = DIST_DIR / config.APP_NAME

def run_nuitka(target_script, console_mode="disable", output_name="main"):
    print(f"🔥 Starting Nuitka Compilation: {target_script}...")
    
    cmd = [

        sys.executable, "-m", "nuitka",
        "--standalone",
        "--include-package=setuptools",  # Required for distutils shim
        "--include-package=tufup",       # Ensure all tufup submodules are present
        "--include-package=chromadb",    # Fix Vector DB runtime errors
        "--include-package=numpy",       # Ensure numpy is fully included to avoid runtime init errors
        "--include-package=cv2",         # Ensure opencv is fully included
        "--prefer-source-code",          # Better dependency resolution for numpy/cv2
        
        # Dynamic Robo Modules
        "--include-module=robo_laterais_viga_pyside",
        "--include-package=laje_src",
        "--include-module=fundo_pyside",
        "--include-module=bootstrap",    # Robo Pilares Entry Point
        "--include-package=src.interfaces", # Sorter Interfaces (Lazy loaded)
        "--include-package=src.robots",     # Robot Logic (Lazy loaded)
        f"--include-data-dir={BASE_DIR}/ferramentas_LOAD_LISP=ferramentas_LOAD_LISP",
        f"--include-data-dir={BASE_DIR}/SCRIPTS_ROBOS=SCRIPTS_ROBOS",
        
        "--plugin-enable=pyside6",
        "--enable-plugin=tk-inter", # Required for Robo Laterais (tkinter)
        # Python 3.12 compatibility for distutils:
        "--include-package=setuptools._distutils",
        "--include-package=_distutils_hack", # Required for setuptools <-> distutils in Py3.12
        "--include-package=pkg_resources",   # Often needed by tufup/setuptools
        "--include-qt-plugins=all",
        "--nofollow-import-to=pytest",
        "--nofollow-import-to=unittest",
        "--nofollow-import-to=scipy.testing",
        "--nofollow-import-to=numpy.testing",
        # "--nofollow-import-to=scipy", # Removed: potentially causing numpy init issues
        "--disable-ccache",
        f"--windows-console-mode={console_mode}",
        f"--output-dir={DIST_DIR}",
        f"--windows-icon-from-ico={ICON_PATH}",
        "--company-name=VisionEstrutural",
        "--product-name=AgenteCAD",
        f"--output-filename={config.APP_NAME}.exe",
        "--file-version=" + config.APP_VERSION,
        "--product-version=" + config.APP_VERSION,
        str(target_script)
    ]
     
    if not ICON_PATH.exists():
        cmd = [x for x in cmd if "icon" not in x]

    print("Executing:", " ".join(cmd))
    
    # Configure Environment with Robo Paths for Nuitka to find them
    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH", "")
    additional_paths = [
        str(ROBO_LATERAIS_DIR),
        str(ROBO_LAJES_DIR),
        str(ROBO_FUNDOS_DIR),
        str(ROBO_PILARES_DIR),
        str(BASE_DIR)
    ]
    env["PYTHONPATH"] = os.pathsep.join(additional_paths + [current_pythonpath])
    print(f"🔧 PYTHONPATH configured with {len(additional_paths)} extra paths for resolution.")

    subprocess.check_call(cmd, cwd=str(BASE_DIR), env=env)
    
    # Handle Output
    # Nuitka creates {script_stem}.dist
    script_stem = Path(target_script).stem
    built_dist = DIST_DIR / f"{script_stem}.dist"
    
    if built_dist.exists():
        if output_name == "main":
            # For main app, we move the whole folder to be the bundle root
            if FINAL_BUNDLE_DIR.exists():
                shutil.rmtree(FINAL_BUNDLE_DIR)
            shutil.move(built_dist, FINAL_BUNDLE_DIR)
            print(f"✅ Main App Compiled: {FINAL_BUNDLE_DIR}")
        else:
            # For auxiliary tools (updater), we move the executable AND dependencies 
            # into the MAIN bundle. BUT, Nuitka standalone builds are self-contained.
            # Merging them reduces size but is complex (dll hell).
            # EASIER STRATEGY: Build updater as a ONEFILE (very slow start) or Standalone?
            # User wants it in the same repo.
            # Ideally, they share DLLs.
            # Nuitka "Module" mode? No.
            # For simplicity now: Build Updater as standalone, verify it works.
            # Wait, if we put updater.exe inside AgenteCAD/, it needs its own DLLs if standalone.
            # That duplicates size.
            # For now, let's just copy the updater.exe into the main folder? 
            # NO, Nuitka standalone EXE depends on the .dist folder structure.
            # If we want a single "update.exe" inside the main folder check, we need OneFile.
            # But OneFile is slow.
            # Let's build updater as OneFile? Or just put it in a subfolder?
            # User expectation: "update.exe" alongside "main.exe".
            # If we simply copy main.exe logic to updater.py, we might share the dist?
            # Nuitka has --nofollow-imports to use existing python env? No.
            
            # DECISION: Build updater.py using the SAME env/dist?
            # Nuitka supports building multiple entry points in one dist? Not easily.
            # Alternative: Keep updater simple. Just use the generated `updater.dist` folder renamed to `updater/`?
            # User asked for `update.exe` inside the repo.
            # Let's try to build updater as ONEFILE (--onefile) to enable it to sit single-file next to main.exe.
            pass

    else:
        print(f"❌ Nuitka failed to produce output for {target_script}")
        sys.exit(1)

def build_all():
    # 0. Clean
    if DIST_DIR.exists():
        try:
            shutil.rmtree(DIST_DIR)
        except:
            pass

    # 1. Build Main App (Standalone Folder)
    # User requested Console Mode "force" for debugging startup issues
    run_nuitka(BASE_DIR / "main.py", "force", "main")
    
    # 2. Build Updater (OneFile? or just another folder?)
    # Using Onefile for updater is cleanest for "just one exe file to click".
    # Warning: OneFile unpacks to temp, might be slow start (3-5s). Acceptable for an updater.
    print("🔨 Building Updater/Bootstrapper (OneFile)...")
    updater_name = "Estrutural_Analyzer_download_updater.exe"
    
    subprocess.check_call([
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--windows-console-mode=force", # Force console for updater so user sees progress
        f"--windows-icon-from-ico={ICON_PATH}" if ICON_PATH.exists() else "",
        f"--output-filename={updater_name}",
        f"--output-dir={DIST_DIR}",
        f"--include-data-file={BASE_DIR}/repository/metadata/root.json=root.json", # Embed initial trust
        f"--include-data-file={BASE_DIR}/keys/timestamp.pub=timestamp.pub", # Embed public key
        f"--include-data-dir={BASE_DIR}/ferramentas_LOAD_LISP=ferramentas_LOAD_LISP", # Include LISP tools
        f"--include-data-dir={BASE_DIR}/SCRIPTS_ROBOS=SCRIPTS_ROBOS", # Include Scripts output dir structure
        str(BASE_DIR / "src" / "updater.py")
    ], cwd=str(BASE_DIR))
    
    # Updater is now standalone in dist/, no need to move it into the bundle.
    if (DIST_DIR / updater_name).exists():
        print(f"✅ Bootstrapper Built: {DIST_DIR / updater_name}")
    else:
        print("⚠️ Bootstrapper build failed.")


def prepare_bundle_extras():
    print("📦 Adding Security Keys to Bundle...")
    target_keys_dir = FINAL_BUNDLE_DIR / "keys"
    target_keys_dir.mkdir(exist_ok=True, parents=True)
    
    # Copy Public Key
    src_key = KEYS_DIR / "timestamp.pub"
    if src_key.exists():
        shutil.copy(src_key, target_keys_dir / "timestamp.pub")
        print("   -> Key copied.")
    else:
        print("❌ CRITICAL: timestamp.pub not found in keys/!")
        sys.exit(1)

    # CREATE DEBUG.BAT
    print("📝 Creating debug.bat for persistent terminal session...")
    debug_bat_content = f"@echo off\necho 🚀 Iniciando {config.APP_NAME} em modo de depuração...\necho.\n{config.APP_NAME}.exe\necho.\necho ⚠️ O programa foi encerrado. O terminal continuará aberto para depuração.\npause\n"
    with open(FINAL_BUNDLE_DIR / "debug.bat", "w", encoding="utf-8") as f:
        f.write(debug_bat_content)

def update_repo():
    keys_dir = KEYS_DIR
    repo_dir = REPO_DIR
    
    # 1. Initialize Repo (bypass prompt)
    print("   -> Initializing Tufup Repository (Loading keys)...")
    repo = Repository(app_name=config.APP_NAME, repo_dir=repo_dir, keys_dir=keys_dir)
    # _load_keys_and_roles(create_keys=False) evita o prompt "Overwrite key pair?"
    repo._load_keys_and_roles(create_keys=False)
    
    # 2. Check & Clean existing version
    latest_archive = repo.roles.get_latest_archive()
    if latest_archive:
        print(f"   -> Latest archive in repo: {latest_archive.version}")
        # Converte para string para garantir comparação
        if str(latest_archive.version) == str(config.APP_VERSION):
            print(f"   -> Version {config.APP_VERSION} already exists. Removing from metadata...")
            repo.remove_latest_bundle()
    
    # 3. Force clean physical file (Safety net against prompts)
    # Tufup asks for confirmation if file exists, even if metadata was removed (rare but possible)
    targets_dir = repo_dir / "targets"
    archive_name = f"{config.APP_NAME}-{config.APP_VERSION}.tar.gz"
    conflicting_archive = targets_dir / archive_name
    if conflicting_archive.exists():
        print(f"   -> [Pre-flight] Force removing conflicting file: {archive_name}")
        try:
            os.remove(str(conflicting_archive))
        except Exception as e:
            print(f"   ⚠️ Warning: failed to os.remove: {e}")

    # 4. Add Bundle
    print(f"   -> Adding bundle from: {FINAL_BUNDLE_DIR}")
    # skip_patch=True is safer for automated builds involving re-uploads
    repo.add_bundle(
        new_bundle_dir=FINAL_BUNDLE_DIR,
        new_version=config.APP_VERSION,
        skip_patch=True
    )
    
    # 5. Publish Changes
    print("   -> Publishing changes (signing)...")
    repo.publish_changes(private_key_dirs=[KEYS_DIR])
    print("   -> Repository Updated locally.")


    
def main():
    print("🚀 Build & Package (Local Only)")
    print(f"   Version: {config.APP_VERSION}")
    
    # 1. Compile
    build_all()
    
    # 2. Extras
    prepare_bundle_extras()
    
    # 3. Tufup
    try:
        update_repo()
    except Exception as e:
        print(f"❌ Tufup Error: {e}")
        sys.exit(1)
        
    print("\n✅ BUILD COMPLETE!")
    exe_path = FINAL_BUNDLE_DIR / f"{config.APP_NAME}.exe"
    print(f"1. Test directory: {FINAL_BUNDLE_DIR}")
    print(f"2. Executable: {exe_path}")
    print(f"3. Debug Helper: {FINAL_BUNDLE_DIR / 'debug.bat'} (Para manter o terminal aberto)")

if __name__ == "__main__":
    main()
