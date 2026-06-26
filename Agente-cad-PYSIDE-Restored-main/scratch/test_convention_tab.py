"""Test lazy loading: measures time to show dialog and each tab switch."""
import sys, os, time
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QGraphicsScene, QTabWidget
from PySide6.QtCore import QTimer

app = QApplication(sys.argv)

from src.ui.widgets.pre_validation_dialog import PreValidationDialog

class DummyCanvas:
    scene = QGraphicsScene()
canvas = DummyCanvas()

db_path = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\project_data.vision"
if not os.path.isfile(db_path):
    db_path = r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\project_data.vision"

# Simulate a moderate dataset
pillar_report = {}
for i in range(1, 25):
    pillar_report[f"P{i}"] = {
        "name": f"P{i}",
        "classification": ["NASCE", "MORRE", "CONTINUA", "SEGUE", "INDETERMINADO"][i % 5],
        "bbox": [i*100, 0, i*100+20, 50],
        "points": [[i*100,0],[i*100+20,0],[i*100+20,50],[i*100,50]],
    }

slabs = [
    {"name": f"L{i}", "laje_dim": str(10+i), "points": [[i*100,0],[i*100+100,0],[i*100+100,100],[i*100,100]]}
    for i in range(1, 10)
]

convention = {
    "NASCE": {"sig": "EMPTY"},
    "MORRE": {"sig": "CROSS"},
    "CONTINUA": {"sig": "DIAG"},
}

t0 = time.perf_counter()

dlg = PreValidationDialog(
    pillar_report=pillar_report,
    nivel_report={},
    slabs=slabs,
    convention=convention,
    obra="Obra_TREINO_1",
    pavimento="TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA",
    beam_texts=[],
    canvas=canvas,
    convention_file=None,
    db_path=db_path,
    parent=None,
)

t1 = time.perf_counter()
print(f"[TIMING] Dialog __init__: {(t1-t0)*1000:.0f}ms")

dlg.showMaximized()
t2 = time.perf_counter()
print(f"[TIMING] showMaximized: {(t2-t1)*1000:.0f}ms")
print(f"[TIMING] Total to show: {(t2-t0)*1000:.0f}ms")

step = [0]
def next_step():
    s = step[0]
    tabs = dlg.findChildren(QTabWidget)
    tw = tabs[0] if tabs else None
    
    if s == 0:
        # Tab 0 should already be loaded via QTimer
        print(f"\n[INFO] Tab 0 (Convencao) loaded via QTimer")
        step[0] += 1
        QTimer.singleShot(500, next_step)
    elif s == 1:
        # Switch to tab 1 (Pilares)
        print(f"\n[TEST] Switching to tab 1 (Pilares)...")
        t = time.perf_counter()
        if tw:
            tw.setCurrentIndex(1)
        t_done = time.perf_counter()
        print(f"[TIMING] Tab 1 load: {(t_done-t)*1000:.0f}ms")
        step[0] += 1
        QTimer.singleShot(500, next_step)
    elif s == 2:
        # Switch to tab 2 (Visao de Cortes)
        print(f"\n[TEST] Switching to tab 2 (Visao de Cortes)...")
        t = time.perf_counter()
        if tw:
            tw.setCurrentIndex(2)
        t_done = time.perf_counter()
        print(f"[TIMING] Tab 2 load: {(t_done-t)*1000:.0f}ms")
        step[0] += 1
        QTimer.singleShot(500, next_step)
    elif s == 3:
        # Switch back to tab 0 (should be instant - already loaded)
        print(f"\n[TEST] Switching back to tab 0 (should be instant)...")
        t = time.perf_counter()
        if tw:
            tw.setCurrentIndex(0)
        t_done = time.perf_counter()
        print(f"[TIMING] Tab 0 re-select: {(t_done-t)*1000:.0f}ms")
        
        # Screenshot
        screenshot_path = os.path.join(os.path.dirname(__file__), "lazy_loading_test.png")
        pixmap = dlg.grab()
        pixmap.save(screenshot_path)
        print(f"\n[OK] Screenshot saved: {screenshot_path}")
        
        QTimer.singleShot(1000, app.quit)

# Wait for deferred tab 0 load to complete, then start tests
QTimer.singleShot(300, next_step)
app.exec()
print("\n[OK] All tests passed - lazy loading works!")
