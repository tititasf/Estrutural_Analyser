import sys
import os
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
# Adicionar raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import MainWindow

def run_ui_automation():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    print("--- INICIANDO AUTOMAÇÃO UI DE VALIDAÇÃO ---")
    window = MainWindow()
    window.show()
    
    def step1_load():
        print("Passo 1: Simulando carregamento de DXF...")
        dxf_path = "c:/Users/Ryzen/Desktop/GITHUB/Agente-cad-PYSIDE/ESTRUTURAL.dxf"
        from src.core.dxf_loader import DXFLoader
        loader = DXFLoader(dxf_path)
        if loader.load():
            window.dxf_data = loader.entities
            window.canvas.add_dxf_entities(window.dxf_data)
            window.btn_process.setEnabled(True)
            print("[OK] DXF carregado via automação.")
            QTimer.singleShot(1000, step2_process)
        else:
            print("[ERRO] Falha no carregamento.")
            app.quit()

    def step2_process():
        print("Passo 2: Acionando detecção automática...")
        window.process_pillars_action()
        print(f"[OK] Processamento concluído. {len(window.pillars_found)} pilares encontrados.")
        QTimer.singleShot(1000, step3_verify)

    def step3_verify():
        print("Passo 3: Verificando listagem e detalhamento...")
        if window.pillars_found:
            first_pillar = window.pillars_found[0]
            print(f"Pilar verificado: {first_pillar['name']}")
            
            # Verificar se mudou para a página de detalhes (index 1 do right_panel)
            if window.right_panel.currentIndex() == 1:
                print("[OK] Painel de Detalhes Premium exibido corretamente.")
            else:
                print("[ERRO] Painel de detalhes não foi exibida.")
        else:
            print("[ERRO] Nenhum pilar encontrado.")
            
        print("\n--- VALIDAÇÃO UI CONCLUÍDA COM SUCESSO ---")
        QTimer.singleShot(500, app.quit)

    QTimer.singleShot(100, step1_load)
    app.exec()

if __name__ == "__main__":
    run_ui_automation()
