import sys
import os
import ctypes
from PySide6.QtWidgets import QApplication, QMessageBox
import traceback

# Importações do projeto
from licensing_service_v2 import LicensingService
from login_dialog import LoginDialog
from robo_laterais_viga_pyside import VigaMainWindow

def main():
    # Fix High DPI scaling
    if sys.platform == 'win32':
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        
    app = QApplication(sys.argv)
    app.setApplicationName("Robo Laterais Viga V2")
    # Evita que a aplicação feche quando o diálogo de login é aceito e fecha
    app.setQuitOnLastWindowClosed(False)
    
    # 1. Initialize Licensing
    licensing = LicensingService()
    
    # 2. Inicia o Login
    login_dlg = LoginDialog(licensing)
    
    print("Aguardando login...")
    if login_dlg.exec():
        user_info = licensing.user_data
        print(f"Login bem-sucedido para: {user_info.get('nome')}")
        
        # 3. Open Main Window
        try:
             window = VigaMainWindow()
             # Injetar serviço de licença
             window.licensing_service = licensing
             window.update_license_display()
             window.setWindowTitle(f"Robo Laterais Viga - {user_info.get('nome')} ({user_info.get('creditos'):.2f} m²)")
             
             # Agora que temos a janela principal, podemos permitir que o app feche ao fechar esta janela
             app.setQuitOnLastWindowClosed(True)
             
             window.show()
             print("Janela principal aberta.")
             sys.exit(app.exec())
        except Exception as e:
             print(f"Erro fatal ao abrir janela principal: {e}")
             traceback.print_exc()
             QMessageBox.critical(None, "Erro Crítico", f"Erro ao iniciar janela principal:\n{e}")
             sys.exit(1)
    else:
        print("Login cancelado pelo usuário.")
        sys.exit(0)

if __name__ == "__main__":
    main()
