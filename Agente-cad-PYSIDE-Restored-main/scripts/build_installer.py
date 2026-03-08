import os
import sys
import subprocess
import shutil
from pathlib import Path

# Add parent dir to path to import src.config
sys.path.append(str(Path(__file__).parent.parent))
from src import config

def build_installer():
    print("📀 Building Professional Installer...")
    
    # 1. Find ISCC
    iscc_path = shutil.which("ISCC")
    
    if not iscc_path:
        # Try 'where' command (Windows)
        try:
            output = subprocess.check_output(["where", "ISCC"], encoding="utf-8").strip()
            lines = output.splitlines()
            if lines and os.path.exists(lines[0]):
                iscc_path = lines[0]
        except Exception:
            pass

    if not iscc_path:
        # Check standard paths
        chk_paths = [
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            r"C:\Program Files\Inno Setup 6\ISCC.exe"
        ]
        for p in chk_paths:
            if os.path.exists(p):
                iscc_path = p
                break
    
    if not iscc_path:
        print("❌ Inno Setup Compiler (ISCC) not found!")
        print("   Please install Inno Setup 6+ and add it to PATH.")
        sys.exit(1)
        
    print(f"   Using Compiler: {iscc_path}")

    # 2. Define Variables
    script_path = Path("scripts/installer.iss").absolute()
    version = config.APP_VERSION
    output_name = f"AgenteCAD_Setup_v{version}"
    
    # 3. Verify Dist
    dist_dir = Path("dist/AgenteCAD")
    if not dist_dir.exists():
        print(f"❌ Error: Dist directory {dist_dir} does not exist.")
        sys.exit(1)

    # 4. Run Build
    cmd = [
        iscc_path,
        f"/DMyAppVersion={version}",
        f"/DOutputBaseFilename={output_name}",
        str(script_path)
    ]
    
    print(f"   Compiling installer for v{version}...")
    try:
        subprocess.check_call(cmd)
        print("✅ Installer finished successfully!")
        print(f"   Output: releases/{output_name}.exe")
    except subprocess.CalledProcessError as e:
        print(f"❌ Installer compilation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_installer()
