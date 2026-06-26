import os

def clean_file(path, start_marker):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        start_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith(start_marker):
                start_idx = i
                break
        
        if start_idx == -1:
            print(f"Marker '{start_marker}' not found in {path}. Skipping.")
            return

        # Keep everything from start_marker onwards
        new_content = "".join(lines[start_idx:])
        
        # Backup
        with open(path + ".bak_clean", 'w', encoding='utf-8') as f:
            f.writelines(lines)
            
        # Overwrite
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        print(f"Cleaned {path}. Removed Top {start_idx} lines.")
        
    except Exception as e:
        print(f"Error cleaning {path}: {e}")

# Clean Project Manager
clean_file(
    r"src\ui\widgets\project_manager.py", 
    "from PySide6.QtWidgets import"
)

# Clean Database
clean_file(
    r"src\core\database.py", 
    "import sqlite3"
)
