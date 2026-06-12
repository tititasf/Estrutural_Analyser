"""
Test: auto-selects LV item in Comparison Engine and reports crash / RAM.
Run: python test_ce_crash.py > C:/Temp/ce_test.log 2>&1
"""
import sys, gc, traceback, os
sys.path.insert(0, '.')

import faulthandler
log_f = open('C:/Temp/ce_crash_log.txt', 'w')
faulthandler.enable()           # stderr
faulthandler.enable(file=log_f) # e arquivo

def hook(etype, evalue, tb):
    msg = f'\n=== UNCAUGHT EXCEPTION ===\n'
    sys.stderr.write(msg); log_f.write(msg)
    traceback.print_exception(etype, evalue, tb)
    traceback.print_exception(etype, evalue, tb, file=log_f)
    log_f.flush()
sys.excepthook = hook

try:
    import psutil
    proc = psutil.Process(os.getpid())
    def rss(): return proc.memory_info().rss // 1024 // 1024
except ImportError:
    def rss(): return -1

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

app = QApplication(sys.argv)

print(f'[1] App created. RAM={rss()}MB', flush=True)

from src.ui.modules.comparison_engine import TriLevelArea, DADOS_OBRAS_ROOT

print(f'[2] Module imported. RAM={rss()}MB', flush=True)

area = TriLevelArea()
area.resize(1200, 700)
area.show()

print(f'[3] TriLevelArea created. RAM={rss()}MB', flush=True)

obra = 'Obra_TREINO_16'
obra_dir = DADOS_OBRAS_ROOT / obra
area._current_obra = obra
area._current_pav  = '1PV'
area._load_data(obra_dir)

print(f'[4] load_data done. RAM={rss()}MB', flush=True)
print(f'    _est_labels count: {len(area._est_labels)}', flush=True)
print(f'    _est_ents_raw count: {len(area._est_ents_raw)}', flush=True)
print(f'    _kb_ents count: {len(area._kb_ents)}', flush=True)

# Check N1 bbox
n1_bbox = area._get_n1_bbox_for('V4_A')
print(f'    N1 bbox for V4_A: {n1_bbox}', flush=True)
n2_bbox = area._get_n2_bbox_for('V4_A')
print(f'    N2 bbox for V4_A: {n2_bbox}', flush=True)

# Check N1 DXF
n1_dxf = area._find_n1_dxf(obra_dir)
print(f'    N1 DXF: {n1_dxf.name if n1_dxf else None} ({n1_dxf.stat().st_size//1024//1024 if n1_dxf else 0}MB)', flush=True)

n2_dxf = area._find_n2_dxf(obra, '1PV', 'LV')
print(f'    N2 DXF: {n2_dxf.name if n2_dxf else None} ({n2_dxf.stat().st_size//1024//1024 if n2_dxf else 0}MB)', flush=True)

n3_dxf = area._find_n3_dxf(obra_dir, 'LV', 'V4_A')
print(f'    N3 DXF: {n3_dxf.name if n3_dxf else None} ({n3_dxf.stat().st_size//1024 if n3_dxf else 0}KB)', flush=True)


def step2_select():
    print(f'\n[5] Calling load_item(LV, V4_A). RAM={rss()}MB', flush=True)
    try:
        area.load_item('LV', 'V4_A')
        print(f'[6] load_item returned. RAM={rss()}MB', flush=True)
    except Exception as e:
        print(f'[6] load_item EXCEPTION: {type(e).__name__}: {e}', flush=True)
        traceback.print_exc()

def step3_done():
    print(f'\n[7] Done. RAM={rss()}MB', flush=True)
    log_f.flush()
    app.quit()

QTimer.singleShot(500,  step2_select)
QTimer.singleShot(5000, step3_done)

print(f'[4b] Starting event loop...', flush=True)
code = app.exec()
print(f'[8] Event loop exited with code={code}', flush=True)
log_f.close()
sys.exit(code)
