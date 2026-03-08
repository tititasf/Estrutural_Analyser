import PyInstaller.__main__
import os
import sys
import shutil
from pathlib import Path

# Config
APP_NAME = "Estrutural_Analyzer_download_updater"
SCRIPT_PATH = "src/updater.py"
ICON_PATH = "assets/icon.ico"
DIST_DIR = "dist"
WORK_DIR = "build/pyinstaller_bootstrapper"

def build():
    print("🚀 Building Bootstrapper with PyInstaller...")
    
    # Ensure dependencies
    if not os.path.exists("repository/metadata/root.json"):
        print("❌ Error: repository/metadata/root.json not found.")
        print("   Run scripts/deploy_update.py first.")
        sys.exit(1)
    
    # Define Data Adds (Source;Desc)
    # PyInstaller uses --add-data "src;dest" (Windows uses ;)
    add_data = [
        "repository/metadata/root.json;.", # Root metadata to root of bundle
        "keys/timestamp.pub;.",            # Public key to root
        "assets/icon.ico;assets",          # Icon file to assets folder
        "assets/logo.jpg;assets"           # Logo file to assets folder
    ]
    
    # We must construct the args list
    args = [
        SCRIPT_PATH,
        f"--name={APP_NAME}",
        "--onefile",
        "--noconsole", # GUI Mode - No Black Window
        f"--icon={ICON_PATH}",
        "--clean",
        "--noconfirm",
        f"--distpath={DIST_DIR}",
        f"--workpath={WORK_DIR}",
        "--runtime-tmpdir=.", # Unpack mostly in temp
        # Needed imports
        "--hidden-import=requests",
        "--hidden-import=tufup",
        "--hidden-import=winshell",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--collect-all=tufup", # Ensure all tufup internal data/deps are grabbed
        "--collect-all=certifi", # Ensure SSL certs are grabbed
    ]

    # Add data files
    for item in add_data:
        # Check if source exists
        real_src = item.split(";")[0]
        if not os.path.exists(real_src):
            print(f"⚠️ Warning: Data file {real_src} not found.")
        else:
            args.append(f"--add-data={item}")

    print("Executing PyInstaller...")
    PyInstaller.__main__.run(args)
    
    final_exe = Path(DIST_DIR) / f"{APP_NAME}.exe"
    if final_exe.exists():
        print(f"\n✅ Success: {final_exe}")
        print("   Ready to distribute.")
    else:
        print("\n❌ Build failed.")

if __name__ == "__main__":
    build()
