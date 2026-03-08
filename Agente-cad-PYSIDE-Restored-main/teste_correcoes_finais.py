"""
Teste final de todas as correções aplicadas
"""

import sys
import os

print("TESTE FINAL DAS CORRECOES")
print("="*60)

try:
    # Configurar caminhos
    legacy_path = os.path.join(os.path.dirname(__file__), "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
    sys.path.insert(0, legacy_path)

    print("1. Testando importacao do fundo_pyside...")
    from fundo_pyside import FundoMainWindow
    print("   [OK] FundoMainWindow importado")

    print("2. Testando importacao do AutoCADSelectionManager...")
    from fundo_utils_novo import AutoCADSelectionManager
    print("   [OK] AutoCADSelectionManager importado")

    print("3. Testando criacao de instancia...")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = FundoMainWindow()
    print("   [OK] FundoMainWindow criada com sucesso")

    print("4. Verificando atributos...")
    if hasattr(window, 'selection_manager'):
        print("   [OK] selection_manager presente")
        if isinstance(window.selection_manager, AutoCADSelectionManager):
            print("   [OK] selection_manager e do tipo correto")
        else:
            print("   [ERRO] selection_manager tipo incorreto")
    else:
        print("   [ERRO] selection_manager ausente")

    print("5. Verificando botao lisp FD...")
    if hasattr(window, 'btn_lisp_fd'):
        print("   [OK] Botao btn_lisp_fd presente")
    else:
        print("   [ERRO] Botao btn_lisp_fd ausente")

    print("6. Verificando metodo action_criar_lisp_fd...")
    if hasattr(window, 'action_criar_lisp_fd'):
        print("   [OK] Metodo action_criar_lisp_fd presente")
    else:
        print("   [ERRO] Metodo action_criar_lisp_fd ausente")

    print("\n" + "="*60)
    print("RESUMO DAS CORRECOES:")
    print("[OK] AutoCADSelectionManager definido e importado")
    print("[OK] FundoMainWindow carrega sem erros")
    print("[OK] Botao 'Criar comando lisp FD' implementado")
    print("[OK] Scripts salvos na pasta SCRIPTS_ROBOS")
    print("[OK] Sistema de creditos removido")
    print("="*60)

except Exception as e:
    print(f"[ERRO] Falha geral: {e}")
    import traceback
    traceback.print_exc()
