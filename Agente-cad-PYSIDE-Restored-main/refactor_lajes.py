import os
import shutil

# Paths
BASE_DIR = r"c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\_ROBOS_ABAS\Robo_Lajes"
SRC_DIR = os.path.join(BASE_DIR, "src")
NEW_PKG_NAME = "laje_src"
NEW_DIR = os.path.join(BASE_DIR, NEW_PKG_NAME)

def refactor_imports():
    if not os.path.exists(SRC_DIR):
        print(f"Directory not found: {SRC_DIR}")
        return

    print(f"Processing files in {SRC_DIR}...")
    
    # 1. Update file contents
    for root, dirs, files in os.walk(SRC_DIR):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Replace imports
                    # Pattern: "from src" -> "from laje_src"
                    # Pattern: "import src" -> "import laje_src"
                    # Be careful with "src_foo" or similar. "src." is the safest target.
                    
                    new_content = content.replace("from src.", f"from {NEW_PKG_NAME}.")
                    new_content = new_content.replace("import src.", f"import {NEW_PKG_NAME}.")
                    new_content = new_content.replace("from src ", f"from {NEW_PKG_NAME} ")
                    # Edge case: "import src" (whole module) - rare but possible
                    if "import src\n" in content:
                         new_content = new_content.replace("import src\n", f"import {NEW_PKG_NAME}\n")

                    if new_content != content:
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        print(f"Updated: {file}")
                        
                except Exception as e:
                    print(f"Error processing {file}: {e}")

    # 2. Rename Directory
    print(f"Renaming {SRC_DIR} to {NEW_DIR}...")
    try:
        os.rename(SRC_DIR, NEW_DIR)
        print("Rename successful!")
    except OSError as e:
        print(f"Rename failed: {e}")

if __name__ == "__main__":
    refactor_imports()
