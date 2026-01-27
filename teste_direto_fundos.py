"""
Teste direto de geração de scripts de fundos
Gera scripts AutoCAD diretamente para comparação
"""

import os
import sys
from datetime import datetime

# Adicionar caminhos
legacy_path = os.path.join(os.path.dirname(__file__), "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
sys.path.insert(0, legacy_path)

def criar_dados_teste_completos():
    """Cria dados de teste abrangentes"""
    return [
        {
            "id": "teste_200x20_basico",
            "numero": "V200.1",
            "nome": "Viga 200x20 Básica",
            "largura": 200,
            "altura": 20,
            "pavimento": "Teste1",
            "observacoes": "Teste básico sem aberturas ou chanfros",
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
            "id": "teste_300x30_com_chanfros",
            "numero": "V300.1",
            "nome": "Viga 300x30 com Chanfros",
            "largura": 300,
            "altura": 30,
            "pavimento": "Teste1",
            "observacoes": "Teste com chanfros",
            "painel1": 80,
            "painel2": 100,
            "painel3": 60,
            "painel4": 60,
            "sarrafo_esq": 8,
            "sarrafo_dir": 8,
            "chanfro_te": 15,
            "chanfro_fe": 15,
            "chanfro_td": 8,
            "chanfro_fd": 8,
            "tipo_distribuicao": "Padrao",
            "tipo_painel_inicial": "Normal"
        },
        {
            "id": "teste_400x40_com_aberturas",
            "numero": "V400.1",
            "nome": "Viga 400x40 com Aberturas",
            "largura": 400,
            "altura": 40,
            "pavimento": "Teste1",
            "observacoes": "Teste com aberturas",
            "painel1": 100,
            "painel2": 120,
            "painel3": 80,
            "painel4": 100,
            "sarrafo_esq": 10,
            "sarrafo_dir": 10,
            "abertura_te_dist": 50,
            "abertura_te_prof": 20,
            "abertura_te_larg": 15,
            "abertura_fe_dist": 50,
            "abertura_fe_prof": 20,
            "abertura_fe_larg": 15,
            "tipo_distribuicao": "Padrao",
            "tipo_painel_inicial": "Normal"
        },
        {
            "id": "teste_600x60_completo",
            "numero": "V600.1",
            "nome": "Viga 600x60 Completa",
            "largura": 600,
            "altura": 60,
            "pavimento": "Teste1",
            "observacoes": "Teste completo",
            "painel1": 150,
            "painel2": 180,
            "painel3": 120,
            "painel4": 150,
            "sarrafo_esq": 15,
            "sarrafo_dir": 15,
            "chanfro_te": 25,
            "chanfro_fe": 25,
            "chanfro_td": 15,
            "chanfro_fd": 15,
            "abertura_te_dist": 100,
            "abertura_te_prof": 30,
            "abertura_te_larg": 25,
            "abertura_fe_dist": 100,
            "abertura_fe_prof": 30,
            "abertura_fe_larg": 25,
            "tipo_distribuicao": "Padrao",
            "tipo_painel_inicial": "Normal"
        }
    ]

def gerar_script_autocad_basico(dados):
    """Gera um script AutoCAD básico baseado nos dados"""
    largura = dados.get('largura', 200)
    altura = dados.get('altura', 20)
    numero = dados.get('numero', 'V200.1')
    nome = dados.get('nome', 'Viga Teste')

    # Coordenadas da viga (retângulo simples)
    x1, y1 = 0, 0
    x2, y2 = largura, altura

    script = f""";; Script AutoCAD para {nome} ({numero})
;; Gerado em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

;; Desenhar retângulo da viga
-LINE
{x1},{y1}
{x2},{y1}
{x2},{y2}
{x1},{y2}
{x1},{y1}

;; Adicionar texto com o número da viga
-TEXT
{x1 + largura/2},{y1 + altura/2}
{altura/4}
0
{numero}

;; Finalizar
"""

    return script

def testar_geracao_scripts():
    """Testa geração de scripts"""
    print("TESTE DIRETO DE GERACAO DE SCRIPTS")
    print("="*50)

    dados_teste = criar_dados_teste_completos()

    scripts_dir = os.path.join(os.path.dirname(__file__), "SCRIPTS_ROBOS")
    os.makedirs(scripts_dir, exist_ok=True)

    resultados = {}

    for dados in dados_teste:
        test_id = dados['id']
        print(f"\nTestando: {test_id}")

        try:
            # Gerar script básico
            script = gerar_script_autocad_basico(dados)

            # Salvar script
            script_file = os.path.join(scripts_dir, f"{test_id}_{datetime.now().strftime('%H%M%S')}.scr")
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write(script)

            resultados[test_id] = script
            print(f"Script salvo: {script_file}")
            print(f"Tamanho: {len(script)} caracteres")

        except Exception as e:
            print(f"Erro: {str(e)}")
            resultados[test_id] = f"ERRO: {str(e)}"

    return resultados

def comparar_com_legacy():
    """Tenta comparar com versão legacy simplificada"""
    print("\nTESTANDO INTEGRACAO COM LEGACY")
    print("="*50)

    dados_teste = criar_dados_teste_completos()

    # Tentar usar a versão legacy modificada
    try:
        from fundo_analyzer_teste import executar_teste_legacy
        resultados_legacy = executar_teste_legacy(dados_teste[:1])  # Apenas o primeiro para teste
        print("Resultados legacy:", resultados_legacy)
    except Exception as e:
        print(f"Erro ao testar legacy: {str(e)}")

if __name__ == "__main__":
    # Executar testes diretos
    resultados = testar_geracao_scripts()

    # Tentar comparar com legacy
    comparar_com_legacy()

    print("\nRESUMO:")
    print(f"Scripts gerados: {len([r for r in resultados.values() if not str(r).startswith('ERRO:')])}")
    print(f"Erros: {len([r for r in resultados.values() if str(r).startswith('ERRO:')])}")