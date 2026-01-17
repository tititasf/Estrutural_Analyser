import os

def remove_bom(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        
        # Rewrite as utf-8 (no BOM)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Sanitized: {filepath}")
    except Exception as e:
        print(f"❌ Error sanitizing {filepath}: {e}")

files_to_check = [
    "main.py",
    "src/config.py"
]

for f in files_to_check:
    if os.path.exists(f):
        remove_bom(f)
