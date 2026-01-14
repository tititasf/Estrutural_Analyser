import os
import re
import tkinter as tk
from tkinter import messagebox
import json
from datetime import datetime
import traceback
import math

class GeradorScriptViga:
    def __init__(self):
        """Inicializa o gerador de scripts para laterais de viga."""
        self.config = self._carregar_config()
        
    def _carregar_config(self):
        """Carrega as configurações do arquivo config.json."""
        config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
        
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
                "laje": "COTA",
                "sarrafos_verticais_extremidades": "SARR_2.2x7",
                "sarrafos_verticais_grades": "SARR_2.2x3.5"
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
        
    def gerar_script(self, dados, diretorio_saida=""):
        """
        Gera o script SCR para o fundo selecionado na lista.
        
        Args:
            dados: Dicionário com os dados do item selecionado
            diretorio_saida: Diretório onde salvar o script
            
        Returns:
            tuple: (script_text, caminho_arquivo) se sucesso, (script_text, None) se arquivo já existe,
                  (None, None) se erro
        """
        try:
            # Validar diretório de saída
            if not diretorio_saida:
                return None, None
            if not os.path.exists(diretorio_saida):
                os.makedirs(diretorio_saida)
            nome = dados.get('nome', 'SemNome')
            observacoes = dados.get('obs', '')
            numero = dados.get('numero', '')
            base_nome = f"{nome}{'_' + observacoes if observacoes else ''}"
            sufixo = 1
            while True:
                arquivo_nome = f"{base_nome}-{sufixo}.scr"
                caminho_arquivo = os.path.join(diretorio_saida, arquivo_nome)
                if not os.path.exists(caminho_arquivo):
                    break
                sufixo += 1
            script_text = self._gerar_conteudo_script(dados) or ""
            # Adiciona a linha de numeracao no início
            if numero:
                largura_total = dados.get('largura', 0)
                altura_geral_raw = str(dados.get('altura_geral', 0))
                altura_geral = 0
                if '+' in altura_geral_raw:
                    altura_geral = sum(float(p.strip()) for p in altura_geral_raw.split('+') if p.strip())
                else:
                    try:
                        altura_geral = float(altura_geral_raw)
                    except ValueError:
                        altura_geral = 0
                script_text = f"; (numeracao: {numero}, largura: {largura_total}, altura: {altura_geral})\n;\n" + script_text
            with open(caminho_arquivo, "w", encoding="utf-16") as f:
                f.write(script_text)
            return script_text, caminho_arquivo
        except Exception as e:
            traceback.print_exc()
            return None, None
            
    def _gerar_conteudo_script(self, dados):
        """
        Gera o conteúdo do script SCR com base nos dados da viga.
        
        Args:
            dados: Dicionário com os dados do item
            
        Returns:
            str: Conteúdo do script
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

            # Obter ajuste global
            try:
                ajuste_global = float(dados.get('ajuste', 0))
            except Exception:
                ajuste_global = 0

            # Função auxiliar para aplicar ajuste global em Y
            def y_aj(y):
                return y + ajuste_global
            
            # Obter dados do item
            nome = dados.get('nome', 'SemNome')
            observacoes = dados.get('obs', '')
            texto_esquerdo = dados.get('texto_esq', 'Texto Esquerdo')
            texto_direito = dados.get('texto_dir', 'Texto Direito')
            continuacao = dados.get('continuacao', 'Não informado')
            print(f"[INFO] Nome: {nome} | Largura: {dados.get('largura', 0)} | Altura: {dados.get('altura_geral', 0)} | Continuação: {continuacao}")
            
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
            # Priorizar os valores de 'paineis_larguras' (lista) se existirem, depois p1, p2, ..., p6
            paineis = []
            paineis_individuais = []

            # 1. Usar paineis_larguras se existir e for válida
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
                # 2. Se não, usar p1, p2, ..., p6
                for i in range(1, 7):
                    pos_key = f'p{i}'
                    if pos_key in dados and dados[pos_key] and float(dados[pos_key]) > 0:
                        paineis_individuais.append(float(dados[pos_key]))
            
            # Calcular as posições acumuladas para as divisões verticais
            if paineis_individuais:
                pos_acumulada = 0
                for largura in paineis_individuais:
                    pos_acumulada += largura
                    if pos_acumulada <= largura_total:
                        paineis.append(pos_acumulada)
            
            # Se não tiver valores p1-p6, tenta usar o campo 'paineis' se existir
            elif 'paineis' in dados and dados['paineis']:
                pos_acumulada = 0
                for painel in dados['paineis']:
                    if painel and float(painel) > 0:
                        pos_acumulada += float(painel)
                        if pos_acumulada <= largura_total:
                            paineis.append(pos_acumulada)
                            paineis_individuais.append(float(painel))
            
            # Se não houver painéis definidos, criar painéis com divisões automáticas
            # nunca permitindo painéis maiores que 244 unidades
            if not paineis or (paineis and paineis[-1] < largura_total):
                # Limpar painéis existentes se necessário
                if not paineis:
                    paineis = []
                    paineis_individuais = []
                
                # Calcular a parte restante a ser dividida
                largura_restante = largura_total
                if paineis:
                    largura_restante = largura_total - paineis[-1]
                
                # Determinar número de painéis necessários
                tamanho_max_painel = 244  # Tamanho máximo de cada painel
                
                # Calcular quantos painéis são necessários para a largura restante
                num_paineis_restantes = max(1, math.ceil(largura_restante / tamanho_max_painel))
                
                # Distribuir uniformemente o espaço restante
                tamanho_painel = largura_restante / num_paineis_restantes
                
                # Posição inicial para adicionar novos painéis
                pos_inicial = 0
                if paineis:
                    pos_inicial = paineis[-1]
                
                # Adicionar os novos painéis
                for i in range(1, num_paineis_restantes + 1):
                    pos_acumulada = pos_inicial + (tamanho_painel * i)
                    if i == num_paineis_restantes:  # Último painel
                        pos_acumulada = largura_total  # Garantir que chegue exatamente ao final
                    
                    paineis.append(pos_acumulada)
                    
                    # Adicionar também aos painéis individuais
                    if i == 1:
                        # Primeiro painel novo
                        largura_individual = pos_acumulada - pos_inicial
                    else:
                        # Painéis subsequentes
                        largura_individual = pos_acumulada - paineis[-2]
                    
                    paineis_individuais.append(largura_individual)
            
            # Garantir que a largura total está incluída como último ponto
            if paineis and paineis[-1] < largura_total:
                diferenca = largura_total - paineis[-1]
                paineis.append(largura_total)
                paineis_individuais.append(diferenca)
            elif not paineis:
                # Caso especial onde não há divisões - criar pelo menos um painel
                paineis = [largura_total]
                paineis_individuais = [largura_total]
            
            # Configurações iniciais para o desenho
            x_inicial = 12795.5914
            
            # Se for "Último Segmento" (mapeado como "Proxima Parte"), deslocar 20cm para esquerda
            if str(dados.get('continuacao', '')).replace(' ', '').lower() == "proximaparte":
                x_inicial -= 20.0

            # Aplica o ajuste global diretamente na cota Y inicial, afetando TODO o desenho
            y_inicial = 13158.9905 + ajuste_global
            
            # Obter os layers configurados
            # Prioritize layers injected in 'dados' (live config), fallback to self.config (disk)
            layers_cfg = dados.get('layers', {})
            def _l(name):
                return layers_cfg.get(name, self._get_layer(name))

            layer_paineis = _l("paineis")
            layer_sarrafos_verticais = _l("sarrafos_verticais")
            layer_sarrafos_horizontais = _l("sarrafos_horizontais")
            layer_sarrafos_horizontais_pequenos = _l("sarrafos_horizontais_pequenos")
            layer_nome_observacoes = _l("nome_observacoes")
            layer_textos_laterais = _l("textos_laterais")
            layer_cotas = _l("cotas")
            layer_laje = _l("laje")
            layer_sarrafos_vert_ext = _l("sarrafos_verticais_extremidades")
            layer_sarrafos_vert_grades = _l("sarrafos_verticais_grades")
            layer_obstaculo = _l("obstaculo")
            layer_texto_pontaletes = _l("texto_pontaletes")
            
            # Comandos dinâmicos de Hatch
            # Prioritize layers injected in 'dados' (live config), fallback to self.config (disk)
            cmds_cfg = dados.get('comandos', {})
            def _cmd(key, default_val):
                 if key in cmds_cfg: return cmds_cfg[key]
                 if self.config and 'comandos' in self.config and key in self.config['comandos']:
                     return self.config['comandos'][key]
                 return default_val

            cmd_hh = _cmd('HH', 'HH')
            cmd_hhh = _cmd('HHH', 'HHH')
            cmd_hatch_amarelo = _cmd('hatch_amarelo_reap', 'HHH')
            cmd_hhhh = _cmd('HHHH', 'HHHH') # Obstaculo
            
            # Obter o tipo de linha configurado
            tipo_linha_cfg = self._get_tipo_linha().upper()
            
            # Definir comandos para Estrutura (Sempre PLINE) e Detalhes (MLINE ou PLINE)
            cmd_estrutura = "PLINE"
            cmd_detalhe = tipo_linha_cfg if tipo_linha_cfg == "MLINE" else "PLINE"
            
            # Configuração inicial do MLINE se necessário
            setup_mline = ""
            if cmd_detalhe == "MLINE":
                # Configura Justificativa = Zero (0), Escala = 1.0 (ou configuravel)
                # Como SETVAR muitas vezes é bloqueado ou complexo via script simples sem entrelinhas,
                # vamos tentar via comando MLINE direto se possivel, ou variáveis de sistema.
                # CMLJUST: 0=Top, 1=Middle(Zero), 2=Bottom ? Não, AutoCAD Doc: 0=Top, 1=Zero, 2=Bottom.
                # Vamos usar a sequencia de comando do MLINE para garantir.
                # _MLINE -> J (Justification) -> Z (Zero) -> S (Scale) -> 2.2 (ou 1) -> Esc
                # Assume-se escala 1.0 para desenhar na medida real se o MLINE style já tiver offset, 
                # ou escala X se for linha simples que vira dupla.
                # O usuário pediu MLINE para sarrafos. Sarrafos tem geralmente 2.2cm ou 7cm.
                # Se o desenho usa linha simples no centro, o MLINE vai criar a espessura.
                # Vamos definir CMLSCALE 1.0 e Justification Zero por padrão.
                # Usar variáveis de sistema para configurar MLINE sem precisar entrar no comando
                # CMLJUST: 0=Top, 1=Middle(Zero), 2=Bottom
                # User requested LEFT (which corresponds to 0-Top in MLINE terminology if drawn L->R) justification.
                # Actually, in AutoCAD MLINE:
                # Top (0): Offset is above the line.
                # Zero (1): Center.
                # Bottom (2): Below.
                # If we want thickness to "Left" relative to drawing direction? 
                # AutoCAD Justification works on the element's local Y axis. 
                # Let's set 0 (Top) and control direction.
                # Define o estilo inicial como SAR3
                setup_mline = "_CMLSTYLE\nSAR3\n;\n_CMLJUST\n0\n;\n_CMLSCALE\n1.0\n;"
            
            # Verificar modo sarrafeado ou grade
            paineis_tipo1 = dados.get('paineis_tipo1', ["Sarrafeado"]*len(paineis_individuais))
            paineis_tipo2 = dados.get('paineis_tipo2', ["Sarrafeado"]*len(paineis_individuais))
            modo_sarrafeado = (
                dados.get('modo', 'sarr').lower() == 'sarr' and
                all(t1 == "Sarrafeado" for t1 in paineis_tipo1) and
                all(t2 == "Sarrafeado" for t2 in paineis_tipo2)
            )
            
            # Obter altura 1 do painel 1 para deslocar os textos laterais
            altura1_painel1 = 0
            if 'paineis_alturas' in dados and isinstance(dados['paineis_alturas'], list) and len(dados['paineis_alturas']) > 0:
                altura1_painel1 = soma_altura_partes(dados['paineis_alturas'][0])
            # O texto deve ficar na base da viga (y_inicial) - 38cm para ajuste visual
            y_texto_lateral = y_inicial - 38
            
            # Iniciar o script com zoom para a área de desenho
            script = f"""_OSMODE
