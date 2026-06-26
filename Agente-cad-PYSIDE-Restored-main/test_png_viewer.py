"""
Teste: carrega N1 DXF via PNG subprocess e valida pixmap display.
Aguarda o sinal ready() para verificar resultado correto.
"""
import sys, faulthandler, os
sys.path.insert(0, '.')
faulthandler.enable()

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import QTimer

app = QApplication(sys.argv)

from src.ui.modules.comparison_engine import DXFVectorView, DADOS_OBRAS_ROOT

win = QWidget()
win.setWindowTitle('PNG Viewer Test')
lay = QVBoxLayout(win)
v = DXFVectorView()
lbl = QLabel('Aguardando...')
lay.addWidget(v)
lay.addWidget(lbl)
win.resize(900, 700)
win.show()

N1_PATH = str(DADOS_OBRAS_ROOT / 'Obra_TREINO_1/Fase-1_Ingestao/Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF/TMC-EST-EX-0000-LOC-R03_R12_ASCII_ODA.dxf')

results = []

def on_ready():
    has_pm = v._pixmap is not None and not v._pixmap.isNull()
    status = v._status_text
    ops    = len(v._ops)
    msg = f'ready: pixmap={has_pm}, ops={ops}, status={status!r}'
    print(f'[READY] {msg}', flush=True)
    lbl.setText(msg)
    results.append(has_pm)

    # Carregar item 2 para testar cancel+reload
    if len(results) == 1:
        print('[TEST] Reloading same DXF (cancel+reload test)...', flush=True)
        v.ready.disconnect(on_ready)
        v.ready.connect(on_ready2)
        v.load_dxf(N1_PATH)

def on_ready2():
    has_pm = v._pixmap is not None and not v._pixmap.isNull()
    status = v._status_text
    msg = f'reload ready: pixmap={has_pm}, status={status!r}'
    print(f'[READY2] {msg}', flush=True)
    lbl.setText(msg)

    if has_pm:
        print('[PASS] PNG display working correctly!', flush=True)
    else:
        print('[FAIL] No pixmap!', flush=True)

    # Esperar 3s para visualizar, depois sair
    QTimer.singleShot(3000, quit_safe)

def quit_safe():
    print('[EXIT] Quitting...', flush=True)
    # Cancelar worker pendente antes de sair para evitar exit 127
    if v._worker is not None:
        v._worker.cancel()
    app.quit()

v.ready.connect(on_ready)

print('[START] Loading N1 DXF...', flush=True)
v.load_dxf(N1_PATH)

# Timeout de segurança
QTimer.singleShot(120000, lambda: (print('[TIMEOUT]', flush=True), quit_safe()))

sys.exit(app.exec())
