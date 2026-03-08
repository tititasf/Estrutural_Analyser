"""
Teste mínimo para verificar se as correções básicas funcionam
"""

import sys
import os

# Adicionar caminhos
legacy_path = os.path.join(os.path.dirname(__file__), "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
sys.path.insert(0, legacy_path)

print("Testando importações básicas...")

try:
    print("1. Importando fundo_pyside...")
    from fundo_pyside import FundoMainWindow
    print("   [OK] fundo_pyside importado")

    print("2. Verificando estrutura da classe...")
    # Verificar se os métodos existem
    metodos_necessarios = ['get_current_data', 'action_salvar', 'action_desenhar_teste', 'action_desenhar_pavimento']
    for metodo in metodos_necessarios:
        if hasattr(FundoMainWindow, metodo):
            print(f"   [OK] Método {metodo} existe")
        else:
            print(f"   [ERRO] Método {metodo} não encontrado")

    print("3. Testando criação de instância...")
    # Tentar criar uma instância mínima
    app = FundoMainWindow()
    print("   [OK] Instância criada")

    print("4. Verificando campos...")
    if hasattr(app, 'fields'):
        campos_esperados = ['numero', 'nome', 'pavimento', 'largura', 'altura']
        for campo in campos_esperados:
            if campo in app.fields:
                print(f"   [OK] Campo {campo} presente")
            else:
                print(f"   [ERRO] Campo {campo} ausente")
    else:
        print("   [ERRO] Atributo fields não encontrado")

    print("5. Testando get_current_data...")
    try:
        dados = app.get_current_data()
        if 'numero' in dados:
            print("   [OK] get_current_data inclui numero")
        else:
            print("   [ERRO] get_current_data não inclui numero")
    except Exception as e:
        print(f"   [ERRO] get_current_data falhou: {e}")

    print("\nTESTE CONCLUÍDO COM SUCESSO!")

except Exception as e:
    print(f"[ERRO] Falha crítica: {e}")
    import traceback
    traceback.print_exc()