0
;
_ZOOM
C {x_inicial+largura_total/2},{y_inicial+altura_geral/2} 100
;
-LAYER
S {layer_paineis}

;
{setup_mline}
; Linha lateral esquerda
_ZOOM
C {x_inicial},{y_inicial+altura_geral/2} 5
;
_{cmd_estrutura}
{x_inicial},{y_inicial}
{x_inicial},{y_inicial+altura_geral}

;
; Linha lateral direita
_ZOOM
C {x_inicial+largura_total},{y_inicial+altura_geral/2} 5
;
_{cmd_estrutura}
{x_inicial+largura_total},{y_inicial}
{x_inicial+largura_total},{y_inicial+altura_geral}

;
-LAYER
S {layer_textos_laterais}

;
"""
            # Definir estilo de texto (standart) antes de criar textos
            script += ";\n-style\nstandart\n\n0\n\n\n\n\n\n;\n"
            
            # Adicionar textos laterais apenas se não estiverem vazios
            if texto_esquerdo.strip():
                script += f"_ZOOM\nC {x_inicial-5},{y_texto_lateral} 5\n;\n_TEXT\n{x_inicial-5},{y_texto_lateral}\n8\n90\n{texto_esquerdo}\n;\n"
            if texto_direito.strip():
                script += f"_ZOOM\nC {x_inicial+largura_total+12},{y_texto_lateral} 5\n;\n_TEXT\n{x_inicial+largura_total+12},{y_texto_lateral}\n8\n90\n{texto_direito}\n;\n"
            script += f"-LAYER\nS {layer_sarrafos_vert_ext}\n\n;\n"
            # Adicionar sarrafos verticais nas extremidades
            script += f"""; Sarrafo Esquerdo
_ZOOM
C {x_inicial+7},{y_inicial+altura_geral/2} 5
;
"""
            if cmd_detalhe == "MLINE":
                script += "_CMLSCALE\n7.0\n;\n"
                # MLINE Left: Move 7cm Left (to x_inicial). Draw Down (Thickness Right/Inside).
                script += f"""_{cmd_detalhe}
{x_inicial+7},{y_inicial+altura_geral}
{x_inicial+7},{y_inicial}

;
"""
            else:
                script += f"""_{cmd_detalhe}
{x_inicial+7},{y_inicial}
{x_inicial+7},{y_inicial+altura_geral}

;
"""

            script += f""";
; Sarrafo Direito
_ZOOM
C {x_inicial+largura_total-7},{y_inicial+altura_geral/2} 5
;
"""
            if cmd_detalhe == "MLINE":
                script += "_CMLSCALE\n7.0\n;\n"
                # MLINE Right: Move 7cm Right (to x_end). Draw Up (Thickness Left/Inside).
                # x_end = x_inicial + largura_total
                script += f"""_{cmd_detalhe}
{x_inicial+largura_total-7},{y_inicial}
{x_inicial+largura_total-7},{y_inicial+altura_geral}

;
"""
            else:
                script += f"""_{cmd_detalhe}
{x_inicial+largura_total-7},{y_inicial+altura_geral}
{x_inicial+largura_total-7},{y_inicial}

;
"""
            script += f"""-LAYER
S {layer_paineis}

;
"""
            # Adicionar linhas verticais para divisão de painéis (painéis já estão em valores acumulados)
            for i, pos in enumerate(paineis):
                if pos > 0 and pos < largura_total:
                    script += f"""; Linha Painel {i+1} (vertical)
_ZOOM
C {x_inicial+pos},{y_inicial+altura_geral/2} 5
;
_{cmd_estrutura}
{x_inicial+pos},{y_inicial}
{x_inicial+pos},{y_inicial+altura_geral}

;
"""
            script += "-LAYER\nS " + layer_paineis + "\n\n;"
            # Garantir que pelo menos as linhas horizontais principais (moldura) sejam desenhadas
            if not paineis or len(paineis) == 0 or (len(paineis) == 1 and paineis[0] >= largura_total):
                # Se não houver painéis definidos, criar a moldura principal
                script += f"""; Linha horizontal superior
_ZOOM
C {x_inicial+largura_total/2},{y_inicial+altura_geral} 5
;
_{cmd_estrutura}
{x_inicial},{y_inicial+altura_geral}
{x_inicial+largura_total},{y_inicial+altura_geral}

;
; Linha horizontal inferior
_ZOOM
C {x_inicial+largura_total/2},{y_inicial} 5
;
_{cmd_estrutura}
{x_inicial},{y_inicial}
{x_inicial+largura_total},{y_inicial}

;
"""
            else:
                # Adicionar linhas horizontais para os painéis
                pos_anterior = 0
                for i, pos in enumerate(paineis):
                    if i == 0 and pos > 0:
                        # Linha horizontal superior do primeiro painel
                        script += f"""; Linha horizontal superior do Painel {i+1}
_ZOOM
C {(x_inicial+pos)/2},{y_inicial+altura_geral} 5
;
_{cmd_estrutura}
{x_inicial},{y_inicial+altura_geral}
{x_inicial+pos},{y_inicial+altura_geral}

;
; Linha horizontal inferior do Painel {i+1}
_ZOOM
C {(x_inicial+pos)/2},{y_inicial} 5
;
_{cmd_estrutura}
{x_inicial},{y_inicial}
{x_inicial+pos},{y_inicial}

;
"""
                    elif pos > pos_anterior:
                        # Linhas horizontais dos painéis intermediários
                        script += f"""; Linha horizontal superior do Painel {i+1}
_ZOOM
C {(x_inicial+pos_anterior+x_inicial+pos)/2},{y_inicial+altura_geral} 5
;
_{cmd_estrutura}
{x_inicial+pos_anterior},{y_inicial+altura_geral}
{x_inicial+pos},{y_inicial+altura_geral}

;
; Linha horizontal inferior do Painel {i+1}
_ZOOM
C {(x_inicial+pos_anterior+x_inicial+pos)/2},{y_inicial} 5
;
_{cmd_estrutura}
{x_inicial+pos_anterior},{y_inicial}
{x_inicial+pos},{y_inicial}

;
"""
                    pos_anterior = pos
            
            # Adicionar lajes por painel (superior, inferior e central)
            lajes_sup = dados.get('lajes_sup', [0]*len(paineis_individuais))
            lajes_inf = dados.get('lajes_inf', [0]*len(paineis_individuais))
            lajes_central = dados.get('lajes_central_alt', [0]*len(paineis_individuais))
            
            # Geração robusta e didática por painel
            x_painel = x_inicial
            for i, largura_painel in enumerate(paineis_individuais):
                # --- Altura 1 ---
                altura1_raw = str(dados.get('paineis_alturas', [0]*len(paineis_individuais))[i]) if 'paineis_alturas' in dados else '0'
                altura1_partes = [float(p.strip()) for p in altura1_raw.split('+') if p.strip()]
                altura1 = soma_altura_partes(altura1_raw)
                # --- Altura 2 ---
                altura2_raw = str(dados.get('paineis_alturas2', [0]*len(paineis_individuais))[i]) if 'paineis_alturas2' in dados else '0'
                altura2_partes = [float(p.strip()) for p in altura2_raw.split('+') if p.strip()]
                altura2 = soma_altura_partes(altura2_raw)
                laje_sup = lajes_sup[i] if i < len(lajes_sup) else 0
                laje_inf = lajes_inf[i] if i < len(lajes_inf) else 0
                laje_central = lajes_central[i] if i < len(lajes_central) else 0
                
                script += f""";=====================================================================
