"""
Script de Validacao: Comparacao entre versao Legacy e Nova versao PySide
Testa geracao de scripts identicos para fundos de vigas
"""

import os
import sys
import json
from datetime import datetime

# Adicionar caminhos dos robos
legacy_path = os.path.join(os.path.dirname(__file__), "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
sys.path.insert(0, legacy_path)

def criar_dados_sinteticos():
    """Cria dados sinteticos para testes de validacao"""

    dados_teste = [
        {
            "id": "teste_200x20_sem_aberturas",
            "numero": "V200.1",
            "nome": "Viga 200x20 Basica",
            "largura": 200,
            "altura": 20,
            "pavimento": "Teste1",
            "observacoes": "Teste basico sem aberturas ou chanfros",
            "painel1": 60,
            "painel2": 70,
            "painel3": 40,
            "painel4": 30,
            "sarrafo_esq": 5,
            "sarrafo_dir": 5,
            "tipo_distribuicao": "Padrao",
            "tipo_painel_inicial": "Normal"
        },
        {
            "id": "teste_200x20_com_chanfros",
            "numero": "V200.2",
            "nome": "Viga 200x20 com Chanfros",
            "largura": 200,
            "altura": 20,
            "pavimento": "Teste1",
            "observacoes": "Teste com chanfros",
            "painel1": 60,
            "painel2": 70,
            "painel3": 40,
            "painel4": 30,
            "sarrafo_esq": 5,
            "sarrafo_dir": 5,
            "chanfro_te": 10,
            "chanfro_fe": 10,
            "chanfro_td": 5,
            "chanfro_fd": 5,
            "tipo_distribuicao": "Padrao",
            "tipo_painel_inicial": "Normal"
        }
    ]

    return dados_teste

def testar_versao_legacy(dados_teste):
    """Testa a versao legacy sem login"""
    print("="*60)
    print("TESTANDO VERSAO LEGACY")
    print("="*60)

    resultados_legacy = {}

    try:
        for dados in dados_teste:
            print(f"\nTestando: {dados['id']}")

            try:
                # Simular uso da funcao utilitaria
                from fundo_utils import gerar_script_robo_util

                # Mock config manager
                class MockConfigManager:
                    pass

                config_manager = MockConfigManager()
                script = gerar_script_robo_util(dados, config_manager)
                resultados_legacy[dados['id']] = script

                print(f"Script gerado: {len(script)} caracteres")

            except Exception as e:
                print(f"Erro: {str(e)}")
                resultados_legacy[dados['id']] = f"ERRO: {str(e)}"

    except Exception as e:
        print(f"Erro ao testar versao legacy: {str(e)}")

    return resultados_legacy

def testar_versao_nova(dados_teste):
    """Testa a nova versao PySide"""
    print("="*60)
    print("TESTANDO VERSAO PYQT")
    print("="*60)

    resultados_nova = {}

    try:
        for dados in dados_teste:
            print(f"\nTestando: {dados['id']}")

            try:
                # Usar a funcao utilitaria de geracao de script
                from fundo_utils import gerar_script_robo_util

                # Mock config manager
                class MockConfigManager:
                    pass

                config_manager = MockConfigManager()
                script = gerar_script_robo_util(dados, config_manager)
                resultados_nova[dados['id']] = script

                print(f"Script gerado: {len(script)} caracteres")

            except Exception as e:
                print(f"Erro: {str(e)}")
                resultados_nova[dados['id']] = f"ERRO: {str(e)}"

    except Exception as e:
        print(f"Erro ao testar versao nova: {str(e)}")

    return resultados_nova

def comparar_resultados(resultados_legacy, resultados_nova):
    """Compara os resultados das duas versoes"""
    print("="*60)
    print("COMPARACAO DE RESULTADOS")
    print("="*60)

    comparacao = {}

    for test_id in resultados_legacy.keys():
        legacy = resultados_legacy[test_id]
        nova = resultados_nova.get(test_id, "TESTE NAO EXECUTADO")

        if legacy.startswith("ERRO:") or nova.startswith("ERRO:"):
            status = "ERRO"
        elif legacy == nova:
            status = "IDENTICO"
        else:
            status = "DIFERENTE"

        comparacao[test_id] = {
            "status": status,
            "legacy_len": len(legacy) if not legacy.startswith("ERRO:") else 0,
            "nova_len": len(nova) if not nova.startswith("ERRO:") else 0,
            "legacy": legacy,
            "nova": nova
        }

        print(f"\n{test_id}: {status}")
        if status == "DIFERENTE":
            print(f"   Legacy: {len(legacy)} chars")
            print(f"   Nova:   {len(nova)} chars")

    return comparacao

def salvar_scripts(resultados_legacy, resultados_nova, comparacao):
    """Salva os scripts gerados na pasta SCRIPTS_ROBOS"""
    scripts_dir = os.path.join(os.path.dirname(__file__), "SCRIPTS_ROBOS")
    os.makedirs(scripts_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Salvar resultados
    for test_id, resultado in comparacao.items():
        # Salvar script legacy
        legacy_file = os.path.join(scripts_dir, f"{test_id}_legacy_{timestamp}.scr")
        with open(legacy_file, 'w', encoding='utf-8') as f:
            f.write(resultado['legacy'])

        # Salvar script novo
        nova_file = os.path.join(scripts_dir, f"{test_id}_novo_{timestamp}.scr")
        with open(nova_file, 'w', encoding='utf-8') as f:
            f.write(resultado['nova'])

    # Salvar relatorio de comparacao
    relatorio_file = os.path.join(scripts_dir, f"relatorio_comparacao_{timestamp}.json")
    with open(relatorio_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": timestamp,
            "comparacao": comparacao,
            "resumo": {
                "total_testes": len(comparacao),
                "identicos": len([r for r in comparacao.values() if r['status'] == "IDENTICO"]),
                "diferentes": len([r for r in comparacao.values() if r['status'] == "DIFERENTE"]),
                "erros": len([r for r in comparacao.values() if r['status'] == "ERRO"])
            }
        }, f, indent=2, ensure_ascii=False)

    print(f"\nScripts salvos em: {scripts_dir}")
    print(f"Relatorio: {relatorio_file}")

def main():
    """Funcao principal de teste"""
    print("Iniciando Teste de Validacao - FundoAnalyzer")
    print("="*60)

    # Criar dados sinteticos
    dados_teste = criar_dados_sinteticos()
    print(f"Criados {len(dados_teste)} casos de teste")

    # Testar versao legacy
    resultados_legacy = testar_versao_legacy(dados_teste)

    # Testar versao nova
    resultados_nova = testar_versao_nova(dados_teste)

    # Comparar resultados
    comparacao = comparar_resultados(resultados_legacy, resultados_nova)

    # Salvar scripts
    salvar_scripts(resultados_legacy, resultados_nova, comparacao)

    # Resumo final
    print("\n" + "="*60)
    print("RESUMO FINAL")
    print("="*60)

    total = len(comparacao)
    identicos = len([r for r in comparacao.values() if r['status'] == "IDENTICO"])
    diferentes = len([r for r in comparacao.values() if r['status'] == "DIFERENTE"])
    erros = len([r for r in comparacao.values() if r['status'] == "ERRO"])

    print(f"Total de testes: {total}")
    print(f"Scripts identicos: {identicos}")
    print(f"Scripts diferentes: {diferentes}")
    print(f"Erros: {erros}")

    if diferentes == 0 and erros == 0:
        print("SUCESSO: Todas as versoes geram scripts identicos!")
    else:
        print("ATENCAO: Diferencas encontradas entre as versoes")

if __name__ == "__main__":
    main()