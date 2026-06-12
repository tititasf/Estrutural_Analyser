"""
Teste mínimo: carrega N1 DXF via subprocess PNG e verifica se QPixmap funciona.
"""
import sys, faulthandler, traceback
sys.path.insert(0, '.')
faulthandler.enable()

def hook(etype, val, tb):
    print('=== EXCEPTION ===', flush=True)
    traceback.print_exception(etype, val, tb)
sys.excepthook = hook

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtCore import QTimer

app = QApplication(sys.argv)

from src.ui.modules.comparison_engine import DXFVectorView, DADOS_OBRAS_ROOT

win = QWidget()
lay = QVBoxLayout(win)
v = DXFVectorView()
lay.addWidget(v)
win.resize(800, 600)
win.show()

print('[1] Widget created', flush=True)

N1_PATH = str(DADOS_OBRAS_ROOT / 'Obra_TREINO_1/Fase-1_Ingestao/Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF/TMC-EST-EX-0000-LOC-R03_R12_ASCII_ODA.dxf')

def step1():
    print('[2] Loading N1 DXF...', flush=True)
    v.load_dxf(N1_PATH)

def step2():
    print(f'[3] After N1: pixmap={v._pixmap}, ops={len(v._ops)}, status={v._status_text!r}', flush=True)

def step3():
    print('[4] Loading N1 AGAIN (cancel+reload)...', flush=True)
    v.load_dxf(N1_PATH)

def step4():
    print(f'[5] After reload: pixmap={v._pixmap is not None}, status={v._status_text!r}', flush=True)
    app.quit()

QTimer.singleShot(500,  step1)
QTimer.singleShot(8000, step2)
QTimer.singleShot(8500, step3)
QTimer.singleShot(16000, step4)
QTimer.singleShot(25000, lambda: (print('[TIMEOUT]', flush=True), app.quit()))

print('[0] Event loop starting...', flush=True)
sys.exit(app.exec())
