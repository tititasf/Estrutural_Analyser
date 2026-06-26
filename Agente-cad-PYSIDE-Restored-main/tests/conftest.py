"""
conftest.py — Configuração global do pytest para este projeto.

Execução normal (unit/integration sem GUI):
    python -m pytest tests/

Execução com testes GUI do Robô FV (requer sessão desktop interativa):
    python -m pytest tests/test_fundo_multi_project_bug.py tests/test_fundo_multi_project_fix.py tests/test_fundo_sync_fix.py tests/test_viga_bulk_sync.py tests/test_coordinator.py -v

Execução do teste de automação interativo (requer app aberto):
    python tests/test_humano_autonomo.py
"""

# Scripts interativos que não são colecionáveis pelo pytest:
#   - test_humano_autonomo.py: lança GUI real + sys.exit() no módulo
#   - ui_automation_test.py: importa main.py + PySide6 no topo do módulo

# Testes GUI que causam Windows fatal exception (access violation C-level)
# quando rodados no mesmo processo que outros testes pytest.
# fundo_pyside.py linha 11 faz import PySide6 de nível global — não pode ser
# capturado por try/except Python. Requer sessão Qt isolada (subprocesso ou
# pytest-xdist com forking).
# Rodar individualmente: python -m pytest tests/test_fundo_*.py -v

collect_ignore = [
    "test_humano_autonomo.py",           # script interativo: lança GUI + sys.exit() no módulo
    "ui_automation_test.py",             # script interativo: importa main.py + PySide6 no módulo
    "test_fundo_multi_project_bug.py",   # GUI — fundo_pyside.py crash no processo pytest
    "test_fundo_multi_project_fix.py",   # GUI — fundo_pyside.py crash no processo pytest
    "test_fundo_sync_fix.py",            # GUI — fundo_pyside.py crash no processo pytest
    "test_viga_bulk_sync.py",            # GUI — MainWindow crash no processo pytest
    "test_coordinator.py",               # GUI — DataCoordinator/PySide6 signals
    "test_ui_visual.py",                 # GUI — pywinauto/PySide6 integration visual
]

collect_ignore_glob = ["screenshots/*"]
