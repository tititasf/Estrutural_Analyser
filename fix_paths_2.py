import os
import re

target_dirs = [
    r"C:\Users\Thierry\.codex\skills",
    r"C:\Users\Thierry\Desktop\corporacao-senciente\squads",
    r"C:\Users\Thierry\Desktop\corporacao-senciente\.claude"
]
prefix = "C:/Users/Thierry/Desktop/corporacao-senciente/"

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception:
            return
    except Exception:
        return
        
    original_content = content
    
    content = re.sub(r'(?<!\S)\.aios-core/', prefix + '.aios-core/', content)
    content = re.sub(r'(?<!\S)\.aios/', prefix + '.aios/', content)
    content = re.sub(r'(?<!\S)\.claude/', prefix + '.claude/', content)
    
    content = re.sub(r'([\'"])\.aios-core/', r'\1' + prefix + '.aios-core/', content)
    content = re.sub(r'([\'"])\.aios/', r'\1' + prefix + '.aios/', content)
    content = re.sub(r'([\'"])\.claude/', r'\1' + prefix + '.claude/', content)

    if content != original_content:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated {filepath}")
        except Exception as e:
            pass

for d in target_dirs:
    for root, _, files in os.walk(d):
        for file in files:
            if file.endswith('.md') or file.endswith('.yaml') or file.endswith('.yml'):
                process_file(os.path.join(root, file))
