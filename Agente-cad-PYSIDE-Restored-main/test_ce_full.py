"""
Teste COMPLETO do Comparison Engine com ComparisonEngineModule real.
Simula clique no item da lista via QTest (automação real de GUI).
"""
import sys, os, traceback, time
sys.path.insert(0, '.')

import faulthandler
faulthandler.enable()

def hook(etype, evalue, tb):
    print('\n=== UNCAUGHT EXCEPTION ===', flush=True)
    traceback.print_exception(etype, evalue, tb)
sys.excepthook = hook

try:
    import psutil
    proc_self = psutil.Process(os.getpid())
    def rss(): return proc_self.memory_info().rss // 1024 // 1024
except ImportError:
    def rss(): return -1

from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest

app = QApplication(sys.argv)

print(f'[1] App created. RAM={rss()}MB', flush=True)

from src.ui.modules.comparison_engine import ComparisonEngineModule, DADOS_OBRAS_ROOT

print(f'[2] Module imported. RAM={rss()}MB', flush=True)

# Criar janela principal com ComparisonEngineModule (flow real)
win = QMainWindow()
win.setWindowTitle('CE Full Test')
win.resize(1400, 800)

ce = ComparisonEngineModule()
win.setCentralWidget(ce)
win.show()

print(f'[3] ComparisonEngineModule created. RAM={rss()}MB', flush=True)

# Conectar signals de erro
def on_crash_signal(msg=''):
    print(f'[ERROR] Signal: {msg}', flush=True)

STEP = [0]
CRASHED = [False]

def step1_check_obra():
    """Verificar que obra foi carregada no combo"""
    obra = ce.fase8_panel.cmb_obra.currentText()
    pav  = ce.fase8_panel.cmb_pav.currentText()
    print(f'[4] Obra loaded: obra={obra!r}, pav={pav!r}. RAM={rss()}MB', flush=True)

    lst = ce.nav_sidebar.lst
    count = lst.count()
    print(f'[4] NavSidebar list items: {count}', flush=True)
    for i in range(min(5, count)):
        item = lst.item(i)
        data = item.data(Qt.UserRole) if item else None
        print(f'    [{i}] text={item.text()!r} data={data}', flush=True)

    if count == 0:
        print('[4] ERROR: No items in list!', flush=True)
        app.quit()
        return

    QTimer.singleShot(500, step2_click_item)

CLICK_INDEX = [0]   # quale item clicar

def step2_click_item():
    """Simular clicks em múltiplos itens — cada click tem 8s para completar"""
    lst = ce.nav_sidebar.lst
    idx = CLICK_INDEX[0]

    # Encontrar próximo item selecionável
    selectable = [(i, lst.item(i)) for i in range(lst.count())
                  if lst.item(i) and lst.item(i).data(Qt.UserRole)]
    if idx >= len(selectable):
        print(f'[5] All {idx} items tested OK!', flush=True)
        step3_check_result()
        return

    real_i, item = selectable[idx]
    data = item.data(Qt.UserRole)
    print(f'[5.{idx}] Clicking [{real_i}] {item.text()!r} data={data}. RAM={rss()}MB', flush=True)

    rect = lst.visualItemRect(item)
    center = rect.center()
    QTest.mouseClick(lst.viewport(), Qt.LeftButton, Qt.NoModifier, center)
    print(f'[5.{idx}] Click sent.', flush=True)

    CLICK_INDEX[0] += 1
    if CLICK_INDEX[0] < 5:   # testar 5 itens
        QTimer.singleShot(8000, step2_click_item)
    else:
        QTimer.singleShot(8000, step3_check_result)

def step3_check_result():
    print(f'\n[6] Result check. RAM={rss()}MB', flush=True)
    # Check tri_level columns
    for i, col in enumerate(ce.tri_level._columns):
        ops_count = len(col.img_widget._ops) if hasattr(col.img_widget, '_ops') else -1
        loading = col.img_widget._loading if hasattr(col.img_widget, '_loading') else '?'
        status = col.img_widget._status_text if hasattr(col.img_widget, '_status_text') else '?'
        print(f'    col[{i}]: ops={ops_count}, loading={loading}, status={status!r}', flush=True)
    print(f'[6] SUCCESS — no crash!', flush=True)
    app.quit()

# Iniciar sequência após a UI estar pronta
QTimer.singleShot(1500, step1_check_obra)  # 1.5s para obra carregar via QTimer.singleShot(0)
QTimer.singleShot(70000, lambda: (print('[TIMEOUT] 70s exceeded', flush=True), app.quit()))

print('[3b] Starting event loop...', flush=True)
code = app.exec()
print(f'[7] Event loop exit code={code}. RAM={rss()}MB', flush=True)
sys.exit(code)