; PAINEL {i+1}
; =====================================================================
"""
                # Painel Altura 1
                script += f"""; ===== PAINEL {i+1} ALTURA 1 =====
"""
                if altura1 > 0:
                    y_base_alt1 = y_inicial
                    y_topo_alt1 = y_inicial + altura1
                    script += f"""-LAYER
S {layer_paineis}

;
_ZOOM
C {(x_painel + x_painel+largura_painel)/2},{(y_base_alt1 + y_topo_alt1)/2} 5
;
_{cmd_estrutura}
{x_painel},{y_base_alt1}
{x_painel+largura_painel},{y_base_alt1}
{x_painel+largura_painel},{y_topo_alt1}
{x_painel},{y_topo_alt1}
{x_painel},{y_base_alt1}

;
"""
                    # Se altura1 tem mais de um segmento, desenhar linha horizontal extra
                    if len(altura1_partes) > 1:
                        y_extra = y_inicial + altura1_partes[0]
                        script += f"""; Linha extra de divisão de Altura 1 (segmento)
_ZOOM
C {(x_painel + x_painel+largura_painel)/2},{y_extra} 5
;
_{cmd_estrutura}
{x_painel},{y_extra}
{x_painel+largura_painel},{y_extra}

;
"""
                else:
                    script += f"""; Não há painel de Altura 1 neste painel
"""
                
                # --- HATCH GENERATION ---
                # Realizar o hatch logo após o retângulo estrutural, antes de sarrafos/grades
                hatch_types = dados.get('paineis_hatch', [])
                if i < len(hatch_types):
                    h_type = hatch_types[i]
                    if h_type:
                        # Centro do painel (considerando A1 + Laje Central + A2)
                        h_total_panel = altura1 + laje_central + altura2
                        cx = x_painel + largura_painel / 2
                        cy = y_inicial + h_total_panel / 2
                        
                        cx = x_painel + largura_painel / 2
                        cy = y_inicial + h_total_panel / 2
                        
                        cmd = cmd_hh if h_type == 'green' else cmd_hatch_amarelo
                        script += f"; Hatch {h_type}\n{cmd}\n{cx:.3f},{cy:.3f}\n;\n"

                # --- BLOCK NUMBERING GENERATION ---
                numeracao_cfg = dados.get('numeracao_blocos', {})
                if numeracao_cfg.get('ativo', False):
                    start_index = dados.get('indice_inicial_painel', 0)
                    current_num = start_index + i + 1
                    cmd_bloco = numeracao_cfg.get('comandos', {}).get(str(current_num), '')
                    
                    if cmd_bloco:
                        # Center of the panel
                        h_total_panel = altura1 + laje_central + altura2
                        # Fallback se h_total for 0 (caso raro)
                        if h_total_panel <= 0: h_total_panel = altura_geral
                        
                        cx = x_painel + largura_painel / 2
                        cy = y_inicial + h_total_panel / 2
                        
                        script += f"; Inserção do Bloco Numérico {current_num} ({cmd_bloco})\n"
                        script += f"_INSERT\n{cmd_bloco}\n{cx:.3f},{cy:.3f}\n\n\n;\n"
                        
                        # --- TEXTO PONTALETES (Se Grade) ---
                        # Insere texto informativo 20 unidades abaixo do bloco de numeração
                        tipo1 = dados.get('paineis_tipo1', ["Sarrafeado"]*len(paineis_individuais))[i] if 'paineis_tipo1' in dados else "Sarrafeado"
                        # Verifica se é grade (pode checar tipo2 tbm se necessário, mas user disse "quando modo grade um painel")
                        is_grade = (tipo1 == "Grade")
                        
                        if is_grade and largura_painel >= 60:
                            txt_pont = ""
                            if 60 <= largura_painel < 90:
                                txt_pont = "3-%%189PONT."
                            elif 90 <= largura_painel < 120:
                                txt_pont = "4-%%189PONT."
                            elif 120 <= largura_painel < 150:
                                txt_pont = "5-%%189PONT."
                            elif 150 <= largura_painel < 180:
                                txt_pont = "6-%%189PONT."
                            elif 180 <= largura_painel < 210:
                                txt_pont = "7-%%189PONT."
                            elif 210 <= largura_painel <= 244:
                                txt_pont = "8-%%189PONT."
                            
                            if txt_pont:
                                y_txt_pont = cy - 20
                                script += f"; Texto Pontaletes\n-LAYER\nS {layer_texto_pontaletes}\n\n;\n_TEXT\nJ\nMC\n{cx:.3f},{y_txt_pont:.3f}\n8\n0\n{txt_pont}\n;\n"

                # Sarrafos Altura 1
                script += f"""; ===== SARRAFOS/GRADES ALTURA 1 PAINEL {i+1} =====\n"""
                tipo1 = dados.get('paineis_tipo1', ["Sarrafeado"]*len(paineis_individuais))[i] if 'paineis_tipo1' in dados else "Sarrafeado"
                if tipo1 == "Grade":
                    # Lógica de grade para Altura 1 (GRA)
                    altura_grade = 2.2
                    largura_vert = 3.5
                    # Subtrai 2.2 da altura da grade vinda da interface
                    altura_vert = float(dados.get('paineis_grade_altura1', [7.0]*len(paineis_individuais))[i]) - 2.2
                    y_grade_top = y_inicial + altura1 - 2.2  # horizontal
                    y_grade_bot = y_grade_top + altura_grade
                    x_grade_ini = x_painel + (15 if i == 0 else 0)
                    x_grade_fim = x_painel + largura_painel - (15 if i == len(paineis_individuais)-1 else 0)
                    
                    # Retângulo horizontal da grade (layer horizontal)
                    script += f"-LAYER\nS {layer_sarrafos_horizontais}\n\n;\n"
                    if cmd_detalhe == "MLINE":
                         # MLINE: Justification 0 (Top).
                         # Grade Horizontal: Top Edge is y_grade_top.
                         # We want thickness Down.
                         # Vector L->R: Left is Up.
                         # Vector R->L: Left is Down.
                         # So Draw R -> L.
                        script += f"_CMLSCALE\n2.2\n;\n_{cmd_detalhe}\n{x_grade_fim},{y_grade_top}\n{x_grade_ini},{y_grade_top}\n\n;\n"
                    else:
                        # PLINE: Retângulo
                        script += f"_{cmd_detalhe}\n{x_grade_ini},{y_grade_top}\n{x_grade_fim},{y_grade_top}\n{x_grade_fim},{y_grade_bot}\n{x_grade_ini},{y_grade_bot}\nC\n;\n"
                    
                    # Verticais para BAIXO (y decrescente) (layer vertical)
                    script += f"-LAYER\nS {layer_sarrafos_vert_grades}\n\n;\n"
                    
                    # Vertical esquerda
                    if cmd_detalhe == "MLINE":
                        # Troca para estilo de 3.5cm centro
                        script += "_CMLSTYLE\nMEIOPONT\n;\n"
                        # x_grade_ini is Left Edge.
                        # We want thickness Right.
                        # Justification Left (0). Top->Bottom vector. Left is Right.
                        # User requested shift +3.5cm Right.
                        x_mline = x_grade_ini + 3.5
                        script += f"_CMLSCALE\n7.0\n;\n_{cmd_detalhe}\n{x_mline},{y_grade_bot-2.2}\n{x_mline},{y_grade_bot-2.2-altura_vert}\n\n;\n"
                        # Volta para o estilo padrão de 7cm
                        script += "_CMLSTYLE\nSAR3\n;\n"
                    else:
                        script += f"_{cmd_detalhe}\n{x_grade_ini},{y_grade_bot-2.2}\n{x_grade_ini+largura_vert},{y_grade_bot-2.2}\n{x_grade_ini+largura_vert},{y_grade_bot-2.2-altura_vert}\n{x_grade_ini},{y_grade_bot-2.2-altura_vert}\nC\n;\n"
                    
                    # Vertical direita
                    x_vert_dir = x_painel + largura_painel - largura_vert
                    if i == len(paineis_individuais)-1:
                        x_vert_dir = x_painel + largura_painel - 15 - largura_vert
                    
                    if cmd_detalhe == "MLINE":
                        # Troca para estilo de 3.5cm centro
                        script += "_CMLSTYLE\nMEIOPONT\n;\n"
                        # x_vert_dir is Left Edge of the vertical sarrafo.
                        # We want thickness Right.
                        # Vector Top->Bottom.
                        # User requested shift +3.5cm Right.
                        x_mline = x_vert_dir + 3.5
                        script += f"_CMLSCALE\n7.0\n;\n_{cmd_detalhe}\n{x_mline},{y_grade_bot-2.2}\n{x_mline},{y_grade_bot-2.2-altura_vert}\n\n;\n"
                        # Volta para o estilo padrão de 7cm
                        script += "_CMLSTYLE\nSAR3\n;\n"
                    else:
                        script += f"_{cmd_detalhe}\n{x_vert_dir},{y_grade_bot-2.2}\n{x_vert_dir+largura_vert},{y_grade_bot-2.2}\n{x_vert_dir+largura_vert},{y_grade_bot-2.2-altura_vert}\n{x_vert_dir},{y_grade_bot-2.2-altura_vert}\nC\n;\n"
                else:
                    # Desenhar sarrafos horizontais para Altura 1 (Sarrafeado)
                    if altura1 > 0:
                        layer_sarrafos_horizontais = self._get_layer("sarrafos_horizontais")
                        layer_sarrafos_horizontais_pequenos = self._get_layer("sarrafos_horizontais_pequenos")
                        def get_linha_specs(altura):
                            if altura < 15:
                                return layer_sarrafos_horizontais_pequenos, [(5, "baixo"), (5, "cima")]
                            elif altura < 30:
                                return layer_sarrafos_horizontais, [(7, "baixo"), (7, "cima")]
                            elif altura < 80:
                                return layer_sarrafos_horizontais, [(7, "baixo"), (7, "cima"), (3.5, "centro_cima"), (3.5, "centro_baixo")]
                            else:
                                return layer_sarrafos_horizontais, [
                                    (7, "baixo"), (7, "cima"),
                                    (3.5, "centro_cima"), (3.5, "centro_baixo"),
                                    (3.5, "quarto_inf_cima"), (3.5, "quarto_inf_baixo"),
                                    (3.5, "quarto_sup_cima"), (3.5, "quarto_sup_baixo")
                                ]
                        layer_horiz, posicoes_horiz = get_linha_specs(altura1)
                        y_base_alt1 = y_inicial
                        for pos_spec in posicoes_horiz:
                            tipo, posicao = pos_spec
                            
                            # Filtro MLINE: Mantém apenas uma linha (topo) por sarrafo
                            if cmd_detalhe == "MLINE" and "_baixo" in posicao:
                                continue

                            # Calcular posição Y
                            if posicao == "baixo":
                                y_pos = y_base_alt1 + 7
                            elif posicao == "cima":
                                # Em MLINE, desenhamos no topo absoluto para projetar para baixo
                                y_pos = y_base_alt1 + altura1 - (0 if cmd_detalhe == "MLINE" else 7)
                            elif "centro_cima" in posicao:
                                y_pos = y_base_alt1 + (altura1/2) + tipo
                            elif "centro_baixo" in posicao:
                                y_pos = y_base_alt1 + (altura1/2) - tipo
                            elif "quarto_inf_cima" in posicao:
                                y_pos = y_base_alt1 + (altura1/4) + tipo
                            elif "quarto_inf_baixo" in posicao:
                                y_pos = y_base_alt1 + (altura1/4) - tipo
                            elif "quarto_sup_cima" in posicao:
                                y_pos = y_base_alt1 + (3*altura1/4) + tipo
                            elif "quarto_sup_baixo" in posicao:
                                y_pos = y_base_alt1 + (3*altura1/4) - tipo
                            else:
                                y_pos = y_base_alt1

                            # Ajuste do recuo de 7cm no primeiro e último painel
                            x_ini = x_painel
                            x_fim = x_painel + largura_painel
                            if i == 0:
                                x_ini += 7
                            if i == len(paineis_individuais)-1:
                                x_fim -= 7
                            
                            draw_reversed = False
                            cml_scale_cmd = ""
                            if cmd_detalhe == "MLINE":
                                scale = 7.0
                                if "pequenos" in layer_horiz:
                                    scale = 5.0
                                cml_scale_cmd = f"_CMLSCALE\n{scale}\n;\n"
                                # Direção L->R + CMLJUST 0 = Espessura para BAIXO
                                draw_reversed = False 
                            else:
                                # Modo PLINE: Mantém direção original (cima = R->L)
                                if "cima" in posicao:
                                    draw_reversed = True

                            sx, ex = x_ini, x_fim
                            if draw_reversed:
                                sx, ex = x_fim, x_ini
                                
                            script += f"-LAYER\nS {layer_horiz}\n\n;\n_ZOOM\nC {(x_ini + x_fim)/2},{y_pos} 5\n;\n{cml_scale_cmd}_{cmd_detalhe}\n{sx},{y_pos}\n{ex},{y_pos}\n\n;\n"
                    else:
                        script += f"; Não há sarrafos de Altura 1 neste painel\n"
                # Painel Altura 2
                script += f"""; ===== PAINEL {i+1} ALTURA 2 =====\n"""
                if altura2 > 0:
                    y_base_alt2 = y_inicial + altura1
                    if laje_central > 0:
                        y_base_alt2 += laje_central
                    y_topo_alt2 = y_base_alt2 + altura2
                    script += f"""-LAYER\nS {layer_paineis}\n\n;\n_ZOOM\nC {(x_painel + x_painel+largura_painel)/2},{(y_base_alt2 + y_topo_alt2)/2} 5\n;\n_{cmd_estrutura}\n{x_painel},{y_base_alt2}\n{x_painel+largura_painel},{y_base_alt2}\n{x_painel+largura_painel},{y_topo_alt2}\n{x_painel},{y_topo_alt2}\n{x_painel},{y_base_alt2}\n\n;\n"""
                    if len(altura2_partes) > 1:
                        y_extra2 = y_base_alt2 + altura2_partes[0]
                        script += f"""; Linha extra de divisão de Altura 2 (segmento)
