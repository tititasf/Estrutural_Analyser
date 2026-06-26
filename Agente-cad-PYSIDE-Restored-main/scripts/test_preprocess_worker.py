"""
test_preprocess_worker.py — Testa PreProcessAllWorker._process() fora do Qt.

Roda a lógica completa de interpretação+salvamento e imprime relatório.
Uso: python scripts/test_preprocess_worker.py [--obra Obra_TREINO_1] [--force]
"""
import sys
import os
import time
import argparse
from pathlib import Path

# Garante que a raiz do projeto está no path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── Stub mínimo de Signal para rodar fora do Qt ───────────────────────────────
class _Signal:
    def __init__(self, *args): pass
    def emit(self, *args):
        if args:
            msg = args[-1] if isinstance(args[-1], str) else str(args)
            print(f"  [sig] {msg}", flush=True)
    def connect(self, *a): pass

# Monkey-patch QThread para não precisar de Qt
import types
fake_qthread = types.ModuleType('PySide6.QtCore')
class FakeQThread:
    def __init__(self, parent=None): pass
    def msleep(self, ms): time.sleep(ms/1000)
class _Stub:
    def __init__(self, *a, **kw): pass
    def __getattr__(self, n): return _Stub()
    def __call__(self, *a, **kw): return _Stub()

fake_qthread.QThread = FakeQThread
fake_qthread.Signal = _Signal
fake_qthread.Qt = _Stub()
fake_qthread.QObject = object
fake_qthread.QTimer = _Stub()
fake_qthread.QProcess = _Stub
sys.modules['PySide6'] = types.ModuleType('PySide6')
sys.modules['PySide6.QtCore'] = fake_qthread

# Stub completo dos módulos Qt necessários para import do diagnostic_hub
for mod in ['PySide6.QtWidgets', 'PySide6.QtGui']:
    m = types.ModuleType(mod)
    class _W:
        def __init__(self, *a, **kw): pass
        def __getattr__(self, n): return _W()
        def __call__(self, *a, **kw): return _W()
    for name in ['QWidget','QDialog','QLabel','QPushButton','QVBoxLayout','QHBoxLayout',
                 'QFrame','QScrollArea','QCheckBox','QProgressBar','QSizePolicy','QComboBox',
                 'QTabWidget','QListWidget','QListWidgetItem','QSplitter','QDialogButtonBox',
                 'QRadioButton','QButtonGroup','QMessageBox','QGraphicsLineItem',
                 'QGraphicsPathItem','QGraphicsEllipseItem']:
        setattr(m, name, _W)
    sys.modules[mod] = m

# Stubs para módulos internos UI que diagnostic_hub importa
for mod_name in [
    'src.ui.components.organisms',
    'src.ui.canvas',
    'src.ui.theme',
    'src.core.services.fase4_importer',
]:
    m = types.ModuleType(mod_name)
    class _S:
        def __init__(self, *a, **kw): pass
        def __getattr__(self, n): return _S()
    for attr in ['DiagnosticSidebar','TechSheetPanel','CADCanvas','Colors','Fonts','Radius',
                 'Fase4Importer','RenderMode']:
        setattr(m, attr, _S)
    sys.modules[mod_name] = m

# ── Agora importar o worker real ──────────────────────────────────────────────
os.chdir(str(ROOT))

from src.ui.modules.diagnostic_hub import PreProcessAllWorker   # noqa


def run_test(obra_name: str, force: bool = False):
    DADOS = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
    obra_path = DADOS / obra_name

    print(f"\n{'='*60}")
    print(f"PreProcessAllWorker — TESTE STANDALONE")
    print(f"  Obra: {obra_name}")
    print(f"  Path: {obra_path}")
    print(f"  Force: {force}")
    print(f"{'='*60}\n")

    progress_log = []
    results = []
    finished_ficha = {}
    errors = []

    # Instanciar e substituir sinais por callbacks diretos
    worker = PreProcessAllWorker.__new__(PreProcessAllWorker)
    worker.obra_name = obra_name
    worker.obra_path = obra_path
    worker.force = force
    worker._abort = False

    # Conectar sinais manualmente (stubs já printar, mas queremos capturar tb)
    worker.progress = _Signal()
    worker.torre_result = _Signal()
    worker.finished = _Signal()
    worker.error = _Signal()

    orig_progress = worker.progress.emit
    orig_torre = worker.torre_result.emit
    orig_finished = worker.finished.emit
    orig_error = worker.error.emit

    def on_progress(pct, msg):
        progress_log.append((pct, msg))
        safe = msg.encode('ascii', errors='replace').decode('ascii')
        print(f"  [{pct:3d}%] {safe}", flush=True)

    def on_torre(d):
        results.append(d)

    def on_finished(ficha):
        finished_ficha.update(ficha)
        safe = ficha.get('resumo_semantico', '').encode('ascii', errors='replace').decode('ascii')
        print(f"\n  FICHA GERADA: {safe}", flush=True)

    def on_error(msg):
        errors.append(msg)
        safe = str(msg).encode('ascii', errors='replace').decode('ascii')
        print(f"\n  ERRO: {safe}", flush=True)

    worker.progress.emit = on_progress
    worker.torre_result.emit = on_torre
    worker.finished.emit = on_finished
    worker.error.emit = on_error

    t0 = time.time()
    try:
        worker._process()
    except Exception as e:
        import traceback
        print(f"\n  EXCEPTION: {e}")
        traceback.print_exc()

    elapsed = time.time() - t0

    # Relatório final
    print(f"\n{'='*60}")
    print(f"RELATÓRIO ({elapsed:.1f}s)")
    print(f"{'='*60}")
    if errors:
        print(f"  ERROS: {len(errors)}")
        for e in errors:
            print(f"    {e[:200]}")
    if finished_ficha:
        pavs = finished_ficha.get('pavimentos', [])
        totais = finished_ficha.get('totais', {})
        print(f"  Pavimentos processados: {len(pavs)}")
        print(f"  Totais: {totais.get('pilares',0)} pilares | {totais.get('vigas',0)} vigas | {totais.get('lajes',0)} lajes")
        print()
        for pav in pavs:
            status_icon = "OK" if pav.get('status') == 'ok' else "!!"
            nome_safe = pav['nome'][-30:].encode('ascii', errors='replace').decode('ascii')
            print(f"  [{status_icon}] {nome_safe:30s} | {pav['n_pilares']:3d}P {pav['n_vigas']:3d}V {pav['n_lajes']:3d}L | status={pav['status']}")
        # Verificar DB
        print()
        try:
            import sqlite3
            conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
            n_pil = conn.execute("SELECT COUNT(*) FROM pillars").fetchone()[0]
            n_beam = conn.execute("SELECT COUNT(*) FROM beams").fetchone()[0]
            n_slab = conn.execute("SELECT COUNT(*) FROM slabs").fetchone()[0]
            n_proj = conn.execute("SELECT COUNT(*) FROM projects WHERE work_name=?", (obra_name,)).fetchone()[0]
            conn.close()
            print(f"  DB após execução:")
            print(f"    pillars={n_pil} | beams={n_beam} | slabs={n_slab}")
            print(f"    projects para {obra_name}: {n_proj}")
        except Exception as e:
            print(f"  DB check falhou: {e}")
        # Verificar JSON
        estado = obra_path / "pre_processamento_estado.json"
        print(f"\n  pre_processamento_estado.json: {'GERADO' if estado.exists() else 'AUSENTE'}")
    else:
        print("  NENHUMA FICHA GERADA")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', default='Obra_TREINO_1')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    run_test(args.obra, args.force)
