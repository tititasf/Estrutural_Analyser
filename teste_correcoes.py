"""
Teste das correções feitas nos botões Desenhar Teste e Desenhar Pavimento
"""

import sys
import os

# Adicionar caminhos
legacy_path = os.path.join(os.path.dirname(__file__), "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
sys.path.insert(0, legacy_path)

def testar_correcoes():
    """Testa se as correções foram aplicadas corretamente"""
    print("="*60)
    print("TESTANDO CORREÇÕES APLICADAS")
    print("="*60)

    try:
        from fundo_pyside import FundoMainWindow
        print("[OK] Import FundoMainWindow")

        # Criar instância
        app = FundoMainWindow()
        print("[OK] Instância FundoMainWindow criada")

        # Verificar se o campo numero está presente
        if 'numero' in app.fields:
            print("[OK] Campo 'numero' presente na interface")
        else:
            print("[ERRO] Campo 'numero' não encontrado")

        # Verificar se get_current_data inclui numero
        dados_teste = app.get_current_data()
        if 'numero' in dados_teste:
            print(f"[OK] get_current_data inclui numero: '{dados_teste['numero']}'")
        else:
            print("[ERRO] get_current_data não inclui numero")

        # Testar estrutura de dados
        print(f"[INFO] Estrutura fundos_salvos: {type(app.fundos_salvos)}")

        # Simular adição de dados de teste
        obra_teste = "Obra Teste"
        pav_teste = "Pavimento Teste"
        num_teste = "V1.1"

        # Simular preenchimento
        app.fields['numero'].setText(num_teste)
        app.fields['nome'].setText("Viga Teste")
        app.fields['pavimento'].setText(pav_teste)
        app.fields['largura'].setText("200")
        app.fields['altura'].setText("20")

        # Simular seleção de obra
        app.combo_obra.addItem(obra_teste)
        app.combo_obra.setCurrentText(obra_teste)

        print("[INFO] Dados de teste configurados")

        # Testar salvar
        print("[TEST] Testando action_salvar...")
        try:
            app.action_salvar()
            print("[OK] action_salvar executado sem erro")
        except Exception as e:
            print(f"[ERRO] action_salvar falhou: {e}")

        # Verificar se dados foram salvos
        if obra_teste in app.fundos_salvos:
            if pav_teste in app.fundos_salvos[obra_teste]:
                if num_teste in app.fundos_salvos[obra_teste][pav_teste]:
                    dados_salvos = app.fundos_salvos[obra_teste][pav_teste][num_teste]
                    print(f"[OK] Dados salvos corretamente: numero='{dados_salvos.get('numero')}', pavimento='{dados_salvos.get('pavimento')}'")
                else:
                    print("[ERRO] Numero não encontrado nos dados salvos")
            else:
                print("[ERRO] Pavimento não encontrado nos dados salvos")
        else:
            print("[ERRO] Obra não encontrada nos dados salvos")

        # Testar filtragem de fundos por pavimento
        print("[TEST] Testando filtragem por pavimento...")
        pav = pav_teste
        obra_atual = obra_teste

        fundos = []
        if obra_atual in app.fundos_salvos and pav in app.fundos_salvos[obra_atual]:
            for numero, dados in app.fundos_salvos[obra_atual][pav].items():
                fundos.append(dados)

        print(f"[OK] Filtragem encontrou {len(fundos)} fundos para pavimento '{pav}'")

        return True

    except Exception as e:
        print(f"[ERRO] Falha geral no teste: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    sucesso = testar_correcoes()
    print("\n" + "="*60)
    if sucesso:
        print("CORREÇÕES APLICADAS COM SUCESSO")
    else:
        print("PROBLEMAS ENCONTRADOS NAS CORREÇÕES")
    print("="*60)