_ZOOM
C {(x_painel + x_painel+largura_painel)/2},{y_extra2} 5
;
_{cmd_estrutura}
{x_painel},{y_extra2}
{x_painel+largura_painel},{y_extra2}

;
"""
                else:
                    script += f"""; Não há painel de Altura 2 neste painel\n"""
                # Sarrafos Altura 2
                script += f"""; ===== SARRAFOS/GRADES ALTURA 2 PAINEL {i+1} =====\n"""
                tipo2 = dados.get('paineis_tipo2', ["Sarrafeado"]*len(paineis_individuais))[i] if 'paineis_tipo2' in dados else "Sarrafeado"
                if tipo2 == "Grade" and altura2 > 0:
                    # Lógica de grade para Altura 2 (GRA)
                    altura_grade2 = 2.2
                    largura_vert2 = 3.5
                    # Subtrai 2.2 da altura da grade vinda da interface
                    altura_vert2 = float(dados.get('paineis_grade_altura2', [7.0]*len(paineis_individuais))[i]) - 2.2
                    y_base_alt2 = y_inicial + altura1
                    if laje_central > 0:
                        y_base_alt2 += laje_central
                    y_grade2_top = y_base_alt2 + altura2 - 2.2  # horizontal
                    y_grade2_bot = y_grade2_top + altura_grade2
                    x_grade2_ini = x_painel + (15 if i == 0 else 0)
                    x_grade2_fim = x_painel + largura_painel - (15 if i == len(paineis_individuais)-1 else 0)
                    
                    # Retângulo horizontal da grade (layer horizontal)
                    script += f"-LAYER\nS {layer_sarrafos_horizontais}\n\n;\n"
                    if cmd_detalhe == "MLINE":
                         # MLINE: Justification 0 (Top).
                         # Grade Horizontal 2: y_grade2_top is Top Edge. Thickness Down.
                         # Draw R -> L.
                        script += f"_CMLSCALE\n2.2\n;\n_{cmd_detalhe}\n{x_grade2_fim},{y_grade2_top}\n{x_grade2_ini},{y_grade2_top}\n\n;\n"
                    else:
                        script += f"_{cmd_detalhe}\n{x_grade2_ini},{y_grade2_top}\n{x_grade2_fim},{y_grade2_top}\n{x_grade2_fim},{y_grade2_bot}\n{x_grade2_ini},{y_grade2_bot}\nC\n;\n"
                        
                    # Verticais para BAIXO (y decrescente) (layer vertical)
                    script += f"-LAYER\nS {layer_sarrafos_vert_grades}\n\n;\n"
                    
                    # Vertical esquerda
                    if cmd_detalhe == "MLINE":
                        # Troca para estilo de 3.5cm centro
                        script += "_CMLSTYLE\nMEIOPONT\n;\n"
                        # x_grade2_ini Left Edge. Thickness Right.
                        # Draw Top -> Bottom.
                        # Shift +3.5cm Right.
                        x_mline = x_grade2_ini + 3.5
                        script += f"_CMLSCALE\n7.0\n;\n_{cmd_detalhe}\n{x_mline},{y_grade2_bot - 2.2}\n{x_mline},{y_grade2_bot - 2.2-altura_vert2}\n\n;\n"
                        # Volta para o estilo padrão de 7cm
                        script += "_CMLSTYLE\nSAR3\n;\n"
                    else:
                        script += f"_{cmd_detalhe}\n{x_grade2_ini},{y_grade2_bot - 2.2}\n{x_grade2_ini+largura_vert2},{y_grade2_bot - 2.2}\n{x_grade2_ini+largura_vert2},{y_grade2_bot - 2.2-altura_vert2}\n{x_grade2_ini},{y_grade2_bot - 2.2-altura_vert2}\nC\n;\n"
                    
                    # Vertical direita
                    x_vert2_dir = x_painel + largura_painel - largura_vert2
                    if i == len(paineis_individuais)-1:
                        x_vert2_dir = x_painel + largura_painel - 15 - largura_vert2
                    
                    if cmd_detalhe == "MLINE":
                        # Troca para estilo de 3.5cm centro
                        script += "_CMLSTYLE\nMEIOPONT\n;\n"
                        # x_vert2_dir Left Edge. Thickness Right.
                        # Draw Top -> Bottom.
                        # Shift +3.5cm Right.
                        x_mline = x_vert2_dir + 3.5
                        script += f"_CMLSCALE\n7.0\n;\n_{cmd_detalhe}\n{x_mline},{y_grade2_bot - 2.2}\n{x_mline},{y_grade2_bot - 2.2-altura_vert2}\n\n;\n"
                        # Volta para o estilo padrão de 7cm
                        script += "_CMLSTYLE\nSAR3\n;\n"
                    else:
                        script += f"_{cmd_detalhe}\n{x_vert2_dir},{y_grade2_bot - 2.2}\n{x_vert2_dir+largura_vert2},{y_grade2_bot - 2.2}\n{x_vert2_dir+largura_vert2},{y_grade2_bot - 2.2-altura_vert2}\n{x_vert2_dir},{y_grade2_bot - 2.2-altura_vert2}\nC\n;\n"
                else:
                    if altura2 > 0:
                        layer_sarrafos_horizontais = self._get_layer("sarrafos_horizontais")
                        layer_sarrafos_horizontais_pequenos = self._get_layer("sarrafos_horizontais_pequenos")
                        layer_sarrafos_verticais = self._get_layer("sarrafos_verticais")
                        # Função para determinar os sarrafos horizontais com base na altura (usada em Altura 1, Altura 2 e modo sarrafeado)
                        def get_linha_specs(altura):
                            if altura < 15:
                                return layer_sarrafos_horizontais_pequenos, [(5, "baixo"), (5, "cima")]
                            elif altura < 30:
                                return layer_sarrafos_horizontais, [(7, "baixo"), (7, "cima")]
                            elif altura < 80:
                                return layer_sarrafos_horizontais, [(7, "baixo"), (7, "cima"), (3.5, "centro_cima"), (3.5, "centro_baixo")]
                            else:
                                return layer_sarrafos_horizontais, [
                                    (7, "baixo"), (7, "cima"),
                                    (3.5, "centro_cima"), (3.5, "centro_baixo"),
                                    (3.5, "quarto_inf_cima"), (3.5, "quarto_inf_baixo"),
                                    (3.5, "quarto_sup_cima"), (3.5, "quarto_sup_baixo")
                                ]
                        layer_horiz, posicoes_horiz = get_linha_specs(altura2)
                        y_base_alt2 = y_inicial + altura1
                        if laje_central > 0:
                            y_base_alt2 += laje_central
                        for pos_spec in posicoes_horiz:
                            tipo, posicao = pos_spec
                            
                            # Filtro MLINE: Mantém apenas uma linha (topo) por sarrafo
                            if cmd_detalhe == "MLINE" and "_baixo" in posicao:
                                continue

                            # Calcular posição Y
                            if posicao == "baixo":
                                y_pos = y_base_alt2 + 7
                            elif posicao == "cima":
                                # Em MLINE, desenhamos no topo absoluto para projetar para baixo
                                y_pos = y_base_alt2 + altura2 - (0 if cmd_detalhe == "MLINE" else 7)
                            elif "centro_cima" in posicao:
                                y_pos = y_base_alt2 + (altura2/2) + tipo
                            elif "centro_baixo" in posicao:
                                y_pos = y_base_alt2 + (altura2/2) - tipo
                            elif "quarto_inf_cima" in posicao:
                                y_pos = y_base_alt2 + (altura2/4) + tipo
                            elif "quarto_inf_baixo" in posicao:
                                y_pos = y_base_alt2 + (altura2/4) - tipo
                            elif "quarto_sup_cima" in posicao:
                                y_pos = y_base_alt2 + (3*altura2/4) + tipo
                            elif "quarto_sup_baixo" in posicao:
                                y_pos = y_base_alt2 + (3*altura2/4) - tipo
                            else:
                                y_pos = y_base_alt2

                            # Ajuste do recuo de 7cm no primeiro e último painel
                            x_ini = x_painel
                            x_fim = x_painel + largura_painel
                            if i == 0:
                                x_ini += 7
                            if i == len(paineis_individuais)-1:
                                x_fim -= 7
                            
                            draw_reversed = False
                            cml_scale_cmd = ""
                            if cmd_detalhe == "MLINE":
                                scale = 7.0
                                if "pequenos" in layer_horiz:
                                    scale = 5.0
                                cml_scale_cmd = f"_CMLSCALE\n{scale}\n;\n"
                                # Direção L->R + CMLJUST 0 = Espessura para BAIXO
                                draw_reversed = False 
                            else:
                                # Modo PLINE: Mantém direção original (cima = R->L)
                                if "cima" in posicao:
                                    draw_reversed = True

                            sx, ex = x_ini, x_fim
                            if draw_reversed:
                                sx, ex = x_fim, x_ini
                            
                            script += f"-LAYER\nS {layer_horiz}\n\n;\n_ZOOM\nC {(x_ini + x_fim)/2},{y_pos} 5\n;\n{cml_scale_cmd}_{cmd_detalhe}\n{sx},{y_pos}\n{ex},{y_pos}\n\n;\n"
                        # Sarrafos verticais Altura 2 - apenas no primeiro e último painel válido
                        if i == 0:
                            # Sarrafo esquerdo
                            script += f"""-LAYER\nS {layer_sarrafos_verticais}\n\n;\n_ZOOM\nC {x_painel+7},{(y_base_alt2 + y_base_alt2+altura2)/2} 5\n;\n_{cmd_detalhe}\n{x_painel+7},{y_base_alt2}\n{x_painel+7},{y_base_alt2+altura2}\n\n;\n"""
                        if i == len(paineis_individuais)-1:
                            # Sarrafo direito
                            script += f"""-LAYER\nS {layer_sarrafos_verticais}\n\n;\n_ZOOM\nC {x_painel+largura_painel-7},{(y_base_alt2 + y_base_alt2+altura2)/2} 5\n;\n_{cmd_detalhe}\n{x_painel+largura_painel-7},{y_base_alt2}\n{x_painel+largura_painel-7},{y_base_alt2+altura2}\n\n;\n"""
                        if altura2 >= 80:
                            x_quarto1 = x_painel + largura_painel/4
                            x_quarto3 = x_painel + 3*largura_painel/4
                            script += f"""_ZOOM\nC {x_quarto1},{(y_base_alt2 + y_base_alt2+altura2)/2} 5\n;\n_{cmd_detalhe}\n{x_quarto1},{y_base_alt2}\n{x_quarto1},{y_base_alt2+altura2}\n\n;\n_ZOOM\nC {x_quarto3},{(y_base_alt2 + y_base_alt2+altura2)/2} 5\n;\n_{cmd_detalhe}\n{x_quarto3},{y_base_alt2}\n{x_quarto3},{y_base_alt2+altura2}\n\n;\n"""
                    else:
                        script += f"; Não há sarrafos de Altura 2 neste painel\n"
                # Lajes
                script += f"""; ===== LAJES PAINEL {i+1} =====
