import os
import sys
import shutil
import subprocess
from pathlib import Path
from tufup.repo import Repository

# --- CONFIGURATION ---
# Add parent dir to path to import src.config
sys.path.append(str(Path(__file__).parent.parent))
from src import config

DIST_DIR = Path("dist")
REPO_DIR = Path("repository")
KEYS_DIR = Path("keys")
NUITKA_OUTPUT_DIR = DIST_DIR / "main.dist"
FINAL_BUNDLE_DIR = DIST_DIR / config.APP_NAME

def run_nuitka(target_script, console_mode="disable", output_name="main"):
    print(f"🔥 Starting Nuitka Compilation: {target_script}...")
    
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        # "--lto=yes", # Disabled for speed (too slow on Scipy)
        "--plugin-enable=pyside6",
        "--include-qt-plugins=all",
        "--nofollow-import-to=pytest",
        "--nofollow-import-to=unittest",
        "--nofollow-import-to=scipy.testing",
        "--nofollow-import-to=numpy.testing",
        "--nofollow-import-to=scipy", # Exclude scipy entirely (too slow/bloat)
        "--disable-ccache", # Disable broken cache
        f"--windows-console-mode={console_mode}",
        "--output-dir=dist",
        "--windows-icon-from-ico=assets/icon.ico",
        "--company-name=VisionEstrutural",
        "--product-name=AgenteCAD",
        "--file-version=" + config.APP_VERSION,
        "--product-version=" + config.APP_VERSION,
        target_script
    ]
     
    if not os.path.exists("assets/icon.ico"):
        cmd = [x for x in cmd if "icon" not in x]

    print("Executing:", " ".join(cmd))
    subprocess.check_call(cmd)
    
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
    run_nuitka("main.py", "force", "main")
    
    # 2. Build Updater (OneFile? or just another folder?)
    # Using Onefile for updater is cleanest for "just one exe file to click".
    # Warning: OneFile unpacks to temp, might be slow start (3-5s). Acceptable for an updater.
    print("🔨 Building Updater/Bootstrapper (OneFile)...")
    updater_name = "Estrutural_Analyzer_download_updater.exe"
    
    subprocess.check_call([
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--windows-console-mode=force", # Force console for updater so user sees progress
        "--windows-icon-from-ico=assets/icon.ico",
        f"--output-filename={updater_name}",
        "--output-dir=dist",
        "--include-data-file=repository/metadata/root.json=root.json", # Embed initial trust
        "--include-data-file=keys/timestamp.pub=timestamp.pub", # Embed public key
        "src/updater.py"
    ])
    
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

def update_repo():
    print("🛡️ Preparation of Tufup Repository (Local)...")
    
    # Initialize Repo if needed
    # Fixed argument error by passing app_name explicitly
    repo = Repository(app_name=config.APP_NAME, repo_dir=REPO_DIR, keys_dir=KEYS_DIR)
    
    # Add Bundle
    repo.add_bundle(
        new_version=config.APP_VERSION,
        new_bundle_dir=FINAL_BUNDLE_DIR
    )
    
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
    print(f"1. Test your new executable here: {FINAL_BUNDLE_DIR / 'main.exe'}")
    print("2. If satisfied, run: python scripts/deploy_update.py")

if __name__ == "__main__":
    main()
