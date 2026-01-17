import sys
import os
import shutil
import subprocess
from pathlib import Path

def build_fast():
    print("🚀 Fast Build (PyInstaller) for Updater Validation")
    print("================================================")
    
    # Clean dist
    dist_dir = Path("dist")
    if dist_dir.exists():
        try:
            shutil.rmtree(dist_dir)
        except Exception as e:
            print(f"⚠️ Warning: Could not clean dist dir: {e}")
        
    # 1. Build Updater (OneFile)
    print("🔨 Building Updater (updater.exe)...")
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name=updater",
        "--clean",
        "--log-level=WARN",
        "--windowed", # Start as hidden? No, updater usually needs console unless GUI. script says updater has visible console in other builds.
        # User requested visible updater? Let's keep console visible for debug.
        "--console", 
        "--icon=assets/icon.ico",
        "src/updater.py"
    ])
    
    # 2. Build Main App (OneDir - to mimic Nuitka structure vaguely, but Tufup needs a zip)
    # Wait, simple flow:
    # Build main.exe (onedir or onefile).
    # Zip it.
    # Tufup it.
    
    print("🔨 Building Main App (main.exe)...")
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        "--onedir", # Tufup usually updates a directory.
        "--name=AgenteCAD",
        "--clean",
        "--log-level=WARN",
        "--noconsole",
        "--icon=assets/icon.ico",
        "main.py"
    ])
    
    print("✅ Build Complete.")
    print("   Updater: dist/updater.exe")
    print("   Main:    dist/AgenteCAD/main.exe")
    
    # 3. Packaging for Tufup
    # We need to run finish_packaging.py logic here or simpler?
    # finish_packaging.py uses nuitka dist structure?
    # Let's just run finish_packaging.py if it works on "AgenteCAD" folder.
    
    print("📦 Running Tufup Packaging...")
    try:
        subprocess.check_call([sys.executable, "scripts/finish_packaging.py"])
        print("✅ Tufup Repo Updated.")
    except Exception as e:
        print(f"❌ Packaging failed: {e}")

if __name__ == "__main__":
    build_fast()
