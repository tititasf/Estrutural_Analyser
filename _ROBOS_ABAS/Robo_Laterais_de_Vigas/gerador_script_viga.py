import os
import re
import tkinter as tk
from tkinter import messagebox
import json
from datetime import datetime
import traceback
import math

class GeradorScriptViga:
    def __init__(self, config=None):
        """Inicializa o gerador de scripts para laterais de viga."""
        if config:
            self.config = config
        else:
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
                "sarrafos_verticais_grades": "SARR_2.2x7",
                "parafuso": "BARRA_ANCORAGEM"
            },
            "comandos": {
                "extensor1": "ex2",
                "extensor2": "Bextend"
            },
            "opcoes": {
                "tipo_linha": "PLINE",
                "parafuso_block": "PAR_ESQ"
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
                continuacao = dados.get('continuacao', '')
                script_text = f"; (numeracao: {numero}, largura: {largura_total}, altura: {altura_geral}, continuacao: {continuacao})\n;\n" + script_text
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
        script_secao = ""
 



        # Obter ajuste global
        try:
            ajuste_global = float(dados.get('ajuste', 0))
        except Exception:
            ajuste_global = 0

        # Função auxiliar para aplicar ajuste global em Y
        def y_aj(y):
            return y + ajuste_global
        
        # Função auxiliar para somar partes de altura "20+30"
        def soma_altura_partes(valor):
            if isinstance(valor, (int, float)): return float(valor)
            try:
                return sum(float(x) for x in str(valor).split('+') if x.strip())
            except:
                return 0.0
        
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
        
        # --- GERAÇÃO VISÃO DE CORTE (Section View) ---
        # Visao de corte agora gerada em arquivo separado por solicitacao.
        # Codigo movido para metodo proprio.
        pass
        # ---------------------------------------------
        
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
            script = f""";
;
_ZOOM
C {x_inicial+largura_total/2},{y_inicial+altura_geral/2} 100
;
-LAYER
S {layer_paineis}

;
{setup_mline}
"""
            # --- REMOVIDO: Linhas Globais (Esqueleto) para evitar duplicidade com painéis individuais ---
            # O loop de painéis abaixo já desenha o retângulo completo de cada painel.
            # Manter apenas Textos e Sarrafos de Extremidade (que são desenhados neste bloco intermediário)
            
            # (Anteriormente desenhava Linha Lateral Esquerda e Direita aqui - Removido)

            # Definir estilo de texto (standart) antes de criar textos
            script += ";\n-style\nstandart\n\n0\n\n\n\n\n\n;\n"
            
            # Adicionar textos laterais apenas se não estiverem vazios
            if texto_esquerdo.strip():
                script += f"_ZOOM\nC {x_inicial-5},{y_texto_lateral} 5\n;\n_TEXT\n{x_inicial-5},{y_texto_lateral}\n8\n90\n{texto_esquerdo}\n;\n"
            if texto_direito.strip():
                script += f"_ZOOM\nC {x_inicial+largura_total+12},{y_texto_lateral} 5\n;\n_TEXT\n{x_inicial+largura_total+12},{y_texto_lateral}\n8\n90\n{texto_direito}\n;\n"
            
            # --- Sarrafos de Extremidade ---
            script += f"-LAYER\nS {layer_sarrafos_vert_ext}\n\n;\n"
            script += f"; DEBUG: Sarrafo Settings: L_ID={dados.get('sarrafo_left_id')} L_Bool={dados.get('sarrafo_left')} R_ID={dados.get('sarrafo_right_id')}\n"
            # Adicionar sarrafos verticais nas extremidades
            if dados.get('sarrafo_left', True):
                script += f"""; Sarrafo Esquerdo
_ZOOM
C {x_inicial+7},{y_inicial+altura_geral/2} 5
;
"""
                if cmd_detalhe == "MLINE":
                    script += "_CMLSCALE\n7.0\n;\n"
                    # MLINE Left
                    script += f"""_{cmd_detalhe}
{x_inicial+7},{y_inicial+altura_geral+3.5}
{x_inicial+7},{y_inicial}

;
"""
                else:
                    script += f"""_{cmd_detalhe}
{x_inicial+7},{y_inicial}
{x_inicial+7},{y_inicial+altura_geral+3.5}

;
"""

            if dados.get('sarrafo_right', True):
                script += f""";
; Sarrafo Direito
_ZOOM
C {x_inicial+largura_total-7},{y_inicial+altura_geral/2} 5
;
"""
                if cmd_detalhe == "MLINE":
                    script += "_CMLSCALE\n7.0\n;\n"
                    # MLINE Right
                    script += f"""_{cmd_detalhe}
{x_inicial+largura_total-7},{y_inicial}
{x_inicial+largura_total-7},{y_inicial+altura_geral+3.5}

;
"""
                else:
                    script += f"""_{cmd_detalhe}
{x_inicial+largura_total-7},{y_inicial+altura_geral+3.5}
{x_inicial+largura_total-7},{y_inicial}

;
"""
            script += f"""-LAYER
S {layer_paineis}

;
"""
            # (Anteriormente desenhava Linhas Verticais de Divisão e Horizontais Globais aqui - Removido)

            
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

                # --- BLOCK NUMBERING REMOVED FROM HERE (Moved to end) ---
                numeracao_cfg = dados.get('numeracao_blocos', {})
                # ... (rest of old logic deleted)
                    
                # --- END BLOCK NUMBERING REMOVAL ---

                # Sarrafos Altura 1
                script += f"""; ===== SARRAFOS/GRADES ALTURA 1 PAINEL {i+1} =====\n"""
                tipo1 = dados.get('paineis_tipo1', ["Sarrafeado"]*len(paineis_individuais))[i] if 'paineis_tipo1' in dados else "Sarrafeado"
                if tipo1 == "Grade":
                    # Lógica de grade para Altura 1 (GRA)
                    altura_grade = 2.2
                    largura_vert = 7.0
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
                        # Troca para estilo de 7.0cm centro
                        script += "_CMLSTYLE\nMEIOPONT\n;\n"
                        # x_grade_ini is Left Edge.
                        # We want thickness Right.
                        # Justification Left (0). Top->Bottom vector. Left is Right.
                        # User requested shift +3.5cm Right (to center a 7cm sarrafo).
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
                        # Troca para estilo de 7.0cm centro
                        script += "_CMLSTYLE\nMEIOPONT\n;\n"
                        # x_vert_dir is Left Edge of the vertical sarrafo.
                        # We want thickness Right.
                        # Vector Top->Bottom.
                        # User requested shift +7.0cm Right.
                        x_mline = x_vert_dir + 7.0
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
                                return layer_sarrafos_horizontais, [(7, "baixo"), (7, "cima"), (7.0, "centro_cima"), (7.0, "centro_baixo")]
                            else:
                                return layer_sarrafos_horizontais, [
                                    (7, "baixo"), (7, "cima"),
                                    (7.0, "centro_cima"), (7.0, "centro_baixo"),
                                    (7.0, "quarto_inf_cima"), (7.0, "quarto_inf_baixo"),
                                    (7.0, "quarto_sup_cima"), (7.0, "quarto_sup_baixo")
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
                    # --- Sarrafo Extremidade H2 (Esquerdo/Direito) ---
                    sarrafo_h2_esq = dados.get('sarrafo_h2_esq', False)
                    sarrafo_h2_dir = dados.get('sarrafo_h2_dir', False)
                    
                    # Esquerdo (Painel 0)
                    if i == 0 and sarrafo_h2_esq:
                        script += f"; Sarrafo H2 Esquerdo\n-LAYER\nS {layer_sarrafos_vert_ext}\n\n;\n"
                        y_sh2_top = y_topo_alt2
                        x_sh2 = x_painel + 7
                        
                        if cmd_detalhe == "MLINE":
                            script += "_CMLSCALE\n7.0\n;\n"
                            # Copiando lógica do sarrafo principal esquerdo: Top -> Bottom
                            script += f"_{cmd_detalhe}\n{x_sh2},{y_sh2_top}\n{x_sh2},{y_base_alt2}\n\n;\n"
                        else:
                            script += f"_{cmd_detalhe}\n{x_sh2},{y_base_alt2}\n{x_sh2},{y_sh2_top}\n\n;\n"
                            
                    # Direito (Último Painel)
                    if i == len(paineis_individuais)-1 and sarrafo_h2_dir:
                        script += f"; Sarrafo H2 Direito\n-LAYER\nS {layer_sarrafos_vert_ext}\n\n;\n"
                        y_sh2_top = y_topo_alt2
                        x_sh2 = x_painel + largura_painel - 7
                        
                        if cmd_detalhe == "MLINE":
                            script += "_CMLSCALE\n7.0\n;\n"
                            # Copiando lógica do sarrafo principal direito: Bottom -> Top
                            script += f"_{cmd_detalhe}\n{x_sh2},{y_base_alt2}\n{x_sh2},{y_sh2_top}\n\n;\n"
                        else:
                            script += f"_{cmd_detalhe}\n{x_sh2},{y_sh2_top}\n{x_sh2},{y_base_alt2}\n\n;\n"

                else:
                    script += f"""; Não há painel de Altura 2 neste painel\n"""
                # Sarrafos Altura 2
                script += f"""; ===== SARRAFOS/GRADES ALTURA 2 PAINEL {i+1} =====\n"""
                tipo2 = dados.get('paineis_tipo2', ["Sarrafeado"]*len(paineis_individuais))[i] if 'paineis_tipo2' in dados else "Sarrafeado"
                if tipo2 == "Grade" and altura2 > 0:
                    # Lógica de grade para Altura 2 (GRA)
                    altura_grade2 = 2.2
                    largura_vert2 = 7.0
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
                        # Troca para estilo de 7.0cm centro
                        script += "_CMLSTYLE\nMEIOPONT\n;\n"
                        # x_grade2_ini Left Edge. Thickness Right.
                        # Draw Top -> Bottom.
                        # Shift +7.0cm Right.
                        x_mline = x_grade2_ini + 7.0
                        script += f"_CMLSCALE\n14.0\n;\n_{cmd_detalhe}\n{x_mline},{y_grade2_bot - 2.2}\n{x_mline},{y_grade2_bot - 2.2-altura_vert2}\n\n;\n"
                        # Volta para o estilo padrão de 7cm
                        script += "_CMLSTYLE\nSAR3\n;\n"
                    else:
                        script += f"_{cmd_detalhe}\n{x_grade2_ini},{y_grade2_bot - 2.2}\n{x_grade2_ini+largura_vert2},{y_grade2_bot - 2.2}\n{x_grade2_ini+largura_vert2},{y_grade2_bot - 2.2-altura_vert2}\n{x_grade2_ini},{y_grade2_bot - 2.2-altura_vert2}\nC\n;\n"
                    
                    # Vertical direita
                    x_vert2_dir = x_painel + largura_painel - largura_vert2
                    if i == len(paineis_individuais)-1:
                        x_vert2_dir = x_painel + largura_painel - 15 - largura_vert2
                    
                    if cmd_detalhe == "MLINE":
                        # Troca para estilo de 7.0cm centro
                        script += "_CMLSTYLE\nMEIOPONT\n;\n"
                        # x_vert2_dir Left Edge. Thickness Right.
                        # Draw Top -> Bottom.
                        # Shift +7.0cm Right.
                        x_mline = x_vert2_dir + 7.0
                        script += f"_CMLSCALE\n14.0\n;\n_{cmd_detalhe}\n{x_mline},{y_grade2_bot - 2.2}\n{x_mline},{y_grade2_bot - 2.2-altura_vert2}\n\n;\n"
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
                                return layer_sarrafos_horizontais, [(7, "baixo"), (7, "cima"), (7.0, "centro_cima"), (7.0, "centro_baixo")]
                            else:
                                return layer_sarrafos_horizontais, [
                                    (7, "baixo"), (7, "cima"),
                                    (7.0, "centro_cima"), (7.0, "centro_baixo"),
                                    (7.0, "quarto_inf_cima"), (7.0, "quarto_inf_baixo"),
                                    (7.0, "quarto_sup_cima"), (7.0, "quarto_sup_baixo")
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
            script += f"""-DIMSTYLE\nR\ncotas\n-LAYER\nS {layer_cotas}\n\n;\n"""
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
                                          (7.0, "centro_cima"), (7.0, "centro_baixo")]
                    else:
                        return layer_sarrafos_horizontais, [(7, "baixo"), (7, "cima"),
                                          (7.0, "centro_cima"), (7.0, "centro_baixo"),
                                          (7.0, "quarto_inf_cima"), (7.0, "quarto_inf_baixo"),
                                          (7.0, "quarto_sup_cima"), (7.0, "quarto_sup_baixo")]
                
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

            # ===================== SARRAFOS DE PRESSÃO (PLINE DASHED) =====================
            # H1 Esquerda (ID=2)
            if dados.get('sarrafo_left_id', 0) == 2 and len(paineis_individuais) > 0:
                h = soma_altura_partes(dados.get('paineis_alturas', [0]*len(paineis_individuais))[0])
                script += f"-LAYER\nS SARR_2.2x7\n\n;\n_-LINETYPE\nS\nDASHED\n\n;\nPLINE\n{x_inicial},{y_inicial}\n{x_inicial},{y_inicial+h}\n{x_inicial+7},{y_inicial+h}\n{x_inicial+7},{y_inicial}\nC\n\n;\n_-LINETYPE\nS\nByLayer\n\n;\n"

            # H1 Direita (ID=2)
            if dados.get('sarrafo_right_id', 0) == 2 and len(paineis_individuais) > 0:
                h = soma_altura_partes(dados.get('paineis_alturas', [0]*len(paineis_individuais))[-1])
                x = x_inicial + largura_total
                script += f"-LAYER\nS SARR_2.2x7\n\n;\n_-LINETYPE\nS\nDASHED\n\n;\nPLINE\n{x},{y_inicial}\n{x},{y_inicial+h}\n{x-7},{y_inicial+h}\n{x-7},{y_inicial}\nC\n\n;\n_-LINETYPE\nS\nByLayer\n\n;\n"

            # H2 Esquerda (ID=2)
            if dados.get('sarrafo_h2_left_id', 0) == 2 and len(paineis_individuais) > 0:
                altura1 = soma_altura_partes(dados.get('paineis_alturas', [0]*len(paineis_individuais))[0])
                altura2 = soma_altura_partes(dados.get('paineis_alturas2', [0]*len(paineis_individuais))[0])
                laje_c_alt = float(dados.get('lajes_central_alt', [0]*len(paineis_individuais))[0])
                if altura2 > 0:
                    y_base = y_inicial + altura1 + (laje_c_alt if laje_c_alt > 0 else 0)
                    y_topo = y_base + altura2
                    script += f"-LAYER\nS SARR_2.2x7\n\n;\n_-LINETYPE\nS\nDASHED\n\n;\nPLINE\n{x_inicial},{y_base}\n{x_inicial},{y_topo}\n{x_inicial+7},{y_topo}\n{x_inicial+7},{y_base}\nC\n\n;\n_-LINETYPE\nS\nByLayer\n\n;\n"

            # H2 Direita (ID=2)
            if dados.get('sarrafo_h2_right_id', 0) == 2 and len(paineis_individuais) > 0:
                altura1 = soma_altura_partes(dados.get('paineis_alturas', [0]*len(paineis_individuais))[-1])
                altura2 = soma_altura_partes(dados.get('paineis_alturas2', [0]*len(paineis_individuais))[-1])
                laje_c_alt = float(dados.get('lajes_central_alt', [0]*len(paineis_individuais))[-1])
                if altura2 > 0:
                    y_base = y_inicial + altura1 + (laje_c_alt if laje_c_alt > 0 else 0)
                    y_topo = y_base + altura2
                    x = x_inicial + largura_total
                    script += f"-LAYER\nS SARR_2.2x7\n\n;\n_-LINETYPE\nS\nDASHED\n\n;\nPLINE\n{x},{y_base}\n{x},{y_topo}\n{x-7},{y_topo}\n{x-7},{y_base}\nC\n\n;\n_-LINETYPE\nS\nByLayer\n\n;\n"

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
                script += f"; Abertura {desc_ab} (Forçar H1: {forcar_h1})\n{_cmd('app', 'APP')}\n{x1_ab:.3f},{y_aj(y1_ab):.3f}\n{x2_ab:.3f},{y_aj(y2_ab):.3f}\n;\n"
                # Linhas extras de topo e fundo da seleção
                script += f"-LAYER\nS\npainéis\n\n"
                script += f"PLINE\n{x1_ab:.3f},{y_aj(y1_ab):.3f}\n{x2_ab:.3f},{y_aj(y1_ab):.3f}\n\n"
                script += f"PLINE\n{x1_ab:.3f},{y_aj(y2_ab):.3f}\n{x2_ab:.3f},{y_aj(y2_ab):.3f}\n\n"
                
                # Extra APP para Topo (i=0 e i=2) somente se for Grade
                if tipo_loc == "Grade":
                    if i == 0: # Topo Esquerda - APP na direita (para fora)
                         x_ex_1 = x2_ab
                         x_ex_2 = x2_ab + 15.0
                         y_ex_1 = y1_ab
                         y_ex_2 = y1_ab - 2.2
                         script += f"; Extra APP Topo Esq -> Dir\nAPP\n{x_ex_1:.3f},{y_aj(y_ex_1):.3f}\n{x_ex_2:.3f},{y_aj(y_ex_2):.3f}\n;\n"
                         # Linha 1: Painéis (Sempre)
                         script += f"-LAYER\nS\n{layer_paineis}\n\n"
                         script += f"LINE\n{x_ex_1:.3f},{y_aj(y_ex_1):.3f}\n{x_ex_2:.3f},{y_aj(y_ex_1):.3f}\n\n"
                         # Linha 2: Laje (Somente se existir laje superior)
                         if st_loc > 0:
                             script += f"-LAYER\nS\n{layer_laje}\n\n"
                             script += f"LINE\n{x_ex_1:.3f},{y_aj(y_ex_1):.3f}\n{x_ex_2:.3f},{y_aj(y_ex_1):.3f}\n\n"
                    elif i == 2: # Topo Direita - APP na esquerda (para fora)
                         x_ex_1 = x1_ab
                         x_ex_2 = x1_ab - 15.0
                         y_ex_1 = y1_ab
                         y_ex_2 = y1_ab - 2.2
                         script += f"; Extra APP Topo Dir -> Esq\nAPP\n{x_ex_1:.3f},{y_aj(y_ex_1):.3f}\n{x_ex_2:.3f},{y_aj(y_ex_2):.3f}\n;\n"
                         # Linha 1: Painéis (Sempre)
                         script += f"-LAYER\nS\n{layer_paineis}\n\n"
                         script += f"LINE\n{x_ex_1:.3f},{y_aj(y_ex_1):.3f}\n{x_ex_2:.3f},{y_aj(y_ex_1):.3f}\n\n"
                         # Linha 2: Laje (Somente se existir laje superior)
                         if st_loc > 0:
                             script += f"-LAYER\nS\n{layer_laje}\n\n"
                             script += f"LINE\n{x_ex_1:.3f},{y_aj(y_ex_1):.3f}\n{x_ex_2:.3f},{y_aj(y_ex_1):.3f}\n\n"
                
                cmd_key = ""
                if i == 0: cmd_key = "ABVET" if tipo_loc == "Grade" else "ABFET"
                elif i == 1: cmd_key = "ABVEF" if tipo_loc == "Grade" else "ABFEF"
                elif i == 2:
                    cmd_key = "ABVDT" if tipo_loc == "Grade" else "ABFDT"
                    if str(dados.get('continuacao', '')).lower() != 'obstaculo' and tipo_loc == "Grade":
                        cmd_key = "ABVDTV"
                elif i == 3: cmd_key = "ABVDF" if tipo_loc == "Grade" else "ABFDF"
                
                cmd_v = _cmd(cmd_key, cmd_key)
                
                if "ABV" in cmd_key: # Grade vertical
                    y3_grade = y2_ab + (prof_ajust_app - alt_grade_v) if i in [0, 2] else y2_ab - (prof_ajust_app - alt_grade_v)
                    script += f"{cmd_v}\n{x1_ab:.3f},{y_aj(y1_ab):.3f}\n{x2_ab:.3f},{y_aj(y2_ab):.3f}\n{x2_ab:.3f},{y_aj(y3_grade):.3f}\n;\n"
                else:
                    script += f"{cmd_v}\n{x1_ab:.3f},{y_aj(y1_ab):.3f}\n{x2_ab:.3f},{y_aj(y2_ab):.3f}\n;\n"
                
                if laje_v_ajuste > 0:
                    x_mid_ab = (x1_ab + x2_ab) / 2
                    script += f";\n{_cmd('appdel', 'appdel')}\n{x_mid_ab:.3f},{y_aj(y1_ab):.3f}\n;\n"
                    # Se quiser adicionar mais tipos, basta seguir o padrão acima

            # Detalhe Pilar Esquerda
            dist_pilar_esq, larg_pilar_esq = detalhe_pilar_esq
            if larg_pilar_esq > 0:
                x1 = x_painel_esq + dist_pilar_esq
                y1 = y_inicial
                x2 = x1 + larg_pilar_esq
                y2 = y_inicial + altura1_esq
                # Adicionando comando APP antes da abertura de pilar
                script += f"""; Preparar Abertura Pilar Esquerda\n{_cmd('app', 'APP')}\n{x1:.3f},{y1:.3f}\n{x2:.3f},{y2:.3f}\n;\n"""
                # Linhas extras de topo e fundo da seleção
                script += f"-LAYER\nS\npainéis\n\n"
                script += f"PLINE\n{x1:.3f},{y1:.3f}\n{x2:.3f},{y1:.3f}\n\n"
                script += f"PLINE\n{x1:.3f},{y2:.3f}\n{x2:.3f},{y2:.3f}\n\n"
                # Comando apv2/apv2e para detalhe pilar esquerdo
                altura_grade_1_esq = float(dados.get('paineis_grade_altura1', [7.0]*len(paineis_individuais))[idx_primeiro]) if 'paineis_grade_altura1' in dados else 7.0
                y_grade_fundo_esq = y1 + altura1_esq - 2.2 - (altura_grade_1_esq - 2.2)
                comando_esq = _cmd('apv2e', 'apv2EINI') if dist_pilar_esq == 0 else _cmd('apv2', 'apv2ini')
                script += f"{comando_esq}\n{x1:.3f},{y1:.3f}\n{x2:.3f},{y2:.3f}\n{x1:.3f},{y_grade_fundo_esq:.3f}\n;\n"
            # Detalhe Pilar Direita
            dist_pilar_dir, larg_pilar_dir = detalhe_pilar_dir
            if larg_pilar_dir > 0:
                x2 = x_painel_dir - dist_pilar_dir
                y1 = y_inicial
                x1 = x2 - larg_pilar_dir
                y2 = y_inicial + altura1_dir
                # Adicionando comando APP antes da abertura de pilar
                script += f"""; Preparar Abertura Pilar Direita\n{_cmd('app', 'APP')}\n{x1:.3f},{y1:.3f}\n{x2:.3f},{y2:.3f}\n;\n"""
                # Linhas extras de topo e fundo da seleção
                script += f"-LAYER\nS\npainéis\n\n"
                script += f"PLINE\n{x1:.3f},{y1:.3f}\n{x2:.3f},{y1:.3f}\n\n"
                script += f"PLINE\n{x1:.3f},{y2:.3f}\n{x2:.3f},{y2:.3f}\n\n"
                # Comando apv2/apv2D para detalhe pilar direito
                altura_grade_1_dir = float(dados.get('paineis_grade_altura1', [7.0]*len(paineis_individuais))[idx_ultimo]) if 'paineis_grade_altura1' in dados else 7.0
                y_grade_fundo_dir = y1 + altura1_dir - 2.2 - (altura_grade_1_dir - 2.2)
                comando_dir = _cmd('apv2D', 'apv2DINI') if dist_pilar_dir == 0 else _cmd('apv2', 'apv2ini')
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
            # (script_secao removido daqui, pois agora é arquivo separado)

            script += f"; Ajuste: {ajuste_global}\n"
            
            # --- BLOCK NUMBERING & PONTALETE TEXTS (DRAWN LAST) ---
            numeracao_cfg = dados.get('numeracao_blocos', {})
            if numeracao_cfg.get('ativo', False):
                count = dados.get('indice_inicial_painel', 0) + 1
                
                # Helper for Pontalete Text
                def gen_pont_text(width, is_grade, is_first, is_last, ab_list, px, py, is_h2):
                     if not is_grade or width < 60: return ""
                     
                     eff_width = width

                     # Desconto de Aberturas de Pilar (Distância 0) - Apenas em H1
                     if not is_h2:
                         if is_first:
                             dist_p_esq, larg_p_esq = detalhe_pilar_esq
                             if dist_p_esq == 0 and larg_p_esq > 0:
                                 eff_width -= larg_p_esq
                         if is_last:
                             dist_p_dir, larg_p_dir = detalhe_pilar_dir
                             if dist_p_dir == 0 and larg_p_dir > 0:
                                 eff_width -= larg_p_dir

                     forcar_list = dados.get('forcar_altura1', [False]*4)
                     
                     if is_first:
                         # Top Left (0)
                         if 0 < len(ab_list):
                             d, p, l = ab_list[0]
                             if l > 0 and p > 0:
                                 in_h2 = not forcar_list[0]
                                 if (is_h2 and in_h2) or (not is_h2 and not in_h2):
                                     eff_width -= l
                         # Bottom Left (1)
                         if 1 < len(ab_list):
                             d, p, l = ab_list[1]
                             if l > 0 and p > 0:
                                 if not is_h2:
                                     eff_width -= l
                                     
                     if is_last:
                         # Top Right (2)
                         if 2 < len(ab_list):
                             d, p, l = ab_list[2]
                             if l > 0 and p > 0:
                                 in_h2 = not forcar_list[2]
                                 if (is_h2 and in_h2) or (not is_h2 and not in_h2):
                                     eff_width -= l
                         # Bottom Right (3)
                         if 3 < len(ab_list):
                             d, p, l = ab_list[3]
                             if l > 0 and p > 0:
                                 if not is_h2:
                                     eff_width -= l
                     
                     if eff_width < 60: return ""
                     
                     txt = ""
                     if 60 <= eff_width < 90: txt = "3-%%189PONT."
                     elif 90 <= eff_width < 120: txt = "4-%%189PONT."
                     elif 120 <= eff_width < 150: txt = "5-%%189PONT."
                     elif 150 <= eff_width < 180: txt = "6-%%189PONT."
                     elif 180 <= eff_width < 210: txt = "7-%%189PONT."
                     elif 210 <= eff_width <= 244: txt = "8-%%189PONT."
                     
                     if txt:
                         return f"; Texto Pontaletes\n-LAYER\nS {layer_texto_pontaletes}\n\n;\n_TEXT\nJ\nMC\n{px:.3f},{py:.3f}\n8\n0\n{txt}\n;\n"
                     return ""

                x_painel_acc = x_inicial
                
                # --- PASS 1: H1 PANELS ---
                for i, largura_painel in enumerate(paineis_individuais):
                    altura1 = soma_altura_partes(dados.get('paineis_alturas', [0]*len(paineis_individuais))[i])
                    if altura1 > 0:
                        cmd_bloco = numeracao_cfg.get('comandos', {}).get(str(count), '')
                        if cmd_bloco:
                            cx = x_painel_acc + largura_painel / 2
                            cy = y_inicial + altura1 / 2
                            script += f"; Bloco Num {count} (H1)\n_INSERT\n{cmd_bloco}\n{cx:.3f},{cy:.3f}\n\n\n;\n"
                            
                            # Pontalete H1 (is_h2=False)
                            t1 = dados.get('paineis_tipo1', ["Sarrafeado"]*len(paineis_individuais))[i]
                            pont_script = gen_pont_text(largura_painel, (t1=="Grade"), (i==idx_primeiro), (i==idx_ultimo), aberturas, cx, cy-20, False)
                            script += pont_script
                            
                        count += 1
                    x_painel_acc += largura_painel

                # --- PASS 2: H2 PANELS ---
                x_painel_acc = x_inicial
                for i, largura_painel in enumerate(paineis_individuais):
                    altura1 = soma_altura_partes(dados.get('paineis_alturas', [0]*len(paineis_individuais))[i])
                    altura2 = soma_altura_partes(dados.get('paineis_alturas2', [0]*len(paineis_individuais))[i])
                    sc = float(dados.get('lajes_central_alt', [0]*len(paineis_individuais))[i])
                    
                    if altura2 > 0:
                        cmd_bloco = numeracao_cfg.get('comandos', {}).get(str(count), '')
                        if cmd_bloco:
                            cx = x_painel_acc + largura_painel / 2
                            cy = y_inicial + altura1 + sc + (altura2 / 2)
                            script += f"; Bloco Num {count} (H2)\n_INSERT\n{cmd_bloco}\n{cx:.3f},{cy:.3f}\n\n\n;\n"
                            
                            # Pontalete H2 (is_h2=True)
                            t2 = dados.get('paineis_tipo2', ["Sarrafeado"]*len(paineis_individuais))[i]
                            pont_script = gen_pont_text(largura_painel, (t2=="Grade"), (i==idx_primeiro), (i==idx_ultimo), aberturas, cx, cy-20, True)
                            script += pont_script
                            
                        count += 1
                    x_painel_acc += largura_painel
            return script

    def gerar_script_visao_corte_arquivo(self, dados_A, dados_B, diretorio_saida, index_vc):
        """
        Gera um arquivo .scr separado para a Visão de Corte.
        Nome: VC-{index}_V{Num}.{SufA}_V{Num}.{SufB}.scr
        """
        try:
             # Nomes para o arquivo
            nomeA = dados_A.get('nome', 'SemNomeA')
            nomeB = dados_B.get('nome', 'SemNomeB')
            
            # Limpeza de nomes
            nomeA_clean = nomeA.replace(' ', '_')
            nomeB_clean = nomeB.replace(' ', '_')
            
            filename = f"VC-{index_vc}_{nomeA_clean}_{nomeB_clean}.scr"
            caminho_arquivo = os.path.join(diretorio_saida, filename)
            
            # Coordenadas base: 0,0 (será movido pelo Ordenador)
            # Altura geral pode ser a maior das duas vigas
            try:
                hA = float(dados_A.get('altura_geral', 0))
            except ValueError:
                hA = 0.0
            try:
                hB = float(dados_B.get('altura_geral', 0))
            except ValueError:
                hB = 0.0
            altura_ref = max(hA, hB)
            
            # Gerar conteúdo
            # x_orig, y_orig = 0, 0 -> para facilitar ordenacao
            script_content = self._gerar_secao_corte(dados_A, dados_B, 0, 0)
            
            if not script_content:
                return None

            # Headers para o Ordenador reconhecer
            largura_est = 200 # Estimado da VC
            header = f"; (numeracao: VC-{index_vc}, largura: {largura_est}, altura: {altura_ref})\n;\n"
            
            full_content = header + script_content
            
            with open(caminho_arquivo, "w", encoding="utf-16") as f:
                f.write(full_content)
                
            print(f"[VC] Gerado: {filename}")
            return caminho_arquivo

        except Exception as e:
            traceback.print_exc()
            return None
            



    def _gerar_secao_corte(self, dA, dB, x_orig, y_orig):
        """Gera os comandos AutoCAD para a Visão de Corte (Comparativo A/B)."""
        print(f"DEBUG_SECAO: Iniciando geração de seção de corte. X={x_orig}, Y={y_orig}")
        script = f"; --- VISÃO DE CORTE ---\n"
        
        try:
            # 1. Função Auxiliar de Layers (usando config existente)
            def _l(name):
                return self._get_layer(name)
            
            layer_laje = _l("laje")        # Laje
            layer_paineis = _l("paineis")  # Painéis / Retângulos
            layer_sarrafos_grade = _l("sarrafos_verticais_grades") # Rosa
            layer_sarrafos = _l("sarrafos_verticais") # Padrão
            layer_cotas = _l("cotas")
            layer_texto = _l("nome_observacoes") # Alterado de textos_laterais para nome_observacoes
            layer_parafuso = _l("parafuso")
            
            # Tipo de linha das configurações
            tipo_linha_config = self.config.get('opcoes', {}).get('tipo_linha', 'PLINE')
            
            # 2. Helpers de Geometria
            def get_val(d, key, default=0.0):
                val = d.get(key, default)
                if isinstance(val, (int, float)): return float(val)
                try:
                    return float(str(val).replace(',', '.'))
                except:
                    return default

            # Extração de Dados (Fundo da Viga)
            # Tenta 'fundo_viga' (usado no collect) e 'bottom' (usado no VigaState.to_dict/asdict)
            fundo_A = get_val(dA, 'fundo_viga') or get_val(dA, 'bottom', 0.0)
            fundo_B = get_val(dB, 'fundo_viga') or get_val(dB, 'bottom', 0.0)
            
            # Helper para somar lista de 1 elemento se for lista
            def get_h(d, keys):
                for k in keys:
                    val = d.get(k)
                    if isinstance(val, list) and len(val) > 0:
                        # Assumindo 1 painel para seção de corte ou pegando o maior/primeiro?
                        # O preview pega do primeiro painel.
                         v = val[0]
                         if isinstance(v, (int, float)): return float(v)
                         try: return sum(float(x) for x in str(v).split('+') if x.strip())
                         except: return 0.0
                    if val is not None:
                        # Tenta direto
                        try: return float(val)
                        except: pass
                return 0.0

            h1_A = get_h(dA, ['paineis_alturas', 'altura_geral']) 
            h2_A = get_h(dA, ['paineis_alturas2', 'altura_2_geral'])
            
            h1_B = get_h(dB, ['paineis_alturas', 'altura_geral'])
            h2_B = get_h(dB, ['paineis_alturas2', 'altura_2_geral'])
            
            # Lajes (arrays)
            def get_arr_0(d, key):
                arr = d.get(key, [])
                if arr and len(arr) > 0: return float(arr[0])
                return 0.0
            
            ls_A = get_arr_0(dA, 'lajes_sup'); li_A = get_arr_0(dA, 'lajes_inf'); lc_A = get_arr_0(dA, 'lajes_central_alt')
            ls_B = get_arr_0(dB, 'lajes_sup'); li_B = get_arr_0(dB, 'lajes_inf'); lc_B = get_arr_0(dB, 'lajes_central_alt')
            
            type1_A = dA.get('paineis_tipo1', ['Sarrafeado'])[0]
            type1_B = dB.get('paineis_tipo1', ['Sarrafeado'])[0]
            
            grade_h1_A = dA.get('paineis_grade_altura1', [7.0])[0]
            grade_h1_B = dB.get('paineis_grade_altura1', [7.0])[0]

            # 3. Dimensões Base e Escala (S=2.0 conforme solicitado)
            S = 2.0
            
            w_fundo = max(fundo_A, fundo_B)
            width = w_fundo
            if width <= 0: width = 50.0 # Default
            
            sum_h_A = h1_A + h2_A + ls_A + lc_A + li_A
            sum_h_B = h1_B + h2_B + ls_B + lc_B + li_B
            total_h = max(sum_h_A, sum_h_B, 60.0)

            # 4. Desenho
            


            # ZOOM (Escalado)
            cx = x_orig + (width * S) / 2
            cy = y_orig + (total_h * S) / 2
            script += f"_ZOOM\nC {cx:.3f},{cy:.3f} {(100 * S)}\n;\n"

            # 4.1 FUNDO (Laje/Fundo)
            # Lógica Unified do Preview: Se LI existe em QUALQUER lado, desce tudo.
            has_li_A = (li_A > 0)
            has_li_B = (li_B > 0)
            has_any_li = has_li_A or has_li_B
            
            # Offset vertical base
            # No Preview (Y-down): y_unified = offset se LI.
            # Aqui (Y-up): Vamos definir y=0 da seção como a base da tábua de fundo?
            # Se tiver LI, a tábua de fundo DESCE. 
            # Digamos que y_orig seja o nível "0" de referência (base da parede/viga apoiada).
            # Se tem LI, o fundo é desenhado EM BAIXO de y_orig? 
            # Ou y_orig é o fundo absoluto?
            # Vamos assumir: y_orig é a base do fundo da viga (face inferior da tábua de fundo se não houver LI).
            
            # Ajuste baseado no Preview:
            # Se LI, drop 11.0 (8.8 + 2.2).
            # Vamos simplificar: Desenhar o fundo.
            # Se tem LI, o fundo é mais largo e rebaixado?
            # No preview: y_plate_draw = y_unified + ...
            # Vamos adotar Y locais relativos a y_orig.
            
            # Offset vertical base (Ajuste solicitado)
            # LI: Fundo=4.2, Alinhado. Sem LI: Fundo=10.8, Paredes=8.6 (Fixas)
            if has_any_li:
                y_base_draw = 4.2
                y_start_walls = 4.2 # Alinhado
            else:
                y_base_draw = 10.8
                y_start_walls = 8.6
            
            x_min = -70.0 if has_li_A else 0.0
            x_max = width + 70.0 if has_li_B else width
            
            # Desenha FUNDO (Escalado)
            script += f"-LAYER\nS {layer_paineis}\n\n;\n_PLINE\n"
            script += f"{(x_orig + x_min * S):.3f},{(y_orig + y_base_draw * S):.3f}\n"
            script += f"{(x_orig + x_max * S):.3f},{(y_orig + y_base_draw * S):.3f}\n"
            script += f"{(x_orig + x_max * S):.3f},{(y_orig + (y_base_draw + 2.0) * S):.3f}\n"
            script += f"{(x_orig + x_min * S):.3f},{(y_orig + (y_base_draw + 2.0) * S):.3f}\n"
            script += "C\n;\n"
            
            # Helper Rect (Escalado)
            def draw_rect(x, y, w, h, style=None):
                x_val = x_orig + x * S
                y_val = y_orig + y * S
                w_sc = w * S
                h_sc = h * S
                
                use_mline = (tipo_linha_config == "MLINE" and style != "PLINE")
                
                if use_mline:
                    m_style = style if style else "SAR3"
                    if w > h:
                        # MLINE Horizontal
                        m_scale = h_sc * 2 if m_style == "MEIOPONT" else h_sc
                        return f"_CMLSTYLE\n{m_style}\n_CMLJUST\n2\n_CMLSCALE\n{m_scale:.3f}\n_MLINE\n{x_val:.3f},{y_val:.3f}\n{(x_val+w_sc):.3f},{y_val:.3f}\n\n;\n"
                    else:
                        # MLINE Vertical
                        m_scale = w_sc * 2 if m_style == "MEIOPONT" else w_sc
                        return f"_CMLSTYLE\n{m_style}\n_CMLJUST\n2\n_CMLSCALE\n{m_scale:.3f}\n_MLINE\n{(x_val+w_sc):.3f},{y_val:.3f}\n{(x_val+w_sc):.3f},{(y_val+h_sc):.3f}\n\n;\n"
                else:
                    x2 = x_val + w_sc
                    y2 = y_val + h_sc
                    return f"_PLINE\n{x_val:.3f},{y_val:.3f}\n{x2:.3f},{y_val:.3f}\n{x2:.3f},{y2:.3f}\n{x_val:.3f},{y2:.3f}\nC\n;\n"

            # 4.2 SARRAFOS DE FUNDO E LATERAIS (Padrão Canvas)
            if w_fundo > 0:
                script += f"-LAYER\nS {layer_sarrafos}\n\n;\n"
                
                # Nível base abaixo do fundo
                y_sar_base = y_base_draw - 2.2
                
                # 4.2.1 Sarrafos Laterais do Fundo (10.0 x 2.2) e Cópias Verticais
                # Regras: Cópias em +22/+26 (H>40) e +72/+76 (H>90). Somente se ambos NÃO tiverem LI.
                
                allow_base_ext = (not has_li_A) and (not has_li_B)
                allow_40_ext = allow_base_ext and (h1_A > 40 and h1_B > 40)
                allow_90_ext = allow_base_ext and (h1_A > 90 and h1_B > 90)
                
                # Lista de níveis Y para os sarrafos lateral/apoio
                y_levels = [y_sar_base] # Base sempre existe
                if allow_40_ext:
                    y_levels.extend([y_sar_base + 22.0 - 0.10, y_sar_base + 26.0 - 0.10])
                if allow_90_ext:
                    y_levels.extend([y_sar_base + 72.0 - 0.10, y_sar_base + 76.0 - 0.10])
                
                # Offsets solicitados: 8.8cm para Grade, 4.0cm para Sarrafo (Ajustado -0.2cm para dentro)
                off_A = 8.8 if "Grade" in type1_A else 4.0
                off_B = 8.8 if "Grade" in type1_B else 4.0
                
                for y_lev in y_levels:
                    x_center_A = None
                    x_center_B = None

                    # Lado A
                    # Regra: Se tem LI, não desenha sarrafo de apoio abaixo do fundo (y_lev < y_base_draw)
                    if not has_li_A:
                        if not (y_lev < y_base_draw and has_any_li):
                            x_sar_A = (x_min - 10.0) - off_A
                            script += draw_rect(x_sar_A, y_lev, 10.0, 2.2, style="SAR3")
                            x_center_A = x_sar_A + 5.0
                    
                    # Lado B
                    if not has_li_B:
                        if not (y_lev < y_base_draw and has_any_li):
                            x_sar_B = x_max + off_B
                            script += draw_rect(x_sar_B, y_lev, 10.0, 2.2, style="SAR3")
                            x_center_B = x_sar_B + 5.0

                    # 4.2.1.1 Conector para este nível (1cm espessura, 1cm abaixo do nível atual)
                    # Regra solicitada: Apenas 1 conector por par (no sarrafo de cima).
                    # Níveis com conector: y_sar_base, y_sar_base + 26.0, y_sar_base + 76.0
                    needs_connector = False
                    is_base = abs(y_lev - y_sar_base) < 0.01
                    if is_base: needs_connector = True
                    elif abs(y_lev - (y_sar_base + 26.0 - 0.10)) < 0.01: needs_connector = True
                    elif abs(y_lev - (y_sar_base + 76.0 - 0.10)) < 0.01: needs_connector = True

                    if needs_connector and x_center_A is not None and x_center_B is not None:
                        script += f"-LAYER\nS {layer_parafuso}\n\n;\n"
                        
                        y_val_conn = y_lev - 1.0 - 1.0
                        
                        if is_base:
                            # Ajustes: Retângulo encolhe 0.9 de cada lado. Extra move 5.85 esq.
                            x_draw_start = x_center_A + 0.9
                            x_draw_end = x_center_B - 0.9
                            w_conn = x_draw_end - x_draw_start
                            
                            script += draw_rect(x_draw_start, y_val_conn, w_conn, 1.0, style="PLINE")
                            
                            x_extra = x_center_B + 20.0 - 5.85 - 5.0
                            script += draw_rect(x_extra, y_val_conn, 12.0, 1.0, style="PLINE")
                            
                            # Insert Blocks nos cantos ajustados
                            y_ins_base = y_orig + (y_val_conn + 0.5) * S
                            
                            # Ponta Esquerda
                            x_ins_esq = x_orig + x_draw_start * S
                            script += f"_INSERT\nPAR_FUNDO_ESQ\n{x_ins_esq:.3f},{y_ins_base:.3f}\n1.0\n0\n;\n"
                            
                            # Ponta Direita
                            x_ins_dir = x_orig + x_draw_end * S
                            script += f"_INSERT\nPAR_FUNDO_DIR\n{x_ins_dir:.3f},{y_ins_base:.3f}\n1.0\n0\n;\n"
                        else:
                            y_val_conn += 0.6
                            
                            # Retângulo extra interno (2cm de altura)
                            # Fixando no CENTRO da Viga (Fundo)
                            center_beam = (x_min + x_max) / 2.0
                            fundo_width = x_max - x_min
                            
                            # Largura deve ser proporcional ao fundo (Fundo - 4.0cm para manter recuo interno padrao)
                            w_inner = fundo_width - 4.0
                            
                            # Ajuste fino: mover 1cm para esquerda
                            center_beam -= 1.0 
                            
                            x_in_start = center_beam - (w_inner / 2.0)
                            x_in_end = center_beam + (w_inner / 2.0)
                            
                            y_inner_base = y_val_conn - 0.5
                            
                            script += draw_rect(x_in_start, y_inner_base, w_inner, 2.0, style="PLINE")

                            # Insert Blocks nas pontas internas
                            # Centro do retângulo de 2cm é y_inner_base + 1.0 = (y_val_conn - 0.5) + 1.0 = y_val_conn + 0.5
                            y_ins_inner = y_orig + (y_val_conn + 0.5) * S 
                            
                            # Ponta Esquerda
                            x_ins_in_esq = x_orig + x_in_start * S
                            script += f"_INSERT\npar_int_esq\n{x_ins_in_esq:.3f},{y_ins_inner:.3f}\n1.0\n0\n;\n"
                            
                            # Ponta Direita
                            x_ins_in_dir = x_orig + x_in_end * S
                            script += f"_INSERT\npar_int_dir\n{x_ins_in_dir:.3f},{y_ins_inner:.3f}\n1.0\n0\n;\n"

                            x_start = x_center_A - 18.0
                            x_end = x_center_B + 3.5 + 1.5 # Estende +1.5cm conforme solicitado
                            w_conn = x_end - x_start
                            script += draw_rect(x_start, y_val_conn, w_conn, 1.0, style="PLINE")
                            
                            y_vert_rect = y_val_conn + 0.5 - 3.0
                            script += draw_rect(x_end, y_vert_rect, 1.2, 6.0, style="PLINE")
                            
                            block_name = self.config.get('opcoes', {}).get('parafuso_block', 'PAR_ESQ')
                            # Ajuste solicitado: Mover +28cm para a direita (era -15, agora +13 em relação a x_start)
                            # Ou mover 28 relativo à posição antiga (-15 + 28 = +13)
                            x_ins = x_orig + (x_start - 15.0 + 28.0) * S
                            y_ins = y_orig + (y_val_conn + 0.5) * S
                            script += f"_INSERT\n{block_name}\n{x_ins:.3f},{y_ins:.3f}\n1.0\n0\n;\n"
                        
                            
                            # Capture coordinates for dimensions
                            if abs(y_lev - (y_sar_base + 26.0 - 0.10)) < 0.01:
                                pos_conn_25 = {'x_end': x_end, 'y_val': y_val_conn}
                            elif abs(y_lev - (y_sar_base + 76.0 - 0.10)) < 0.01:
                                pos_conn_75 = {'x_end': x_end, 'y_val': y_val_conn}
                        
                        script += f"-LAYER\nS {layer_sarrafos}\n\n;\n"
            
            # Cotas Verticais de Parafusos (Solicitadas)
            # 1. Do parafuso 25 até o fundo do H1 (y_start_walls)
            if 'pos_conn_25' in locals():
                x_cota = x_orig + (pos_conn_25['x_end'] + 30.0) * S
                x_ponto = x_orig + pos_conn_25['x_end'] * S
                y_ponto_25 = y_orig + (pos_conn_25['y_val'] + 0.5) * S # Centro do parafuso
                y_h1_bot = y_orig + y_start_walls * S
                
                script += f"-DIMSTYLE\nR\nCOTAX2\n-LAYER\nS {layer_cotas}\n\n;\n"
                script += f"_DIMLINEAR\n{x_ponto},{y_h1_bot}\n{x_ponto},{y_ponto_25}\n{x_cota},{(y_h1_bot + y_ponto_25)/2}\n;\n"

            # 2. Do parafuso 75 até o parafuso 25
            if 'pos_conn_25' in locals() and 'pos_conn_75' in locals():
                x_cota_75 = x_orig + (pos_conn_75['x_end'] + 30.0) * S
                x_ponto_75 = x_orig + pos_conn_75['x_end'] * S
                y_ponto_75 = y_orig + (pos_conn_75['y_val'] + 0.5) * S
                y_ponto_25 = y_orig + (pos_conn_25['y_val'] + 0.5) * S
                
                script += f"_DIMLINEAR\n{x_ponto_75},{y_ponto_25}\n{x_ponto_75},{y_ponto_75}\n{x_cota_75},{(y_ponto_25 + y_ponto_75)/2}\n;\n"

            # 4.2.2 Quadradinhos de Fundo (2.2 x 7) - Apoio da VIGA (0 a width)
            # Regra: Se houver laje inferior, não desenha sarrafos de apoio abaixo do fundo
            if not has_any_li:
                script += f"-LAYER\nS {layer_sarrafos}\n\n;\n"
                h_sq = 2.2
                w_sq = 7.0

                if width <= 10:
                    script += draw_rect(0, y_sar_base, width, h_sq, style="SAR3")
                else:
                    # Nas esquinas da VIGA (0 e width)
                    script += draw_rect(0, y_sar_base, w_sq, h_sq, style="SAR3")
                    script += draw_rect(width - w_sq, y_sar_base, w_sq, h_sq, style="SAR3")
                    
                    # Intermediários a cada 30cm (dentro da viga)
                    if width > 30:
                        num_center = int((width - 0.001) // 30)
                        gap_w = (width - 14.0 - (num_center * 7.0)) / (num_center + 1)
                        for k in range(1, num_center + 1):
                            x_p = 7.0 + (k * gap_w) + ((k-1) * 7.0)
                            script += draw_rect(x_p, y_sar_base, 7.0, h_sq, style="SAR3")

            # 4.3 FLANCOS LATERAIS (A e B)
            # Base Y para paredes definida acima conforme LI
            # y_start_walls já calculado
            
            sides = [
                {'data': dA, 'is_A': True, 'x_wall': -1.8, 'h1': h1_A, 'h2': h2_A, 'li': li_A, 'lc': lc_A, 'ls': ls_A, 'type1': type1_A, 'gh1': grade_h1_A, 'dir': -1},
                {'data': dB, 'is_A': False, 'x_wall': width, 'h1': h1_B, 'h2': h2_B, 'li': li_B, 'lc': lc_B, 'ls': ls_B, 'type1': type1_B, 'gh1': grade_h1_B, 'dir': 1}
            ]
            
            max_y_reached = 0.0

            for cfg in sides:
                cur_y = y_start_walls
                
                # 1. LI (Rebaixo/Laje Inferior)
                if cfg['li'] > 0:
                    h_li = cfg['li']
                    script += f"-LAYER\nS {layer_laje}\n\n;\n"
                    lx_start = 0 if cfg['is_A'] else width
                    lx_end = lx_start + (70.0 * cfg['dir'])
                    
                    # Linha da Laje (Escalada)
                    y_laje = cur_y + h_li
                    script += f"_PLINE\n{(x_orig + lx_start * S):.3f},{(y_orig + y_laje * S):.3f}\n{(x_orig + lx_end * S):.3f},{(y_orig + y_laje * S):.3f}\n\n;\n"
                    cur_y += h_li
                    
                # 2. H1 (Parede)
                if cfg['h1'] > 0:
                    script += f"-LAYER\nS {layer_paineis}\n\n;\n"
                    wx = cfg['x_wall']
                    wy = cur_y
                    script += draw_rect(wx, wy, 1.8, cfg['h1'], style="PLINE")
                    
                    # Sarrafos / Grades H1
                    s_type = cfg['type1']
                    s_style = "MEIOPONT" if "Grade" in s_type else "SAR3"
                    s_width = 7.0 if "Grade" in s_type else 2.2
                    
                    # Altura do montante vertical recuada 2.2cm
                    h_vert = cfg['h1'] - 2.2
                    sx_sar = (wx - s_width) if cfg['is_A'] else (wx + 1.8)
                    
                    # Recuo no topo: Montante vertical para 2.2cm abaixo do topo da parede
                    script += f"-LAYER\nS {(layer_sarrafos_grade if 'Grade' in s_type else layer_sarrafos)}\n\n;\n"
                    script += draw_rect(sx_sar, wy, s_width, h_vert, style=s_style)
                    
                    # Sarrafo Horizontal de Topo (2.2x7) preenchendo o vão
                    y_topo = wy + h_vert
                    if cfg['is_A']:
                        # Lado A: Expande para a esquerda a partir da face externa do montante
                        x_topo = sx_sar + s_width - 7.0
                    else:
                        # Lado B: Expande para a direita a partir da face externa do montante
                        x_topo = sx_sar
                    
                    script += f"-LAYER\nS {layer_sarrafos}\n\n;\n"
                    script += draw_rect(x_topo, y_topo, 7.0, 2.2, style="SAR3")
                    
                    cur_y += cfg['h1']

                # 3. LC (Laje Central)
                if cfg['lc'] > 0:
                    h_block = 2.0 # Ajustado para 2.0
                    lx_start = 0 if cfg['is_A'] else width
                    lx_now = lx_start + (70.0 * cfg['dir'])
                    
                    # Retângulo Inferior (Vermelho/Sarrafos) -> Sempre PLINE
                    script += f"-LAYER\nS {layer_sarrafos}\n\n;\n"
                    r_x = min(lx_start, lx_now)
                    script += draw_rect(r_x, cur_y, 70.0, h_block, style="PLINE")
                    
                    # Linha Superior (Laje)
                    script += f"-LAYER\nS {layer_laje}\n\n;\n"
                    y_top_lc = cur_y + cfg['lc']
                    script += f"_PLINE\n{(x_orig + lx_start * S):.3f},{(y_orig + y_top_lc * S):.3f}\n{(x_orig + lx_now * S):.3f},{(y_orig + y_top_lc * S):.3f}\n\n;\n"
                    
                    cur_y += cfg['lc']

                # 4. H2
                if cfg['h2'] > 0:
                     script += f"-LAYER\nS {layer_paineis}\n\n;\n"
                     wx = cfg['x_wall']
                     wy = cur_y
                     script += draw_rect(wx, wy, 1.8, cfg['h2'], style="PLINE")
                     
                     # Sarrafo H2 (Agora com largura de 7.0 para Grades)
                     s_type = cfg['type1']
                     s_style = "MEIOPONT" if "Grade" in s_type else "SAR3"
                     s_width = 7.0 if "Grade" in s_type else 2.2
                     
                     # Altura do montante vertical recuada 2.2cm
                     h_vert = cfg['h2'] - 2.2
                     sx_sar = (wx - s_width) if cfg['is_A'] else (wx + 1.8)
                     
                     script += f"-LAYER\nS {(layer_sarrafos_grade if 'Grade' in s_type else layer_sarrafos)}\n\n;\n"
                     script += draw_rect(sx_sar, wy, s_width, h_vert, style=s_style)
                     
                     # Sarrafo Horizontal de Topo (2.2x7) preenchendo o vão
                     y_topo = wy + h_vert
                     if cfg['is_A']:
                        x_topo = sx_sar + s_width - 7.0
                     else:
                        x_topo = sx_sar
                     
                     script += f"-LAYER\nS {layer_sarrafos}\n\n;\n"
                     script += draw_rect(x_topo, y_topo, 7.0, 2.2, style="SAR3")
                     
                     cur_y += cfg['h2']

                # 5. LS (Laje Superior)
                if cfg['ls'] > 0:
                    h_block = 2.0 # Ajustado para 2.0
                    lx_start = 0 if cfg['is_A'] else width
                    lx_now = lx_start + (70.0 * cfg['dir'])
                    
                    # Retângulo Inferior (Sarrafos) -> Sempre PLINE conforme contexto de acessórios
                    script += f"-LAYER\nS {layer_sarrafos}\n\n;\n"
                    r_x = min(lx_start, lx_now)
                    script += draw_rect(r_x, cur_y, 70.0, h_block, style="PLINE")

                    # Linha Superior (Laje)
                    script += f"-LAYER\nS {layer_laje}\n\n;\n"
                    y_top_ls = cur_y + cfg['ls']
                    script += f"_PLINE\n{(x_orig + lx_start * S):.3f},{(y_orig + y_top_ls * S):.3f}\n{(x_orig + lx_now * S):.3f},{(y_orig + y_top_ls * S):.3f}\n\n;\n"
                    
                    cur_y += cfg['ls']
                
                if cur_y > max_y_reached: max_y_reached = cur_y
            
            # --- COTAS DETALHADAS (Estilo Canvas) ---
            # --- COTAS --- (Usando DIMSTYLE COTAX2 para escala 2x)
            script += f"-DIMSTYLE\nR\nCOTAX2\n-LAYER\nS {layer_cotas}\n\n;\n"
            
            # 1. Cota Largura Total (Topo) -> REMOVIDO (User: "nao necessito")
            # dim_y_top = y_orig + max_y_reached + 20
            # script += ...

            # 2. Cota Vão Interno (Baixo - Letra C) (Escalada)
            dim_y_bot = y_orig + (y_base_draw + 2.0) * S
            script += f"_DIMLINEAR\n{(x_orig):.3f},{(y_orig + y_base_draw * S):.3f}\n{(x_orig + width * S):.3f},{(y_orig + y_base_draw * S):.3f}\n{(x_orig + (width * S) / 2):.3f},{(dim_y_bot):.3f}\n;\n"
            
            # 3. Cota Altura Total (Interna Direita) (Escalada)
            x_dim_interna = x_orig + (width - 2.0) * S
            y_start_dim_interna = (y_base_draw + 2.0) if has_any_li else 12.6
            script += f"_DIMLINEAR\n{(x_orig + width * S):.3f},{(y_orig + y_start_dim_interna * S):.3f}\n{(x_orig + width * S):.3f},{(y_orig + max_y_reached * S):.3f}\n{(x_dim_interna):.3f},{(y_orig + (max_y_reached * S) / 2):.3f}\n;\n"
            
            # 4.1. Cotas em Cadeia (Esquerda) (Escalada) - EXTRA
            # "70cm para a esquerda" -> x_orig - 70.0 * S
            x_dim_left = x_orig - 70.0 * S
            cfg_A = sides[0]
            dim_y_A = y_start_walls
            
            for k_comp, h_val in [('li', cfg_A['li']), ('h1', cfg_A['h1']), ('lc', cfg_A['lc']), ('h2', cfg_A['h2']), ('ls', cfg_A['ls'])]:
                if h_val > 0:
                    # Ajuste solicitado: "cota das lajes... deve ser 2cm menor, subindo a ponta de baixo para cima"
                    offset_y_dim = 2.0 if k_comp in ['li', 'lc', 'ls'] else 0.0
                    
                    # Texto da cota 20cm a ESQUERDA da linha de cota
                    x_text_loc = x_dim_left - 20.0 * S
                    script += f"_DIMLINEAR\n{(x_dim_left):.3f},{(y_orig + (dim_y_A + offset_y_dim) * S):.3f}\n{(x_dim_left):.3f},{(y_orig + (dim_y_A + h_val) * S):.3f}\n{(x_text_loc):.3f},{(y_orig + (dim_y_A + h_val/2) * S):.3f}\n;\n"
                    dim_y_A += h_val

            # 4.2. Cotas em Cadeia (Direita) (Escalada)
            x_dim_right = x_orig + (width + 70.0) * S
            cfg_B = sides[1]
            dim_y = y_start_walls
                
            for k_comp, h_val in [('li', cfg_B['li']), ('h1', cfg_B['h1']), ('lc', cfg_B['lc']), ('h2', cfg_B['h2']), ('ls', cfg_B['ls'])]:
                if h_val > 0:
                    # Ajuste solicitado: "cota das lajes... deve ser 2cm menor, subindo a ponta de baixo para cima"
                    offset_y_dim = 2.0 if k_comp in ['li', 'lc', 'ls'] else 0.0
                    
                    script += f"_DIMLINEAR\n{(x_dim_right):.3f},{(y_orig + (dim_y + offset_y_dim) * S):.3f}\n{(x_dim_right):.3f},{(y_orig + (dim_y + h_val) * S):.3f}\n{(x_dim_right):.3f},{(y_orig + (dim_y + h_val/2) * S):.3f}\n;\n"
                    dim_y += h_val

            # 5. Cota Total Direita (Escalada)
            y_start_total = 4.2 if has_any_li else 8.6
            x_dim_total_right = x_orig + (width + 90.0) * S
            script += f"_DIMLINEAR\n{(x_orig + width * S):.3f},{(y_orig + y_start_total * S):.3f}\n{(x_orig + width * S):.3f},{(y_orig + max_y_reached * S):.3f}\n{(x_dim_total_right):.3f},{(y_orig + (max_y_reached * S) / 2):.3f}\n;\n"

            
            # --- TEXTOS / LABELS ---
            script += f"-LAYER\nS {layer_texto}\n\n;\n"
            
            # A e B (Escalados)
            # A e B (Escalados)
            # Solicitado: A move 7cm dir (era -40 -> -33)
            # Solicitado: B move 6cm esq (era +27 -> +21)
            y_label_A = y_orig + (15 + li_A) * S
            y_label_B = y_orig + (15 + li_B) * S
            
            script += f"_TEXT\n{(x_orig - 33 * S):.3f},{(y_label_A):.3f}\n{15 * S}\n0\nA\n;\n"
            script += f"_TEXT\n{(x_orig + (width + 21) * S):.3f},{(y_label_B):.3f}\n{15 * S}\n0\nB\n;\n"
            
            # C (Escalado)
            script += f"_TEXT\nC\n{(x_orig + (width * S) / 2):.3f},{(y_orig - 15 * S):.3f}\n{15 * S}\n0\nC\n;\n"

            # Titulo (Escalado apenas posição e altura)
            nome_display = dA.get('nome','').split('.')[0]
            h_text_display = (total_h - 2) if has_any_li else (total_h - 4)
            dims_text = f"{width:.0f}x{h_text_display:.0f}"
            
            y_titulo = y_orig + (max_y_reached + 60) * S
            script += f"_TEXT\nC\n{(x_orig + (width * S) / 2):.3f},{(y_titulo):.3f}\n{20 * S}\n0\n{nome_display}\n;\n"
            script += f"_TEXT\nC\n{(x_orig + (width * S) / 2):.3f},{(y_titulo - 25 * S):.3f}\n{15 * S}\n0\n({dims_text})\n;\n"
            
            script += "; --- FIM VISÃO DE CORTE ---\n\n"
            return script
            
        except Exception as e:
            traceback.print_exc()
            return f"; Erro ao gerar secao de corte: {str(e)}\n"


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