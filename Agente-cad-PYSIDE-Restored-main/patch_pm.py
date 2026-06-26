import sys

path = 'src/ui/widgets/project_manager.py'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

target = 'elif "laje" in t: self.db.save_slab(item_data, self.current_project_id)'
repl = target + '\n            elif "viga" in t or "fundo" in t: self.db.save_beam(item_data, self.current_project_id)\n        \n        try:\n            self._refresh_all_phase3_lists()\n        except Exception:\n            pass'

if target in c:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(c.replace(target, repl))
    print("Patched successfully")
else:
    print("Target not found")