"""
                # Desenhar laje superior, se houver
                if laje_sup > 0:
                    y_laje_sup = y_inicial + altura1 + laje_central + altura2
                    script += f"""; Laje Superior\n-LAYER
S {layer_laje}

;
_ZOOM
C {(x_painel + x_painel+largura_painel)/2},{y_laje_sup + laje_sup/2} 5
;
_{cmd_estrutura}
{x_painel},{y_laje_sup}
{x_painel+largura_painel},{y_laje_sup}
{x_painel+largura_painel},{y_laje_sup + laje_sup}
{x_painel},{y_laje_sup + laje_sup}
{x_painel},{y_laje_sup}

;
{cmd_hhh}
{x_painel + largura_painel/2},{y_laje_sup + laje_sup/2}
;
"""
                else:
                    script += f"""; Não há laje superior neste painel\n"""
                # Desenhar laje inferior, se houver
                if laje_inf > 0:
                    y_laje_inf = y_inicial - laje_inf
                    script += f"""; Laje Inferior\n-LAYER
S {layer_laje}

;
_ZOOM
C {(x_painel + x_painel+largura_painel)/2},{y_laje_inf + laje_inf/2} 5
;
_{cmd_estrutura}
{x_painel},{y_laje_inf}
{x_painel+largura_painel},{y_laje_inf}
{x_painel+largura_painel},{y_laje_inf + laje_inf}
{x_painel},{y_laje_inf + laje_inf}
{x_painel},{y_laje_inf}

;
{cmd_hhh}
{x_painel + largura_painel/2},{y_laje_inf + laje_inf/2}
;
"""
                else:
                    script += f"""; Não há laje inferior neste painel\n"""
                # Desenhar laje central, se houver
                if laje_central > 0:
                    y_laje_central = y_inicial + altura1
                    script += f"""; Laje Central\n-LAYER
S {layer_laje}

;
_ZOOM
C {(x_painel + x_painel+largura_painel)/2},{y_laje_central + laje_central/2} 5
;
_{cmd_estrutura}
{x_painel},{y_laje_central}
{x_painel+largura_painel},{y_laje_central}
{x_painel+largura_painel},{y_laje_central + laje_central}
{x_painel},{y_laje_central + laje_central}
{x_painel},{y_laje_central}

;
{cmd_hhh}
{x_painel + largura_painel/2},{y_laje_central + laje_central/2}
;
"""
                else:
                    script += f"""; Não há laje central neste painel\n"""
                
                x_painel += largura_painel
            
            # ===================== COTAS HORIZONTAIS =====================
            script += f"""-LAYER
S {layer_cotas}

