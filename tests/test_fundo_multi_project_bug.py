
import sys
import os
from PySide6.QtWidgets import QApplication

# Setup paths
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
robo_fundos_path = os.path.join(base_dir, "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
if robo_fundos_path not in sys.path:
    sys.path.append(robo_fundos_path)

try:
    from fundo_pyside import FundoMainWindow
except ImportError:
    print("Cannot import FundoMainWindow")
    sys.exit(1)

def test_multi_project_conflict():
    # Evitar criar QApplication múltiplas vezes se já existir
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    window = FundoMainWindow()
    
    # Limpar dados para o teste
    window.fundos_salvos = {}
    
    # 1. Sync Obra A, Beam 1
    window.sync_context("OBRA A", "PAV 1")
    v_list_a = [{'name': 'V1', 'number': '1'}]
    count_a = window.add_viga_bulk(v_list_a)
    print(f"Obra A Sync: {count_a} itens") 
    
    # 2. Sync Obra B, Beam 1 (Same number)
    window.sync_context("OBRA B", "PAV 1")
    v_list_b = [{'name': 'V1-B', 'number': '1'}]
    count_b = window.add_viga_bulk(v_list_b)
    print(f"Obra B Sync (same number): {count_b} itens") 
    
    if count_a == 1 and count_b == 0:
        print("!!! BUG REPRODUCED: Item with same number in DIFFERENT project skipped !!!")
        sys.exit(0) # Success in reproducing bug
    else:
        print(f"Bug not reproduced as expected. A={count_a}, B={count_b}")
        sys.exit(1)

if __name__ == "__main__":
    test_multi_project_conflict()
