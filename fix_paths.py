import os
import re

base_dir = r"C:\Users\Thierry\Desktop\corporacao-senciente"
target_dirs = [os.path.join(base_dir, ".aios-core"), os.path.join(base_dir, ".claude"), os.path.join(base_dir, "skills")]
prefix = "C:/Users/Thierry/Desktop/corporacao-senciente/"

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        original_content = content
        
        # We want to replace '.aios-core/' with 'C:/Users/Thierry/Desktop/corporacao-senciente/.aios-core/'
        # ONLY if it is not already preceded by the prefix (or parts of it).
        # We can use a regex with negative lookbehind.
        # But python's negative lookbehind requires fixed width.
        
        # A simpler way: just replace all occurrences of '.aios-core/', '.aios/', '.claude/'
        # then fix any double prefixes 'C:/Users/Thierry/Desktop/corporacao-senciente/C:/Users/Thierry/Desktop/corporacao-senciente/'
        
        content = re.sub(r'(?<!\S)\.aios-core/', prefix + '.aios-core/', content)
        content = re.sub(r'(?<!\S)\.aios/', prefix + '.aios/', content)
        content = re.sub(r'(?<!\S)\.claude/', prefix + '.claude/', content)
        
        # also handle quotes
        content = re.sub(r'([\'"])\.aios-core/', r'\1' + prefix + '.aios-core/', content)
        content = re.sub(r'([\'"])\.aios/', r'\1' + prefix + '.aios/', content)
        content = re.sub(r'([\'"])\.claude/', r'\1' + prefix + '.claude/', content)

        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated {filepath}")
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

for d in target_dirs:
    for root, _, files in os.walk(d):
        for file in files:
            if file.endswith('.md') or file.endswith('.yaml') or file.endswith('.yml'):
                process_file(os.path.join(root, file))
