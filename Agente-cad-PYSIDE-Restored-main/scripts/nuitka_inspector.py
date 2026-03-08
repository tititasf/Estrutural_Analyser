import ast
import os
import sys
import subprocess
from pathlib import Path

def check_msvc():
    """Checks if MSVC cl.exe is available."""
    print("🔎 Checking for C Compiler (MSVC)...")
    try:
        # Check if cl is in path
        result = subprocess.run(["cl"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if "Microsoft (R) C/C++ Optimizing Compiler" in result.stderr or "usage: cl" in result.stderr:
            print("✅ MSVC Detected!")
            return True
    except FileNotFoundError:
        pass
    
    print("⚠️ MSVC (cl.exe) not found in PATH.")
    print("   Make sure you are running in a 'x64 Native Tools Command Prompt' or that Visual Studio is installed.")
    print("   Nuitka might fallback to MinGW which is slower.")
    return False

def get_imports(file_path):
    """Scans a python file for import statements."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except Exception as e:
        print(f"⚠️ Could not parse {file_path}: {e}")
        return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.add(n.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split('.')[0])
    return imports

def analyze_project(root_dir):
    """Recursively analyzes imports in the project."""
    print(f"📦 Analyzing imports in {root_dir}...")
    all_imports = set()
    
    for r, d, f in os.walk(root_dir):
        if "venv" in r or ".git" in r or "__pycache__" in r:
            continue
        for file in f:
            if file.endswith(".py"):
                path = os.path.join(r, file)
                all_imports.update(get_imports(path))
    
    return all_imports

def suggest_flags(imports):
    """Suggests Nuitka flags based on detected imports."""
    flags = []
    
    # Common Hidden Import Culprits
    if "pandas" in imports:
        print("💡 Detected 'pandas'. Enabling plugin.")
        flags.append("--enable-plugin=numpy") # Often needed with pandas
    
    if "PySide6" in imports:
        print("💡 Detected 'PySide6'. Enabling plugin.")
        flags.append("--enable-plugin=pyside6")
        flags.append("--include-qt-plugins=all") # Safe bet for UI apps
        
    if "cv2" in imports:
        print("💡 Detected 'cv2'. Make sure opencv-python-headless is used if no GUI needed, else standard.")
        
    if "shapely" in imports:
         print("💡 Detected 'shapely'. Usually fine, but watch out for DLLs.")
         
    return flags

def main():
    print("🚀 Nuitka Pre-Flight Inspector")
    print("===============================")
    
    root = Path(__file__).parent.parent
    has_msvc = check_msvc()
    
    imports = analyze_project(root)
    print(f"📊 Found {len(imports)} unique root imports.")
    
    print("\n--- Suggested Nuitka Flags ---")
    suggested = suggest_flags(imports)
    
    base_flags = [
        "--standalone",
        "--lto=yes" if has_msvc else "--lto=no",
        "--jobs=4", # Safe number
        "--output-dir=dist_nuitka",
        "--main=main.py"
    ]
    
    full_cmd = ["python", "-m", "nuitka"] + base_flags + suggested
    
    print("\n📝 Generated Build Command:")
    print(" ".join(full_cmd))
    
    # Generate a simple batch file for the user
    bat_path = root / "build_nuitka.bat"
    with open(bat_path, "w") as f:
        f.write("REM Auto-generated Nuitka Build Script\n")
        f.write(" ".join(full_cmd))
    
    print(f"\n✅ Build script written to: {bat_path}")
    print("👉 Run this script to start compilation!")

if __name__ == "__main__":
    main()
