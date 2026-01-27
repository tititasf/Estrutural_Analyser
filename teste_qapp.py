"""
Teste da criação da QApplication
"""

import sys
import os

# Configurar caminhos
legacy_path = os.path.join(os.path.dirname(__file__), "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
sys.path.insert(0, legacy_path)

print("Testando QApplication...")

try:
    from PySide6.QtWidgets import QApplication
    print("Import QApplication OK")

    # Verificar se já existe uma QApplication
    app = QApplication.instance()
    if app is None:
        print("Criando nova QApplication...")
        app = QApplication(sys.argv)
        print("QApplication criada")
    else:
        print("QApplication já existe")

    print("Testando import fundo_pyside...")
    from fundo_pyside import FundoMainWindow
    print("Import OK")

    print("Testando criação FundoMainWindow...")
    # Tentar criar sem mostrar a janela
    window = FundoMainWindow()
    print("FundoMainWindow criada com sucesso!")

    # Verificar atributos básicos
    if hasattr(window, 'fields'):
        print("Atributo fields presente")
        if 'numero' in window.fields:
            print("Campo numero presente")
        else:
            print("Campo numero ausente")
    else:
        print("Atributo fields ausente")

    print("TESTE CONCLUÍDO!")

except Exception as e:
    print(f"ERRO: {e}")
    import traceback
    traceback.print_exc()