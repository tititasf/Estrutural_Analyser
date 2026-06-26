"""Integrity check for pre_validation_dialog.py"""
import sys, ast, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

filepath = os.path.join('src', 'ui', 'widgets', 'pre_validation_dialog.py')

# 1. Syntax check
try:
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source)
    print('[OK] Syntax check passed')
except SyntaxError as e:
    print(f'[ERRO] Syntax error: {e}')
    sys.exit(1)

# 2. Check class definitions
classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
print(f'Classes: {classes}')

# 3. Check all methods in PreValidationDialog
pvd_methods = []
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == 'PreValidationDialog':
        pvd_methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        print(f'\nPreValidationDialog methods ({len(pvd_methods)}):')
        for m in pvd_methods:
            print(f'  {m}')

# 4. Check important methods exist
critical_methods = [
    '_build_ui', '_build_header', '_build_footer',
    '_build_convention_tab', '_build_pillars_tab', '_build_cut_views_tab',
    '_build_convention_panel', '_build_pillar_table', '_build_detail_reference_viewer',
    '_make_conv_viewer_for_term', '_make_mini_viewer',
    '_populate_pillar_table', '_query_detail_recorte', '_load_dxf_to_scene',
    'get_result', '_confirm_and_save',
]
print(f'\nCritical method check:')
missing = []
for cm in critical_methods:
    found = cm in pvd_methods
    status = 'OK' if found else 'MISSING!'
    print(f'  {cm}: {status}')
    if not found:
        missing.append(cm)

if missing:
    print(f'\n[ALERTA] Missing methods: {missing}')
else:
    print('\n[OK] All critical methods present')

# 5. Check ConvencaoPilaresDialog
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == 'ConvencaoPilaresDialog':
        sub_methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        print(f'\nConvencaoPilaresDialog methods ({len(sub_methods)}):')
        for m in sub_methods:
            print(f'  {m}')

# 6. Count lines
lines = source.count('\n') + 1
print(f'\nTotal lines: {lines}')
print(f'Total bytes: {len(source)}')

# 7. Check helper classes
helper_classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name != 'PreValidationDialog' and n.name != 'ConvencaoPilaresDialog']
print(f'\nHelper classes: {helper_classes}')

# 8. Quick import test
print('\n--- Import test ---')
try:
    from src.ui.widgets.pre_validation_dialog import PreValidationDialog, ConvencaoPilaresDialog
    print('[OK] Both classes importable')
except Exception as e:
    print(f'[ERRO] Import failed: {e}')

print('\n=== INTEGRITY CHECK COMPLETE ===')
