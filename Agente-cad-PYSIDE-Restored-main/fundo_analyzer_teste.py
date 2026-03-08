"""
Versão modificada do fundo_analyzer.py para testes
Remove sistema de login e créditos
"""

import sys
import os

# Garantir path correto
current_dir = os.path.dirname(os.path.abspath(__file__))
robo_path = os.path.join(current_dir, "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
if robo_path not in sys.path:
    sys.path.append(robo_path)

try:
    from fundo_producao import FundoProducaoApp
except ImportError as e:
    print(f"Erro ao importar FundoProducaoApp: {e}")
    sys.exit(1)

def executar_teste_legacy(dados_teste):
    """Executa teste na versão legacy sem login"""
    resultados = {}

    try:
        # Criar aplicação
        app = FundoProducaoApp()

        # Mock credit manager para bypass
        class MockCreditManager:
            def calcular_area_total(self, dados):
                largura = float(dados.get('largura', 0))
                altura = float(dados.get('altura', 0))
                return largura * altura / 1000000  # Área em m²

            def consultar_saldo(self):
                return True, "1000.00"

            def debitar_multiplos_fundos(self, fundos):
                return True, "Débito realizado"

        app.credit_manager = MockCreditManager()

        for dados in dados_teste:
            print(f"Testando: {dados['id']}")

            try:
                # Simular dados
                app.fundos_salvos = {dados['numero']: dados}

                # Gerar script usando função utilitária
                from fundo_utils import gerar_script_robo_util

                # Mock config manager
                class MockConfigManager:
                    def get_config(self, section, key):
                        # Valores padrão para teste
                        defaults = {
                            'opcoes': {
                                'logica_sarrafos': 'padrao',
                                'unidade': 'mm',
                                'tipo_linha': 'continua'
                            },
                            'parametros': {
                                'tolerancia': 1.0,
                                'escala': 1.0
                            }
                        }
                        return defaults.get(section, {}).get(key, None)

                config_manager = MockConfigManager()
                script = gerar_script_robo_util(dados, config_manager)
                resultados[dados['id']] = script

                print(f"Script gerado: {len(script)} caracteres")

            except Exception as e:
                print(f"Erro: {str(e)}")
                resultados[dados['id']] = f"ERRO: {str(e)}"

    except Exception as e:
        print(f"Erro geral: {str(e)}")

    return resultados

if __name__ == "__main__":
    # Dados de teste simples
    dados_teste = [
        {
            "id": "teste_basico",
            "numero": "V200.1",
            "nome": "Viga Teste",
            "largura": 200,
            "altura": 20,
            "pavimento": "Teste1",
            "observacoes": "Teste basico",
            "painel1": 60,
            "painel2": 70,
            "painel3": 40,
            "painel4": 30,
            "sarrafo_esq": 5,
            "sarrafo_dir": 5,
            "tipo_distribuicao": "Padrao",
            "tipo_painel_inicial": "Normal"
        }
    ]

    resultados = executar_teste_legacy(dados_teste)
    print("Resultados:", resultados)