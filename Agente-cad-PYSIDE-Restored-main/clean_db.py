import sys
import os

path = r"c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\src\core\database.py"
if not os.path.exists(path):
    print(f"Error: {path} not found")
    sys.exit(1)

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start = -1
end = -1
for i, l in enumerate(lines):
    if i > 750 and "# Gera novo ID" in l:
        start = i
        break

for i, l in enumerate(lines):
    if start != -1 and i > start and "return new_id" in l:
        # Check if next function starts nearby
        found_next = False
        for next_i in range(i+1, min(i+5, len(lines))):
            if "def save_pillar" in lines[next_i]:
                found_next = True
                break
        if found_next:
            end = i
            break

if start != -1 and end != -1:
    # Remove from previous line (empty line) until end line
    final_lines = lines[:start-1] + lines[end+1:]
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(final_lines)
    print(f"Success: Removed lines {start} to {end}")
else:
    print(f"Failed: start={start}, end={end}")
