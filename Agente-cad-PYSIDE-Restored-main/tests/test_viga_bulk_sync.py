import sys
import os
from PySide6.QtWidgets import QApplication
from unittest.mock import MagicMock

# Adicionar caminhos
base_dir = os.path.abspath(os.path.dirname(__file__) + '/..')
sys.path.append(base_dir)
sys.path.append(os.path.join(base_dir, "_ROBOS_ABAS", "Robo_Laterais_de_Vigas"))
sys.path.append(os.path.join(base_dir, "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao"))

from main import MainWindow

def test_viga_bulk_sync():
    app = QApplication(sys.argv)
    window = MainWindow()
    
    # Mock data
    window.beams_found = [
        {'name': 'V1', 'number': '1'},
        {'name': 'V2', 'number': '2'},
        {'name': 'V3', 'number': '3'}
    ]
    
    # Mock Robots if they are not loaded (to avoid full initialization overhead)
    if not hasattr(window, 'robo_viga') or window.robo_viga is None:
        window.robo_viga = MagicMock()
        window.robo_viga.add_viga_bulk.return_value = 3
    
    if not hasattr(window, 'robo_fundo') or window.robo_fundo is None:
        window.robo_fundo = MagicMock()
        window.robo_fundo.add_viga_bulk.return_value = 3

    # Force combo selection for test
    window.cmb_works.addItem("OBRA-SYNC")
    window.cmb_works.setCurrentText("OBRA-SYNC")
    window.cmb_pavements.addItem("PAV-SYNC")
    window.cmb_pavements.setCurrentText("PAV-SYNC")

    print("\n--- TESTE DE SINCRONIZAÇÃO EM MASSA (MOCK) ---")
    
    # 1. Test Laterais Sync Action
    window.sync_beams_to_laterais_action()
    window.robo_viga.add_global_pavimento.assert_called_with("OBRA-SYNC", "PAV-SYNC")
    window.robo_viga.add_viga_bulk.assert_called()
    print("[OK] Ação de sincronização para Laterais de Vigas validada.")

    # 2. Test Fundo Sync Action
    window.sync_beams_to_fundo_action()
    window.robo_fundo.sync_context.assert_called_with("OBRA-SYNC", "PAV-SYNC")
    window.robo_fundo.add_viga_bulk.assert_called()
    print("[OK] Ação de sincronização para Fundo de Vigas validada.")

    print("\n--- TESTE CONCLUÍDO COM SUCESSO ---")
    QTimer.singleShot(100, app.quit)

if __name__ == "__main__":
    from PySide6.QtCore import QTimer
    test_viga_bulk_sync()
