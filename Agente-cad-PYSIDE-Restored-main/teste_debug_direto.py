"""
Teste direto com debug prints para entender o comportamento dos botões
"""

import sys
import os

# Adicionar caminhos
legacy_path = os.path.join(os.path.dirname(__file__), "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
sys.path.insert(0, legacy_path)

def testar_fundo_pyside_direto():
    """Testa a criação direta da classe FundoMainWindow"""
    print("="*60)
    print("TESTANDO FUNDO PYSIDE DIRETO")
    print("="*60)

    try:
        from fundo_pyside import FundoMainWindow
        print("[DEBUG] Import FundoMainWindow OK")

        # Criar instância (sem mostrar interface)
        app = FundoMainWindow()
        print("[DEBUG] Instância FundoMainWindow criada")

        # Verificar se os campos existem
        print(f"[DEBUG] Campos existentes: {list(app.fields.keys()) if hasattr(app, 'fields') else 'Nenhum campo'}")

        # Verificar se fundos_salvos existe
        print(f"[DEBUG] Fundos salvos: {len(app.fundos_salvos) if hasattr(app, 'fundos_salvos') else 'Atributo não existe'}")

        # Adicionar dados de teste
        dados_teste = {
            "numero": "V200.1",
            "nome": "Viga Teste 200x20",
            "largura": 200,
            "altura": 20,
            "pavimento": "Teste1",
            "observacoes": "Teste básico",
            "painel1": 60,
            "painel2": 70,
            "painel3": 40,
            "painel4": 30,
            "sarrafo_esq": 5,
            "sarrafo_dir": 5,
            "tipo_distribuicao": "Padrao",
            "tipo_painel_inicial": "Normal"
        }

        app.fundos_salvos["V200.1"] = dados_teste
        print(f"[DEBUG] Dados de teste adicionados. Total fundos: {len(app.fundos_salvos)}")

        # Simular preenchimento dos campos
        if hasattr(app, 'fields'):
            for campo, valor in dados_teste.items():
                if campo in app.fields:
                    app.fields[campo].setText(str(valor))
                    print(f"[DEBUG] Campo {campo} definido como: {valor}")

        # Tentar executar get_current_data
        print("[DEBUG] Tentando executar get_current_data...")
        try:
            dados_coletados = app.get_current_data()
            print(f"[DEBUG] Dados coletados com sucesso: {dados_coletados}")
        except Exception as e:
            print(f"[DEBUG] Erro em get_current_data: {e}")
            import traceback
            traceback.print_exc()

        # Tentar executar action_desenhar_teste
        print("[DEBUG] Tentando executar action_desenhar_teste...")
        try:
            app.action_desenhar_teste()
            print("[DEBUG] action_desenhar_teste executado com sucesso")
        except Exception as e:
            print(f"[DEBUG] Erro em action_desenhar_teste: {e}")
            import traceback
            traceback.print_exc()

        return True

    except Exception as e:
        print(f"[DEBUG] Erro geral no teste: {e}")
        import traceback
        traceback.print_exc()
        return False

def testar_fundo_legacy_direto():
    """Testa a criação direta da classe FundoProducaoApp"""
    print("="*60)
    print("TESTANDO FUNDO LEGACY DIRETO")
    print("="*60)

    try:
        from fundo_producao import FundoProducaoApp
        print("[DEBUG] Import FundoProducaoApp OK")

        # Criar instância (sem mostrar interface)
        app = FundoProducaoApp()
        print("[DEBUG] Instância FundoProducaoApp criada")

        # Mock credit manager
        class MockCreditManager:
            def calcular_area_total(self, dados):
                largura = float(dados.get('largura', 0))
                altura = float(dados.get('altura', 0))
                return largura * altura / 1000000

            def consultar_saldo(self):
                return True, "1000.00"

            def debitar_multiplos_fundos(self, fundos):
                return True, "Débito realizado"

        app.credit_manager = MockCreditManager()
        print("[DEBUG] Credit manager mockado")

        # Verificar atributos
        print(f"[DEBUG] Atributos principais: fundos_salvos={hasattr(app, 'fundos_salvos')}, config_manager={hasattr(app, 'config_manager')}")

        return True

    except Exception as e:
        print(f"[DEBUG] Erro geral no teste legacy: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("INICIANDO TESTE DE DEBUG DIRETO")
    print("="*60)

    # Testar PySide primeiro
    sucesso_pyside = testar_fundo_pyside_direto()

    print("\n")

    # Testar Legacy
    sucesso_legacy = testar_fundo_legacy_direto()

    print("\n" + "="*60)
    print("RESUMO DOS TESTES")
    print("="*60)
    print(f"PySide: {'SUCESSO' if sucesso_pyside else 'FALHA'}")
    print(f"Legacy: {'SUCESSO' if sucesso_legacy else 'FALHA'}")