;
"""
            # Verificar a maior laje inferior para ajustar a posição das cotas horizontais
            maior_laje_inf = max([l for l in lajes_inf if l > 0] or [0])
            y_cota_base = y_inicial - maior_laje_inf
            # Cotas dos painéis individuais (embaixo do fundo, ajustadas)
            posicoes_paineis = [0] + paineis
            for i in range(len(paineis_individuais)):
                x_ini = x_inicial + posicoes_paineis[i]
                x_fim = x_inicial + posicoes_paineis[i+1]
                y_cota = y_cota_base - 20
                x_texto = (x_ini + x_fim) / 2
                script += f"""; Cota horizontal painel {i+1}\n_DIMLINEAR\n{x_ini},{y_cota_base}\n{x_fim},{y_cota_base}\n{x_texto},{y_cota}\n;\n"""
            # Cota total horizontal (texto a 40cm abaixo, ajustada)
            script += f"""; Cota horizontal total\n_DIMLINEAR\n{x_inicial},{y_cota_base}\n{x_inicial+largura_total},{y_cota_base}\n{x_inicial+largura_total/2},{y_cota_base-40}\n;\n"""

            # ===================== COTAS VERTICAIS (EXTREMA DIREITA) =====================
            continuacao = str(dados.get('continuacao', '')).replace(' ', '').lower()
            if continuacao not in ['obstaculo', 'vigacontinuacao']:
                x_direita = x_inicial + largura_total
                for i in range(len(paineis_individuais)):
                    # --- Cotas principais (originais) ---
                    altura1 = soma_altura_partes(dados.get('paineis_alturas', [0]*len(paineis_individuais))[i]) if 'paineis_alturas' in dados else 0
                    altura2 = soma_altura_partes(dados.get('paineis_alturas2', [0]*len(paineis_individuais))[i]) if 'paineis_alturas2' in dados else 0
                    laje_inf = float(dados.get('lajes_inf', [0]*len(paineis_individuais))[i]) if 'lajes_inf' in dados else 0
                    laje_central = float(dados.get('lajes_central_alt', [0]*len(paineis_individuais))[i]) if 'lajes_central_alt' in dados else 0
                    laje_sup = float(dados.get('lajes_sup', [0]*len(paineis_individuais))[i]) if 'lajes_sup' in dados else 0
                    y_base = y_inicial
                    # Cota vertical altura 1
                    if altura1 > 0:
                        y_ini = y_base
                        y_fim = y_base + altura1
                        y_texto = (y_ini + y_fim) / 2
                        script += f"""; Cota vertical painel {i+1} - Altura 1\n_DIMLINEAR\n{x_direita},{y_ini}\n{x_direita},{y_fim}\n{x_direita+30},{y_texto}\n;\n"""
                    # Cota vertical altura 2 (ajustada para laje central)
                    if altura2 > 0:
                        y_ini2 = y_inicial + altura1 + laje_central
                        y_fim2 = y_ini2 + altura2
                        y_texto2 = (y_ini2 + y_fim2) / 2
                        script += f"""; Cota vertical painel {i+1} - Altura 2\n_DIMLINEAR\n{x_direita},{y_ini2}\n{x_direita},{y_fim2}\n{x_direita+30},{y_texto2}\n;\n"""
                    # Cota vertical laje inferior
                    if laje_inf > 0:
                        script += f"""; Cota vertical painel {i+1} - Laje Inferior\n_DIMLINEAR\n{x_direita},{y_inicial - laje_inf}\n{x_direita},{y_inicial}\n{x_direita+30},{y_inicial - laje_inf/2}\n;\n"""
                    # Cota vertical laje central
                    if laje_central > 0:
                        script += f"""; Cota vertical painel {i+1} - Laje Central\n_DIMLINEAR\n{x_direita},{y_inicial + altura1}\n{x_direita},{y_inicial + altura1 + laje_central}\n{x_direita+30},{y_inicial + altura1 + laje_central/2}\n;\n"""
                    # Cota vertical laje superior
                    if laje_sup > 0:
                        script += f"""; Cota vertical painel {i+1} - Laje Superior\n_DIMLINEAR\n{x_direita},{y_inicial + altura1 + laje_central + altura2}\n{x_direita},{y_inicial + altura1 + laje_central + altura2 + laje_sup}\n{x_direita+30},{y_inicial + altura1 + laje_central + altura2 + laje_sup/2}\n;\n"""
                    # --- Cotas extras dos segmentos (N+N) ---
                    altura1_raw = str(dados.get('paineis_alturas', [0]*len(paineis_individuais))[i]) if 'paineis_alturas' in dados else '0'
                    altura1_partes = [float(p.strip()) for p in altura1_raw.split('+') if p.strip()]
                    altura2_raw = str(dados.get('paineis_alturas2', [0]*len(paineis_individuais))[i]) if 'paineis_alturas2' in dados else '0'
                    altura2_partes = [float(p.strip()) for p in altura2_raw.split('+') if p.strip()]
                    # Altura 1 segmentos extras
                    if len(altura1_partes) > 1:
                        y_ini = y_base
                        for idx, seg in enumerate(altura1_partes):
                            y_fim = y_ini + seg
                            y_texto = (y_ini + y_fim) / 2
                            x_cota = x_direita + 15
                            script += f"""; Cota extra painel {i+1} - Altura 1 segmento {idx+1}\n_DIMLINEAR\n{x_direita},{y_ini}\n{x_direita},{y_fim}\n{x_cota},{y_texto}\n;\n"""
                            y_ini = y_fim
                    # Altura 2 segmentos extras
                    if len(altura2_partes) > 1:
                        y_ini2 = y_inicial + altura1 + laje_central
                        for idx, seg in enumerate(altura2_partes):
                            y_fim = y_ini2 + seg
                            y_texto = (y_ini2 + y_fim) / 2
                            x_cota = x_direita + 15
                            script += f"""; Cota extra painel {i+1} - Altura 2 segmento {idx+1}\n_DIMLINEAR\n{x_direita},{y_ini2}\n{x_direita},{y_fim}\n{x_cota},{y_texto}\n;\n"""
                            y_ini2 = y_fim
                # Cota vertical total (do fundo da laje inferior até topo de tudo)
                altura1_total = soma_altura_partes(dados.get('paineis_alturas', [0])[0]) if 'paineis_alturas' in dados else 0
                altura2_total = soma_altura_partes(dados.get('paineis_alturas2', [0])[0]) if 'paineis_alturas2' in dados else 0
                laje_sup_total = float(dados.get('lajes_sup', [0])[0]) if 'lajes_sup' in dados else 0
                laje_inf_total = float(dados.get('lajes_inf', [0])[0]) if 'lajes_inf' in dados else 0
                laje_central_total = float(dados.get('lajes_central_alt', [0])[0]) if 'lajes_central_alt' in dados else 0
                y_ini_total = y_inicial - laje_inf_total
                y_fim_total = y_inicial + altura1_total + laje_central_total + altura2_total + laje_sup_total
                script += f"""; Cota vertical total\n_DIMLINEAR\n{x_direita},{y_ini_total}\n{x_direita},{y_fim_total}\n{x_direita+50},{(y_ini_total + y_fim_total)/2}\n;\n"""

            # Adicionar sarrafos horizontais se modo sarrafeado
            if modo_sarrafeado:
                # Determinar os sarrafos horizontais com base na altura
                def get_linha_specs(altura):
                    if altura < 15:
                        return layer_sarrafos_horizontais_pequenos, [(5, "baixo"), (5, "cima")]
                    elif altura < 30:
                        return layer_sarrafos_horizontais, [(7, "baixo"), (7, "cima")]
                    elif altura < 80:
                        return layer_sarrafos_horizontais, [(7, "baixo"), (7, "cima"), 
                                          (3.5, "centro_cima"), (3.5, "centro_baixo")]
                    else:
                        return layer_sarrafos_horizontais, [(7, "baixo"), (7, "cima"),
                                          (3.5, "centro_cima"), (3.5, "centro_baixo"),
                                          (3.5, "quarto_inf_cima"), (3.5, "quarto_inf_baixo"),
                                          (3.5, "quarto_sup_cima"), (3.5, "quarto_sup_baixo")]
                
                layer, posicoes = get_linha_specs(altura_geral)
                
                script += f"""-LAYER
S {layer}

;
"""
                # Função auxiliar para calcular a posição Y de cada sarrafo
                def calcular_y(pos_spec, altura):
                    tipo, posicao = pos_spec
                    if posicao == "baixo":
                        return 7  # Fixo a 7 cm do fundo
                    elif posicao == "cima":
                        return altura - 7  # Fixo a 7 cm do topo
                    elif posicao == "centro_cima":
                        return (altura/2) + tipo
                    elif posicao == "centro_baixo":
                        return (altura/2) - tipo
                    elif posicao == "quarto_inf_cima":
                        return (altura/4) + tipo
                    elif posicao == "quarto_inf_baixo":
                        return (altura/4) - tipo
                    elif posicao == "quarto_sup_cima":
                        return (3*altura/4) + tipo
                    elif posicao == "quarto_sup_baixo":
                        return (3*altura/4) - tipo
                    return 0
                
                # Preparar as posições dos painéis (já deve estar em posições acumuladas)
                posicoes_paineis = [0] + paineis  # adicionar 0 no início
                
                # Desenhar os sarrafos horizontais para cada posição especificada
                for pos_spec in posicoes:
                    tipo, posicao = pos_spec
                    
                    # Filtro MLINE: Mantém apenas uma linha (topo) por sarrafo
                    if cmd_detalhe == "MLINE" and "_baixo" in posicao:
                        continue

                    # Calcular posição Y
                    if posicao == "baixo":
                        y_pos = 7
                    elif posicao == "cima":
                        y_pos = altura_geral - (0 if cmd_detalhe == "MLINE" else 7)
                    elif "centro_cima" in posicao:
                        y_pos = (altura_geral/2) + tipo
                    elif "centro_baixo" in posicao:
                        y_pos = (altura_geral/2) - tipo
                    elif "quarto_inf_cima" in posicao:
                        y_pos = (altura_geral/4) + tipo
                    elif "quarto_inf_baixo" in posicao:
                        y_pos = (altura_geral/4) - tipo
                    elif "quarto_sup_cima" in posicao:
                        y_pos = (3*altura_geral/4) + tipo
                    elif "quarto_sup_baixo" in posicao:
                        y_pos = (3*altura_geral/4) - tipo
                    else:
                        y_pos = 0
                    
                    # Scaling and direction for MLINE
                    scale_setup = ""
                    draw_reversed = ("cima" in posicao)

                    if cmd_detalhe == "MLINE":
                        scale = 7.0
                        if "pequenos" in layer:
                            scale = 5.0
                        scale_setup = f"_CMLSCALE\n{scale}\n;\n"
                        draw_reversed = False # Direção L->R + CMLJUST 0 = Espessura para BAIXO
                    
                    # Para cada seção entre os painéis, adicionar um sarrafo
                    for i in range(len(posicoes_paineis)-1):
                        pos_inicio = posicoes_paineis[i]
                        pos_fim = posicoes_paineis[i+1]
                        
                        # Calcular offset baseado na posição (primeiro e último painéis têm offset)
                        offset_inicio = 7 if i == 0 else 0
                        offset_fim = 7 if i == len(posicoes_paineis)-2 and pos_fim >= largura_total else 0
                        
                        # Adicionar o sarrafo horizontal para esta seção
                        num_painel = i + 1
                        nome_secao = f"painel {num_painel}"
                        
                        sx, ex = x_inicial+pos_inicio+offset_inicio, x_inicial+pos_fim-offset_fim
                        if draw_reversed:
                            sx, ex = ex, sx

                        script += f"""; Sarrafo horizontal {nome_secao} {posicao}
