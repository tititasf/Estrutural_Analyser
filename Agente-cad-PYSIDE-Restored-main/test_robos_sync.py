import sys
import os
from PySide6.QtWidgets import QApplication

base_dir = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main'
sys.path.insert(0, base_dir)

try:
    from main import MainWindow
    app = QApplication(sys.argv)
    window = MainWindow()
    
    print("\n[TEST] Selecionando '📁 Obra_TREINO_1' no cmb_works global...")
    idx = window.cmb_works.findText("📁 Obra_TREINO_1")
    if idx >= 0:
        window.cmb_works.setCurrentIndex(idx)
        print("Sucesso ao selecionar!")
    else:
        print("Obra_TREINO_1 não encontrada! Obras disponíveis:")
        for i in range(window.cmb_works.count()):
            print(f" - {window.cmb_works.itemText(i)}")
        
    print("\n--- Verificando RoboViga ---")
    if getattr(window, 'robo_viga', None):
        print(f"cmb_obra currentText: {window.robo_viga.cmb_obra.currentText()}")
        if hasattr(window.robo_viga, 'cmb_pav'):
            print(f"cmb_pav count: {window.robo_viga.cmb_pav.count()}")
            for i in range(window.robo_viga.cmb_pav.count()):
                print(f"  - {window.robo_viga.cmb_pav.itemText(i)}")
        else:
            print("RoboViga NÃO tem cmb_pav")
    else:
        print("RoboViga NÃO instanciado.")

    print("\n--- Verificando RoboFundo ---")
    if getattr(window, 'robo_fundo', None):
        if hasattr(window.robo_fundo, 'combo_obra'):
            print(f"combo_obra currentText: {window.robo_fundo.combo_obra.currentText()}")
        if hasattr(window.robo_fundo, 'combo_pavimento'):
            print(f"combo_pavimento count: {window.robo_fundo.combo_pavimento.count()}")
            for i in range(window.robo_fundo.combo_pavimento.count()):
                print(f"  - {window.robo_fundo.combo_pavimento.itemText(i)}")
        else:
            print("RoboFundo NÃO tem combo_pavimento")
    else:
        print("RoboFundo NÃO instanciado.")

    print("\n--- Verificando RoboPilares ---")
    if getattr(window, 'robo_pilares', None):
        print("RoboPilares instanciado.")
        from PySide6.QtWidgets import QTableWidget
        tables = window.robo_pilares.findChildren(QTableWidget)
        for t in tables:
            print(f"Tabela Pilares: {t.objectName()} | rows={t.rowCount()}")
            if t.rowCount() > 0:
                print(f"  Row 0: {t.item(0, 0)}")
                
        # Let's see the VM
        if hasattr(window.robo_pilares, 'vm'):
            print(f"VM current_obra: {getattr(window.robo_pilares.vm, 'current_obra', None)}")
            if window.robo_pilares.vm.current_obra:
                print(f"  Pavimentos na VM: {len(window.robo_pilares.vm.current_obra.pavimentos)}")
                for p in window.robo_pilares.vm.current_obra.pavimentos:
                    print(f"    - {getattr(p, 'nome', p)}")
            else:
                print("  Nenhuma current_obra na VM!")
    else:
        print("RoboPilares NÃO instanciado.")
        
except Exception as e:
    import traceback
    traceback.print_exc()

sys.exit(0)
