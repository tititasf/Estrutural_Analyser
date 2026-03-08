
import sys
import os
from PySide6.QtWidgets import QApplication

# Setup paths
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
robo_fundos_path = os.path.join(base_dir, "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
if robo_fundos_path not in sys.path:
    sys.path.append(robo_fundos_path)

from fundo_pyside import FundoMainWindow

def test_multi_project_fix():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    window = FundoMainWindow()
    window.fundos_salvos = {} # Limpar para o teste
    
    # 1. Sync Obra A, Beam 1

    window.sync_context("OBRA A", "PAV 1")
    v_list_a = [{'name': 'V1', 'number': '1'}]
    count_a = window.add_viga_bulk(v_list_a)
    print(f"Obra A Sync: {count_a} itens") 
    
    # 2. Sync Obra B, Beam 1 (Same number)
    # Agora deve funcionar pois a estrutura é por Obra/Pavimento
    window.sync_context("OBRA B", "PAV 1")
    v_list_b = [{'name': 'V1-B', 'number': '1'}]
    count_b = window.add_viga_bulk(v_list_b)
    print(f"Obra B Sync (same number): {count_b} itens") 
    
    # 3. Verificar estrutura nested
    is_nested_a = "OBRA A" in window.fundos_salvos and "PAV 1" in window.fundos_salvos["OBRA A"]
    is_nested_b = "OBRA B" in window.fundos_salvos and "PAV 1" in window.fundos_salvos["OBRA B"]
    
    print(f"Nested A: {is_nested_a}, Nested B: {is_nested_b}")
    
    if count_a == 1 and count_b == 1 and is_nested_a and is_nested_b:
        print("✅ FIX VERIFIED: Multiple projects handled independently!")
        sys.exit(0)
    else:
        print(f"FAILED: A={count_a}, B={count_b}")
        sys.exit(1)

if __name__ == "__main__":
    test_multi_project_fix()