_ZOOM
C {(x_inicial+pos_inicio+x_inicial+pos_fim)/2},{y_inicial+y_pos} 5
;
{scale_setup}_{cmd_detalhe}
{sx},{y_inicial+y_pos}
{ex},{y_inicial+y_pos}

;
"""
                # Sarrafo vertical no centro de cada painel
                script += f"""-LAYER
S {layer_sarrafos_verticais}

;
"""
            
            # Obter valores do painel 1 para posicionamento do nome
            laje_sup_nome = float(lajes_sup[0]) if lajes_sup and len(lajes_sup) > 0 else 0
            altura2_nome = soma_altura_partes(dados.get('paineis_alturas2', [0])[0]) if 'paineis_alturas2' in dados else 0
            laje_central_nome = float(lajes_central[0]) if lajes_central and len(lajes_central) > 0 else 0
            y_nome = y_inicial + altura_geral + laje_sup_nome + altura2_nome + laje_central_nome + 8
            # Nome
            script += f"-LAYER\nS {layer_nome_observacoes}\n\n;\n"
            script += f"_ZOOM\nC {x_inicial},{y_nome} 5\n;\n_TEXT\n{x_inicial},{y_nome}\n16\n0\n{nome}\n;\n"
            if observacoes.strip():
                script += f"_ZOOM\nC {x_inicial+50},{y_nome} 5\n;\n_TEXT\n{x_inicial+50},{y_nome}\n16\n0\n{observacoes}\n;\n"
            
            # Desenhar linha horizontal extra para altura_geral no formato N+N
            if '+' in altura_geral_raw:
                partes = [float(p.strip()) for p in altura_geral_raw.split('+') if p.strip()]
                if len(partes) > 1:
                    y_extra = y_inicial + partes[0]
                    script += f"""; Linha extra de divisão universal (altura_geral)
_ZOOM
C {x_inicial+largura_total/2},{y_extra} 5
;
-LAYER
S {layer_paineis}

;
_{cmd_estrutura}
{x_inicial},{y_extra}
{x_inicial+largura_total},{y_extra}

