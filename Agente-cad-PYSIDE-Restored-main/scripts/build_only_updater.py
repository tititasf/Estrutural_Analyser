import os
import sys
import subprocess
import shutil
from pathlib import Path

# Add parent dir to path to import src.config
sys.path.append(str(Path(__file__).parent.parent))
from src import config

def build_updater_only():
    print("🚀 Building Standalone Updater/Bootstrapper...")
    print(f"   App Version: {config.APP_VERSION}")
    
    # Configuration
    updater_script = "src/updater.py"
    output_name = "Estrutural_Analyzer_download_updater.exe"
    dist_dir = Path("dist")
    
    # Ensure dist exists
    dist_dir.mkdir(exist_ok=True)
    
    # Nuitka Command (Mirrors build_nuitka.py exactly)
    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        # Force console so user sees "Downloading..." status. 
        # Change to "disable" only if you implement a GUI for the updater later.
        "--windows-console-mode=force", 
        "--windows-icon-from-ico=assets/icon.ico",
        f"--output-filename={output_name}",
        "--output-dir=dist",
        
        # Embed Security & Metadata
        # 1. Initial Trust (root.json) - Critical for first connection
        "--include-data-file=repository/metadata/root.json=root.json",
        # 2. Public Key (timestamp.pub) - Critical for verification
        "--include-data-file=keys/timestamp.pub=timestamp.pub", 
        
        # 3. SSL Certificate (Manual Include to fix Nuitka/Certifi Import Error)
        "--include-data-file=C:/Users/Ryzen/AppData/Local/Programs/Python/Python312/Lib/site-packages/certifi/cacert.pem=cacert.pem",
        
        updater_script
    ]
    
    print("------------------------------------------------xxx")
    print("Executing Nuitka Build...")
    subprocess.check_call(cmd)
    
    final_path = dist_dir / output_name
    if final_path.exists():
        print(f"\n✅ SUCCESS: Bootstrapper created at:")
        print(f"   {final_path.absolute()}")
        print("\n👉 You can send this file ALONE to the client.")
        print("   It will download the rest automatically.")
    else:
        print("\n❌ Build Failed.")
        sys.exit(1)

if __name__ == "__main__":
    if not os.path.exists("repository/metadata/root.json"):
        print("❌ Error: repository/metadata/root.json not found.")
        print("   You must run 'python scripts/deploy_update.py' (or initialized repo) first to have keys.")
        sys.exit(1)
        
    build_updater_only()
