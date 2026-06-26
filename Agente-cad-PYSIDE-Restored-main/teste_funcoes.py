"""
Teste das funções corrigidas
"""

import sys
import os

# Configurar caminhos
legacy_path = os.path.join(os.path.dirname(__file__), "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
sys.path.insert(0, legacy_path)

print("Testando funções corrigidas...")

try:
    from PySide6.QtWidgets import QApplication
    from fundo_pyside import FundoMainWindow

    # Criar QApplication se necessário
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # Criar janela
    window = FundoMainWindow()
    print("FundoMainWindow criada")

    # Testar get_current_data
    print("\n1. Testando get_current_data...")
    dados = window.get_current_data()
    print(f"Campos retornados: {list(dados.keys())}")

    if 'numero' in dados:
        print(f"Campo numero presente: '{dados['numero']}'")
    else:
        print("ERRO: Campo numero ausente")

    # Configurar dados de teste
    print("\n2. Configurando dados de teste...")
    window.fields['numero'].setText('V1.1')
    window.fields['nome'].setText('Viga Teste')
    window.fields['pavimento'].setText('Pav Teste')
    window.fields['largura'].setText('200')
    window.fields['altura'].setText('20')

    # Adicionar obra ao combo
    window.combo_obra.addItem('Obra Teste')
    window.combo_obra.setCurrentText('Obra Teste')

    print("Dados de teste configurados")

    # Testar get_current_data novamente
    print("\n3. Testando get_current_data com dados preenchidos...")
    dados2 = window.get_current_data()
    print(f"numero: '{dados2.get('numero')}'")
    print(f"nome: '{dados2.get('nome')}'")
    print(f"pavimento: '{dados2.get('pavimento')}'")
    print(f"largura: '{dados2.get('largura')}'")
    print(f"altura: '{dados2.get('altura')}'")

    # Testar salvar
    print("\n4. Testando action_salvar...")
    try:
        window.action_salvar()
        print("action_salvar executado")
    except Exception as e:
        print(f"Erro em action_salvar: {e}")

    # Verificar estrutura de dados
    print("\n5. Verificando estrutura de dados...")
    print(f"fundos_salvos keys: {list(window.fundos_salvos.keys())}")

    if 'Obra Teste' in window.fundos_salvos:
        print("Obra Teste encontrada")
        if 'Pav Teste' in window.fundos_salvos['Obra Teste']:
            print("Pav Teste encontrado")
            if 'V1.1' in window.fundos_salvos['Obra Teste']['Pav Teste']:
                print("V1.1 encontrado nos dados salvos")
                dados_salvos = window.fundos_salvos['Obra Teste']['Pav Teste']['V1.1']
                print(f"Dados salvos: numero='{dados_salvos.get('numero')}', pavimento='{dados_salvos.get('pavimento')}'")
            else:
                print("V1.1 não encontrado")
        else:
            print("Pav Teste não encontrado")
    else:
        print("Obra Teste não encontrada")

    # Testar filtragem por pavimento
    print("\n6. Testando filtragem por pavimento...")
    obra_atual = 'Obra Teste'
    pav = 'Pav Teste'

    fundos = []
    if obra_atual in window.fundos_salvos and pav in window.fundos_salvos[obra_atual]:
        for numero, dados in window.fundos_salvos[obra_atual][pav].items():
            fundos.append(dados)
            print(f"  Fundo encontrado: {numero}")

    print(f"Total de fundos filtrados: {len(fundos)}")

    print("\nTESTE DAS FUNÇÕES CORRIGIDAS CONCLUÍDO!")

except Exception as e:
    print(f"ERRO GERAL: {e}")
    import traceback
    traceback.print_exc()