;
"""
                        # No início do método _gerar_conteudo_script, ler os novos campos do dicionário:
            sarrafo_alt2_esq = dados.get('sarrafo_alt2_esq', False)
            sarrafo_alt2_dir = dados.get('sarrafo_alt2_dir', False)

            # Após desenhar os painéis altura 2, desenhar os sarrafos altura 2 se necessário
            if sarrafo_alt2_esq and len(paineis_individuais) > 0:
                # Sarrafo Altura 2 Esquerda (primeiro painel)
                x_painel = x_inicial
                altura1 = soma_altura_partes(dados.get('paineis_alturas', [0]*len(paineis_individuais))[0])
                altura2 = soma_altura_partes(dados.get('paineis_alturas2', [0]*len(paineis_individuais))[0])
                laje_c_alt = float(dados.get('lajes_central_alt', [0]*len(paineis_individuais))[0])
                if altura2 > 0:
                    y_base_alt2 = y_inicial + altura1
                    if laje_c_alt > 0:
                        y_base_alt2 += laje_c_alt
                    y_topo_alt2 = y_base_alt2 + altura2
                    script += f"-LAYER\nS SARR_2.2x7\n\n;\n"
                    script += f"_{cmd_detalhe}\n{x_painel+7},{y_base_alt2}\n{x_painel+7},{y_topo_alt2}\n\n;\n"
            if sarrafo_alt2_dir and len(paineis_individuais) > 0:
                # Sarrafo Altura 2 Direita (último painel)
                x_painel = x_inicial + sum(paineis_individuais[:-1])
                largura_painel = paineis_individuais[-1]
                altura1 = soma_altura_partes(dados.get('paineis_alturas', [0]*len(paineis_individuais))[-1])
                altura2 = soma_altura_partes(dados.get('paineis_alturas2', [0]*len(paineis_individuais))[-1])
                laje_c_alt = float(dados.get('lajes_central_alt', [0]*len(paineis_individuais))[-1])
                if altura2 > 0:
                    y_base_alt2 = y_inicial + altura1
                    if laje_c_alt > 0:
                        y_base_alt2 += laje_c_alt
                    y_topo_alt2 = y_base_alt2 + altura2
                    script += f"-LAYER\nS SARR_2.2x7\n\n;\n"
                    script += f"_{cmd_detalhe}\n{x_painel+largura_painel-7},{y_base_alt2}\n{x_painel+largura_painel-7},{y_topo_alt2}\n\n;\n"

            # ===================== RETÂNGULOS DE ABERTURAS E DETALHES DE PILAR =====================
            # Aberturas: [[dist, prof, larg], ...] para T/E, F/E, T/D, F/D
            aberturas = dados.get('aberturas', [[0,0,0] for _ in range(4)])
            # Detalhe Pilar: [dist, larg] esquerda e direita
            detalhe_pilar_esq = dados.get('detalhe_pilar_esq', [0, 0])
            detalhe_pilar_dir = dados.get('detalhe_pilar_dir', [0, 0])

            # Coordenadas de referência dos painéis
            # Encontrar primeiro e último painel válidos
            idx_primeiro = -1
            idx_ultimo = -1
            for i in range(len(paineis_individuais)):
                if paineis_individuais[i] > 0:
                    if idx_primeiro == -1:
                        idx_primeiro = i
                    idx_ultimo = i
            if idx_primeiro == -1 or idx_ultimo == -1:
                idx_primeiro = 0
                idx_ultimo = len(paineis_individuais)-1
            # X dos painéis
            x_painel_esq = x_inicial
            for i in range(idx_primeiro):
                x_painel_esq += paineis_individuais[i]
            x_painel_dir = x_inicial + sum(paineis_individuais[:idx_ultimo+1])
            # Alturas do primeiro e último painel
            altura1_esq = soma_altura_partes(dados.get('paineis_alturas', [0]*len(paineis_individuais))[idx_primeiro])
            laje_sup_esq = float(dados.get('lajes_sup', [0]*len(paineis_individuais))[idx_primeiro])
            laje_inf_esq = float(dados.get('lajes_inf', [0]*len(paineis_individuais))[idx_primeiro])
            laje_central_esq = float(dados.get('lajes_central_alt', [0]*len(paineis_individuais))[idx_primeiro])
            altura1_dir = soma_altura_partes(dados.get('paineis_alturas', [0]*len(paineis_individuais))[idx_ultimo])
            laje_sup_dir = float(dados.get('lajes_sup', [0]*len(paineis_individuais))[idx_ultimo])
            laje_inf_dir = float(dados.get('lajes_inf', [0]*len(paineis_individuais))[idx_ultimo])
            laje_central_dir = float(dados.get('lajes_central_alt', [0]*len(paineis_individuais))[idx_ultimo])
            # Y das esquinas
            y_topo_esq = y_inicial + altura1_esq + laje_central_esq + laje_sup_esq
            y_fundo_esq = y_inicial - laje_inf_esq
            y_topo_dir = y_inicial + altura1_dir + laje_central_dir + laje_sup_dir
            y_fundo_dir = y_inicial - laje_inf_dir

            # ===================== ABERTURAS POR ESQUINA =====================
            modo_grade = (
                dados.get('modo', '').lower() == 'grade' or
                any(t1 == 'Grade' for t1 in paineis_tipo1) or
                any(t2 == 'Grade' for t2 in paineis_tipo2)
            )
            # ===================== ABERTURAS POR ESQUINA =====================
            # Aberturas: 0=Topo/Esq, 1=Fundo/Esq, 2=Topo/Dir, 3=Fundo/Dir
            for i, (dist_h, prof, larg) in enumerate(aberturas):
                if prof <= 0 or larg <= 0:
                    continue
                
                # Forçar H1 flag (agora vindo dos dados)
                forcar_h1 = False
                if 'forcar_altura1' in dados and len(dados['forcar_altura1']) > i:
                    forcar_h1 = dados['forcar_altura1'][i]

                # Qual painel referenciar para obter as alturas locais
                idx_local = idx_primeiro if i in [0, 1] else idx_ultimo
                x_ref_local = x_painel_esq if i in [0, 1] else x_painel_dir
                
                # Alturas do painel de referência
                h1_loc = soma_altura_partes(dados.get('paineis_alturas', [0]*6)[idx_local])
                h2_loc = soma_altura_partes(dados.get('paineis_alturas2', [0]*6)[idx_local])
                sc_loc = float(dados.get('lajes_central_alt', [0]*6)[idx_local])
                st_loc = float(dados.get('lajes_sup', [0]*6)[idx_local])
                sb_loc = float(dados.get('lajes_inf', [0]*6)[idx_local])
                
                # Determinar tipo (Grade/Sarrafeado) para o comando correto
                tipo_loc = dados.get('paineis_tipo1', ["Sarrafeado"]*6)[idx_local]
                if h2_loc > 0 and not forcar_h1:
                    tipo_loc = dados.get('paineis_tipo2', ["Sarrafeado"]*6)[idx_local]
                
                # Altura da grade se for o caso
                alt_grade_v = 7.0
                if tipo_loc == "Grade":
                    if forcar_h1 or h2_loc <= 0:
                        alt_grade_v = float(dados.get('paineis_grade_altura1', [7.0]*6)[idx_local])
                    else:
                        alt_grade_v = float(dados.get('paineis_grade_altura2', [7.0]*6)[idx_local])

                # Referências Verticais
                y_abs_top = y_inicial + h1_loc + sc_loc + h2_loc + st_loc
                y_h1_top = y_inicial + h1_loc + sc_loc
                y_abs_bot = y_inicial - sb_loc
                y_h1_bot = y_inicial
                
                # Ajuste de laje para o comando appdel (limpeza de hachura da laje)
                laje_v_ajuste = 0
                if i in [0, 2]: # Topo
                    laje_v_ajuste = 0 if forcar_h1 else st_loc
                else: # Fundo
                    laje_v_ajuste = 0 if forcar_h1 else sb_loc

                prof_ajust_app = max(0, prof - laje_v_ajuste) if laje_v_ajuste > 0 else prof
                
                # Posicionamento X (Horizontal)
                if i in [0, 1]: # Esquina Esquerda
                    x1_ab = x_ref_local + dist_h
                    x2_ab = x1_ab + larg
                else: # Esquina Direita
                    x2_ab = x_ref_local - dist_h
                    x1_ab = x2_ab - larg
                
                # Posicionamento Y (Vertical)
                if i in [0, 2]: # Topo
                    y_start_ab = y_h1_top if forcar_h1 else y_abs_top
                    y1_ab = y_start_ab
                    y2_ab = y1_ab - prof
                else: # Fundo
                    y_start_ab = y_h1_bot if forcar_h1 else y_abs_bot
                    y1_ab = y_start_ab
                    y2_ab = y1_ab + prof
                
                # Gerar script comandos
                script += f"ZOOM\nC {(x1_ab+x2_ab)/2:.3f},{(y1_ab+y2_ab)/2:.3f} 10\n;\n"
                desc_ab = ["T/E", "F/E", "T/D", "F/D"][i]
                script += f"; Abertura {desc_ab} (Forçar H1: {forcar_h1})\nAPP\n{x1_ab:.3f},{y_aj(y1_ab):.3f}\n{x2_ab:.3f},{y_aj(y2_ab):.3f}\n;\n"
                
                cmd_v = ""
                if i == 0: cmd_v = "ABVET" if tipo_loc == "Grade" else "ABFET"
                elif i == 1: cmd_v = "ABVEF" if tipo_loc == "Grade" else "ABFEF"
                elif i == 2:
                    cmd_v = "ABVDT" if tipo_loc == "Grade" else "ABFDT"
                    if str(dados.get('continuacao', '')).lower() != 'obstaculo' and tipo_loc == "Grade":
                        cmd_v = "ABVDTV"
                elif i == 3: cmd_v = "ABVDF" if tipo_loc == "Grade" else "ABFDF"
                
                if "ABV" in cmd_v: # Grade vertical
                    y3_grade = y2_ab + (prof_ajust_app - alt_grade_v) if i in [0, 2] else y2_ab - (prof_ajust_app - alt_grade_v)
                    script += f"{cmd_v}\n{x1_ab:.3f},{y_aj(y1_ab):.3f}\n{x2_ab:.3f},{y_aj(y2_ab):.3f}\n{x2_ab:.3f},{y_aj(y3_grade):.3f}\n;\n"
                else:
                    script += f"{cmd_v}\n{x1_ab:.3f},{y_aj(y1_ab):.3f}\n{x2_ab:.3f},{y_aj(y2_ab):.3f}\n;\n"
                
                if laje_v_ajuste > 0:
                    x_mid_ab = (x1_ab + x2_ab) / 2
                    script += f";\nappdel\n{x_mid_ab:.3f},{y_aj(y1_ab):.3f}\n;\n"
                    # Se quiser adicionar mais tipos, basta seguir o padrão acima

            # Detalhe Pilar Esquerda
            dist_pilar_esq, larg_pilar_esq = detalhe_pilar_esq
            if larg_pilar_esq > 0:
                x1 = x_painel_esq + dist_pilar_esq
                y1 = y_inicial
                x2 = x1 + larg_pilar_esq
                y2 = y_inicial + altura1_esq
                script += f"""; Detalhe Pilar Esquerda\nRECTANGLE\n{x1:.3f},{y1:.3f}\n{x2:.3f},{y2:.3f}\n;\n"""
                # Comando apv2/apv2e para detalhe pilar esquerdo
                altura_grade_1_esq = float(dados.get('paineis_grade_altura1', [7.0]*len(paineis_individuais))[idx_primeiro]) if 'paineis_grade_altura1' in dados else 7.0
                y_grade_fundo_esq = y_inicial + altura1_esq - 2.2 - (altura_grade_1_esq - 2.2)
                comando_esq = "apv2e" if dist_pilar_esq == 0 else "apv2"
                script += f"{comando_esq}\n{x1:.3f},{y1:.3f}\n{x2:.3f},{y2:.3f}\n{x1:.3f},{y_grade_fundo_esq:.3f}\n;\n"
            # Detalhe Pilar Direita
            dist_pilar_dir, larg_pilar_dir = detalhe_pilar_dir
            if larg_pilar_dir > 0:
                x2 = x_painel_dir - dist_pilar_dir
                y1 = y_inicial
                x1 = x2 - larg_pilar_dir
                y2 = y_inicial + altura1_dir
                script += f"""; Detalhe Pilar Direita\nRECTANGLE\n{x1:.3f},{y1:.3f}\n{x2:.3f},{y2:.3f}\n;\n"""
                # Comando apv2/apv2D para detalhe pilar direito
                altura_grade_1_dir = float(dados.get('paineis_grade_altura1', [7.0]*len(paineis_individuais))[idx_ultimo]) if 'paineis_grade_altura1' in dados else 7.0
                y_grade_fundo_dir = y_inicial + altura1_dir - 2.2 - (altura_grade_1_dir - 2.2)
                comando_dir = "apv2D" if dist_pilar_dir == 0 else "apv2"
                script += f"{comando_dir}\n{x1:.3f},{y1:.3f}\n{x2:.3f},{y2:.3f}\n{x1:.3f},{y_grade_fundo_dir:.3f}\n;\n"
            # ===================== OBSTÁCULO À DIREITA =====================
            if str(dados.get('continuacao', '')).lower() == 'obstaculo':
                largura_obstaculo = 30.0
                idx_ultimo = idx_ultimo  # já definido acima
                if idx_ultimo != -1:
                    # Posição X inicial: fim do último painel
                    x_obs_ini = x_painel_dir
                    # Alturas do último painel
                    altura1 = soma_altura_partes(dados.get('paineis_alturas', [0]*len(paineis_individuais))[idx_ultimo])
                    altura2 = soma_altura_partes(dados.get('paineis_alturas2', [0]*len(paineis_individuais))[idx_ultimo])
                    laje_sup = float(dados.get('lajes_sup', [0]*len(paineis_individuais))[idx_ultimo])
                    laje_inf = float(dados.get('lajes_inf', [0]*len(paineis_individuais))[idx_ultimo])
                    laje_central = float(dados.get('lajes_central_alt', [0]*len(paineis_individuais))[idx_ultimo])
                    # Y topo: y_inicial + altura1 + laje_central + laje_sup + laje_central + altura2
                    y_obs_top = y_inicial + altura1 + laje_central + laje_sup + laje_central + altura2
                    y_obs_base = y_inicial - laje_inf
                    # Centro do retângulo
                    x_centro = x_obs_ini + largura_obstaculo / 2
                    y_centro = (y_obs_base + y_obs_top) / 2
                    # Layer de cotas
                    script += f"""; === INICIO OBSTACULO ===\n-LAYER\nS {layer_obstaculo}\n\n; Obstaculo\nRECTANGLE\n{x_obs_ini:.3f},{y_obs_base:.3f}\n{(x_obs_ini+largura_obstaculo):.3f},{y_obs_top:.3f}\n;\n{cmd_hhhh}\n{x_centro:.3f},{y_centro:.3f}\n; === FIM OBSTÁCULO ===\n"""

            # Adiciona comentário especial se for Viga Continuação
            if str(dados.get('continuacao', '')).replace(' ', '').lower() == 'vigacontinuacao':
                script += '; "Viga Continuacao"\n'

            # Ajuste final e retorno
            script += f"; Ajuste: {ajuste_global}\n"
            return script
            
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Erro", f"Erro ao gerar conteúdo do script: {str(e)}")
            return "" # Retorna string vazia ao invés de None para evitar erro de concatenação

def gerar_script_viga(dados, diretorio_saida=""):
    """
    Função para gerar o script SCR para uma viga.
    
    Args:
        dados: Dicionário com os dados da viga
        diretorio_saida: Diretório onde salvar o script
        
    Returns:
        tuple: (script_text, caminho_arquivo) ou (None, None) em caso de erro
    """
    try:
        gerador = GeradorScriptViga()
        return gerador.gerar_script(dados, diretorio_saida)
    except Exception as e:
        traceback.print_exc()
        messagebox.showerror("Erro", f"Erro ao gerar o script: {str(e)}")
        return None, None 