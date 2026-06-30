path = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/src/ui/modules/comparison_engine.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.read().splitlines()

start = 8368
end = 8382

replacement = [
    '                from scripts.arete_lj_canonico import canonical',
    '                import sys, os',
    '                if str(SCRIPTS_DIR) not in sys.path:',
    '                    sys.path.append(str(SCRIPTS_DIR))',
    '                from engrev_laj_recorte_loop import _score_diff',
    '                ref_fc = canonical(Path(left))',
    '                cand_fc = canonical(Path(right))',
    '                pct, fails = _score_diff(ref_fc, cand_fc)',
    '                suffix = "OK" if not fails else "diverge: " + ", ".join(fails)',
    '                return f"{label}: {pct:.0f}% ({detail}; marco/linhas LAJ; {suffix})."'
]

new_lines = lines[:start] + replacement + lines[end:]

with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))
print("Patched successfully!")
