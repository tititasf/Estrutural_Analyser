"""
Teste apenas de importação
"""

import sys
import os

print("Configurando caminhos...")
legacy_path = os.path.join(os.path.dirname(__file__), "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
print(f"Caminho legacy: {legacy_path}")
sys.path.insert(0, legacy_path)

print("Testando importações...")

try:
    print("Importando PySide6...")
    from PySide6.QtWidgets import QApplication, QMainWindow
    print("PySide6 OK")

    print("Importando fundo_pyside...")
    import fundo_pyside
    print("fundo_pyside importado")

    print("Verificando classe FundoMainWindow...")
    if hasattr(fundo_pyside, 'FundoMainWindow'):
        print("FundoMainWindow encontrado")
    else:
        print("FundoMainWindow não encontrado")

    print("Importações bem-sucedidas!")

except Exception as e:
    print(f"Erro na importação: {e}")
    import traceback
    traceback.print_exc()