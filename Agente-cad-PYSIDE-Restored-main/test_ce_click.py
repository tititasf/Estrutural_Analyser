"""
Teste: ComparisonEngineModule completo com cliques reais.
Aguarda ready() signal de cada coluna para não crashar no exit.
"""
import sys, faulthandler, traceback
sys.path.insert(0, '.')
faulthandler.enable()

def hook(e, v, tb): print('EXCEPTION:', e.__name__, v, flush=True); traceback.print_tb(tb)
sys.excepthook = hook

from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest

app = QApplication(sys.argv)

from src.ui.modules.comparison_engine import ComparisonEngineModule

win = QMainWindow()
ce = ComparisonEngineModule()
win.setCentralWidget(ce)
win.resize(1400, 800)
win.show()

print('[1] App created', flush=True)

RESULTS = []
CLICK_IDX = [0]
MAX_CLICKS = 3   # Testar 3 itens

def cancel_all_workers():
    """Cancela todos workers ativos antes de sair."""
    for col in ce.tri_level._columns:
        w = col.img_widget._worker
        if w is not None:
            w.cancel()

def quit_safe():
    cancel_all_workers()
    QTimer.singleShot(500, app.quit)

def do_next_click():
    lst = ce.nav_sidebar.lst
    selectable = [(i, lst.item(i)) for i in range(lst.count())
                  if lst.item(i) and lst.item(i).data(Qt.UserRole)]
    idx = CLICK_IDX[0]
    if idx >= min(MAX_CLICKS, len(selectable)):
        print(f'[DONE] Tested {idx} items, all OK!', flush=True)
        for r in RESULTS:
            print(f'  {r}', flush=True)
        quit_safe()
        return

    real_i, item = selectable[idx]
    data = item.data(Qt.UserRole)
    print(f'[CLICK {idx}] {item.text()!r} data={data}', flush=True)

    rect = lst.visualItemRect(item)
    QTest.mouseClick(lst.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center())
    CLICK_IDX[0] += 1

    # Aguardar coluna N1 ficar pronta antes do próximo clique
    col0 = ce.tri_level._columns[0].img_widget
    col0.ready.connect(on_col0_ready)

def on_col0_ready():
    col0 = ce.tri_level._columns[0].img_widget
    try: col0.ready.disconnect(on_col0_ready)
    except Exception: pass

    has_pm = col0._pixmap is not None and not (col0._pixmap.isNull() if col0._pixmap else True)
    ops = len(col0._ops)
    status = col0._status_text
    RESULTS.append(f'click {CLICK_IDX[0]-1} N1: pixmap={has_pm}, ops={ops}, status={status!r}')
    print(f'  N1 ready: pixmap={has_pm}, ops={ops}, status={status!r}', flush=True)

    # Próximo clique após pequena pausa
    QTimer.singleShot(500, do_next_click)

def start():
    obra = ce.fase8_panel.cmb_obra.currentText()
    count = ce.nav_sidebar.lst.count()
    print(f'[2] obra={obra!r}, items={count}', flush=True)
    if count == 0:
        print('[FAIL] No items!', flush=True)
        quit_safe()
        return
    do_next_click()

QTimer.singleShot(1500, start)
QTimer.singleShot(300000, lambda: (print('[TIMEOUT]', flush=True), quit_safe()))

print('[0] Event loop starting...', flush=True)
sys.exit(app.exec())
