import os
import re
import tkinter as tk
from tkinter import messagebox
import json
from datetime import datetime
import traceback
import math

class GeradorScriptCombinados:
    def __init__(self):
        """Inicializa o gerador de scripts para laterais de viga combinadas."""
        self.config = self._carregar_config()

    def _carregar_config(self):
        """Carrega as configurações do arquivo config.json (mesma pasta do Robo_Laterais_de_Vigas)."""
        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return self._obter_config_padrao()
        except Exception as e:
            print(f"Erro ao carregar configurações: {str(e)}")
            return self._obter_config_padrao()
    
    def _obter_config_padrao(self):
        """Retorna configurações padrão para o gerador de scripts."""
        return {
            "layers": {
                "paineis": "Painéis",
                "sarrafos_verticais": "SARR_2.2x7",
                "sarrafos_horizontais": "SARR_2.2x7",
                "sarrafos_horizontais_pequenos": "SARR_2.2x5",
                "nome_observacoes": "NOMENCLATURA",
                "textos_laterais": "5",
                "cotas": "COTA",
                "laje": "COTA"
            },
            "comandos": {
                "extensor1": "ex2",
                "extensor2": "Bextend"
            },
            "opcoes": {
                "tipo_linha": "PLINE"
            }
        }
        
    def _get_layer(self, layer_name):
        """Retorna o nome da layer configurada."""
        if "layers" in self.config and layer_name in self.config["layers"]:
            return self.config["layers"][layer_name]
        return self._obter_config_padrao()["layers"].get(layer_name, "0")
    
    def _get_tipo_linha(self):
        """Retorna o tipo de linha configurado."""
        if "opcoes" in self.config and "tipo_linha" in self.config["opcoes"]:
            return self.config["opcoes"]["tipo_linha"]
        return "PLINE"

    def _gerar_conteudo_script_fundo(self, dados):
        """
        Gera o conteúdo do script SCR para um único fundo com base nos dados.
        Adaptado de _gerar_conteudo_script do gerador_script_viga.
        """
        try:
            # Função utilitária para somar partes de altura (N+N ou float)
            def soma_altura_partes(val):
                if isinstance(val, str) and '+' in val:
                    return sum(float(p.strip()) for p in val.split('+') if p.strip())
                try:
                    return float(val)
                except Exception:
                    return 0

            # Obter dados do item
            nome = dados.get('nome', 'SemNome')
            observacoes = dados.get('obs', '')
            texto_esquerdo = dados.get('texto_esq', 'Texto Esquerdo')
            texto_direito = dados.get('texto_dir', 'Texto Direito')
            
            # Obter dimensões
            largura_total = float(dados.get('largura', 0))
            altura_geral_raw = str(dados.get('altura_geral', 0))
            if '+' in altura_geral_raw:
                altura_geral = sum(float(p.strip()) for p in altura_geral_raw.split('+') if p.strip())
            else:
                try:
                    altura_geral = float(altura_geral_raw)
                except Exception:
                    altura_geral = 0
            
            # Obter valores específicos dos painéis
            paineis = []
            paineis_individuais = []

            paineis_larguras = dados.get('paineis_larguras', None)
            if paineis_larguras and isinstance(paineis_larguras, list) and any(float(x) > 0 for x in paineis_larguras):
                for largura in paineis_larguras:
                    try:
                        largura_f = float(largura)
                        if largura_f > 0:
                            paineis_individuais.append(largura_f)
                    except Exception:
                        continue
            else:
                for i in range(1, 7):
                    pos_key = f'p{i}'
                    if pos_key in dados and dados[pos_key] and float(dados[pos_key]) > 0:
                        paineis_individuais.append(float(dados[pos_key]))
            
            if paineis_individuais:
                pos_acumulada = 0
                for largura in paineis_individuais:
                    pos_acumulada += largura
                    if pos_acumulada <= largura_total:
                        paineis.append(pos_acumulada)
            elif 'paineis' in dados and dados['paineis']:
                pos_acumulada = 0
                for painel in dados['paineis']:
                    if painel and float(painel) > 0:
                        pos_acumulada += float(painel)
                        if pos_acumulada <= largura_total:
                            paineis.append(pos_acumulada)
                            paineis_individuais.append(float(painel))
            
            if not paineis or (paineis and paineis[-1] < largura_total):
                if not paineis:
                    paineis = []
                    paineis_individuais = []
                
                largura_restante = largura_total
                if paineis:
                    largura_restante = largura_total - paineis[-1]
                
                tamanho_max_painel = 244
                num_paineis_restantes = max(1, math.ceil(largura_restante / tamanho_max_painel))
                tamanho_painel = largura_restante / num_paineis_restantes
                pos_inicial = 0
                if paineis:
                    pos_inicial = paineis[-1]
                
                for i in range(1, num_paineis_restantes + 1):
                    pos_acumulada = pos_inicial + (tamanho_painel * i)
                    if i == num_paineis_restantes:
                        pos_acumulada = largura_total
                    
                    paineis.append(pos_acumulada)
                    
                    if i == 1:
                        largura_individual = pos_acumulada - pos_inicial
                    else:
                        largura_individual = pos_acumulada - paineis[-2]
                    
                    paineis_individuais.append(largura_individual)
            
            if paineis and paineis[-1] < largura_total:
                diferenca = largura_total - paineis[-1]
                paineis.append(largura_total)
                paineis_individuais.append(diferenca)
            elif not paineis:
                paineis = [largura_total]
                paineis_individuais = [largura_total]
            
            x_inicial = 12795.5914
            y_inicial = 13158.9905
            
            layer_paineis = self._get_layer("paineis")
            layer_sarrafos_verticais = self._get_layer("sarrafos_verticais")
            layer_sarrafos_horizontais = self._get_layer("sarrafos_horizontais")
            layer_sarrafos_horizontais_pequenos = self._get_layer("sarrafos_horizontais_pequenos")
            layer_nome_observacoes = self._get_layer("nome_observacoes")
            layer_textos_laterais = self._get_layer("textos_laterais")
            layer_cotas = self._get_layer("cotas")
            layer_laje = self._get_layer("laje")
            
            tipo_linha = self._get_tipo_linha()
            
            script_content = ""

            # Cabeçalho do Script (Removido todos os comandos de layer, cor, linetype, etc., conforme pedido)
            script_header = f"""
; =====================================================================
; CONFIGURAÇÕES INICIAIS DO DESENHO
; =====================================================================
"""
            script_content += script_header
            # Definir estilo de texto (standart)
            script_content += ";\n-style\nstandart\n\n0\n\n\n\n\n\n;\n"

            # Desenhar o painel principal (retângulo externo)
            script_painel_principal = f"""
; =====================================================================
; DESENHO DO PAINEL PRINCIPAL (RETÂNGULO EXTERNO)
; =====================================================================
-LAYER
S {layer_paineis}
;
__{tipo_linha}
{x_inicial},{y_inicial}
{x_inicial+largura_total},{y_inicial}
{x_inicial+largura_total},{y_inicial+altura_geral}
{x_inicial},{y_inicial+altura_geral}
C
;
"""
            script_content += script_painel_principal

            # Desenhar as divisões dos painéis
            script_divisoes_paineis = ""
            x_atual = x_inicial
            for i, largura_painel in enumerate(paineis_individuais):
                if i < len(paineis_individuais) - 1: # Não desenha a última linha, já está no retângulo principal
                    script_divisoes_paineis += f"""
; Divisão do Painel {i+1}
-LAYER
S {layer_paineis}
;
__{tipo_linha}
{x_atual + largura_painel},{y_inicial}
{x_atual + largura_painel},{y_inicial+altura_geral}
;
"""
                x_atual += largura_painel
            if script_divisoes_paineis:
                script_content += script_divisoes_paineis

            # Desenhar sarrafos (vertical e horizontal) - Lógica adaptada
            script_sarrafos_verticais = ""
            sarrafo_largura = 2.2 # Largura padrão do sarrafo
            for i, largura_painel in enumerate(paineis_individuais):
                if i < len(paineis_individuais) - 1: # Sarrafos entre os painéis
                    x_sarrafo_vert = x_inicial + sum(paineis_individuais[:i+1]) - sarrafo_largura / 2
                    # Desenhar sarrafo vertical (ajustar coordenadas Y conforme o desenho da viga)
                    script_sarrafos_verticais += f"""
; Sarrafo Vertical entre Painéis {i+1} e {i+2}
-LAYER
S {layer_sarrafos_verticais}
;
__{tipo_linha}
{x_sarrafo_vert},{y_inicial}
{x_sarrafo_vert},{y_inicial+altura_geral}
;
"""
            if script_sarrafos_verticais:
                script_content += script_sarrafos_verticais

            script_sarrafos_horizontais = f"""
; Sarrafo Horizontal Superior
-LAYER
S {layer_sarrafos_horizontais}
;
__{tipo_linha}
{x_inicial},{y_inicial+altura_geral - sarrafo_largura/2}
{x_inicial+largura_total},{y_inicial+altura_geral - sarrafo_largura/2}
;
; Sarrafo Horizontal Inferior
__{tipo_linha}
{x_inicial},{y_inicial+sarrafo_largura/2}
{x_inicial+largura_total},{y_inicial+sarrafo_largura/2}
;
"""
            script_content += script_sarrafos_horizontais

            return script_content

        except Exception as e:
            traceback.print_exc()
            return ""

    def gerar_script_unico(self, dados, diretorio_saida, sufixo_pavimento):
        """
        Gera um script SCR para um único fundo combinado e o salva.
        
        Args:
            dados: Dicionário com os dados do fundo a ser combinado.
            diretorio_saida: O diretório base para salvar o script.
            sufixo_pavimento: Sufixo a ser adicionado ao nome do arquivo (ex: _COMBINADOS).
            
        Returns:
            tuple: (script_text, caminho_arquivo) se sucesso, (None, None) se erro.
        """
        try:
            if not diretorio_saida:
                return None, None
            if not os.path.exists(diretorio_saida):
                os.makedirs(diretorio_saida)

            nome = dados.get('nome', 'SemNome')
            observacoes = dados.get('obs', '')
            
            # Adiciona o sufixo do pavimento ao nome do arquivo
            base_nome = f"{nome}{'_' + observacoes if observacoes else ''}{sufixo_pavimento}"
            
            # Lógica para garantir nome de arquivo único
            sufixo_num = 1
            while True:
                arquivo_nome = f"{base_nome}-{sufixo_num}.scr"
                caminho_arquivo = os.path.join(diretorio_saida, arquivo_nome)
                if not os.path.exists(caminho_arquivo):
                    break
                sufixo_num += 1

            script_text = self._gerar_conteudo_script_fundo(dados)
            if dados.get('numero'):
                script_text = f"; (numeracao: {dados.get('numero')})\n" + script_text

            with open(caminho_arquivo, "w", encoding="utf-16") as f:
                f.write(script_text)
            return script_text, caminho_arquivo
        except Exception as e:
            traceback.print_exc()
            return None, None

    def gerar_script_combinado(self, combinacao_data, fundos_salvos, diretorio_saida, output_filepath=None):
        """
        Gera um script SCR para uma combinação de fundos.
        
        Args:
            combinacao_data: Dicionário com os dados da combinação (nome, ids).
            fundos_salvos: Dicionário completo de todos os fundos salvos.
            diretorio_saida: O diretório base para salvar o script.
            output_filepath: Caminho completo opcional para salvar o arquivo. Se fornecido, ignora diretorio_saida e a lógica de nome único.
            
        Returns:
            tuple: (script_text, caminho_arquivo) se sucesso, (None, None) se erro.
        """
        try:
            nome_combinacao = combinacao_data['nome']
            fundos_ids = combinacao_data['ids']

            if not diretorio_saida and not output_filepath: # Verifica se nenhum caminho válido foi fornecido
                return None, None
            
            # Se um caminho de arquivo de saída específico for fornecido, use-o diretamente
            if output_filepath:
                caminho_arquivo = output_filepath
                # Garante que o diretório para o output_filepath exista
                output_dir = os.path.dirname(output_filepath)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
            else:
                # Lógica existente para garantir nome de arquivo único para a combinação
                if not os.path.exists(diretorio_saida):
                    os.makedirs(diretorio_saida)
                base_nome_combinacao = f"COMB_{nome_combinacao}"
                sufixo_num = 1
                while True:
                    arquivo_nome = f"{base_nome_combinacao}-{sufixo_num}.scr"
                    caminho_arquivo = os.path.join(diretorio_saida, arquivo_nome)
                    if not os.path.exists(caminho_arquivo):
                        break
                    sufixo_num += 1

            final_script_content = ""

            # Coletar os dados dos dois fundos
            if len(fundos_ids) < 2:
                print("Erro: São necessários dois fundos para gerar o script combinado.")
                return None, None

            seg1_data = fundos_salvos.get(fundos_ids[0])
            seg2_data = fundos_salvos.get(fundos_ids[1])

            if not seg1_data or not seg2_data:
                print("Erro: Dados de um ou ambos os fundos combinados não encontrados.")
                return None, None

            # 1. Obter o maior valor de 'fundo' para a largura da base
            fundo_s1 = float(seg1_data.get('fundo', '0'))
            fundo_s2 = float(seg2_data.get('fundo', '0'))
            fundo_width_cm = max(fundo_s1, fundo_s2)

            # Configurações de desenho (coordenadas base no CAD)
            x_base_cad = 0.0
            y_base_cad = 0.0
            wall_width_cm = 2.2 # Largura da parede da "U" no CAD

            layer_paineis = self._get_layer("paineis") # Usar a layer de painéis para as paredes
            layer_base = self._get_layer("laje") # Usar a layer de laje para a base (linha)

            # Cabeçalho do script simplificado: apenas unidades e seleção de layers
            final_script_content += f"""-LAYER S {layer_paineis}
;
"""

            # 2. Desenhar a base da 'U' (linha PLINE de 2 coordenadas)
            x_base_start = x_base_cad
            y_base = y_base_cad
            x_base_end = x_base_cad + wall_width_cm + fundo_width_cm + wall_width_cm

            # Comando PLINE para a linha da base
            final_script_content += f"""_PLINE
{x_base_start},{y_base}
{x_base_end},{y_base}

;
"""


            # 3. Desenhar as paredes verticais (retângulos PLINE de 4 coordenadas + C)
            # Lógica para gerar comandos PLINE para um segmento vertical (Altura ou Laje)
            def generate_vertical_segment_pline(x_start, y_current, width, height, layer):
                if height <= 0:
                    return [] # Retorna lista vazia se a altura for zero

                commands = []
                # Não adiciona seleção de layer aqui, pois será feita globalmente no cabeçalho
                commands.append(f"_PLINE")
                commands.append(f"{x_start},{y_current}")
                commands.append(f"{x_start + width},{y_current}")
                commands.append(f"{x_start + width},{y_current + height}") # Desenha para cima
                commands.append(f"{x_start},{y_current + height}")
                commands.append(f"C") # Fechar a polilinha
                commands.append(";") # Finalizar comando

                return commands

            # Desenhar a parede esquerda (baseado em seg1_data)
            x_wall_left_start = x_base_cad
            y_current_left = y_base_cad # Começa na base
            wall_width_script = wall_width_cm # Usando cm diretamente para o script

            # Laje Inferior Esquerda
            laje_inf_s1 = float(seg1_data.get('lajes_inf', [0.0])[0])
            commands_li_esq = generate_vertical_segment_pline(x_wall_left_start, y_current_left, wall_width_script, laje_inf_s1, layer_paineis)
            for cmd in commands_li_esq:
                final_script_content += cmd + "\n"
            y_current_left += laje_inf_s1 # Atualiza a posição Y para o próximo segmento

            # Altura 1 Esquerda
            altura1_s1 = float(seg1_data.get('paineis_alturas', [0.0])[0])
            commands_a1_esq = generate_vertical_segment_pline(x_wall_left_start, y_current_left, wall_width_script, altura1_s1, layer_paineis)
            for cmd in commands_a1_esq:
                final_script_content += cmd + "\n"
            y_current_left += altura1_s1 # Atualiza a posição Y

            # Laje Central Esquerda
            laje_central_s1 = float(seg1_data.get('lajes_central_alt', [0.0])[0])
            commands_lc_esq = generate_vertical_segment_pline(x_wall_left_start, y_current_left, wall_width_script, laje_central_s1, layer_paineis)
            for cmd in commands_lc_esq:
                final_script_content += cmd + "\n"
            y_current_left += laje_central_s1 # Atualiza a posição Y

            # Altura 2 Esquerda
            altura2_s1 = float(seg1_data.get('paineis_alturas2', [0.0])[0])
            commands_a2_esq = generate_vertical_segment_pline(x_wall_left_start, y_current_left, wall_width_script, altura2_s1, layer_paineis)
            for cmd in commands_a2_esq:
                final_script_content += cmd + "\n"
            y_current_left += altura2_s1 # Atualiza a posição Y (Altura total da parede esquerda)


            # Desenhar a parede direita (baseado em seg2_data)
            x_wall_right_start = x_base_cad + wall_width_cm + fundo_width_cm
            y_current_right = y_base_cad # Começa na base

            # Laje Inferior Direita
            laje_inf_s2 = float(seg2_data.get('lajes_inf', [0.0])[0])
            commands_li_dir = generate_vertical_segment_pline(x_wall_right_start, y_current_right, wall_width_script, laje_inf_s2, layer_paineis)
            for cmd in commands_li_dir:
                final_script_content += cmd + "\n"
            y_current_right += laje_inf_s2 # Atualiza a posição Y

            # Altura 1 Direita
            altura1_s2 = float(seg2_data.get('paineis_alturas', [0.0])[0])
            commands_a1_dir = generate_vertical_segment_pline(x_wall_right_start, y_current_right, wall_width_script, altura1_s2, layer_paineis)
            for cmd in commands_a1_dir:
                final_script_content += cmd + "\n"
            y_current_right += altura1_s2 # Atualiza a posição Y

            # Laje Central Direita
            laje_central_s2 = float(seg2_data.get('lajes_central_alt', [0.0])[0])
            commands_lc_dir = generate_vertical_segment_pline(x_wall_right_start, y_current_right, wall_width_script, laje_central_s2, layer_paineis)
            for cmd in commands_lc_dir:
                final_script_content += cmd + "\n"
            y_current_right += laje_central_s2 # Atualiza a posição Y

            # Altura 2 Direita
            altura2_s2 = float(seg2_data.get('paineis_alturas2', [0.0])[0])
            commands_a2_dir = generate_vertical_segment_pline(x_wall_right_start, y_current_right, wall_width_script, altura2_s2, layer_paineis)
            for cmd in commands_a2_dir:
                final_script_content += cmd + "\n"
            y_current_right += altura2_s2 # Atualiza a posição Y (Altura total da parede direita)

            # Remover depuração: imprimir o conteúdo final do script
            # print(f"\n--- Conteúdo do Script Final ({nome_combinacao}) ---")
            # print(final_script_content)
            # print("-------------------------------------------\n")

            with open(caminho_arquivo, "w", encoding="utf-16") as f:
                f.write(final_script_content)
            return final_script_content, caminho_arquivo

        except Exception as e:
            traceback.print_exc()
            return None, None

    def _float_safe(self, value):
        """Converte um valor para float de forma segura."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

def gerar_script_teste_combinados(caminho_base):
    """Gera um script de teste para combinados."""
    caminho_ferramentas = os.path.join(caminho_base, 'Ferramentas')
    os.makedirs(caminho_ferramentas, exist_ok=True)
    caminho_arquivo = os.path.join(caminho_ferramentas, 'TESTE_VIGA_TVC.scr')
    
    conteudo_script = [
        "TEXTO DE TESTE DE SCRIPT COMBINADO",
        "LINE 0,0 10,10"
    ]
    
    try:
        with open(caminho_arquivo, 'w') as f:
            for linha in conteudo_script:
                f.write(linha + '\n')
        return True, f"Script de teste gerado com sucesso em: {caminho_arquivo}"
    except Exception as e:
        return False, f"Erro ao gerar script de teste: {e}" 