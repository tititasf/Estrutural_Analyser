
# Helper de ofuscação (adicionado automaticamente)
def _get_obf_str(key):
    """Retorna string ofuscada"""
    _obf_map = {
        _get_obf_str("script.google.com"): base64.b64decode("=02bj5SZsd2bvdmL0BXayN2c"[::-1].encode()).decode(),
        _get_obf_str("macros/s/"): base64.b64decode("vM3Lz9mcjFWb"[::-1].encode()).decode(),
        _get_obf_str("AKfycbz"): base64.b64decode("==geiNWemtUQ"[::-1].encode()).decode(),
        _get_obf_str("credit"): base64.b64decode("0lGZlJ3Y"[::-1].encode()).decode(),
        _get_obf_str("saldo"): base64.b64decode("=8GZsF2c"[::-1].encode()).decode(),
        _get_obf_str("consumo"): base64.b64decode("==wbtV3cu92Y"[::-1].encode()).decode(),
        _get_obf_str("api_key"): base64.b64decode("==Qelt2XpBXY"[::-1].encode()).decode(),
        _get_obf_str("user_id"): base64.b64decode("==AZp9lclNXd"[::-1].encode()).decode(),
        _get_obf_str("calcular_creditos"): base64.b64decode("=M3b0lGZlJ3YfJXYsV3YsF2Y"[::-1].encode()).decode(),
        _get_obf_str("confirmar_consumo"): base64.b64decode("=8Wb1NnbvN2XyFWbylmZu92Y"[::-1].encode()).decode(),
        _get_obf_str("consultar_saldo"): base64.b64decode("vRGbhN3XyFGdsV3cu92Y"[::-1].encode()).decode(),
        _get_obf_str("debitar_creditos"): base64.b64decode("==wcvRXakVmcj9lchRXaiVGZ"[::-1].encode()).decode(),
        _get_obf_str("CreditManager"): base64.b64decode("==gcldWYuFWT0lGZlJ3Q"[::-1].encode()).decode(),
        _get_obf_str("obter_hwid"): base64.b64decode("==AZpdHafJXZ0J2b"[::-1].encode()).decode(),
        _get_obf_str("generate_signature"): base64.b64decode("lJXd0Fmbnl2cfVGdhJXZuV2Z"[::-1].encode()).decode(),
        _get_obf_str("encrypt_string"): base64.b64decode("=cmbpJHdz9Fdwlncj5WZ"[::-1].encode()).decode(),
        _get_obf_str("decrypt_string"): base64.b64decode("=cmbpJHdz9FdwlncjVGZ"[::-1].encode()).decode(),
        _get_obf_str("integrity_check"): base64.b64decode("rNWZoN2X5RXaydWZ05Wa"[::-1].encode()).decode(),
        _get_obf_str("security_utils"): base64.b64decode("=MHbpRXdflHdpJXdjV2c"[::-1].encode()).decode(),
        _get_obf_str("https://"): base64.b64decode("=8yL6MHc0RHa"[::-1].encode()).decode(),
        _get_obf_str("google.com"): base64.b64decode("==QbvNmLlx2Zv92Z"[::-1].encode()).decode(),
        _get_obf_str("apps.script"): base64.b64decode("=QHcpJ3Yz5ycwBXY"[::-1].encode()).decode(),
    }
    return _obf_map.get(key, key)

from difflib import restore
import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import math
from datetime import datetime
import logging
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import win32com.client
import pyautogui
import time
import json
import traceback
from typing import Optional, Union

# IMPORTAR HELPER FROZEN GLOBAL - garante que paths estão configurados
try:
    from _frozen_helper import ensure_paths
    ensure_paths()
except ImportError:
    try:
        from src._frozen_helper import ensure_paths
        ensure_paths()
    except ImportError:
        try:
            from _ensure_frozen import ensure
            ensure()
        except ImportError:
            # Fallback manual
            if getattr(sys, 'frozen', False):
                script_dir = os.path.dirname(sys.executable)
                if script_dir not in sys.path:
                    sys.path.insert(0, script_dir)
                src_dir = os.path.join(script_dir, 'src')
                if os.path.exists(src_dir) and src_dir not in sys.path:
                    sys.path.insert(0, src_dir)
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                parent_dir = os.path.dirname(current_dir)
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)

# DEBUG PARAFUSOS - Importar logger específico com múltiplos fallbacks
try:
    from ..utils.debug_parafusos_logger import get_debug_parafusos_logger
    debug_parafusos = get_debug_parafusos_logger()
except Exception:
    try:
        from utils.debug_parafusos_logger import get_debug_parafusos_logger
        debug_parafusos = get_debug_parafusos_logger()
    except Exception:
        try:
            from src.utils.debug_parafusos_logger import get_debug_parafusos_logger
            debug_parafusos = get_debug_parafusos_logger()
        except Exception:
            debug_parafusos = None

# Resolver caminhos de forma robusta com múltiplos fallbacks
try:
    from ..utils.robust_path_resolver import robust_path_resolver
except Exception:
    try:
        from utils.robust_path_resolver import robust_path_resolver
    except Exception:
        try:
            from src.utils.robust_path_resolver import robust_path_resolver
        except Exception:
            robust_path_resolver = None

# Configurar logging
logging.basicConfig(
    filename='pilares.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Sistema de logs de depuração com múltiplos fallbacks
try:
    from ..utils.debug_logger import get_robo_cima_logger
    robo_logger = get_robo_cima_logger()
except ImportError:
    try:
        from utils.debug_logger import get_robo_cima_logger
        robo_logger = get_robo_cima_logger()
    except ImportError:
        try:
            from src.utils.debug_logger import get_robo_cima_logger
            robo_logger = get_robo_cima_logger()
        except ImportError:
            robo_logger = None

# Variável global para armazenar a instância ativa do GeradorPilar
_instancia_gerador_pilar = None

# Variável global para armazenar as globais do pilar especial
_globais_pilar_especial = {}

def obter_instancia_gerador_pilar():
    """
    Retorna a instância global do gerador de pilares.
    """
    global _instancia_gerador_pilar
    return _instancia_gerador_pilar

def definir_checkbox_pilar_rotacionado(ativar):
    """
    Ativa ou desativa o checkbox "Pilar Rotacionado" na instância global.
    CORREÇÃO: Sincroniza também o pilar_especial_ativo_var.
    """
    global _instancia_gerador_pilar
    if _instancia_gerador_pilar and hasattr(_instancia_gerador_pilar, 'pilar_rotacionado_var'):
        _instancia_gerador_pilar.pilar_rotacionado_var.set(ativar)
        
        # Sincronizar também o pilar_especial_ativo_var
        if hasattr(_instancia_gerador_pilar, 'pilar_especial_ativo_var'):
            _instancia_gerador_pilar.pilar_especial_ativo_var.set(ativar)
            print(f"Checkbox 'Pilar Especial Ativo' sincronizado: {ativar}")
        
        status = "ATIVADO" if ativar else "DESATIVADO"
        print(f"Checkbox 'Pilar Rotacionado' {status} via funcao global")
        if robo_logger:
            robo_logger.info(f"Checkbox 'Pilar Rotacionado' {status} via funcao global")
        return True
    else:
        print("Instancia do GeradorPilar nao disponivel para alterar checkbox")
        if robo_logger:
            robo_logger.warning("Instancia do GeradorPilar nao disponivel para alterar checkbox")
        return False

def definir_dados_parafusos_especiais(dados_parafusos):
    """
    Define os dados de parafusos especiais para uso no robô.
    
    Args:
        dados_parafusos: Dicionário com os dados dos parafusos especiais
        
    Returns:
        bool: True se os dados foram definidos com sucesso
    """
    global _instancia_gerador_pilar
    try:
        if _instancia_gerador_pilar:
            _instancia_gerador_pilar._dados_parafusos_especiais = dados_parafusos
            print(f"[PARAFUSOS_ESPECIAIS] Dados de parafusos especiais definidos no gerador: {len(dados_parafusos)} grupos")
            if robo_logger:
                robo_logger.info(f"Dados de parafusos especiais definidos: {len(dados_parafusos)} grupos")
            return True
        else:
            print(f"[PARAFUSOS_ESPECIAIS] Instância do gerador não disponível")
            return False
    except Exception as e:
        print(f"[ERRO] Erro ao definir dados de parafusos especiais: {str(e)}")
        return False

def definir_globais_pilar_especial(globais):
    """
    Define as globais do pilar especial para uso no robô.
    
    Args:
        globais: Dicionário com as globais calculadas
        
    Returns:
        bool: True se as globais foram definidas com sucesso
    """
    global _globais_pilar_especial
    try:
        print(f"[DEBUG-DEFINIR] Recebido para definir: {type(globais)} com {len(globais) if globais else 0} itens")
        print(f"[DEBUG-DEFINIR] ID do objeto globais recebido: {id(globais)}")
        print(f"[DEBUG-DEFINIR] _globais_pilar_especial ANTES: ID={id(_globais_pilar_especial)}, len={len(_globais_pilar_especial) if _globais_pilar_especial else 0}")
        
        if robo_logger:
            robo_logger.subsection("DEFINIÇÃO DE GLOBAIS PILAR ESPECIAL")
            robo_logger.info(f"🔄 Recebido para definir: {type(globais)} com {len(globais) if globais else 0} itens")
            robo_logger.info(f"🔄 ID do objeto globais recebido: {id(globais)}")
            robo_logger.info(f"🔄 _globais_pilar_especial ANTES: ID={id(_globais_pilar_especial)}, len={len(_globais_pilar_especial) if _globais_pilar_especial else 0}")
        
        _globais_pilar_especial = globais
        
        print(f"[DEBUG-DEFINIR] _globais_pilar_especial APÓS: ID={id(_globais_pilar_especial)}, len={len(_globais_pilar_especial) if _globais_pilar_especial else 0}")
        print(f"[DEBUG-DEFINIR] Verificação de igualdade: globais is _globais_pilar_especial = {globais is _globais_pilar_especial}")
        
        if robo_logger:
            robo_logger.info(f"🔄 _globais_pilar_especial APÓS: ID={id(_globais_pilar_especial)}, len={len(_globais_pilar_especial) if _globais_pilar_especial else 0}")
            robo_logger.info(f"🔄 Verificação de igualdade: globais is _globais_pilar_especial = {globais is _globais_pilar_especial}")
        
        if globais:
            print(f"[DEBUG-DEFINIR] Amostra de chaves recebidas: {list(globais.keys())[:3]}")
            print(f"[DEBUG-DEFINIR] Amostra de chaves armazenadas: {list(_globais_pilar_especial.keys())[:3]}")
            
            if robo_logger:
                robo_logger.info(f"🔄 Amostra de chaves recebidas: {list(globais.keys())[:3]}")
                robo_logger.info(f"🔄 Amostra de chaves armazenadas: {list(_globais_pilar_especial.keys())[:3]}")
        
        print(f"[OK] Globais do pilar especial definidas: {len(globais)} valores")
        print(f"   Tipo: {globais.get('tipo_pilar', 'N/A')}")
        print(f"   Dimensões: comp_1={globais.get('comp_1', 'N/A')}, comp_2={globais.get('comp_2', 'N/A')}")
        print(f"   Larguras: larg_1={globais.get('larg_1', 'N/A')}, larg_2={globais.get('larg_2', 'N/A')}")
        
        if robo_logger:
            robo_logger.info(f"✅ Globais do pilar especial definidas: {len(globais)} valores")
            robo_logger.info(f"   Tipo: {globais.get('tipo_pilar', 'N/A')}")
            robo_logger.info(f"   Dimensões: comp_1={globais.get('comp_1', 'N/A')}, comp_2={globais.get('comp_2', 'N/A')}")
            robo_logger.info(f"   Larguras: larg_1={globais.get('larg_1', 'N/A')}, larg_2={globais.get('larg_2', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"[ERRO] Erro ao definir globais do pilar especial: {str(e)}")
        if robo_logger:
            robo_logger.error(f"Erro ao definir globais do pilar especial: {str(e)}")
            robo_logger.error(f"Traceback: {traceback.format_exc()}")
        import traceback
        traceback.print_exc()
        return False

def obter_globais_pilar_especial():
    """
    Retorna as globais do pilar especial armazenadas.
    
    Returns:
        dict: Dicionário com as globais ou {} se vazio
    """
    global _globais_pilar_especial
    return _globais_pilar_especial.copy() if _globais_pilar_especial else {}

def aplicar_alteracao_pilar_especial(valor_original, tipo_alteracao, componente, pilar_num=None, gerador=None):
    """
    Aplica alterações das globais do pilar especial aos valores originais.
    
    Args:
        valor_original: Valor original da coordenada ou tamanho
        tipo_alteracao: 'posicao' ou 'tamanho'
        componente: 'grade_a', 'grade_b', 'parafuso', 'pai_a', 'pai_b', 'metal_a', 'metal_b'
        pilar_num: 1 ou 2 (para pilares específicos)
        gerador: Instância do gerador (opcional)
    
    Returns:
        float: Valor alterado ou valor original se não houver alteração
    """
    # SOLUÇÃO DEFINITIVA: Usar globais do objeto gerador fornecido ou atual
    if gerador is None:
        # Obter a instância atual do gerador
        from Robo_Pilar_Visao_Cima import obter_instancia_gerador_pilar
        gerador = obter_instancia_gerador_pilar()
    
    if not gerador or not hasattr(gerador, '_globais_pilar_especial') or not gerador._globais_pilar_especial:
        print(f"[SOLUCAO-DEFINITIVA] Pilar especial INATIVO (sem globais no gerador) - retornando valor original: {valor_original}")
        if robo_logger:
            robo_logger.warning(f"Pilar especial INATIVO (sem globais no gerador) - retornando valor original: {valor_original}")
        return valor_original
    
    try:
        # NOVO: Lógica específica para pilar especial L - ajuste da coordenada Y do pilar 2
        if (pilar_num == 2 and tipo_alteracao == 'posicao' and 
            'y' in componente.lower() and 
            gerador._globais_pilar_especial.get('tipo_pilar') == 'L' and
            getattr(gerador, 'pilar_especial_ativo_var', None) and 
            gerador.pilar_especial_ativo_var.get()):
            
            # Calcular o deslocamento Y específico para pilar especial L
            comprimento_pilar_1 = float(gerador._globais_pilar_especial.get('comp_1', 0) or 0)
            largura_pilar_2 = float(gerador._globais_pilar_especial.get('larg_2', 0) or 0)
            largura_pilar_1 = float(gerador._globais_pilar_especial.get('larg_1', 0) or 0)
            
            # Regra original: Y2 = Ybase + (-comp_1 + larg_2)
            deslocamento_y_pilar_2 = -comprimento_pilar_1 + largura_pilar_2
            
            # NOVO: Ajuste adicional baseado na largura 1 do pilar 1
            # Se largura 1 = 20: posição atual (sem ajuste adicional)
            # Se largura 1 < 20: mover pilar 2 para baixo (mesma diferença)
            # Se largura 1 > 20: mover pilar 2 para cima (mesma diferença)
            ajuste_largura_1 = largura_pilar_1 - 20.0
            deslocamento_y_pilar_2 += ajuste_largura_1
            
            # NOVO: Ajuste adicional baseado na largura 2 do pilar 2 (sentido oposto)
            # Se largura 2 = 20: posição atual (sem ajuste adicional)
            # Se largura 2 < 20: mover pilar 2 para cima (mesma diferença)
            # Se largura 2 > 20: mover pilar 2 para baixo (mesma diferença)
            ajuste_largura_2 = -(largura_pilar_2 - 20.0)  # Sentido oposto: negativo
            deslocamento_y_pilar_2 += ajuste_largura_2
            
            if robo_logger:
                robo_logger.info(f"🔄 PILAR ESPECIAL L - Ajuste Y do Pilar 2:")
                robo_logger.info(f"   Comprimento Pilar 1: {comprimento_pilar_1}")
                robo_logger.info(f"   Largura Pilar 2: {largura_pilar_2}")
                robo_logger.info(f"   Largura Pilar 1: {largura_pilar_1}")
                robo_logger.info(f"   Deslocamento base: -{comprimento_pilar_1} + {largura_pilar_2} = {deslocamento_y_pilar_2 - ajuste_largura_1 - ajuste_largura_2}")
                robo_logger.info(f"   Ajuste largura 1: {largura_pilar_1} - 20 = {ajuste_largura_1}")
                robo_logger.info(f"   Ajuste largura 2: -({largura_pilar_2} - 20) = {ajuste_largura_2}")
                robo_logger.info(f"   Deslocamento total: {deslocamento_y_pilar_2}")
                robo_logger.info(f"   Valor original Y: {valor_original} -> Novo Y: {valor_original + deslocamento_y_pilar_2}")
            
            print(f"[PILAR-ESPECIAL-L] Ajuste Y Pilar 2:")
            print(f"   Deslocamento base: -{comprimento_pilar_1} + {largura_pilar_2} = {deslocamento_y_pilar_2 - ajuste_largura_1 - ajuste_largura_2}")
            print(f"   Ajuste largura 1: {largura_pilar_1} - 20 = {ajuste_largura_1}")
            print(f"   Ajuste largura 2: -({largura_pilar_2} - 20) = {ajuste_largura_2}")
            print(f"   Deslocamento total: {deslocamento_y_pilar_2}")
            print(f"   Y original: {valor_original} -> Y novo: {valor_original + deslocamento_y_pilar_2}")
            
            return valor_original + deslocamento_y_pilar_2
        
        # NOVO: Ajustes de largura para metais e painéis especiais
        if (gerador._globais_pilar_especial.get('tipo_pilar') == 'L' and
            getattr(gerador, 'pilar_especial_ativo_var', None) and 
            gerador.pilar_especial_ativo_var.get()):
            
            # Obter larguras dos pilares
            largura_pilar_1 = float(gerador._globais_pilar_especial.get('larg_1', 0) or 0)
            largura_pilar_2 = float(gerador._globais_pilar_especial.get('larg_2', 0) or 0)
            
            # 1. METAL B PILAR 1: ajuste baseado na largura do pilar 2
            # NOTA: Ajuste agora integrado diretamente no código (linhas 2451-2457)
            # Não aplicar aqui para evitar duplicação
            if (pilar_num == 1 and componente == 'metal_b' and tipo_alteracao == 'tamanho'):
                print(f"[AJUSTE-LARGURA] Metal B Pilar 1: AJUSTE INTEGRADO NO CÓDIGO - NÃO APLICAR AQUI")
                return valor_original
            
            # 2. METAL A PILAR 2: ajuste baseado na largura do pilar 1
            if (pilar_num == 2 and componente == 'metal_a' and tipo_alteracao == 'tamanho'):
                # Padrão para largura 20cm, se for 30cm aumenta 10cm, se for 10cm diminui 10cm
                ajuste_largura = (largura_pilar_1 - 20.0) * 1  # Direto: se larg_1=30, ajuste=+10
                valor_ajustado = valor_original + ajuste_largura
                
                print(f"[AJUSTE-LARGURA] Metal A Pilar 2: larg_1={largura_pilar_1}cm, ajuste={ajuste_largura:+.1f}cm")
                print(f"[AJUSTE-LARGURA] Tamanho: {valor_original} -> {valor_ajustado}")
                
                if robo_logger:
                    robo_logger.info(f"🔧 AJUSTE LARGURA - Metal A Pilar 2: larg_1={largura_pilar_1}cm, ajuste={ajuste_largura:+.1f}cm")
                    robo_logger.info(f"   Tamanho: {valor_original} -> {valor_ajustado}")
                
                return valor_ajustado
            
            # 3. METAL A PILAR 2: ajuste de posição baseado na largura do pilar 1
            if (pilar_num == 2 and componente == 'metal_a' and tipo_alteracao == 'posicao'):
                # Se somar 10 no tamanho, mover 10 para a esquerda (posição X diminui)
                # Se diminuir 10 no tamanho, mover 10 para a direita (posição X aumenta)
                ajuste_posicao = (largura_pilar_1 - 20.0) * -1  # Inverso: se larg_1=30, ajuste=-10
                valor_ajustado = valor_original + ajuste_posicao
                
                print(f"[AJUSTE-LARGURA] Metal A Pilar 2 POSIÇÃO: larg_1={largura_pilar_1}cm, ajuste={ajuste_posicao:+.1f}cm")
                print(f"[AJUSTE-LARGURA] Posição: {valor_original} -> {valor_ajustado}")
                
                if robo_logger:
                    robo_logger.info(f"🔧 AJUSTE LARGURA - Metal A Pilar 2 POSIÇÃO: larg_1={largura_pilar_1}cm, ajuste={ajuste_posicao:+.1f}cm")
                    robo_logger.info(f"   Posição: {valor_original} -> {valor_ajustado}")
                
                return valor_ajustado
            
            # 4. PAI.A PILAR 2: ajuste de tamanho baseado na largura do pilar 1
            if (pilar_num == 2 and componente == 'pai_a' and tipo_alteracao == 'tamanho'):
                # Padrão para largura 20cm, se for 30cm aumenta 10cm, se for 10cm diminui 10cm
                ajuste_largura = (largura_pilar_1 - 20.0) * 1  # Direto: se larg_1=30, ajuste=+10
                valor_ajustado = valor_original + ajuste_largura
                
                print(f"[AJUSTE-LARGURA] PAI.A Pilar 2: larg_1={largura_pilar_1}cm, ajuste={ajuste_largura:+.1f}cm")
                print(f"[AJUSTE-LARGURA] Tamanho: {valor_original} -> {valor_ajustado}")
                
                if robo_logger:
                    robo_logger.info(f"🔧 AJUSTE LARGURA - PAI.A Pilar 2: larg_1={largura_pilar_1}cm, ajuste={ajuste_largura:+.1f}cm")
                    robo_logger.info(f"   Tamanho: {valor_original} -> {valor_ajustado}")
                
                return valor_ajustado
            
            # 5. PAI.A PILAR 2: ajuste de posição baseado na largura do pilar 1
            if (pilar_num == 2 and componente == 'pai_a' and tipo_alteracao == 'posicao'):
                # Se somar 10 no tamanho, mover 10 para a esquerda (posição X diminui)
                # Se diminuir 10 no tamanho, mover 10 para a direita (posição X aumenta)
                ajuste_posicao = (largura_pilar_1 - 20.0) * -1  # Inverso: se larg_1=30, ajuste=-10
                valor_ajustado = valor_original + ajuste_posicao
                
                print(f"[AJUSTE-LARGURA] PAI.A Pilar 2 POSIÇÃO: larg_1={largura_pilar_1}cm, ajuste={ajuste_posicao:+.1f}cm")
                print(f"[AJUSTE-LARGURA] Posição: {valor_original} -> {valor_ajustado}")
                
                if robo_logger:
                    robo_logger.info(f"🔧 AJUSTE LARGURA - PAI.A Pilar 2 POSIÇÃO: larg_1={largura_pilar_1}cm, ajuste={ajuste_posicao:+.1f}cm")
                    robo_logger.info(f"   Posição: {valor_original} -> {valor_ajustado}")
                
                return valor_ajustado
            
            # 6. PAI.B PILAR 2: ajuste de tamanho baseado na largura do pilar 1
            if (pilar_num == 2 and componente == 'pai_b' and tipo_alteracao == 'tamanho'):
                # Padrão para largura 20cm, se for 30cm aumenta 10cm, se for 10cm diminui 10cm
                ajuste_largura = (largura_pilar_1 - 20.0) * 1  # Direto: se larg_1=30, ajuste=+10
                valor_ajustado = valor_original + ajuste_largura
                
                print(f"[AJUSTE-LARGURA] PAI.B Pilar 2: larg_1={largura_pilar_1}cm, ajuste={ajuste_largura:+.1f}cm")
                print(f"[AJUSTE-LARGURA] Tamanho: {valor_original} -> {valor_ajustado}")
                
                if robo_logger:
                    robo_logger.info(f"🔧 AJUSTE LARGURA - PAI.B Pilar 2: larg_1={largura_pilar_1}cm, ajuste={ajuste_largura:+.1f}cm")
                    robo_logger.info(f"   Tamanho: {valor_original} -> {valor_ajustado}")
                
                return valor_ajustado
            
            # 7. PAI.B PILAR 2: ajuste de posição baseado na largura do pilar 1
            if (pilar_num == 2 and componente == 'pai_b' and tipo_alteracao == 'posicao'):
                # Se somar 10 no tamanho, mover 10 para a esquerda (posição X diminui)
                # Se diminuir 10 no tamanho, mover 10 para a direita (posição X aumenta)
                ajuste_posicao = (largura_pilar_1 - 20.0) * -1  # Inverso: se larg_1=30, ajuste=-10
                valor_ajustado = valor_original + ajuste_posicao
                
                print(f"[AJUSTE-LARGURA] PAI.B Pilar 2 POSIÇÃO: larg_1={largura_pilar_1}cm, ajuste={ajuste_posicao:+.1f}cm")
                print(f"[AJUSTE-LARGURA] Posição: {valor_original} -> {valor_ajustado}")
                
                if robo_logger:
                    robo_logger.info(f"🔧 AJUSTE LARGURA - PAI.B Pilar 2 POSIÇÃO: larg_1={largura_pilar_1}cm, ajuste={ajuste_posicao:+.1f}cm")
                    robo_logger.info(f"   Posição: {valor_original} -> {valor_ajustado}")
                
                return valor_ajustado
        
        # Construir chave para buscar a alteração
        if pilar_num:
            # CORREÇÃO: Remover underscore do componente para corresponder às chaves das globais
            componente_sem_underscore = componente.replace('_', '')
            chave = f"pilar{pilar_num}_{componente_sem_underscore}_{tipo_alteracao}"
        else:
            chave = f"{componente}_{tipo_alteracao}"
        
        alteracao = gerador._globais_pilar_especial.get(chave, 0)
        
        # Se não há alteração, retornar valor original
        if alteracao == 0:
            print(f"[SOLUCAO-DEFINITIVA] Sem alteração para {chave} - retornando valor original: {valor_original}")
            if robo_logger:
                robo_logger.debug(f"Sem alteração para {chave} - retornando valor original: {valor_original}")
            return valor_original
        
        # CORREÇÃO: Para tamanhos, usar o valor da global diretamente (substituir, não somar)
        # Para posições, somar o offset ao valor original
        if tipo_alteracao == 'tamanho':
            # Para tamanhos, a global contém o valor final calculado
            valor_alterado = alteracao
            print(f"[SOLUCAO-DEFINITIVA] Aplicando tamanho pilar especial: {valor_original} -> {valor_alterado} ({chave})")
            if robo_logger:
                robo_logger.info(f"Aplicando tamanho pilar especial: {valor_original} -> {valor_alterado} ({chave})")
        else:
            # Para posições, somar o offset
            valor_alterado = valor_original + alteracao
            print(f"[SOLUCAO-DEFINITIVA] Aplicando posição pilar especial: {valor_original} + {alteracao} = {valor_alterado} ({chave})")
            if robo_logger:
                robo_logger.info(f"Aplicando posição pilar especial: {valor_original} + {alteracao} = {valor_alterado} ({chave})")
        
        return valor_alterado
        
    except Exception as e:
        print(f"[AVISO] Erro ao aplicar alteração pilar especial: {e}")
        if robo_logger:
            robo_logger.error(f"Erro ao aplicar alteração pilar especial: {e}")
        return valor_original

class ConfigManager:
    def __init__(self, config_file: str = "config_cima.json"):
        # Usar sistema de paths robusto que funciona independentemente de como é executado
        try:
            from config_paths import CONFIG_DIR, TEMPLATES_DIR
            self.config_file = os.path.join(CONFIG_DIR, config_file)
            # CORREÇÃO: Templates estão no diretório config, não templates
            self.templates_file = os.path.join(CONFIG_DIR, "templates_config_cima.json")
        except ImportError:
            # Fallback usando robust_path_resolver
            try:
                import sys
                sys.path.append(os.path.dirname(os.path.dirname(__file__)))
                from utils.robust_path_resolver import robust_path_resolver
                project_root = robust_path_resolver.get_project_root()
            except:
                # Fallback final para estrutura relativa - MELHORADO para funcionar em qualquer contexto
                current_dir = os.path.dirname(os.path.abspath(__file__))
                # Tentar diferentes caminhos para encontrar o projeto
                possible_paths = [
                    os.path.dirname(os.path.dirname(current_dir)),  # src/robots -> PILARES
                    os.path.dirname(current_dir),  # robots -> src
                    os.path.join(os.path.dirname(current_dir), ".."),  # robots -> PILARES
                ]
                
                project_root = None
                for path in possible_paths:
                    config_test = os.path.join(path, "config", "templates_config_cima.json")
                    if os.path.exists(config_test):
                        project_root = path
                        break
                
                if project_root is None:
                    # Último recurso: usar o diretório atual
                    project_root = os.getcwd()
            
            # Usar caminhos relativos baseados na nova estrutura (tudo em config)
            self.config_file = os.path.join(project_root, "config", config_file)
            self.templates_file = os.path.join(project_root, "config", "templates_config_cima.json")
        
        # Logs de debug removidos para produção
        
        self.config = self.load_config()
        self.templates = self.load_templates()

    def load_config(self) -> dict:
        """Carrega as configurações do arquivo. Se não existir, cria com valores padrão."""
        default_config = self.get_default_config()
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # Verifica se a chave está com encoding incorreto e corrige
                    if "painÃ©is" in loaded_config.get("layers", {}):
                        loaded_config["layers"]["paineis"] = loaded_config["layers"].pop("painÃ©is")
                    
                    # Mesclar configurações padrão com as carregadas
                    merged_config = self.merge_configs(default_config, loaded_config)
                    
                    # Se houve mudanças, salvar o arquivo atualizado
                    if merged_config != loaded_config:
                        self.config = merged_config
                        self.save_config()
                    
                    return merged_config
        except Exception as e:
            print(f"Erro ao carregar configurações: {e}")
            # Se houver erro, remove o arquivo corrompido
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
        return default_config

    def get_default_config(self) -> dict:
        """Retorna as configurações padrão."""
        return {
            "layers": {
                "paineis": "hachura-chapa",  # Alterado para corresponder à verificação no código
                "sarrafos": "SARRAFO",
                "sarrafo_grade": "SARRAFO_GRADE",  # Layer específico para sarrafo das grades
                "cotas": "COTA",
                "textos": "NOMENCLATURA",
                "metal": "GRAVATA",
                "hachura": "Hachura"
            },
            "blocks": {
                "sar_gra_a1": "B1A.E",
                "sar_gra_a2": "B1A.D",
                "sar_gra_a3": "B2A.E",
                "sar_gra_b1": "B1B.E",
                "sar_gra_b2": "B1B.D",
                "sar_gra_b3": "B2B.E",
                "parafuso_cima": "PAR.CIM",
                "parafuso_baixo": "PAR.BAI",
                "parafuso_esquerda": "PAR.ESQ",
                "parafuso_direita": "PAR.DIR",
                "par_cima": "PAR_CIMA",
                "par_baixo": "PAR_BAIXO",
                "block_central_grade_vertical": "BCGV",
                "ta": "TA",
                "tb": "TB", 
                "tc": "TC",
                "td": "TD"
            },
            "drawing_options": {
                "scale_factor": 2,
                "dimstyle": "cotax2",
                "dimstyleCENTRO": "cotax2",
                "textos_abcd": "texto",  # Novo campo adicionado
                "incluir_texto_nome": "sim",  # Nova configuração para incluir texto do nome
                "grades_com_sarrafo": "nao",  # Nova configuração para grades com sarrafo
                "tipo_linha": "pline"  # Nova configuração para tipo de linha (pline ou mline)
            }
        }

    def merge_configs(self, default_config: dict, loaded_config: dict) -> dict:
        """Mescla configurações padrão com as carregadas, adicionando novos campos."""
        merged = loaded_config.copy()
        
        for section, values in default_config.items():
            if section not in merged:
                merged[section] = values.copy()
            else:
                for key, value in values.items():
                    if key not in merged[section]:
                        merged[section][key] = value
        
        return merged

    def save_config(self) -> None:
        """Salva as configurações no arquivo."""
        try:
            # Garante que a chave paineis está correta antes de salvar
            if "layers" in self.config and "painÃ©is" in self.config["layers"]:
                self.config["layers"]["paineis"] = self.config["layers"].pop("painÃ©is")
            
            # Salva o arquivo com indentação e encoding correto
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar configurações: {e}")

    def get_config(self, *keys: str) -> str:
        """Obtém um valor específico da configuração usando uma sequência de chaves."""
        result = self.config
        for key in keys:
            if isinstance(result, dict):
                # Trata o caso especial da chave paineis
                if key == "paineis" and "painÃ©is" in result:
                    key = "painÃ©is"
                if key in result:
                    result = result[key]
                else:
                    # Se não encontrar a chave, tenta buscar no padrão
                    default_config = self.get_default_config()
                    try:
                        default_result = default_config
                        for default_key in keys:
                            default_result = default_result[default_key]
                        return default_result
                    except (KeyError, TypeError):
                        return key
            else:
                return key
        return result

    def load_templates(self) -> dict:
        """Carrega os templates salvos."""
        try:
            if os.path.exists(self.templates_file):
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Erro ao carregar templates: {e}")
        return {}

    def save_template(self, template_name: str, config: dict):
        """Salva um novo template. Se já existir, adiciona sufixo numérico."""
        # Verificar se o template já existe
        if template_name in self.templates:
            # Encontrar o próximo sufixo disponível
            base_name = template_name
            suffix = 1
            while f"{base_name}.{suffix}" in self.templates:
                suffix += 1
            template_name = f"{base_name}.{suffix}"
            print(f"Template '{base_name}' já existe. Salvando como '{template_name}'")
        
        self.templates[template_name] = config
        try:
            with open(self.templates_file, 'w', encoding='utf-8') as f:
                json.dump(self.templates, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar template: {e}")

    def delete_template(self, template_name: str):
        """Remove um template existente."""
        if template_name in self.templates:
            del self.templates[template_name]
            try:
                with open(self.templates_file, 'w', encoding='utf-8') as f:
                    json.dump(self.templates, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"Erro ao deletar template: {e}")

class AplicacaoUnificada:
    def __init__(self):
        try:
            self.root = tk.Tk()
            self.root.title("Gerador de Pilares")
            self.root.state('zoomed')  # Iniciar maximizado
            
            # Criar frame principal
            self.frame_principal = ttk.Frame(self.root)
            self.frame_principal.pack(fill='both', expand=True)
            
            # Criar interface do gerador
            self.gerador = GeradorPilar(self.frame_principal, master=self)
            
            # Configurar redimensionamento
            self.root.grid_columnconfigure(0, weight=1)
            self.root.grid_rowconfigure(0, weight=1)
            
            logging.info("Aplicação inicializada com sucesso")
            
        except Exception as e:
            logging.error(f"Erro ao inicializar aplicação: {str(e)}")
            raise

    def iniciar(self):
        try:
            self.root.mainloop()
        except Exception as e:
            logging.error(f"Erro durante execução da aplicação: {str(e)}")
            raise

    def registrar_sincronizacao(self, sucesso):
        """Registra o resultado da sincronização."""
        self.sincronizacao_sucesso.set(sucesso)

# Renomear OutraInterface para GeradorPilar
class GeradorPilar:
    def __init__(self, parent, master=None):
        global _instancia_gerador_pilar
        
        self.root = parent
        self.master = master
        self.config_manager = ConfigManager()
        
        # Coordenadas iniciais
        self.x_inicial = -40
        self.y_inicial = 70  # Modificado para 50
        
        # Criar a interface primeiro
        self.criar_interface()
        
        # Inicializar o dicionário de campos depois que a interface foi criada
        self.campos = {
            'nome': self.nome_pilar_entry,
            'comprimento': self.comprimento_pilar_entry,
            'largura': self.largura_pilar_entry
        }
        
        # Registrar esta instância globalmente
        _instancia_gerador_pilar = self
        print("OK Instancia do GeradorPilar registrada globalmente")
        
        # Inicializar globais do pilar especial
        self._globais_pilar_especial = {}
        
        # Inicializar pilar_atual (para pilares especiais)
        self.pilar_atual = 1
        
        if robo_logger:
            robo_logger.info("🔄 Instância do GeradorPilar registrada globalmente")
            robo_logger.info("🔄 Globais do pilar especial inicializadas")

    def log_mensagem(self, mensagem, tipo="info"):
        """Método para logging de mensagens"""
        if tipo == "erro":
            logging.error(mensagem)
        elif tipo == "aviso":
            logging.warning(mensagem)
        else:
            logging.info(mensagem)

    def criar_janela_configuracoes(self):
        """Cria a janela de configurações para layers e blocks."""
        self.config_window = tk.Toplevel(self.root)
        self.config_window.title("Configurações")
        self.config_window.geometry("600x600")  # Alterado de 600x800 para 600x600
        
        notebook = ttk.Notebook(self.config_window)
        notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Frame para Layers
        layers_frame = ttk.LabelFrame(notebook, text="Layers", padding="10")
        notebook.add(layers_frame, text="Layers")
        
        # Criar campos para cada layer
        self.layer_entries = {}
        layer_config = self.config_manager.get_config("layers")
        
        for key, value in layer_config.items():
            frame = ttk.Frame(layers_frame)
            frame.pack(fill="x", pady=2)
            
            ttk.Label(frame, text=key.capitalize() + ":").pack(side="left")
            entry = ttk.Entry(frame)
            entry.insert(0, value)
            entry.pack(side="right", expand=True, fill="x", padx=(5, 0))
            self.layer_entries[key] = entry
        
        # Frame para Blocks
        blocks_frame = ttk.LabelFrame(notebook, text="Blocks", padding="10")
        notebook.add(blocks_frame, text="Blocks")
        
        # Criar campos para cada block
        self.block_entries = {}
        block_config = self.config_manager.get_config("blocks")
        
        for key, value in block_config.items():
            frame = ttk.Frame(blocks_frame)
            frame.pack(fill="x", pady=2)
            
            ttk.Label(frame, text=key.replace("_", " ").capitalize() + ":").pack(side="left")
            entry = ttk.Entry(frame)
            entry.insert(0, value)
            entry.pack(side="right", expand=True, fill="x", padx=(5, 0))
            self.block_entries[key] = entry

        # Frame para Opções de Desenho
        drawing_frame = ttk.LabelFrame(notebook, text="Opções de Desenho", padding="10")
        notebook.add(drawing_frame, text="Opções")
        
        # Campo para scale_factor
        scale_frame = ttk.Frame(drawing_frame)
        scale_frame.pack(fill="x", pady=2)
        
        ttk.Label(scale_frame, text="Fator de Escala:").pack(side="left")
        self.scale_entry = ttk.Entry(scale_frame)
        self.scale_entry.insert(0, str(self.config_manager.get_config("drawing_options", "scale_factor")))
        self.scale_entry.pack(side="right", expand=True, fill="x", padx=(5, 0))

        # Campo para dimstyle
        dimstyle_frame = ttk.Frame(drawing_frame)
        dimstyle_frame.pack(fill="x", pady=2)
        
        ttk.Label(dimstyle_frame, text="Estilo de Cota:").pack(side="left")
        self.dimstyle_entry = ttk.Entry(dimstyle_frame)
        self.dimstyle_entry.insert(0, str(self.config_manager.get_config("drawing_options", "dimstyle")))
        self.dimstyle_entry.pack(side="right", expand=True, fill="x", padx=(5, 0))

        # Campo para dimstyleCENTRO
        dimstyle_centro_frame = ttk.Frame(drawing_frame)
        dimstyle_centro_frame.pack(fill="x", pady=2)
        
        ttk.Label(dimstyle_centro_frame, text="Estilo de Cota Central:").pack(side="left")
        self.dimstyle_centro_entry = ttk.Entry(dimstyle_centro_frame)
        self.dimstyle_centro_entry.insert(0, str(self.config_manager.get_config("drawing_options", "dimstyleCENTRO")))
        self.dimstyle_centro_entry.pack(side="right", expand=True, fill="x", padx=(5, 0))

        # Frame para Opções de Texto ABCD
        text_frame = ttk.LabelFrame(drawing_frame, text="Textos ABCD", padding="10")
        text_frame.pack(fill="x", pady=5)
        
        # Variável para armazenar a opção
        texto_abcd_var = tk.StringVar(value=self.config_manager.get_config("drawing_options", "textos_abcd"))
        self.texto_abcd_var = texto_abcd_var  # Armazenar como atributo da classe
        
        # Radio buttons
        ttk.Radiobutton(text_frame, text="Usar Texto", variable=texto_abcd_var, value="texto").pack(anchor='w')
        ttk.Radiobutton(text_frame, text="Usar Blocos", variable=texto_abcd_var, value="blocos").pack(anchor='w')

        # Frame para Opções de Texto do Nome
        texto_nome_frame = ttk.LabelFrame(drawing_frame, text="Texto do Nome", padding="10")
        texto_nome_frame.pack(fill="x", pady=5)
        
        # Variável para armazenar a opção do texto do nome
        texto_nome_var = tk.StringVar(value=self.config_manager.get_config("drawing_options", "incluir_texto_nome"))
        self.texto_nome_var = texto_nome_var  # Armazenar como atributo da classe
        
        # Radio buttons para texto do nome
        ttk.Radiobutton(texto_nome_frame, text="Sim", variable=texto_nome_var, value="sim").pack(anchor='w')
        ttk.Radiobutton(texto_nome_frame, text="Não", variable=texto_nome_var, value="nao").pack(anchor='w')

        # Frame para Grades com Sarrafo
        grades_sarrafo_frame = ttk.LabelFrame(drawing_frame, text="Grades com Sarrafo", padding="10")
        grades_sarrafo_frame.pack(fill="x", pady=5)
        grades_sarrafo_var = tk.StringVar(value=self.config_manager.get_config("drawing_options", "grades_com_sarrafo"))
        self.grades_sarrafo_var = grades_sarrafo_var
        ttk.Radiobutton(grades_sarrafo_frame, text="Sim", variable=grades_sarrafo_var, value="sim").pack(anchor='w')
        ttk.Radiobutton(grades_sarrafo_frame, text="Não", variable=grades_sarrafo_var, value="nao").pack(anchor='w')

        # Frame para Tipo de Linha
        tipo_linha_frame = ttk.LabelFrame(drawing_frame, text="Tipo de Linha", padding="10")
        tipo_linha_frame.pack(fill="x", pady=5)
        tipo_linha_var = tk.StringVar(value=self.config_manager.get_config("drawing_options", "tipo_linha"))
        self.tipo_linha_var = tipo_linha_var
        ttk.Radiobutton(tipo_linha_frame, text="PLINE (com retângulo 7cm)", variable=tipo_linha_var, value="pline").pack(anchor='w')
        ttk.Radiobutton(tipo_linha_frame, text="MLINE (sem retângulo 7cm)", variable=tipo_linha_var, value="mline").pack(anchor='w')



        def salvar_configuracoes():
            # Atualizar layers
            new_layer_config = {}
            for key, entry in self.layer_entries.items():
                new_layer_config[key] = entry.get()
            self.config_manager.config["layers"] = new_layer_config
            
            # Atualizar blocks
            new_block_config = {}
            for key, entry in self.block_entries.items():
                new_block_config[key] = entry.get()
            self.config_manager.config["blocks"] = new_block_config
            
            # Atualizar drawing_options
            try:
                scale_value = float(self.scale_entry.get())
                dimstyle_value = self.dimstyle_entry.get().strip()
                dimstyle_centro_value = self.dimstyle_centro_entry.get().strip()
                
                if not dimstyle_value:
                    messagebox.showerror("Erro", "O estilo de cota não pode estar vazio!")
                    return
                
                if not dimstyle_centro_value:
                    messagebox.showerror("Erro", "O estilo de cota central não pode estar vazio!")
                    return
                
                self.config_manager.config["drawing_options"] = {
                    "scale_factor": scale_value,
                    "dimstyle": dimstyle_value,
                    "dimstyleCENTRO": dimstyle_centro_value
                }
            except ValueError:
                messagebox.showerror("Erro", "O fator de escala deve ser um número válido!")
                return
            
            # Adicionar novos valores ao salvar
            self.config_manager.config["drawing_options"]["textos_abcd"] = texto_abcd_var.get()
            self.config_manager.config["drawing_options"]["incluir_texto_nome"] = texto_nome_var.get()
            self.config_manager.config["drawing_options"]["grades_com_sarrafo"] = grades_sarrafo_var.get()
            self.config_manager.config["drawing_options"]["tipo_linha"] = tipo_linha_var.get()
            
            # Salvar configurações
            self.config_manager.save_config()
            messagebox.showinfo("Sucesso", "Configurações salvas com sucesso!")
            self.config_window.destroy()

        # Botão Salvar
        ttk.Button(self.config_window, text="Salvar", command=salvar_configuracoes).pack(pady=10)

        # Nova aba para Templates
        template_frame = ttk.Frame(notebook)
        notebook.add(template_frame, text="Templates")
        
        # Frame para gerenciar templates
        manage_frame = ttk.LabelFrame(template_frame, text="Gerenciar Templates", padding="10")
        manage_frame.pack(fill="x", pady=5)
        
        # Entrada para nome do template
        ttk.Label(manage_frame, text="Nome do Template:").pack(anchor='w')
        self.template_name_entry = ttk.Entry(manage_frame)  # Alterado para self.template_name_entry
        self.template_name_entry.pack(fill="x", pady=2)
        
        # Botões de ação
        btn_frame = ttk.Frame(manage_frame)
        btn_frame.pack(fill="x", pady=5)
        
        ttk.Button(btn_frame, text="Salvar Template", command=lambda: self.salvar_template(self.template_name_entry.get())).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Carregar Template", command=lambda: self.carregar_template(self.template_name_entry.get())).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Deletar Template", command=lambda: self.deletar_template(self.template_name_entry.get())).pack(side="left", padx=2)
        
        # Lista de templates existentes
        list_frame = ttk.LabelFrame(template_frame, text="Templates Salvos", padding="10")
        list_frame.pack(fill="both", expand=True, pady=5)
        
        self.template_list = tk.Listbox(list_frame)
        self.template_list.pack(fill="both", expand=True)
        

        
        self.atualizar_lista_templates()
        
        # Vincular evento de clique na lista
        self.template_list.bind("<<ListboxSelect>>", self.selecionar_template)

    def criar_interface(self):
        # Frame principal esquerdo para controles
        self.left_frame = ttk.Frame(self.root, padding="10")
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Frame direito para preview
        self.right_frame = ttk.Frame(self.root, padding="10")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        # Frame para dados básicos
        self.dados_frame = ttk.LabelFrame(self.left_frame, text="Dados do Pilar", padding="5")
        self.dados_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        ttk.Label(self.dados_frame, text="Nome do Pilar:").grid(row=0, column=0, sticky="w", pady=2)
        self.nome_pilar_entry = ttk.Entry(self.dados_frame)
        self.nome_pilar_entry.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(self.dados_frame, text="Comprimento:").grid(row=1, column=0, sticky="w", pady=2)
        self.comprimento_pilar_entry = ttk.Entry(self.dados_frame)
        self.comprimento_pilar_entry.grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(self.dados_frame, text="Largura:").grid(row=2, column=0, sticky="w", pady=2)
        self.largura_pilar_entry = ttk.Entry(self.dados_frame)
        self.largura_pilar_entry.grid(row=2, column=1, sticky="ew", pady=2)
        
        self.pavimento_label = tk.Label(self.dados_frame, text="Pavimento:")
        self.pavimento_label.grid(row=3, column=0, sticky="w")
        self.pavimento_entry = tk.Entry(self.dados_frame)
        self.pavimento_entry.grid(row=3, column=1)
        
        # Checkbox para Pilar Rotacionado
        self.pilar_rotacionado_var = tk.BooleanVar()
        
        # Variável para controlar se deve usar SCALE (para scripts intermediários)
        self.usar_scale_var = tk.BooleanVar(value=True)  # Por padrão, usar SCALE
        
        # Variável para controlar se é pilar especial (para valores diferentes no SCALE)
        self.pilar_especial_ativo_var = tk.BooleanVar(value=False)  # Por padrão, não é pilar especial
        
        self.pilar_rotacionado_checkbox = ttk.Checkbutton(
            self.dados_frame, 
            text="Pilar Rotacionado", 
            variable=self.pilar_rotacionado_var
        )
        self.pilar_rotacionado_checkbox.grid(row=4, column=0, columnspan=2, sticky="w", pady=2)

        # Frame para grades
        self.grades_frame = ttk.LabelFrame(self.left_frame, text="Grades", padding="5")
        self.grades_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        grade_labels = ["Grade 1", "Distância 1", "Grade 2", "Distância 2", "Grade 3"]
        for i, label in enumerate(grade_labels):
            ttk.Label(self.grades_frame, text=label).grid(row=0, column=i, padx=5)

        self.grade1_entry = ttk.Entry(self.grades_frame, width=8)
        self.grade1_entry.grid(row=1, column=0, padx=5, pady=2)
        self.distancia1_entry = ttk.Entry(self.grades_frame, width=8)
        self.distancia1_entry.grid(row=1, column=1, padx=5, pady=2)
        self.grade2_entry = ttk.Entry(self.grades_frame, width=8)
        self.grade2_entry.grid(row=1, column=2, padx=5, pady=2)
        self.distancia2_entry = ttk.Entry(self.grades_frame, width=8)
        self.distancia2_entry.grid(row=1, column=3, padx=5, pady=2)
        self.grade3_entry = ttk.Entry(self.grades_frame, width=8)
        self.grade3_entry.grid(row=1, column=4, padx=5, pady=2)

        # Frame para detalhes das grades - NOVO
        self.detalhes_grades_frame = ttk.LabelFrame(self.left_frame, text="Detalhes das Grades (Distâncias entre Blocos)", padding="5")
        self.detalhes_grades_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)

        # Detalhes Grade 1
        ttk.Label(self.detalhes_grades_frame, text="Grade 1:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", pady=2)
        detalhe_labels_1 = ["D1-D2", "D2-D3", "D3-D4", "D4-D5", "D5-D6"]
        self.detalhe_grade1_entries = []
        for i, label in enumerate(detalhe_labels_1):
            ttk.Label(self.detalhes_grades_frame, text=label).grid(row=1, column=i, padx=2)
            entry = ttk.Entry(self.detalhes_grades_frame, width=6)  # Removido state='readonly'
            entry.grid(row=2, column=i, padx=2, pady=1)
            # DESATIVADO: entry.bind("<KeyRelease>", self.atualizar_grade_por_detalhes)
            # DESATIVADO: entry.bind("<FocusOut>", self.atualizar_grade_por_detalhes)
            self.detalhe_grade1_entries.append(entry)

        # Detalhes Grade 2
        ttk.Label(self.detalhes_grades_frame, text="Grade 2:", font=("Arial", 9, "bold")).grid(row=3, column=0, sticky="w", pady=(10,2))
        detalhe_labels_2 = ["D1-D2", "D2-D3", "D3-D4", "D4-D5", "D5-D6"]
        self.detalhe_grade2_entries = []
        for i, label in enumerate(detalhe_labels_2):
            ttk.Label(self.detalhes_grades_frame, text=label).grid(row=4, column=i, padx=2)
            entry = ttk.Entry(self.detalhes_grades_frame, width=6)  # Removido state='readonly'
            entry.grid(row=5, column=i, padx=2, pady=1)
            # DESATIVADO: entry.bind("<KeyRelease>", self.atualizar_grade_por_detalhes)
            # DESATIVADO: entry.bind("<FocusOut>", self.atualizar_grade_por_detalhes)
            self.detalhe_grade2_entries.append(entry)

        # Detalhes Grade 3
        ttk.Label(self.detalhes_grades_frame, text="Grade 3:", font=("Arial", 9, "bold")).grid(row=6, column=0, sticky="w", pady=(10,2))
        detalhe_labels_3 = ["D1-D2", "D2-D3", "D3-D4", "D4-D5", "D5-D6"]
        self.detalhe_grade3_entries = []
        for i, label in enumerate(detalhe_labels_3):
            ttk.Label(self.detalhes_grades_frame, text=label).grid(row=7, column=i, padx=2)
            entry = ttk.Entry(self.detalhes_grades_frame, width=6)  # Removido state='readonly'
            entry.grid(row=8, column=i, padx=2, pady=1)
            # DESATIVADO: entry.bind("<KeyRelease>", self.atualizar_grade_por_detalhes)
            # DESATIVADO: entry.bind("<FocusOut>", self.atualizar_grade_por_detalhes)
            self.detalhe_grade3_entries.append(entry)

        # Frame para Grade Grupo 2 - NOVO
        self.grades_grupo2_frame = ttk.LabelFrame(self.left_frame, text="Grade Grupo 2", padding="5")
        self.grades_grupo2_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=5)

        grade_grupo2_labels = ["Grade 1", "Distância 1", "Grade 2", "Distância 2", "Grade 3"]
        for i, label in enumerate(grade_grupo2_labels):
            ttk.Label(self.grades_grupo2_frame, text=label).grid(row=0, column=i, padx=5)

        self.grade1_grupo2_entry = ttk.Entry(self.grades_grupo2_frame, width=8)
        self.grade1_grupo2_entry.grid(row=1, column=0, padx=5, pady=2)
        self.distancia1_grupo2_entry = ttk.Entry(self.grades_grupo2_frame, width=8)
        self.distancia1_grupo2_entry.grid(row=1, column=1, padx=5, pady=2)
        self.grade2_grupo2_entry = ttk.Entry(self.grades_grupo2_frame, width=8)
        self.grade2_grupo2_entry.grid(row=1, column=2, padx=5, pady=2)
        self.distancia2_grupo2_entry = ttk.Entry(self.grades_grupo2_frame, width=8)
        self.distancia2_grupo2_entry.grid(row=1, column=3, padx=5, pady=2)
        self.grade3_grupo2_entry = ttk.Entry(self.grades_grupo2_frame, width=8)
        self.grade3_grupo2_entry.grid(row=1, column=4, padx=5, pady=2)

        # Frame para detalhes das grades do Grupo 2 - NOVO
        self.detalhes_grades_grupo2_frame = ttk.LabelFrame(self.left_frame, text="Detalhes das Grades Grupo 2 (Distâncias entre Blocos)", padding="5")
        self.detalhes_grades_grupo2_frame.grid(row=4, column=0, sticky="ew", padx=5, pady=5)

        # Detalhes Grade 1 Grupo 2
        ttk.Label(self.detalhes_grades_grupo2_frame, text="Grade 1:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", pady=2)
        detalhe_labels_1_grupo2 = ["D1-D2", "D2-D3", "D3-D4", "D4-D5", "D5-D6"]
        self.detalhe_grade1_grupo2_entries = []
        for i, label in enumerate(detalhe_labels_1_grupo2):
            ttk.Label(self.detalhes_grades_grupo2_frame, text=label).grid(row=1, column=i, padx=2)
            entry = ttk.Entry(self.detalhes_grades_grupo2_frame, width=6)
            entry.grid(row=2, column=i, padx=2, pady=1)
            self.detalhe_grade1_grupo2_entries.append(entry)

        # Detalhes Grade 2 Grupo 2
        ttk.Label(self.detalhes_grades_grupo2_frame, text="Grade 2:", font=("Arial", 9, "bold")).grid(row=3, column=0, sticky="w", pady=(10,2))
        detalhe_labels_2_grupo2 = ["D1-D2", "D2-D3", "D3-D4", "D4-D5", "D5-D6"]
        self.detalhe_grade2_grupo2_entries = []
        for i, label in enumerate(detalhe_labels_2_grupo2):
            ttk.Label(self.detalhes_grades_grupo2_frame, text=label).grid(row=4, column=i, padx=2)
            entry = ttk.Entry(self.detalhes_grades_grupo2_frame, width=6)
            entry.grid(row=5, column=i, padx=2, pady=1)
            self.detalhe_grade2_grupo2_entries.append(entry)

        # Detalhes Grade 3 Grupo 2
        ttk.Label(self.detalhes_grades_grupo2_frame, text="Grade 3:", font=("Arial", 9, "bold")).grid(row=6, column=0, sticky="w", pady=(10,2))
        detalhe_labels_3_grupo2 = ["D1-D2", "D2-D3", "D3-D4", "D4-D5", "D5-D6"]
        self.detalhe_grade3_grupo2_entries = []
        for i, label in enumerate(detalhe_labels_3_grupo2):
            ttk.Label(self.detalhes_grades_grupo2_frame, text=label).grid(row=7, column=i, padx=2)
            entry = ttk.Entry(self.detalhes_grades_grupo2_frame, width=6)
            entry.grid(row=8, column=i, padx=2, pady=1)
            self.detalhe_grade3_grupo2_entries.append(entry)

        # Frame para parafusos
        self.parafusos_frame = ttk.LabelFrame(self.left_frame, text="Parafusos", padding="5")
        self.parafusos_frame.grid(row=5, column=0, sticky="ew", padx=1, pady=1)

        # Títulos das caixas de texto para parafusos
        parafuso_labels = ["P1-P2", "P2-P3", "P3-P4", "P4-P5", "P5-P6", "P6-P7", "P7-P8", "P8-P9"]
        for i, label in enumerate(parafuso_labels):
            ttk.Label(self.parafusos_frame, text=label).grid(row=0, column=i, padx=2)

        # Caixas de texto para as distâncias entre parafusos
        self.parafuso_entries = []
        for i in range(8):
            entry = ttk.Entry(self.parafusos_frame, width=8)
            entry.grid(row=1, column=i, padx=2, pady=2)
            self.parafuso_entries.append(entry)
            entry.valor_var = tk.StringVar(self.root)
            entry["textvariable"] = entry.valor_var

        # Frame para botões de ação
        self.botoes_frame = ttk.LabelFrame(self.left_frame, text="Ações", padding="5")
        self.botoes_frame.grid(row=6, column=0, sticky="ew", padx=5, pady=5)

        # Reorganizar os botões para garantir que todos sejam visíveis
        # Primeira linha de botões
        ttk.Button(self.botoes_frame, text="Gerar Script", command=self.gerar_e_salvar_script).grid(row=0, column=0, padx=5, pady=2)
        ttk.Button(self.botoes_frame, text="Salvar Teste", command=self.salvar_teste).grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(self.botoes_frame, text="Calcular Valores", command=self.calcular_valores).grid(row=0, column=2, padx=5, pady=2)

        # Segunda linha de botões
        ttk.Button(self.botoes_frame, text="Conectar AutoCAD", command=self.conectar_autocad).grid(row=1, column=0, padx=5, pady=2)
        ttk.Button(self.botoes_frame, text="Desenhar CAD", command=self.desenhar_cad).grid(row=1, column=1, padx=5, pady=2)
        ttk.Button(self.botoes_frame, text="Atualizar Desenho", command=self.atualizar_preview).grid(row=1, column=2, padx=5, pady=2)
        
        # Adicionar botão de Configurações
        ttk.Button(self.botoes_frame, text="Configurações", command=self.criar_janela_configuracoes).grid(row=1, column=3, padx=5, pady=2)

        # Frame para resultado (mover para row=7)
        self.resultado_frame = ttk.LabelFrame(self.left_frame, text="Resultado", padding="5")
        self.resultado_frame.grid(row=7, column=0, sticky="ew", padx=5, pady=5)

        self.resultado_label = ttk.Label(self.resultado_frame, text="")
        self.resultado_label.pack(fill=tk.X, padx=5, pady=2)

        # Frame para log (mover para row=6)
        self.log_frame = ttk.LabelFrame(self.left_frame, text="Log", padding="5")
        self.log_frame.grid(row=6, column=0, sticky="nsew", padx=5, pady=5)

        self.log_text = tk.Text(self.log_frame, wrap=tk.WORD, height=8)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.log_scrollbar = ttk.Scrollbar(self.log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text.configure(yscrollcommand=self.log_scrollbar.set)

        # Status label (mover para row=7)
        self.status_label = ttk.Label(self.left_frame, text="")
        self.status_label.grid(row=7, column=0, sticky="w", padx=5, pady=2)

        # Área de preview no frame direito
        self.fig, self.ax = plt.subplots(figsize=(8, 8))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.right_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

        # Configurar expansão da janela
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.left_frame.columnconfigure(0, weight=1)
        self.right_frame.columnconfigure(0, weight=1)
        self.right_frame.rowconfigure(0, weight=1)

        # Vincular eventos de mouse para zoom e arrastar
        self.canvas_widget.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas_widget.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas_widget.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas_widget.bind("<ButtonRelease-1>", self.on_mouse_release)

        # Vincular eventos aos campos de texto
        self.nome_pilar_entry.bind("<KeyRelease>", self.sincronizar_nome)
        self.comprimento_pilar_entry.bind("<KeyRelease>", self.sincronizar_comprimento)
        self.largura_pilar_entry.bind("<KeyRelease>", self.sincronizar_largura)

        # Vincular eventos de foco aos campos para sincronização
        self.nome_pilar_entry.bind("<FocusOut>", self.sincronizar_nome)
        self.comprimento_pilar_entry.bind("<FocusOut>", self.sincronizar_comprimento)
        self.largura_pilar_entry.bind("<FocusOut>", self.sincronizar_largura)

        # DESATIVADO: Vincular eventos aos campos de grade para atualizar detalhes automaticamente
        # self.grade1_entry.bind("<KeyRelease>", self.atualizar_detalhes_grades)
        # self.grade2_entry.bind("<KeyRelease>", self.atualizar_detalhes_grades)
        # self.grade3_entry.bind("<KeyRelease>", self.atualizar_detalhes_grades)
        # self.grade1_entry.bind("<FocusOut>", self.atualizar_detalhes_grades)
        # self.grade2_entry.bind("<FocusOut>", self.atualizar_detalhes_grades)
        # self.grade3_entry.bind("<FocusOut>", self.atualizar_detalhes_grades)

        # Adicionar rastreadores para os campos de parafusos
        for i, entry in enumerate(self.parafuso_entries):
            entry.valor_var = tk.StringVar(self.root)
            entry.valor_var.trace_add("write", lambda *args, idx=i: self.sincronizar_parafuso(idx))
            entry["textvariable"] = entry.valor_var

    def _obter_parafusos_especiais_para_uso(self, letra):
        """
        Obtém os valores dos parafusos especiais da aba Pilares Especiais.
        
        Args:
            letra (str): 'a' para parafusos A, 'e' para parafusos E
            
        Returns:
            list: Lista de distâncias dos parafusos especiais
        """
        try:
            parafusos = []
            
            # PRIMEIRA TENTATIVA: Usar dados globais dos parafusos especiais se disponíveis
            if hasattr(self, '_dados_parafusos_especiais') and self._dados_parafusos_especiais:
                dados_especiais = self._dados_parafusos_especiais.get(f'par_{letra}', {})
                for i in range(1, 10):
                    campo_name = f"par_{letra}_{i}"
                    if campo_name in dados_especiais:
                        try:
                            valor = float(dados_especiais[campo_name] or 0)
                            if valor > 0:
                                parafusos.append(valor)
                        except (ValueError, TypeError):
                            continue
                            
                # CORREÇÃO: Removida regra que ignorava o primeiro parafuso E
                # Todos os parafusos especificados devem ser desenhados
                
                if parafusos:
                    print(f"[DEBUG] Parafusos especiais {letra.upper()} obtidos dos dados globais: {parafusos}")
                    print(f"[DEBUG] Total de {len(parafusos)} parafusos especiais {letra.upper()} coletados")
                    for idx, valor in enumerate(parafusos):
                        print(f"[DEBUG]   Parafuso {idx+1}: {valor}cm")
                    return parafusos
            
            # SEGUNDA TENTATIVA: Buscar na interface principal
            interface = None
            if hasattr(self, 'master') and hasattr(self.master, 'interface_principal'):
                interface = self.master.interface_principal
            elif hasattr(self, 'interface_principal'):
                interface = self.interface_principal
            else:
                # Buscar globalmente por instância PilarAnalyzer
                import gc
                for obj in gc.get_objects():
                    if obj.__class__.__name__ == 'PilarAnalyzer':
                        interface = obj
                        break
            
            if interface:
                # Obter valores dos campos de parafusos especiais
                for i in range(1, 10):  # par_a_1 até par_a_9 (ou par_e_1 até par_e_9)
                    campo_name = f"par_{letra}_{i}"
                    if hasattr(interface, campo_name):
                        campo = getattr(interface, campo_name)
                        try:
                            valor = float(campo.get() or 0)
                            if valor > 0:
                                parafusos.append(valor)
                        except (ValueError, AttributeError):
                            continue
            
            print(f"[DEBUG] Parafusos especiais {letra.upper()} obtidos da interface: {parafusos}")
            return parafusos
            
        except Exception as e:
            print(f"[ERRO] Erro ao obter parafusos especiais {letra}: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def calcular_posicoes_blocks(self, comprimento, posicao_x):
        """
        Calcula as posições arredondadas dos blocos centrais.
        Para 1 bloco: Arredonda para cima se a parte decimal for >= 0.5, para baixo se < 0.5
        Para 2 blocos: Arredonda de forma complementar (um para baixo, outro para cima)
        Para 3 blocos: Mantém o bloco central exato e arredonda os outros de forma complementar
        """
        posicoes = []
        
        if 31 <= comprimento <= 60:
            # 1 bloco central - arredonda para cima se decimal >= 0.5
            centro_x = posicao_x + comprimento / 2
            # Se a parte decimal for >= 0.5, arredonda para cima, senão para baixo
            parte_decimal = centro_x - math.floor(centro_x)
            if parte_decimal >= 0.5:
                centro_x_rounded = math.ceil(centro_x)
            else:
                centro_x_rounded = math.floor(centro_x)
            posicoes.append(centro_x_rounded)
        
        elif 61 <= comprimento <= 90:
            # 2 blocos - arredondamento complementar
            pos1 = posicao_x + (comprimento / 3)
            pos2 = posicao_x + (2 * comprimento / 3)
            
            # Arredonda primeira posição para baixo
            pos1_rounded = math.floor(pos1)
            # Arredonda segunda posição para cima para compensar
            pos2_rounded = math.ceil(pos2)
            
            posicoes.extend([pos1_rounded, pos2_rounded])
        
        elif 91 <= comprimento:
            # 3 blocos - mantém o central exato
            pos1 = posicao_x + (comprimento / 4)
            pos2 = posicao_x + (comprimento / 2)  # Central
            pos3 = posicao_x + (3 * comprimento / 4)
            
            # Arredonda primeira posição para baixo
            pos1_rounded = math.floor(pos1)
            # Mantém posição central exata
            pos2_rounded = round(pos2)
            # Arredonda última posição para cima
            pos3_rounded = math.ceil(pos3)
            
            posicoes.extend([pos1_rounded, pos2_rounded, pos3_rounded])
        
        return posicoes

    def gerar_script(self):
        print("[DEBUG] === FUNCAO gerar_script() INICIADA ===")
        print("[DEBUG] Verificando se a funcao esta sendo chamada...")
        
        if robo_logger:
            robo_logger.section("GERAÇÃO DE SCRIPT CIMA")
            robo_logger.info("🔄 === INÍCIO DO gerar_script() ===")
        
        print("[DEBUG-GERAR_SCRIPT] === INÍCIO DO gerar_script() ===")
        global _globais_pilar_especial
        print(f"[DEBUG-GERAR_SCRIPT] Estado inicial das globais: ID={id(_globais_pilar_especial)}, len={len(_globais_pilar_especial) if _globais_pilar_especial else 0}")
        
        if robo_logger:
            robo_logger.info(f"🔄 Estado inicial das globais: ID={id(_globais_pilar_especial)}, len={len(_globais_pilar_especial) if _globais_pilar_especial else 0}")
        
        if _globais_pilar_especial:
            print(f"[DEBUG-GERAR_SCRIPT] Amostra de chaves: {list(_globais_pilar_especial.keys())[:3]}")
            print(f"[DEBUG-GERAR_SCRIPT] Tem tipo_pilar? {'tipo_pilar' in _globais_pilar_especial}")
            if robo_logger:
                robo_logger.info(f"🔄 Amostra de chaves: {list(_globais_pilar_especial.keys())[:3]}")
                robo_logger.info(f"🔄 Tem tipo_pilar? {'tipo_pilar' in _globais_pilar_especial}")
        else:
            print("[DEBUG-GERAR_SCRIPT] _globais_pilar_especial está vazio ou None!")
            if robo_logger:
                robo_logger.warning("_globais_pilar_especial está vazio ou None!")
        
        try:
            # DEBUG: Verificar status do checkbox pilar_rotacionado no início da geração
            status_pilar_rotacionado = self.pilar_rotacionado_var.get()
            print(f"DEBUG GERAR_SCRIPT: Status pilar_rotacionado no inicio: {status_pilar_rotacionado}")
            if robo_logger:
                robo_logger.info(f"🔄 Status pilar_rotacionado no inicio: {status_pilar_rotacionado}")
            
            # VERIFICAR SE PILAR ESPECIAL ESTÁ ATIVO
            print("[DEBUG-GERAR_SCRIPT] Prestes a chamar _verificar_pilar_especial_ativo()...")
            print(f"[DEBUG-GERAR_SCRIPT] Estado das globais ANTES da verificação: {_globais_pilar_especial is not None and len(_globais_pilar_especial) > 0}")
            if robo_logger:
                robo_logger.info("🔄 Prestes a chamar _verificar_pilar_especial_ativo()...")
                robo_logger.info(f"🔄 Estado das globais ANTES da verificação: {_globais_pilar_especial is not None and len(_globais_pilar_especial) > 0}")
            
            pilar_especial_ativo = self._verificar_pilar_especial_ativo()
            print(f"[DEBUG-GERAR_SCRIPT] Resultado da verificação: {pilar_especial_ativo}")
            print(f"[DEBUG-GERAR_SCRIPT] Estado das globais APÓS a verificação: {_globais_pilar_especial is not None and len(_globais_pilar_especial) > 0}")
            print(f"DEBUG GERAR_SCRIPT: Pilar especial ativo: {pilar_especial_ativo}")
            
            if robo_logger:
                robo_logger.info(f"🔄 Resultado da verificação: {pilar_especial_ativo}")
                robo_logger.info(f"🔄 Estado das globais APÓS a verificação: {_globais_pilar_especial is not None and len(_globais_pilar_especial) > 0}")
                robo_logger.info(f"🔄 Pilar especial ativo: {pilar_especial_ativo}")
            
            global comprimento_pilar_global, largura_pilar_global
            comprimento_pilar_global = float(self.comprimento_pilar_entry.get().replace(',', '.'))
            largura_pilar_global = float(self.largura_pilar_entry.get().replace(',', '.'))
            # Ajuste global de desenho do lado direito no Pilar 2 (encurta 24 cm apenas no desenho)
            comprimento_desenho_direita = comprimento_pilar_global
            if (
                self._globais_pilar_especial
                and self._globais_pilar_especial.get('tipo_pilar') == 'L'
                and getattr(self, 'pilar_especial_ativo_var', None)
                and self.pilar_especial_ativo_var.get()
            ):
                try:
                    comprimento_desenho_direita = max(0.0, comprimento_pilar_global - 24.0)
                except Exception:
                    comprimento_desenho_direita = comprimento_pilar_global
            nome_pilar = self.nome_pilar_entry.get()
            


            # NOVO: Ajustar coordenadas X e Y base para pilar especial L (APENAS NO SEGUNDO PILAR)
            y_inicial_original = self.y_inicial
            x_inicial_original = self.x_inicial

            if (pilar_especial_ativo and
                hasattr(self, '_globais_pilar_especial') and self._globais_pilar_especial and
                self._globais_pilar_especial.get('tipo_pilar') == 'L' and
                getattr(self, 'pilar_especial_ativo_var', None) and
                self.pilar_especial_ativo_var.get()):
                # Aplicar o ajuste da coordenada X base APENAS para o SEGUNDO pilar especial L
                # Mover 196 unidades para a esquerda
                self.x_inicial = self.x_inicial - 196
                print(f"[PILAR-ESPECIAL-L] Coordenada X base ajustada (SEGUNDO PILAR): {x_inicial_original} -> {self.x_inicial}")
                if robo_logger:
                    robo_logger.info(f"🔄 PILAR ESPECIAL L - Coordenada X base ajustada (SEGUNDO PILAR): {x_inicial_original} -> {self.x_inicial}")

                # Aplicar o ajuste da coordenada Y base APENAS para o SEGUNDO pilar especial L
                self.y_inicial = aplicar_alteracao_pilar_especial(
                    self.y_inicial, 'posicao', 'y', 2, self
                )
                print(f"[PILAR-ESPECIAL-L] Coordenada Y base ajustada (SEGUNDO PILAR): {y_inicial_original} -> {self.y_inicial}")
                if robo_logger:
                    robo_logger.info(f"🔄 PILAR ESPECIAL L - Coordenada Y base ajustada (SEGUNDO PILAR): {y_inicial_original} -> {self.y_inicial}")
            
            # Obter configuração do tipo de linha
            tipo_linha = self.config_manager.get_config("drawing_options", "tipo_linha")
            
            script = f"""_LAYER
S
{self.config_manager.get_config("layers", "paineis")}

;
"""

            # Verificar o layer dos painéis
            layer_painel = self.config_manager.get_config("layers", "paineis")

            # Regras do Pilar Especial L para (não) desenhar certos painéis
            desenhar_pai_c = True
            desenhar_pai_d = True
            if self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L':
                # PARTE 1: não desenhar PAI.D
                # PARTE 2: não desenhar PAI.C
                if getattr(self, 'pilar_especial_ativo_var', None) and self.pilar_especial_ativo_var.get():
                    desenhar_pai_c = False  # Pilar 2
                else:
                    desenhar_pai_d = False  # Pilar 1

            # Desenhar Pilar Principal (PI)
            script += f"""_ZOOM
C {self.x_inicial},{self.y_inicial} 10
;
"""

            # Desenhar Painel C (PAI.C) - condicional para Pilar Especial L
            if desenhar_pai_c:
                script += f"""_ZOOM
C {self.x_inicial-1},{self.y_inicial+largura_pilar_global/2} 10
;
"""
                if tipo_linha == "mline":
                    script += f"""_MLINE
ST
SAR
S
1.8
{self.x_inicial-2},{self.y_inicial}
{self.x_inicial-2},{self.y_inicial+largura_pilar_global}

;
"""
                else:
                    script += f"""_PLINE
{self.x_inicial-2},{self.y_inicial}
{self.x_inicial-2},{self.y_inicial+largura_pilar_global}
{self.x_inicial},{self.y_inicial+largura_pilar_global}
{self.x_inicial},{self.y_inicial}
C
;
"""

            # Desenhar Painel D (PAI.D) - condicional para Pilar Especial L
            if desenhar_pai_d:
                # Ajuste: encurtar 24 cm no Pilar 2 (apenas desenho do lado direito)
                comp_direita = comprimento_pilar_global
                if (
                    self._globais_pilar_especial
                    and self._globais_pilar_especial.get('tipo_pilar') == 'L'
                    and getattr(self, 'pilar_especial_ativo_var', None)
                    and self.pilar_especial_ativo_var.get()
                ):
                    try:
                        comp_direita = max(0.0, float(comprimento_pilar_global) - 24.0)
                    except Exception:
                        comp_direita = comprimento_pilar_global
                script += f"""_ZOOM
C {self.x_inicial+comp_direita+1},{self.y_inicial+largura_pilar_global/2} 10
;
"""
                if tipo_linha == "mline":
                    script += f"""_MLINE
ST
SAR
S
1.8
{self.x_inicial+comp_direita},{self.y_inicial}
{self.x_inicial+comp_direita},{self.y_inicial+largura_pilar_global}

;
"""
                else:
                    script += f"""_PLINE
{self.x_inicial+comp_direita},{self.y_inicial}
{self.x_inicial+comp_direita+2},{self.y_inicial}
{self.x_inicial+comp_direita+2},{self.y_inicial+largura_pilar_global}
{self.x_inicial+comp_direita},{self.y_inicial+largura_pilar_global}
C
;
"""

            # Desenhar Painel B (PAI.B)
            if robo_logger:
                robo_logger.subsection("APLICAÇÃO DE ALTERAÇÕES PILAR ESPECIAL - PAI.B")
                robo_logger.info("🔄 Aplicando alterações do pilar especial para PAI.B...")
            
            # Aplicar alterações do pilar especial para PAI.B
            posicao_x_pai_b = aplicar_alteracao_pilar_especial(self.x_inicial-11, 'posicao', 'pai_b', 1, self)
            posicao_y_pai_b = aplicar_alteracao_pilar_especial(self.y_inicial+largura_pilar_global, 'posicao', 'pai_b', 1, self)
            comprimento_pai_b = aplicar_alteracao_pilar_especial(comprimento_pilar_global+22, 'tamanho', 'pai_b', 1, self)

            # Ajuste adicional: no Pilar 2, mover PAI.B para a direita o mesmo valor que foi diminuído do tamanho
            if (
                self._globais_pilar_especial
                and self._globais_pilar_especial.get('tipo_pilar') == 'L'
                and getattr(self, 'pilar_especial_ativo_var', None)
                and self.pilar_especial_ativo_var.get()
            ):
                try:
                    base_tamanho = (comprimento_pilar_global + 22)
                    diminuido = base_tamanho - float(comprimento_pai_b)
                    if abs(diminuido) > 1e-6:
                        posicao_x_pai_b = float(posicao_x_pai_b) + diminuido
                except Exception:
                    pass

            # REGRAS NOVAS: Ajustes específicos para PAI.B conforme modo/pilar
            if self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L':
                eh_pilar2 = bool(getattr(self, 'pilar_especial_ativo_var', None) and self.pilar_especial_ativo_var.get())
                if eh_pilar2:
                    # Pilar 2: crescer 36.1 cm na extremidade ESQUERDA
                    try:
                        posicao_x_pai_b = float(posicao_x_pai_b) - 36.1
                        comprimento_pai_b = float(comprimento_pai_b) + 36.1
                    except Exception:
                        pass
                    
                    # Aplicar ajustes de largura para PAI.B Pilar 2
                    posicao_x_pai_b = aplicar_alteracao_pilar_especial(posicao_x_pai_b, 'posicao', 'pai_b', 2, self)
                    comprimento_pai_b = aplicar_alteracao_pilar_especial(comprimento_pai_b, 'tamanho', 'pai_b', 2, self)
                else:
                    # Pilar 1: crescer 14.1 cm na extremidade DIREITA (PLINE e MLINE)
                    try:
                        comprimento_pai_b = float(comprimento_pai_b) + 14.1
                    except Exception:
                        pass
            
            if robo_logger:
                robo_logger.info(f"🔄 PAI.B - Posição X: {self.x_inicial-11} -> {posicao_x_pai_b}")
                robo_logger.info(f"🔄 PAI.B - Posição Y: {self.y_inicial+largura_pilar_global} -> {posicao_y_pai_b}")
                robo_logger.info(f"🔄 PAI.B - Comprimento: {comprimento_pilar_global+22} -> {comprimento_pai_b}")
            
            # ÂNCORA POR PILAR (proporcional) mantendo os offsets atuais como referência
            # - Pilar 1: direita fixa (usar a ponta direita atual)
            # - Pilar 2: esquerda fixa (usar a ponta esquerda atual) e encurtar -24 na direita
            eh_p2 = bool(
                self._globais_pilar_especial
                and self._globais_pilar_especial.get('tipo_pilar') == 'L'
                and getattr(self, 'pilar_especial_ativo_var', None)
                and self.pilar_especial_ativo_var.get()
            )
            current_start_b = posicao_x_pai_b
            current_end_b = posicao_x_pai_b + comprimento_pai_b
            if self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L':
                if eh_p2:
                    # Pilar 2: manter início, ajustando somente a direita (-24)
                    posicao_x_pai_b = current_start_b
                    end_x_pai_b = posicao_x_pai_b + comprimento_pai_b - 24.0
                else:
                    # Pilar 1: manter fim atual, recalc início
                    end_x_pai_b = current_end_b
                    posicao_x_pai_b = end_x_pai_b - comprimento_pai_b
            else:
                end_x_pai_b = current_end_b

            script += f"""_ZOOM
C {self.x_inicial+comprimento_pilar_global/2},{self.y_inicial+largura_pilar_global+1} 10
;
"""
            if tipo_linha == "mline":
                script += f"""_MLINE
ST
SAR
S
2
{posicao_x_pai_b},{posicao_y_pai_b + 2}
{end_x_pai_b},{posicao_y_pai_b + 2}

;
"""
            else:
                script += f"""_PLINE
{posicao_x_pai_b},{posicao_y_pai_b}
{end_x_pai_b},{posicao_y_pai_b}
{end_x_pai_b},{posicao_y_pai_b+2}
{posicao_x_pai_b},{posicao_y_pai_b+2}
C
;
"""

            # Desenhar Painel A (PAI.A)
            # Aplicar alterações do pilar especial para PAI.A
            posicao_x_pai_a = aplicar_alteracao_pilar_especial(self.x_inicial-11, 'posicao', 'pai_a', 1, self)
            posicao_y_pai_a = aplicar_alteracao_pilar_especial(self.y_inicial, 'posicao', 'pai_a', 1, self)
            comprimento_pai_a = aplicar_alteracao_pilar_especial(comprimento_pilar_global+22, 'tamanho', 'pai_a', 1, self)

            # REGRAS NOVAS: Ajustes específicos para PAI.A
            if self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L':
                eh_pilar2 = bool(getattr(self, 'pilar_especial_ativo_var', None) and self.pilar_especial_ativo_var.get())
                try:
                    if eh_pilar2:
                        # Pilar 2: crescer 13.0 cm na extremidade ESQUERDA (ambos modos)
                        posicao_x_pai_a = float(posicao_x_pai_a) - 13.0
                        comprimento_pai_a = float(comprimento_pai_a) + 13.0
                        
                        # Aplicar ajustes de largura para PAI.A Pilar 2
                        posicao_x_pai_a = aplicar_alteracao_pilar_especial(posicao_x_pai_a, 'posicao', 'pai_a', 2, self)
                        comprimento_pai_a = aplicar_alteracao_pilar_especial(comprimento_pai_a, 'tamanho', 'pai_a', 2, self)
                    else:
                        # Pilar 1
                        if tipo_linha == "mline":
                            # MLINE: diminuir 2 cm na extremidade DIREITA
                            comprimento_pai_a = float(comprimento_pai_a) - 2.0
                        else:
                            # PLINE: crescer 0.4 cm na extremidade DIREITA
                            comprimento_pai_a = float(comprimento_pai_a) + 0.4
                except Exception:
                    pass
            
            script += f"""_ZOOM
C {self.x_inicial+comprimento_pilar_global/2},{self.y_inicial-1} 10
;
"""
            # ÂNCORA POR PILAR (proporcional) para PAI.A mantendo offsets atuais
            current_start_a = posicao_x_pai_a
            current_end_a = posicao_x_pai_a + comprimento_pai_a
            if self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L':
                if eh_p2:
                    # Pilar 2: manter início e encurtar direita (-24)
                    posicao_x_pai_a = current_start_a
                    end_x_pai_a = posicao_x_pai_a + comprimento_pai_a - 24.0
                else:
                    # Pilar 1: manter fim atual
                    end_x_pai_a = current_end_a
                    posicao_x_pai_a = end_x_pai_a - comprimento_pai_a
            else:
                end_x_pai_a = current_end_a
            if tipo_linha == "mline":
                script += f"""_MLINE
ST
SAR
S
2
{posicao_x_pai_a},{posicao_y_pai_a}
{end_x_pai_a},{posicao_y_pai_a}

;
"""
            else:
                script += f"""_PLINE
{posicao_x_pai_a},{posicao_y_pai_a-2}
{end_x_pai_a},{posicao_y_pai_a-2}
{end_x_pai_a},{posicao_y_pai_a}
{posicao_x_pai_a},{posicao_y_pai_a}
C
;
"""
            # Definir layer "COTA"
            script += f"""_LAYER
S {self.config_manager.get_config("layers", "cotas")}

;
"""

            # Restaurar o estilo de cota para cotax2 após desenhar a cota
            script += f"""-DIMSTYLE
Restore
{self.config_manager.get_config("drawing_options", "dimstyle")}
;
"""
            # Adicionar cota para PAI.A
            # Ajustar posição do texto da cota baseado no tipo de pilar
            if self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L':
                posicao_texto_cota = self.y_inicial - 60  # 60cm abaixo para pilares especiais
            elif comprimento_pilar_global > 222:
                posicao_texto_cota = self.y_inicial - 80  # 80cm abaixo para pilares > 222cm
            else:
                posicao_texto_cota = self.y_inicial - 50  # 50cm abaixo para pilares <= 222cm
            
            # Cota total PAI.A deve acompanhar encurtamento no Pilar 2
            # Usar as posições finais calculadas do PAI.A
            script += f"""_DIMLINEAR
{posicao_x_pai_a},{self.y_inicial-2}
{end_x_pai_a},{self.y_inicial-2}
{(posicao_x_pai_a + end_x_pai_a) / 2},{posicao_texto_cota}
;
"""
            
            # Adicionar cotas de segmento para pilares com comprimento > 222cm
                        # Adicionar cotas de segmento para pilares com comprimento > 222cm
            if comprimento_pilar_global > 222:
                # Primeira cota de segmento: 222cm (corrigido de 244cm)
                script += f"""_DIMLINEAR
{self.x_inicial-11},{self.y_inicial-2}
{self.x_inicial+222+11},{self.y_inicial-2}
{self.x_inicial+222/2},{self.y_inicial-60}
;
"""
                
                # Segunda cota de segmento: restante dinâmico
                comprimento_restante = comprimento_pilar_global - 222
                if comprimento_restante > 0:
                    script += f"""_DIMLINEAR
{self.x_inicial+222+11},{self.y_inicial-2}
{self.x_inicial+comprimento_pilar_global+11},{self.y_inicial-2}
{self.x_inicial+222+11+comprimento_restante/2},{self.y_inicial-60}
;
"""
            
            # Adicionar cotas para PAI.B (novas cotas solicitadas)
            # As cotas para PAI.B são desenhadas se comprimento_pilar_global > 222 OU se for pilar especial
            if comprimento_pilar_global > 222 or (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L'):
                # Posição Y da linha da cota para PAI.B (borda superior do PAI.B)
                y_cota_pai_b = self.y_inicial + largura_pilar_global + 2
                
                # Posição do texto da cota total para PAI.B: 60cm acima da borda superior do PAI.B
                posicao_texto_cota_total_b = y_cota_pai_b + 60
                
                # Cota total para PAI.B
                # Usar as posições finais calculadas do PAI.B
                script += f"""_DIMLINEAR
{posicao_x_pai_b},{y_cota_pai_b}
{end_x_pai_b},{y_cota_pai_b}
{(posicao_x_pai_b + end_x_pai_b) / 2},{posicao_texto_cota_total_b}
;
"""
                # REMOVIDO: Cotas de segmento de 244 que estavam aparecendo apenas para pilares especiais
                # posicao_texto_cota_segmento_b = y_cota_pai_b + 60
                # 
                # # Primeira cota de segmento para PAI.B: restante dinâmico (lógica invertida)
                # comprimento_restante_b = comprimento_pilar_global - 244
                # if comprimento_restante_b > 0:
                #     script += f"""_DIMLINEAR
                # {self.x_inicial-11},{y_cota_pai_b}
                # {self.x_inicial+comprimento_restante_b+11},{y_cota_pai_b}
                # {self.x_inicial+comprimento_restante_b/2},{posicao_texto_cota_segmento_b}
                # ;
                # """
                # 
                # # Segunda cota de segmento para PAI.B: 266cm (lógica invertida)
                # script += f"""_DIMLINEAR
                # {self.x_inicial+comprimento_restante_b+11},{y_cota_pai_b}
                # {self.x_inicial+comprimento_pilar_global+11},{y_cota_pai_b}
                # {self.x_inicial+comprimento_restante_b+11+244/2},{posicao_texto_cota_segmento_b}
                # ;
                # """
            # Definir layer "SARRAFOS"
            script += f"""_LAYER
S {self.config_manager.get_config("layers", "sarrafos")}

;
"""
            # Desenhar Sarrafos Verticais
            # Para Pilar Especial L: alinhar supressão à mesma lógica de PAI.C/PAI.D
            # Se não desenhar PAI.C => suprimir sarrafos da esquerda
            # Se não desenhar PAI.D => suprimir sarrafos da direita
            suprimir_sar_esquerda = False
            suprimir_sar_direita = False
            try:
                suprimir_sar_esquerda = not desenhar_pai_c
                suprimir_sar_direita = not desenhar_pai_d
            except NameError:
                # Fallback para casos não-L ou caminhos alternativos
                if self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L':
                    if getattr(self, 'pilar_especial_ativo_var', None) and self.pilar_especial_ativo_var.get():
                        suprimir_sar_esquerda = True
                    else:
                        suprimir_sar_direita = True

            # Referência da borda direita para SAR do lado D (acompanhar -24 no Pilar 2 L)
            comp_direita_ref = comprimento_pilar_global
            if (
                self._globais_pilar_especial
                and self._globais_pilar_especial.get('tipo_pilar') == 'L'
                and getattr(self, 'pilar_especial_ativo_var', None)
                and self.pilar_especial_ativo_var.get()
            ):
                try:
                    comp_direita_ref = max(0.0, float(comprimento_pilar_global) - 24.0)
                except Exception:
                    comp_direita_ref = comprimento_pilar_global

            if largura_pilar_global < 30:
                # SAR 1 (lado esquerdo)
                if not suprimir_sar_esquerda:
                    script += f""";
_ZOOM
C {self.x_inicial-3},{self.y_inicial+3.5} 1
;
"""
                    # Verificar o tipo de linha configurado
                    tipo_linha = self.config_manager.get_config("drawing_options", "tipo_linha")
                    if tipo_linha == "mline":
                        script += f"""_MLINE
ST
SAR
S
2.2
{self.x_inicial-4},{self.y_inicial}
{self.x_inicial-4},{self.y_inicial+7}

;
"""
                    else:
                        script += f"""_PLINE
{self.x_inicial-4},{self.y_inicial}
{self.x_inicial-4},{self.y_inicial+7}
{self.x_inicial-2},{self.y_inicial+7}
{self.x_inicial-2},{self.y_inicial}
C
;
"""
                        script += f""";
_ZOOM
C {self.x_inicial-3},{self.y_inicial+3.5} 1
;
HP
{self.x_inicial-3},{self.y_inicial+3.5}
;
"""
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "sarrafos")}

;
"""

                # SAR 2 (lado esquerdo)
                if not suprimir_sar_esquerda:
                    script += f""";
_ZOOM
C {self.x_inicial-3},{self.y_inicial+largura_pilar_global-3.5} 1
;
"""
                    if tipo_linha == "mline":
                        script += f"""_MLINE
ST
SAR
S
2.2
{self.x_inicial-4},{self.y_inicial+largura_pilar_global-7}
{self.x_inicial-4},{self.y_inicial+largura_pilar_global}

;
"""
                    else:
                        script += f"""_PLINE
{self.x_inicial-4},{self.y_inicial+largura_pilar_global-7}
{self.x_inicial-4},{self.y_inicial+largura_pilar_global}
{self.x_inicial-2},{self.y_inicial+largura_pilar_global}
{self.x_inicial-2},{self.y_inicial+largura_pilar_global-7}
C
;
"""
                        script += f""";
_ZOOM
C {self.x_inicial-3},{self.y_inicial+largura_pilar_global-3.5} 1
;
HP
{self.x_inicial-3},{self.y_inicial+largura_pilar_global-3.5}
;
"""
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "sarrafos")}

;
"""

                # SAR 3 (lado direito)
                if not suprimir_sar_direita:
                    script += f""";
_ZOOM
C {(self.x_inicial+comp_direita+3) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+3)},{self.y_inicial+3.5} 1
;
"""
                    if tipo_linha == "mline":
                        script += f"""_MLINE
ST
SAR
S
2.2
{(self.x_inicial+comp_direita+1.8) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+1.8)},{self.y_inicial}
{(self.x_inicial+comp_direita+1.8) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+1.8)},{self.y_inicial+7}

;
"""
                    else:
                        script += f"""_PLINE
{(self.x_inicial+comp_direita+2) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+2)},{self.y_inicial}
{(self.x_inicial+comp_direita+4) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+4)},{self.y_inicial}
{(self.x_inicial+comp_direita+4) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+4)},{self.y_inicial+7}
{(self.x_inicial+comp_direita+2) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+2)},{self.y_inicial+7}
C
;
"""
                        script += f""";
_ZOOM
C {(self.x_inicial+comp_direita+3) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+3)},{self.y_inicial+3.5} 1
;
HP
{(self.x_inicial+comp_direita+3) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+3)},{self.y_inicial+3.5}
;
"""
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "sarrafos")}

;
"""

                # SAR 4 (lado direito)
                if not suprimir_sar_direita:
                    script += f""";
_ZOOM
C {(self.x_inicial+comp_direita+3) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+3)},{self.y_inicial+largura_pilar_global-3.5} 1
;
"""
                    if tipo_linha == "mline":
                        script += f"""mline
ST
SAR
S
2.2
{(self.x_inicial+comp_direita+1.8) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+1.8)},{self.y_inicial+largura_pilar_global-7}
{(self.x_inicial+comp_direita+1.8) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+1.8)},{self.y_inicial+largura_pilar_global}

;
"""
                    else:
                        script += f"""_PLINE
{(self.x_inicial+comp_direita+2) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+2)},{self.y_inicial+largura_pilar_global-7}
{(self.x_inicial+comp_direita+4) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+4)},{self.y_inicial+largura_pilar_global-7}
{(self.x_inicial+comp_direita+4) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+4)},{self.y_inicial+largura_pilar_global}
{(self.x_inicial+comp_direita+2) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+2)},{self.y_inicial+largura_pilar_global}
C
;
"""
                    script += f""";
_ZOOM
C {(self.x_inicial+comp_direita+3) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+3)},{self.y_inicial+largura_pilar_global-3.5} 1
;
"""
                if tipo_linha != "mline":
                    script += f"""HP
{(self.x_inicial+comp_direita+3) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+3)},{self.y_inicial+largura_pilar_global-3.5}
;
"""
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "sarrafos")}

;
"""
            else:
                # SAR 9 (lado esquerdo) – suprimir quando suprimir_sar_esquerda
                if not suprimir_sar_esquerda:
                    script += f""";
_ZOOM
C {self.x_inicial-3},{self.y_inicial+largura_pilar_global/2} 1
;
"""
                    if tipo_linha == "mline":
                        script += f"""mline
ST
SAR
S
2.2
{self.x_inicial-4},{self.y_inicial}
{self.x_inicial-4},{self.y_inicial+largura_pilar_global}

;
"""
                    else:
                        script += f"""_PLINE
{self.x_inicial-4},{self.y_inicial}
{self.x_inicial-4},{self.y_inicial+largura_pilar_global}
{self.x_inicial-2},{self.y_inicial+largura_pilar_global}
{self.x_inicial-2},{self.y_inicial}
C
;
"""
                    script += f""";
_ZOOM
C {self.x_inicial-3},{self.y_inicial+largura_pilar_global/2} 1
;
"""
                    if tipo_linha != "mline":
                        script += f"""HP
{self.x_inicial-3},{self.y_inicial+largura_pilar_global/2}
;
"""
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "sarrafos")}

;
"""
                # SAR 10 (lado direito) – suprimir quando suprimir_sar_direita
                if not suprimir_sar_direita:
                    script += f""";
_ZOOM
C {(self.x_inicial+comp_direita+3) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+3)},{self.y_inicial+largura_pilar_global/2} 1
;
"""
                    if tipo_linha == "mline":
                        script += f"""mline
ST
SAR
S
2.2
{(self.x_inicial+comp_direita+1.8) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+1.8)},{self.y_inicial}
{(self.x_inicial+comp_direita+1.8) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+1.8)},{self.y_inicial+largura_pilar_global}

;
"""
                    else:
                        script += f"""_PLINE
{(self.x_inicial+comp_direita+2) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+2)},{self.y_inicial}
{(self.x_inicial+comp_direita+4) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+4)},{self.y_inicial}
{(self.x_inicial+comp_direita+4) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+4)},{self.y_inicial+largura_pilar_global}
{(self.x_inicial+comp_direita+2) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+2)},{self.y_inicial+largura_pilar_global}
C
;
"""
                    script += f""";
_ZOOM
C {(self.x_inicial+comp_direita+3) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+3)},{self.y_inicial+largura_pilar_global/2} 1
;
"""
                    if tipo_linha != "mline":
                        script += f"""HP
{(self.x_inicial+comp_direita+3) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar')=='L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get()) else (self.x_inicial+comprimento_pilar_global+3)},{self.y_inicial+largura_pilar_global/2}
;
"""
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "sarrafos")}

;
"""

            # Desenhar Sarrafos Horizontais
            # SAR 5
            if not suprimir_sar_esquerda and tipo_linha == "mline":
                script += f""";
mline
ST
SAR
S
2.2
{self.x_inicial-11},{self.y_inicial+largura_pilar_global}
{self.x_inicial-4},{self.y_inicial+largura_pilar_global}

;
"""
            else:
                if not suprimir_sar_esquerda:
                    script += f""";
_PLINE
{self.x_inicial-11},{self.y_inicial+largura_pilar_global-2}
{self.x_inicial-4},{self.y_inicial+largura_pilar_global-2}
{self.x_inicial-4},{self.y_inicial+largura_pilar_global}
{self.x_inicial-11},{self.y_inicial+largura_pilar_global}
C
;
"""
            if not suprimir_sar_esquerda:
                script += f""";
_ZOOM
C {self.x_inicial-7.5},{self.y_inicial+largura_pilar_global-1} 1
;
"""
            if not suprimir_sar_esquerda and tipo_linha != "mline":
                script += f"""HP
{self.x_inicial-7.5},{self.y_inicial+largura_pilar_global-1}
;
"""
            if not suprimir_sar_esquerda:
                script += f"""_LAYER
S {self.config_manager.get_config("layers", "sarrafos")}

;
"""
            # SAR 6
            if not suprimir_sar_esquerda:
                script += f""";
_ZOOM
C {self.x_inicial-7.5},{self.y_inicial+1} 1
;
"""
            if not suprimir_sar_esquerda and tipo_linha == "mline":
                script += f"""mline
ST
SAR
S
2.2
{self.x_inicial-11},{self.y_inicial+2.2}
{self.x_inicial-4},{self.y_inicial+2.2}

;
"""
            else:
                if not suprimir_sar_esquerda:
                    script += f"""_PLINE
{self.x_inicial-11},{self.y_inicial+2}
{self.x_inicial-11},{self.y_inicial}
{self.x_inicial-4},{self.y_inicial}
{self.x_inicial-4},{self.y_inicial+2}
C
;
"""
            if not suprimir_sar_esquerda:
                script += f""";
_ZOOM
C {self.x_inicial-7.5},{self.y_inicial+1} 1
;
"""
            if not suprimir_sar_esquerda and tipo_linha != "mline":
                script += f"""HP
{self.x_inicial-7.5},{self.y_inicial+1}
;
"""
            script += f"""_LAYER
S {self.config_manager.get_config("layers", "sarrafos")}

;
"""

            # SAR 7
            if not suprimir_sar_direita:
                script += f""";
_ZOOM
C {self.x_inicial+comp_direita_ref+7.5},{self.y_inicial+largura_pilar_global-1} 1
;
"""
            if not suprimir_sar_direita and tipo_linha == "mline":
                script += f"""mline
ST
SAR
S
2.2
{self.x_inicial+comp_direita_ref+11},{self.y_inicial+largura_pilar_global-2.2}
{self.x_inicial+comp_direita_ref+4},{self.y_inicial+largura_pilar_global-2.2}

;
"""
            else:
                if not suprimir_sar_direita:
                    script += f"""_PLINE
{self.x_inicial+comp_direita_ref+11},{self.y_inicial+largura_pilar_global-2}
{self.x_inicial+comp_direita_ref+11},{self.y_inicial+largura_pilar_global}
{self.x_inicial+comp_direita_ref+4},{self.y_inicial+largura_pilar_global}
{self.x_inicial+comp_direita_ref+4},{self.y_inicial+largura_pilar_global-2}
C
;
"""
            if not suprimir_sar_direita:
                script += f""";
_ZOOM
C {self.x_inicial+comp_direita_ref+7.5},{self.y_inicial+largura_pilar_global-1} 1
;
"""
            if not suprimir_sar_direita and tipo_linha != "mline":
                script += f"""HP
{self.x_inicial+comp_direita_ref+7.5},{self.y_inicial+largura_pilar_global-1}
;
"""
            script += f"""_LAYER
S {self.config_manager.get_config("layers", "sarrafos")}

;
"""

            # SAR 8
            if not suprimir_sar_direita:
                script += f""";
_ZOOM
C {self.x_inicial+comp_direita_ref+7.5},{self.y_inicial+1} 1
;
"""
            if not suprimir_sar_direita and tipo_linha == "mline":
                script += f"""mline
ST
SAR
S
2.2
{self.x_inicial+comp_direita_ref+11},{self.y_inicial}
{self.x_inicial+comp_direita_ref+4},{self.y_inicial}

;
"""
            else:
                if not suprimir_sar_direita:
                    script += f"""_PLINE
{self.x_inicial+comp_direita_ref+11},{self.y_inicial+2}
{self.x_inicial+comp_direita_ref+11},{self.y_inicial}
{self.x_inicial+comp_direita_ref+4},{self.y_inicial}
{self.x_inicial+comp_direita_ref+4},{self.y_inicial+2}
C
;
"""
            if not suprimir_sar_direita:
                script += f""";
_ZOOM
C {self.x_inicial+comp_direita_ref+7.5},{self.y_inicial+1} 1
;
"""
            if not suprimir_sar_direita and tipo_linha != "mline":
                script += f"""HP
{self.x_inicial+comp_direita_ref+7.5},{self.y_inicial+1}
;
"""
            script += f"""_LAYER
S {self.config_manager.get_config("layers", "sarrafos")}

;
"""

            # Desenhar SAR244+.1 e SAR244+.2 se comprimento_pilar > 222
            if comprimento_pilar_global > 222:
                # SAR244+.1
                script += f""";
_ZOOM
C {self.x_inicial-11},{self.y_inicial+largura_pilar_global+4} 1
;
"""
                if tipo_linha == "mline":
                    script += f"""mline
ST
SAR
S
2.2
{self.x_inicial-11},{self.y_inicial+largura_pilar_global+4.2}
{self.x_inicial+comprimento_pilar_global+11},{self.y_inicial+largura_pilar_global+4.2}

;
"""
                else:
                    script += f"""_PLINE
{self.x_inicial-11},{self.y_inicial+largura_pilar_global+2}
{self.x_inicial-11},{self.y_inicial+largura_pilar_global+4.2}
{self.x_inicial+comprimento_pilar_global+11},{self.y_inicial+largura_pilar_global+4.2}
{self.x_inicial+comprimento_pilar_global+11},{self.y_inicial+largura_pilar_global+2}
C
;
"""
                script += f""";
_ZOOM
C {self.x_inicial},{self.y_inicial+largura_pilar_global+5.1} 1
;
"""
                if tipo_linha != "mline":
                    script += f"""HP2
{self.x_inicial},{self.y_inicial+largura_pilar_global+3.1}
;
"""
                script += f"""_LAYER
S {self.config_manager.get_config("layers", "sarrafos")}

;
"""

                # SAR244+.2
                script += f""";
_ZOOM
C {self.x_inicial-11},{self.y_inicial-6.2} 1
;
"""
                if tipo_linha == "mline":
                    script += f"""mline
ST
SAR
S
2.2
{self.x_inicial-11},{self.y_inicial-2}
{self.x_inicial+comprimento_pilar_global+11},{self.y_inicial-2}

;
"""
                else:
                    script += f"""_PLINE
{self.x_inicial-11},{self.y_inicial-4.2}
{self.x_inicial-11},{self.y_inicial-2}
{self.x_inicial+comprimento_pilar_global+11},{self.y_inicial-2}
{self.x_inicial+comprimento_pilar_global+11},{self.y_inicial-4.2}
C
;
"""
                script += f""";
_ZOOM
C {self.x_inicial},{self.y_inicial-5.1} 1
;
"""
                if tipo_linha != "mline":
                    script += f"""HP2
{self.x_inicial},{self.y_inicial-3.1}
;
"""
                script += f"""_LAYER
S {self.config_manager.get_config("layers", "sarrafos")}

;
"""

            # Definir layer "COTA"
            script += f"""_LAYER
S {self.config_manager.get_config("layers", "cotas")}

;
"""

            # Restaurar o estilo de cota para cotax2 após desenhar a cota
            script += f"""-DIMSTYLE
Restore
{self.config_manager.get_config("drawing_options", "dimstyleCENTRO")}
;
"""

            # Adicionar cota entre a ponta direita superior do PAI.A e a ponta direita inferior do PAI.B
            script += f"""_DIMLINEAR
{self.x_inicial+comprimento_pilar_global+11},{self.y_inicial}
{self.x_inicial+comprimento_pilar_global+11},{self.y_inicial+largura_pilar_global}
{self.x_inicial+comprimento_pilar_global-5},{((self.y_inicial + self.y_inicial + largura_pilar_global) / 2) + 7}
;
"""

            # Adicionar cota entre a ponta direita inferior do PAI.C e a ponta esquerda inferior do PAI.D
            if (
                self._globais_pilar_especial
                and self._globais_pilar_especial.get('tipo_pilar') == 'L'
                and self.pilar_especial_ativo_var.get()
            ):
                # Pilar 2: usar coordenadas ajustadas do PAI.C e PAI.D
                posicao_x_pai_c = posicao_x_pai_a  # Usar a posição ajustada do PAI.A (que é o PAI.C)
                end_x_pai_d = end_x_pai_b - 11  # Usar a posição final ajustada do PAI.B (que é o PAI.D) e mover 11cm para esquerda
                pos_y_texto_cota = self.y_inicial + 5  # Posição atual do texto
            else:
                # Pilar 1: usar coordenadas normais e subir o texto em 5cm
                posicao_x_pai_c = self.x_inicial
                end_x_pai_d = self.x_inicial + comprimento_pilar_global
                pos_y_texto_cota = self.y_inicial + 10  # Subir 5cm da posição atual (5 + 5 = 10)
            
            script += f"""_DIMLINEAR
{posicao_x_pai_c},{self.y_inicial}
{end_x_pai_d},{self.y_inicial}
{(posicao_x_pai_c + end_x_pai_d) / 2},{pos_y_texto_cota}
;
"""

            # Restaurar o estilo de cota para cotax2 após desenhar a cota
            script += f"""-DIMSTYLE
Restore
{self.config_manager.get_config("drawing_options", "dimstyle")}
;
"""

            # Adicionar cotas dos sarrafos (apenas para pilares comuns, não para pilares especiais)
            if not (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L'):
                # Adicionar cota para a parte superior do SAR 6
                pos_y_texto_cota_sar = self.y_inicial + 8
                if largura_pilar_global >= 40:
                    pos_y_texto_cota_sar += 15
                script += f"""_DIMLINEAR
{self.x_inicial-11},{self.y_inicial+2}
{self.x_inicial-4},{self.y_inicial+2}
{self.x_inicial-7.5},{pos_y_texto_cota_sar}
;
"""

                # Adicionar cota para a parte superior do SAR 8
                pos_y_texto_cota_sar8 = self.y_inicial + 8
                if largura_pilar_global >= 40:
                    pos_y_texto_cota_sar8 += 15
                script += f"""_DIMLINEAR
{self.x_inicial+comprimento_pilar_global+4},{self.y_inicial+2}
{self.x_inicial+comprimento_pilar_global+11},{self.y_inicial+2}
{self.x_inicial+comprimento_pilar_global+7.5},{pos_y_texto_cota_sar8}
;
"""

            script += ";\n"

            # Definir layer "ESTRUTURA METAL"
            script += f"""_LAYER
S {self.config_manager.get_config("layers", "metal")}

;
"""

            # Desenhar METAL.A
            if comprimento_pilar_global > 222:
                posicao_y_a = self.y_inicial - 13.6
            else:
                posicao_y_a = self.y_inicial - 11.4
            
            # Ajustar posição se grades com sarrafo estiver desabilitado
            if self.config_manager.get_config("drawing_options", "grades_com_sarrafo") == "nao":
                posicao_y_a += 2.4  # Desce 2.4cm (valor positivo porque Y cresce para baixo)
            
            # Aplicar alterações para METAL A
            # - Sem ajuste em Y (não solicitado)
            # - Pilar 1: normal
            # - Pilar 2: mover 4.4 cm para a ESQUERDA e crescer +4.4 no comprimento
            posicao_y_a = posicao_y_a
            if (
                self._globais_pilar_especial
                and self._globais_pilar_especial.get('tipo_pilar') == 'L'
                and self.pilar_especial_ativo_var.get()
            ):
                # PARTE 2 (Pilar 2)
                posicao_x_a = (self.x_inicial - 31) - 4.4
                comprimento_metal_a = (comprimento_pilar_global + 62) + 4.4
                # Ajuste fino específico para MLINE: reduzir 2.4cm na extremidade esquerda
                if tipo_linha == "mline":
                    posicao_x_a += 2.4
                    comprimento_metal_a -= 2.4
                
                # Aplicar ajustes de largura para Metal A Pilar 2
                posicao_x_a = aplicar_alteracao_pilar_especial(posicao_x_a, 'posicao', 'metal_a', 2, self)
                comprimento_metal_a = aplicar_alteracao_pilar_especial(comprimento_metal_a, 'tamanho', 'metal_a', 2, self)
            else:
                # PARTE 1 (ou não L)
                posicao_x_a = aplicar_alteracao_pilar_especial(
                    self.x_inicial - 31, 'posicao', 'metal_a', 1, self
                )
                comprimento_metal_a = aplicar_alteracao_pilar_especial(
                    comprimento_pilar_global + 62, 'tamanho', 'metal_a', 1, self
                )

            # ANCORAGEM POR PILAR para METAL A mantendo offsets previamente aplicados
            # - Pilar 1: manter ponta direita atual
            # - Pilar 2: manter ponta esquerda atual
            try:
                if self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L':
                    eh_p2_local = bool(getattr(self, 'pilar_especial_ativo_var', None) and self.pilar_especial_ativo_var.get())
                    current_start_a = posicao_x_a
                    current_end_a = posicao_x_a + comprimento_metal_a
                    if eh_p2_local:
                        posicao_x_a = current_start_a
                    else:
                        posicao_x_a = current_end_a - comprimento_metal_a
            except Exception:
                pass

            largura_metal = 7

            if robo_logger:
                try:
                    eh_p2_local = bool(self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get())
                    end_draw_a = posicao_x_a + comprimento_metal_a - (24.0 if eh_p2_local else 0.0)
                    robo_logger.info(f"🔧 METAL A - posX={posicao_x_a}, posY={posicao_y_a}, comp={comprimento_metal_a}, endX={end_draw_a}, largura={largura_metal}")
                except Exception:
                    pass

            # Verificar o tipo de linha configurado
            if tipo_linha == "mline":
                # Usar MLINE para o lado A - usar coordenadas do fundo do retângulo
                script += f"""MLINE
ST
METAL2
S
7
{posicao_x_a},{posicao_y_a-largura_metal + 7}
{(posicao_x_a+comprimento_metal_a-24.0) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L' and self.pilar_especial_ativo_var.get()) else (posicao_x_a+comprimento_metal_a)},{posicao_y_a-largura_metal + 7}

"""
            else:
                # Usar PLINE original para o lado A
                script += f"""_PLINE
{posicao_x_a},{posicao_y_a}
{(posicao_x_a+comprimento_metal_a-24.0) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L' and self.pilar_especial_ativo_var.get()) else (posicao_x_a+comprimento_metal_a)},{posicao_y_a}
{(posicao_x_a+comprimento_metal_a-24.0) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L' and self.pilar_especial_ativo_var.get()) else (posicao_x_a+comprimento_metal_a)},{posicao_y_a-largura_metal}
{posicao_x_a},{posicao_y_a-largura_metal}
C
;
"""

            # Definir layer "ESTRUTURA METAL"
            script += f"""_LAYER
S {self.config_manager.get_config("layers", "metal")}

;
"""

            # Desenhar METAL.B
            if comprimento_pilar_global > 222:
                posicao_y_b = self.y_inicial + largura_pilar_global + 9.6 + 6 - 2
            else:
                posicao_y_b = self.y_inicial + largura_pilar_global + 7.4 + 6 - 2
            
            # Ajustar posição se grades com sarrafo estiver desabilitado
            if self.config_manager.get_config("drawing_options", "grades_com_sarrafo") == "nao":
                posicao_y_b -= 2.4  # Sobe 2.4cm (valor negativo porque Y cresce para baixo)
            
            # Aplicar alterações para METAL B
            # - Pilar 1: crescer +5.5 no comprimento acima do atual (que já era base - 58.5)
            # - Pilar 2: mover para direita inicialmente, reduzir tamanho pelo deslocamento
            #            e então ajustar posição para 13.1 cm à esquerda do que ficou; tamanho proporcional ao deslocamento final
            posicao_y_b = posicao_y_b
            if self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L':
                base_x_b = (self.x_inicial - 31)
                base_len_b = (comprimento_pilar_global + 62)
                if not self.pilar_especial_ativo_var.get():
                    # PARTE 1 (Pilar 1)
                    posicao_x_b = base_x_b

                    # Aplicar ajuste fixo do pilar especial L (-58.5 + 5.5 = -53)
                    comprimento_base = (base_len_b - 58.5) + 5.5

                    # Aplicar ajuste adicional baseado na largura do pilar 2
                    largura_pilar_2 = float(self._globais_pilar_especial.get('larg_2', 20) or 20)
                    ajuste_largura = (largura_pilar_2 - 20.0) * -1  # Inverso: se larg_2=25, ajuste=-5
                    comprimento_metal_b = comprimento_base + ajuste_largura
                else:
                    # PARTE 2 (Pilar 2)
                    delta_move_inicial = 58.5
                    delta_move_final = delta_move_inicial - 13.1  # ajustar 13.1 para a esquerda em relação ao atual
                    posicao_x_b = base_x_b + delta_move_final
                    comprimento_metal_b = base_len_b - delta_move_final  # tamanho proporcional ao tanto que mover
                    # Ajuste específico apenas para modo MLINE no lado B do Pilar 2:
                    if tipo_linha == "mline":
                        posicao_x_b -= 3.6  # mover 3.6cm para a esquerda da posição atual
                        comprimento_metal_b += 3.6  # crescer 3.6cm no comprimento
                        # Ajuste fino adicional: reduzir 1.2cm na extremidade esquerda
                        posicao_x_b += 1.2
                        comprimento_metal_b -= 1.2
            else:
                posicao_x_b = aplicar_alteracao_pilar_especial(
                    self.x_inicial - 31, 'posicao', 'metal_b', 1, self
                )
                comprimento_metal_b = aplicar_alteracao_pilar_especial(
                    comprimento_pilar_global + 62, 'tamanho', 'metal_b', 1, self
                )

            # ANCORAGEM POR PILAR para METAL B mantendo offsets previamente aplicados
            try:
                if self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L':
                    eh_p2_local = bool(getattr(self, 'pilar_especial_ativo_var', None) and self.pilar_especial_ativo_var.get())
                    current_start_b = posicao_x_b
                    current_end_b = posicao_x_b + comprimento_metal_b
                    if eh_p2_local:
                        posicao_x_b = current_start_b
                    else:
                        posicao_x_b = current_end_b - comprimento_metal_b
            except Exception:
                pass

            if robo_logger:
                try:
                    eh_p2_local = bool(self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L' and getattr(self,'pilar_especial_ativo_var',None) and self.pilar_especial_ativo_var.get())
                    end_draw_b = posicao_x_b + comprimento_metal_b - (24.0 if eh_p2_local else 0.0)
                    robo_logger.info(f"🔧 METAL B - posX={posicao_x_b}, posY={posicao_y_b}, comp={comprimento_metal_b}, endX={end_draw_b}, largura={largura_metal}")
                except Exception:
                    pass

            # Verificar o tipo de linha configurado
            if tipo_linha == "mline":
                # Usar MLINE para o lado B - usar coordenadas do topo do retângulo
                script += f"""MLINE
ST
METAL2
S
7
{posicao_x_b},{posicao_y_b+largura_metal}
{(posicao_x_b+comprimento_metal_b-24.0) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L' and self.pilar_especial_ativo_var.get()) else (posicao_x_b+comprimento_metal_b)},{posicao_y_b+largura_metal}

;
"""
            else:
                # Usar PLINE original para o lado B
                script += f"""_PLINE
{posicao_x_b},{posicao_y_b}
{(posicao_x_b+comprimento_metal_b-24.0) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L' and self.pilar_especial_ativo_var.get()) else (posicao_x_b+comprimento_metal_b)},{posicao_y_b}
{(posicao_x_b+comprimento_metal_b-24.0) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L' and self.pilar_especial_ativo_var.get()) else (posicao_x_b+comprimento_metal_b)},{posicao_y_b+largura_metal}
{posicao_x_b},{posicao_y_b+largura_metal}
C
;
"""

            # Definir layer "ESTRUTURA METAL"
            script += f"""_LAYER
S {self.config_manager.get_config("layers", "cota")}

;
"""

            # Adicionar cota para a lateral superior da estrutura metálica de cima
            # Ajustar posição Y da cota baseado no comprimento do pilar
            # ELIMINAR COTAS DE METAL PARA MODO ESPECIAL
            if not (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L'):
                posicao_y_cota_total = posicao_y_b+largura_metal+40
                if comprimento_pilar_global > 222:
                    posicao_y_cota_total += 40  # Subir 40cm quando comprimento > 222
                
                script += f"""_DIMLINEAR
{posicao_x_b},{posicao_y_b+largura_metal}
{posicao_x_b+comprimento_metal_b},{posicao_y_b+largura_metal}
{posicao_x_b+comprimento_metal_b/2},{posicao_y_cota_total}
;
"""
            # ESCREVER ESTRUTURA METALICA E ARREDONDAR
            dimstyle = self.config_manager.get_config("drawing_options", "dimstyle")
            if dimstyle == "cotax3":
                script += f"""_DIMROUNDUP3x
;
"""
            else:
                script += f"""_DIMROUNDUP
;
"""

            # Definir layer "ESTRUTURA METAL"
            script += f"""_LAYER
S {self.config_manager.get_config("layers", "metal")}

;
"""

            # Estrutura METAL.AI
            script += f"""_PLINE
{posicao_x_a},{posicao_y_a-2}
{(posicao_x_a+comprimento_metal_a-24.0) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L' and self.pilar_especial_ativo_var.get()) else (posicao_x_a+comprimento_metal_a)},{posicao_y_a-2}
{(posicao_x_a+comprimento_metal_a-24.0) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L' and self.pilar_especial_ativo_var.get()) else (posicao_x_a+comprimento_metal_a)},{posicao_y_a-5}
{posicao_x_a},{posicao_y_a-5}
C
;
"""
            # Definir layer "ESTRUTURA METAL"
            script += f"""_LAYER
S {self.config_manager.get_config("layers", "metal")}

;
"""

            # Estrutura METAL.BI
            script += f"""_PLINE
{posicao_x_b},{posicao_y_b+2}
{(posicao_x_b+comprimento_metal_b-24.0) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L' and self.pilar_especial_ativo_var.get()) else (posicao_x_b+comprimento_metal_b)},{posicao_y_b+2}
{(posicao_x_b+comprimento_metal_b-24.0) if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L' and self.pilar_especial_ativo_var.get()) else (posicao_x_b+comprimento_metal_b)},{posicao_y_b+5}
{posicao_x_b},{posicao_y_b+5}
C
;
"""
            # Definir layer "GRADES"
            script += f"""_LAYER
S {self.config_manager.get_config("layers", "paineis")}

;
"""

            # Usar valores das caixas de texto para GRA.A e GRA.B (base)
            comprimento_retangulos = [
                float(self.grade1_entry.get() or 0),
                float(self.grade2_entry.get() or 0),
                float(self.grade3_entry.get() or 0)
            ]
            espacos = [
                float(self.distancia1_entry.get() or 0),
                float(self.distancia2_entry.get() or 0)
            ]

            # Variáveis auxiliares para regras do Pilar Especial (Modo L)
            eh_modo_l = bool(self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L')
            eh_pilar2 = bool(getattr(self, 'pilar_especial_ativo_var', None) and self.pilar_especial_ativo_var.get())
            comp1 = float(self._globais_pilar_especial.get('comp_1', 0) or 0) if eh_modo_l else 0.0
            comp2 = float(self._globais_pilar_especial.get('comp_2', 0) or 0) if eh_modo_l else 0.0
            larg1 = float(self._globais_pilar_especial.get('larg_1', 0) or 0) if eh_modo_l else 0.0
            larg2 = float(self._globais_pilar_especial.get('larg_2', 0) or 0) if eh_modo_l else 0.0

            # Desenhar GRA.A
            posicao_y_a = -(7 if comprimento_pilar_global <= 222 else 9.2) - 4.4 # Soma 4.8 para subir a grade
            posicao_x = 0 - 11 # Base
            
            # Aplicar alterações do pilar especial para Grade A
            # posicao_y_a = aplicar_alteracao_pilar_especial(posicao_y_a, 'posicao', 'grade_a', 1, self)
            
            # Aplicar alterações do pilar especial para posição X da Grade A (pilar 2)
            if eh_pilar2:
                # Aplicar ajuste fixo do pilar especial L (-13cm)
                posicao_x_ajustada = posicao_x - 13.0

                # Aplicar ajuste adicional baseado na largura do pilar 1
                largura_pilar_1 = float(self._globais_pilar_especial.get('larg_1', 20) or 20)
                ajuste_largura = (largura_pilar_1 - 20.0) * -1  # Inverso: se larg_1=30, ajuste=-10
                posicao_x = posicao_x_ajustada + ajuste_largura

                if robo_logger:
                    robo_logger.info(f"Grade A - Pilar 2 Especial: ajuste fixo -13cm + largura {largura_pilar_1}cm (ajuste {ajuste_largura:+.1f}cm)")
                    robo_logger.info(f"Grade A - Pilar 2: {posicao_x_ajustada} -> {posicao_x}")
            
            # Preparar arrays de comprimentos/espacos para GRA.A
            comprimentos_a = comprimento_retangulos[:]
            espacos_a = espacos[:]
            
            # SEMPRE ler valores das grades normais (Grade Grupo 1) para Grade A
            # Obter valores das grades normais
            grade1_raw = self.grade1_entry.get()
            grade2_raw = self.grade2_entry.get()
            grade3_raw = self.grade3_entry.get()
            distancia1_raw = self.distancia1_entry.get()
            distancia2_raw = self.distancia2_entry.get()
            
            print(f"DEBUG: Valores brutos Grade A - grade1_raw='{grade1_raw}', grade2_raw='{grade2_raw}', grade3_raw='{grade3_raw}'")
            print(f"DEBUG: Valores brutos Grade A - dist1_raw='{distancia1_raw}', dist2_raw='{distancia2_raw}'")
            
            grade1 = float(grade1_raw or 0)
            grade2 = float(grade2_raw or 0)
            grade3 = float(grade3_raw or 0)
            distancia1 = float(distancia1_raw or 0)
            distancia2 = float(distancia2_raw or 0)
            
            # Verificar se os valores estão sendo lidos corretamente
            if grade1 == 0 and grade2 == 0 and grade3 == 0:
                print("DEBUG: Valores Grade A estão zerados - verificar se os dados estão sendo transferidos corretamente")
                print(f"DEBUG: Valores brutos lidos: grade1_raw='{grade1_raw}', grade2_raw='{grade2_raw}', grade3_raw='{grade3_raw}'")
            
            if robo_logger:
                robo_logger.info(f"DEBUG: Valores lidos Grade A - grade1={grade1}, grade2={grade2}, grade3={grade3}, dist1={distancia1}, dist2={distancia2}")
                robo_logger.info(f"DEBUG: Condição Grade A - grade1 > 0: {grade1 > 0}, grade2 > 0: {grade2 > 0}, grade3 > 0: {grade3 > 0}")
                robo_logger.info(f"DEBUG: Condição Grade A - grade1 > 0 or grade2 > 0 or grade3 > 0: {grade1 > 0 or grade2 > 0 or grade3 > 0}")
            print(f"DEBUG: Valores lidos Grade A - grade1={grade1}, grade2={grade2}, grade3={grade3}, dist1={distancia1}, dist2={distancia2}")
            print(f"DEBUG: Condição Grade A - grade1 > 0: {grade1 > 0}, grade2 > 0: {grade2 > 0}, grade3 > 0: {grade3 > 0}")
            print(f"DEBUG: Condição Grade A - grade1 > 0 or grade2 > 0 or grade3 > 0: {grade1 > 0 or grade2 > 0 or grade3 > 0}")
            
            # Calcular total usando Grade Grupo 1 (grades normais)
            total_grupo1 = grade1 + distancia1 + grade2 + distancia2 + grade3
            
            # Usar total do Grupo 1 para Grade A
            total_a = total_grupo1
            
            # Verificar se os campos específicos estão preenchidos
            print(f"DEBUG: Verificando Grade A - grade1={grade1}, grade2={grade2}, grade3={grade3}")
            print(f"DEBUG: Condição Grade A - grade1 > 0: {grade1 > 0}, grade2 > 0: {grade2 > 0}, grade3 > 0: {grade3 > 0}")
            print(f"DEBUG: Condição Grade A - grade1 > 0 or grade2 > 0 or grade3 > 0: {grade1 > 0 or grade2 > 0 or grade3 > 0}")
            
            if grade1 > 0 or grade2 > 0 or grade3 > 0:
                # Usar valores específicos dos campos
                comprimentos_a = [grade1, grade2, grade3]
                espacos_a = [distancia1, distancia2]
                if robo_logger:
                    robo_logger.info(f"GRA.A usando valores específicos: comprimentos={comprimentos_a}, espacos={espacos_a}")
                print(f"DEBUG: GRA.A usando valores específicos: comprimentos={comprimentos_a}, espacos={espacos_a}")
            else:
                # Usar lógica de breakdown
                comprimentos_a, espacos_a = self._breakdown_grades_total(total_a)
                if robo_logger:
                    robo_logger.info(f"GRA.A total={total_a} => comprimentos={comprimentos_a}, espacos={espacos_a}")

                # AJUSTES FIXOS - EXTREMIDADES - PILAR 1/2 - GRADE A
                # Identificar última grade ativa (direita)
                ativos_idx_a = [idx for idx, c in enumerate(comprimentos_a) if c and c > 0]
                if ativos_idx_a:
                    last_idx_a = ativos_idx_a[-1]
                    # Pilar 1 (PARTE 1)
                    if not eh_pilar2:
                        if str(tipo_linha).lower() == "mline":
                            comprimentos_a[last_idx_a] = max(0.1, float(comprimentos_a[last_idx_a]) - 2.0)
                            if robo_logger:
                                robo_logger.info("GRA.A P1 MLINE: -2.0cm na última grade (direita)")
                        else:
                            comprimentos_a[last_idx_a] = max(0.1, float(comprimentos_a[last_idx_a]) + 0.4)
                            if robo_logger:
                                robo_logger.info("GRA.A P1 PLINE: +0.4cm na última grade (direita)")
                    else:
                        # Pilar 2 (PARTE 2) - ambos os modos: -20cm (posição já ajustada pelas globais)
                        comprimentos_a[last_idx_a] = max(0.1, float(comprimentos_a[last_idx_a]) - 20.0)
                        if robo_logger:
                            robo_logger.info("GRA.A P2: -20.0cm na última grade (direita) - posição já ajustada pelas globais")

            # Desenhar preservando múltiplas grades
            posicao_x_base_a = posicao_x
            print(f"DEBUG: Iniciando desenho Grade A - comprimentos_a={comprimentos_a}, espacos_a={espacos_a}")
            print(f"DEBUG: Config grades_com_sarrafo={self.config_manager.get_config('drawing_options', 'grades_com_sarrafo')}")
            for i, comprimento in enumerate(comprimentos_a):
                print(f"DEBUG: Processando Grade A {i+1} - comprimento={comprimento}, comprimento > 0: {comprimento > 0}")
                if comprimento > 0:
                    print(f"DEBUG: Desenhando Grade A {i+1} - comprimento={comprimento}")
                    # Verifica se deve desenhar a linha/retângulo da grade
                    print(f"DEBUG: Verificando grades_com_sarrafo para Grade A {i+1}")
                    config_grades = self.config_manager.get_config("drawing_options", "grades_com_sarrafo")
                    print(f"DEBUG: Config grades_com_sarrafo='{config_grades}', config_grades == 'sim': {config_grades == 'sim'}")
                    
                    # Verificar se deve desenhar as grades individuais
                    if self.config_manager.get_config("drawing_options", "grades_com_sarrafo") == "sim":
                        # Definir layer para sarrafo das grades
                        script += f"""_LAYER
S {self.config_manager.get_config("layers", "sarrafo_grade")}

;
"""
                        # Verificar o tipo de linha configurado
                        if tipo_linha == "mline":
                            # Desenhar retângulo da GRA.A usando MLINE
                            script += f"""_MLINE
ST
sar
S
2.2
{self.x_inicial + posicao_x},{self.y_inicial + posicao_y_a + 2.4}
{self.x_inicial + posicao_x + comprimento},{self.y_inicial + posicao_y_a + 2.4}

;
"""
                        else:
                            # Desenhar retângulo da GRA.A usando PLINE
                            script += f"""_PLINE
{self.x_inicial + posicao_x},{self.y_inicial + posicao_y_a}
{self.x_inicial + posicao_x + comprimento},{self.y_inicial + posicao_y_a}
{self.x_inicial + posicao_x + comprimento},{self.y_inicial + posicao_y_a + 2.4}
{self.x_inicial + posicao_x},{self.y_inicial + posicao_y_a + 2.4}
C
;
"""
                    # Definir layer "PARAFUSO"
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "cota")}

;
"""
                    # Definir layer para os blocos
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "paineis")}

;
"""
                    # Determinar quantas grades ativas existem (com base no que será desenhado)
                    grades_ativas = sum(1 for comp in comprimentos_a if comp > 0)
                    
                    # SAR.GRA.A baseados nos detalhes dos campos (incluindo pontas)
                    posicoes_blocos = self.obter_posicoes_blocos_por_detalhes(i, is_grade_b=False)
                    # Inserir todos os blocks baseados nos detalhes
                    for j, pos_x in enumerate(posicoes_blocos, 0):
                        # Definir tipo de block baseado na posição
                        if j == 0:
                            # Primeiro block (ponta esquerda)
                            if grades_ativas == 1 or i == 0:
                                block_type = "sar_gra_a1"  # A1 para primeira grade ou grade única
                            else:
                                block_type = "sar_gra_a3"  # A3 para outras grades
                        elif j == len(posicoes_blocos) - 1:
                            # Último block (ponta direita)
                            if grades_ativas == 1 or i == grades_ativas - 1:
                                block_type = "sar_gra_a2"  # A2 para última grade ou grade única
                            else:
                                block_type = "sar_gra_a3"  # A3 para outras grades
                        else:
                            # Blocks centrais
                            block_type = "sar_gra_a3"  # Sempre A3 para centrais
                        script += f"""_LAYER
S {self.config_manager.get_config("layers", "paineis")}

;
"""
                        # Ajuste de posição para blocks da ponta direita substituídos por centrais e centrais verdadeiros
                        posicao_ajustada = pos_x
                        if j == len(posicoes_blocos) - 1 and grades_ativas > 1 and i < grades_ativas - 1 and block_type == "sar_gra_a3":
                            # Block da ponta direita substituído por central em grades que não são a última - mover 3.5cm para esquerda
                            posicao_ajustada = pos_x - 3.5
                            print(f"[DEBUG-AJUSTE] Grade A - Aplicando ajuste -3.5cm (substituído): pos_x={pos_x} -> posicao_ajustada={posicao_ajustada}")
                        elif j > 0 and j < len(posicoes_blocos) - 1 and block_type == "sar_gra_a3":
                            # Bloco central verdadeiro - mover 1.75cm para esquerda
                            posicao_ajustada = pos_x - 1.75
                            print(f"[DEBUG-AJUSTE] Grade A - Aplicando ajuste -1.75cm (central verdadeiro): pos_x={pos_x} -> posicao_ajustada={posicao_ajustada}")
                        else:
                            print(f"[DEBUG-AJUSTE] Grade A - Sem ajuste - j={j}, grades_ativas={grades_ativas}, i={i}, block_type={block_type}")
                        
                        # Aplicar ajuste de posição para pilares especiais nos blocks dos detalhes da Grade A
                        posicao_final_block = self.x_inicial + posicao_ajustada
                        if eh_modo_l and eh_pilar2:
                            # Aplicar ajuste fixo do pilar especial L (-13cm) + ajuste de largura
                            posicao_block_ajustada = posicao_final_block - 13.0

                            # Aplicar ajuste adicional baseado na largura do pilar 1
                            largura_pilar_1 = float(self._globais_pilar_especial.get('larg_1', 20) or 20)
                            ajuste_largura = (largura_pilar_1 - 20.0) * -1  # Inverso: se larg_1=30, ajuste=-10
                            posicao_final_block = posicao_block_ajustada + ajuste_largura

                            if robo_logger:
                                robo_logger.info(f"Grade A Block - Pilar 2: ajuste fixo -13cm + largura {largura_pilar_1}cm (ajuste {ajuste_largura:+.1f}cm)")
                                robo_logger.info(f"Grade A Block - Pilar 2: {posicao_block_ajustada} -> {posicao_final_block}")
                        
                        script += f"""-INSERT
{self.config_manager.get_config("blocks", block_type)}
{posicao_final_block},{self.y_inicial + posicao_y_a + 2.4}
1
0
;
"""
                    
                    # ADICIONAR COTAS DOS DETALHES DA GRADE A (apenas para pilares especiais)
                    # Verificar se é pilar especial para decidir se adiciona cotas da grade A
                    if pilar_especial_ativo:
                        # Definir layer para cotas
                        script += f"""_LAYER
S {self.config_manager.get_config("layers", "cota")}

;
"""
                        # Calcular e adicionar cotas entre os blocos centrais
                        # Aplicar ajuste de posição para pilares especiais nas cotas da Grade A
                        ajuste_cota_grade_a = 0
                        if eh_modo_l and eh_pilar2:
                            # Aplicar ajuste fixo do pilar especial L (-13cm) + ajuste de largura
                            ajuste_base = -13.0

                            # Aplicar ajuste adicional baseado na largura do pilar 1
                            largura_pilar_1 = float(self._globais_pilar_especial.get('larg_1', 20) or 20)
                            ajuste_largura = (largura_pilar_1 - 20.0) * -1  # Inverso: se larg_1=30, ajuste=-10
                            ajuste_cota_grade_a = ajuste_base + ajuste_largura

                            if robo_logger:
                                robo_logger.info(f"Grade A Cota - Pilar 2: ajuste fixo -13cm + largura {largura_pilar_1}cm (ajuste {ajuste_largura:+.1f}cm)")
                                robo_logger.info(f"Grade A Cota - Pilar 2: ajuste total {ajuste_cota_grade_a:+.1f}cm")
                        
                        pos_anterior = self.x_inicial + posicoes_blocos[0] + ajuste_cota_grade_a  # Primeira posição (ponta esquerda)
                        for j, pos_x in enumerate(posicoes_blocos[1:-1], 1):  # Excluir pontas
                            # Ajuste de posição para cotas dos blocks centrais - mover 1.75cm para esquerda
                            posicao_cota_ajustada = pos_x - 0 + ajuste_cota_grade_a
                            script += f"""_DIMLINEAR
{pos_anterior},{self.y_inicial + posicao_y_a + 2.4}
{self.x_inicial + posicao_cota_ajustada},{self.y_inicial + posicao_y_a + 2.4}
{(pos_anterior + self.x_inicial + posicao_cota_ajustada) / 2},{self.y_inicial + posicao_y_a + 2.4 - 20}
;
"""
                            pos_anterior = self.x_inicial + posicao_cota_ajustada
                        # Cota final até a ponta direita
                        if len(posicoes_blocos) > 1:
                            script += f"""_DIMLINEAR
{pos_anterior},{self.y_inicial + posicao_y_a + 2.4}
{self.x_inicial + posicoes_blocos[-1] + ajuste_cota_grade_a},{self.y_inicial + posicao_y_a + 2.4}
{(pos_anterior + self.x_inicial + posicoes_blocos[-1] + ajuste_cota_grade_a) / 2},{self.y_inicial + posicao_y_a + 2.4 - 20}
;
"""
                        
                        # ADICIONAR COTA TOTAL DA GRADE A (apenas para pilares especiais)
                        if len(posicoes_blocos) > 1:
                            script += f"""_DIMLINEAR
{self.x_inicial + posicoes_blocos[0] + ajuste_cota_grade_a},{self.y_inicial + posicao_y_a + 2.4}
{self.x_inicial + posicoes_blocos[-1] + ajuste_cota_grade_a},{self.y_inicial + posicao_y_a + 2.4}
{self.x_inicial + (posicoes_blocos[0] + posicoes_blocos[-1]) / 2 + ajuste_cota_grade_a},{self.y_inicial + posicao_y_a + 2.4 - 30}
;
"""
                        
                        # ADICIONAR COTAS DAS DISTÂNCIAS ENTRE GRADES DA GRADE A (apenas para pilares especiais)
                        # Adicionar cota entre grades do lado A, se houver espaço e a próxima grade for válida
                        if i < len(espacos_a) and i < len(comprimentos_a) - 1 and comprimentos_a[i+1] > 0:
                            script += f"""_DIMLINEAR
{self.x_inicial + posicao_x + comprimento},{self.y_inicial + posicao_y_a + 2.4}
{self.x_inicial + posicao_x + comprimento + espacos_a[i]},{self.y_inicial + posicao_y_a + 2.4}
{self.x_inicial + posicao_x + comprimento + espacos_a[i] / 2},{self.y_inicial + posicao_y_a + 2.4 - 30}
;
"""

                    # Calcular posição da próxima grade preservando o offset base
                    # Avançar cursor considerando espaços
                    espaco_atual = espacos_a[i] if i < len(espacos_a) else 0.0
                    posicao_x = posicao_x + comprimento + espaco_atual

            # Desenhar GRA.B
            # Ajuste aqui: Subtrair 11 da coordenada X para cada retângulo
            posicao_y_b = largura_pilar_global + (5 if comprimento_pilar_global <= 222 else 7.2) + 4  + 2.4# Soma 4.8 para subir a grade
            posicao_x = 0 - 11 # Base
            
            # Aplicar alterações do pilar especial para Grade B
            # posicao_y_b = aplicar_alteracao_pilar_especial(posicao_y_b, 'posicao', 'grade_b', 1, self)
            
            # Aplicar alterações do pilar especial para posição X da Grade B (pilar 2)
            # if eh_pilar2:
            #     posicao_x = aplicar_alteracao_pilar_especial(posicao_x, 'posicao', 'grade_b', 2, self)
            
            # Ajuste específico para pilar 2 dos pilares especiais - Grade B
            if eh_modo_l and eh_pilar2:
                posicao_x += 25.4  # Mover 25.4cm para a direita
                if robo_logger:
                    robo_logger.info(f"Grade B - Pilar 2 Especial: movendo 25.4cm para direita: {posicao_x - 25.4} -> {posicao_x}")
            # Preparar arrays de comprimentos/espacos para GRA.B
            comprimentos_b = comprimento_retangulos[:]
            espacos_b = espacos[:]
            
            # SEMPRE ler valores das grades do Grupo 2 para Grade B
            # Obter valores das grades do Grupo 2
            grade1_grupo2 = float(self.grade1_grupo2_entry.get() or 0)
            grade2_grupo2 = float(self.grade2_grupo2_entry.get() or 0)
            grade3_grupo2 = float(self.grade3_grupo2_entry.get() or 0)
            distancia1_grupo2 = float(self.distancia1_grupo2_entry.get() or 0)
            distancia2_grupo2 = float(self.distancia2_grupo2_entry.get() or 0)
            
            if robo_logger:
                robo_logger.info(f"DEBUG: Valores lidos Grade B - grade1_grupo2={grade1_grupo2}, grade2_grupo2={grade2_grupo2}, grade3_grupo2={grade3_grupo2}, dist1_grupo2={distancia1_grupo2}, dist2_grupo2={distancia2_grupo2}")
                robo_logger.info(f"DEBUG: Condição Grade B - grade1_grupo2 > 0: {grade1_grupo2 > 0}, grade2_grupo2 > 0: {grade2_grupo2 > 0}, grade3_grupo2 > 0: {grade3_grupo2 > 0}")
                robo_logger.info(f"DEBUG: Condição Grade B - grade1_grupo2 > 0 or grade2_grupo2 > 0 or grade3_grupo2 > 0: {grade1_grupo2 > 0 or grade2_grupo2 > 0 or grade3_grupo2 > 0}")
            print(f"DEBUG: Valores lidos Grade B - grade1_grupo2={grade1_grupo2}, grade2_grupo2={grade2_grupo2}, grade3_grupo2={grade3_grupo2}, dist1_grupo2={distancia1_grupo2}, dist2_grupo2={distancia2_grupo2}")
            print(f"DEBUG: Condição Grade B - grade1_grupo2 > 0: {grade1_grupo2 > 0}, grade2_grupo2 > 0: {grade2_grupo2 > 0}, grade3_grupo2 > 0: {grade3_grupo2 > 0}")
            print(f"DEBUG: Condição Grade B - grade1_grupo2 > 0 or grade2_grupo2 > 0 or grade3_grupo2 > 0: {grade1_grupo2 > 0 or grade2_grupo2 > 0 or grade3_grupo2 > 0}")
            
            # Calcular total usando Grade Grupo 2
            total_grupo2 = grade1_grupo2 + distancia1_grupo2 + grade2_grupo2 + distancia2_grupo2 + grade3_grupo2
            
            # Usar total do Grupo 2 para Grade B
            total_b = total_grupo2
            
            # Verificar se os campos específicos estão preenchidos
            if grade1_grupo2 > 0 or grade2_grupo2 > 0 or grade3_grupo2 > 0:
                # Usar valores específicos dos campos
                comprimentos_b = [grade1_grupo2, grade2_grupo2, grade3_grupo2]
                espacos_b = [distancia1_grupo2, distancia2_grupo2]
                if robo_logger:
                    robo_logger.info(f"GRA.B usando valores específicos: comprimentos={comprimentos_b}, espacos={espacos_b}")
                print(f"DEBUG: GRA.B usando valores específicos: comprimentos={comprimentos_b}, espacos={espacos_b}")
            else:
                # Usar lógica de breakdown
                comprimentos_b, espacos_b = self._breakdown_grades_total(total_b)
                if robo_logger:
                    robo_logger.info(f"GRA.B total={total_b} => comprimentos={comprimentos_b}, espacos={espacos_b}")

                # AJUSTES FIXOS - EXTREMIDADES - PILAR 1/2 - GRADE B
                ativos_idx_b = [idx for idx, c in enumerate(comprimentos_b) if c and c > 0]
                if ativos_idx_b:
                    last_idx_b = ativos_idx_b[-1]
                    if not eh_pilar2:
                        # Pilar 1: PLINE e MLINE: +16.5cm na última grade (direita)
                        # OBS: especificado também que se for 1 única grade crescer 0.4, mas instrução diz geral +16.5.
                        # Aplicaremos +16.5 conforme pedido explícito para GRADE B P1.
                        comprimentos_b[last_idx_b] = max(0.1, float(comprimentos_b[last_idx_b]) + 16.5)
                        if robo_logger:
                            robo_logger.info("GRA.B P1: +16.5cm na última grade (direita)")
                    else:
                        # Pilar 2: ajustes dependem do modo (posição já ajustada pelas globais)
                        if str(tipo_linha).lower() == "mline":
                            # MLINE: -17.5 na última (posição já ajustada pelas globais)
                            comprimentos_b[last_idx_b] = max(0.1, float(comprimentos_b[last_idx_b]) - 17.5)
                            if robo_logger:
                                robo_logger.info("GRA.B P2 MLINE: -17.5cm na última grade - posição já ajustada pelas globais")
                        else:
                            # PLINE: -19.9 na última (posição já ajustada pelas globais)
                            comprimentos_b[last_idx_b] = max(0.1, float(comprimentos_b[last_idx_b]) - 19.9)
                            if robo_logger:
                                robo_logger.info("GRA.B P2 PLINE: -19.9cm na última grade - posição já ajustada pelas globais")

            posicao_x_base_b = posicao_x
            print(f"DEBUG: Iniciando desenho Grade B - comprimentos_b={comprimentos_b}, espacos_b={espacos_b}")
            for i, comprimento in enumerate(comprimentos_b):
                print(f"DEBUG: Processando Grade B {i+1} - comprimento={comprimento}, comprimento > 0: {comprimento > 0}")
                if comprimento > 0:
                    print(f"DEBUG: Desenhando Grade B {i+1} - comprimento={comprimento}")
                    # Verifica se deve desenhar a linha/retângulo da grade
                    print(f"DEBUG: Verificando grades_com_sarrafo para Grade B {i+1}")
                    config_grades = self.config_manager.get_config("drawing_options", "grades_com_sarrafo")
                    print(f"DEBUG: Config grades_com_sarrafo='{config_grades}', config_grades == 'sim': {config_grades == 'sim'}")
                    
                    # Verificar se deve desenhar as grades individuais
                    if self.config_manager.get_config("drawing_options", "grades_com_sarrafo") == "sim":
                        # Definir layer para sarrafo das grades
                        script += f"""_LAYER
S {self.config_manager.get_config("layers", "sarrafo_grade")}

;
"""
                        # Verificar o tipo de linha configurado
                        if tipo_linha == "mline":
                            # Desenhar retângulo da GRA.B usando MLINE
                            script += f"""_MLINE
ST
sar
S
2.2
{self.x_inicial + posicao_x},{self.y_inicial + posicao_y_b}
{self.x_inicial + posicao_x + comprimento},{self.y_inicial + posicao_y_b}

;
"""
                        else:
                            # Desenhar retângulo da GRA.B usando PLINE
                            script += f"""_PLINE
{self.x_inicial + posicao_x},{self.y_inicial + posicao_y_b}
{self.x_inicial + posicao_x + comprimento},{self.y_inicial + posicao_y_b}
{self.x_inicial + posicao_x + comprimento},{self.y_inicial + posicao_y_b - 2.4}
{self.x_inicial + posicao_x},{self.y_inicial + posicao_y_b - 2.4}
C
;
"""
                    # Determinar quantas grades ativas existem (com base no que será desenhado)
                    grades_ativas = sum(1 for comp in comprimentos_b if comp > 0)
                    
                    # SAR.GRA.B baseados nos detalhes dos campos (incluindo pontas)
                    posicoes_blocos = self.obter_posicoes_blocos_por_detalhes(i, is_grade_b=True)
                    # Inserir todos os blocks baseados nos detalhes
                    for j, pos_x in enumerate(posicoes_blocos, 0):
                        # Definir tipo de block baseado na posição
                        if j == 0:
                            # Primeiro block (ponta esquerda)
                            if grades_ativas == 1 or i == 0:
                                block_type = "sar_gra_b1"  # B1 para primeira grade ou grade única
                            else:
                                block_type = "sar_gra_b3"  # B3 para outras grades
                        elif j == len(posicoes_blocos) - 1:
                            # Último block (ponta direita)
                            if grades_ativas == 1 or i == grades_ativas - 1:
                                block_type = "sar_gra_b2"  # B2 para última grade ou grade única
                            else:
                                block_type = "sar_gra_b3"  # B3 para outras grades
                        else:
                            # Blocks centrais
                            block_type = "sar_gra_b3"  # Sempre B3 para centrais
                        script += f"""_LAYER
S {self.config_manager.get_config("layers", "paineis")}

;
"""
                        # Ajuste de posição para blocks da ponta direita substituídos por centrais e centrais verdadeiros
                        posicao_ajustada = pos_x
                        if j == len(posicoes_blocos) - 1 and grades_ativas > 1 and i < grades_ativas - 1 and block_type == "sar_gra_b3":
                            # Block da ponta direita substituído por central em grades que não são a última - mover 3.5cm para esquerda
                            posicao_ajustada = pos_x - 3.5
                            print(f"[DEBUG-AJUSTE] Grade B - Aplicando ajuste -3.5cm (substituído): pos_x={pos_x} -> posicao_ajustada={posicao_ajustada}")
                        elif j > 0 and j < len(posicoes_blocos) - 1 and block_type == "sar_gra_b3":
                            # Bloco central verdadeiro - mover 1.75cm para esquerda
                            posicao_ajustada = pos_x - 1.75
                            print(f"[DEBUG-AJUSTE] Grade B - Aplicando ajuste -1.75cm (central verdadeiro): pos_x={pos_x} -> posicao_ajustada={posicao_ajustada}")
                        else:
                            print(f"[DEBUG-AJUSTE] Grade B - Sem ajuste - j={j}, grades_ativas={grades_ativas}, i={i}, block_type={block_type}")
                        
                        # Aplicar ajuste de posição para pilares especiais nos blocks dos detalhes da Grade B
                        posicao_final_block = self.x_inicial + posicao_ajustada
                        if eh_modo_l and eh_pilar2:
                            posicao_final_block += 25.4  # Mesmo ajuste da Grade B: +25.4cm para direita
                            if robo_logger:
                                robo_logger.info(f"Grade B Block - Pilar 2 Especial: movendo 25.4cm para direita: {posicao_final_block - 25.4} -> {posicao_final_block}")
                        
                        script += f"""-INSERT
{self.config_manager.get_config("blocks", block_type)}
{posicao_final_block},{self.y_inicial + posicao_y_b - 2.4}
1
0
;
"""
                    
                    # Mudar para layer de cotas para dimensões
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "cota")}

;
"""
                    
                    # ADICIONAR COTAS DOS DETALHES DA GRADE B (sempre para todos os pilares)
                    # Definir layer para cotas
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "cota")}

;
"""
                    # Calcular e adicionar cotas entre os blocos centrais
                    # Aplicar ajuste de posição para pilares especiais nas cotas da Grade B
                    ajuste_cota_grade_b = 0
                    if eh_modo_l and eh_pilar2:
                        ajuste_cota_grade_b = 25.4  # Mesmo ajuste da Grade B: +25.4cm para direita
                    
                    pos_anterior = self.x_inicial + posicoes_blocos[0] + ajuste_cota_grade_b  # Primeira posição (ponta esquerda)
                    for j, pos_x in enumerate(posicoes_blocos[1:-1], 1):  # Excluir pontas
                        # Ajuste de posição para cotas dos blocks centrais - sem ajuste
                        posicao_cota_ajustada = pos_x + ajuste_cota_grade_b
                        script += f"""_DIMLINEAR
{pos_anterior},{self.y_inicial + posicao_y_b - 2.4}
{self.x_inicial + posicao_cota_ajustada},{self.y_inicial + posicao_y_b - 2.4}
{(pos_anterior + self.x_inicial + posicao_cota_ajustada) / 2},{self.y_inicial + posicao_y_b - 2.4 + 20}
;
"""
                        pos_anterior = self.x_inicial + posicao_cota_ajustada
                    # Cota final até a ponta direita
                    if len(posicoes_blocos) > 1:
                        script += f"""_DIMLINEAR
{pos_anterior},{self.y_inicial + posicao_y_b - 2.4}
{self.x_inicial + posicoes_blocos[-1] + ajuste_cota_grade_b},{self.y_inicial + posicao_y_b - 2.4}
{(pos_anterior + self.x_inicial + posicoes_blocos[-1] + ajuste_cota_grade_b) / 2},{self.y_inicial + posicao_y_b - 2.4 + 20}
;
"""
                    
                    # ADICIONAR COTA TOTAL DA GRADE B (sempre para todos os pilares)
                    if len(posicoes_blocos) > 1:
                        script += f"""_DIMLINEAR
{self.x_inicial + posicoes_blocos[0] + ajuste_cota_grade_b},{self.y_inicial + posicao_y_b - 2.4}
{self.x_inicial + posicoes_blocos[-1] + ajuste_cota_grade_b},{self.y_inicial + posicao_y_b - 2.4}
{self.x_inicial + (posicoes_blocos[0] + posicoes_blocos[-1]) / 2 + ajuste_cota_grade_b},{self.y_inicial + posicao_y_b - 2.4 + 40}
;
"""
                    
                    # Código original comentado para referência futura
                    # if False:  # 31 <= comprimento <= 60:
                    #     # Grade 31-60cm: 1 bloco no centro
                    #     centro_x = posicao_x + comprimento / 2
                    #     # Definir layer "PARAFUSO"
                    #     script += f"""_LAYER
                    # S {self.config_manager.get_config("layers", "cota")}
                    # 
                    # ;
                    # """
                    #     # Bloco central
                    #     script += f"""-INSERT
                    # {self.config_manager.get_config("blocks", "sar_gra_b3")}
                    # {self.x_inicial + centro_x - 1.75},{self.y_inicial + posicao_y_b - 2.4}
                    # 1
                    # 0
                    # ;
                    # """
                    #     # Definir layer "COTA"
                    #     script += f"""_LAYER
                    # S {self.config_manager.get_config("layers", "cota")}
                    # 
                    # ;
                    # """
                    #     # Cota entre SAR.GRA.B.1 e SAR.GRA.B.3
                    #     script += f"""_DIMLINEAR
                    # {self.x_inicial + posicao_x},{self.y_inicial + posicao_y_b - 2.4}
                    # {self.x_inicial + centro_x},{self.y_inicial + posicao_y_b - 2.4}
                    # {self.x_inicial + (posicao_x + centro_x) / 2},{self.y_inicial + posicao_y_b - 2.4 + 15}
                    # ;
                    # """
                    #     # Cota entre SAR.GRA.B.3 e SAR.GRA.B.2
                    #     script += f"""_DIMLINEAR
                    # {self.x_inicial + centro_x},{self.y_inicial + posicao_y_b - 2.4}
                    # {self.x_inicial + posicao_x + comprimento},{self.y_inicial + posicao_y_b - 2.4}
                    # {self.x_inicial + (centro_x + posicao_x + comprimento) / 2},{self.y_inicial + posicao_y_b - 2.4 + 15}
                    # ;
                    # """
                    # elif False:  # Código antigo comentado
                    #     pass  # Todo o código antigo foi removido

                    # Adicionar cota entre grades do lado B, se houver espaço e a próxima grade for válida
                    if i < len(espacos_b) and i < len(comprimentos_b) - 1 and comprimentos_b[i+1] > 0:
                        script += f"""_DIMLINEAR
{self.x_inicial + posicao_x + comprimento},{self.y_inicial + posicao_y_b - 2.4}
{self.x_inicial + posicao_x + comprimento + espacos_b[i]},{self.y_inicial + posicao_y_b - 2.4}
{self.x_inicial + posicao_x + comprimento + espacos_b[i] / 2},{self.y_inicial + posicao_y_b - 2.4 + 40}
;
"""

                    # Calcular posição da próxima grade preservando o offset base
                    espaco_atual_b = espacos_b[i] if i < len(espacos_b) else 0.0
                    posicao_x = posicao_x + comprimento + espaco_atual_b

            # Calcular quantidade de parafusos
            quantidade_parafusos = math.ceil((comprimento_pilar_global + 24) / 70) + 1

            # Obter distâncias dos parafusos das caixas de texto (padrão)
            distancias = [float(entry.get() or 0) for entry in self.parafuso_entries]

            # REGRAS ESPECIAIS: Pilar Especial L - Parafusos
            # MUDANÇA: Usar valores dos campos dos parafusos especiais ao invés de recalcular
            if self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L':
                try:
                    # Se for Pilar 2 (PARTE 2), iniciar 41 cm à direita; caso contrário, manter padrão
                    eh_pilar2 = bool(getattr(self, 'pilar_especial_ativo_var', None) and self.pilar_especial_ativo_var.get())
                    if eh_pilar2:
                        posicao_x_parafuso = self.x_inicial + 49.5
                    
                    # USAR OS VALORES DOS PARAFUSOS ESPECIAIS DA ABA PILARES ESPECIAIS
                    # Pilar 1: usar parafusos A, Pilar 2: usar parafusos E
                    pilar_atual = getattr(self, 'pilar_atual', 1)
                    
                    # DEBUG PARAFUSOS - Log do pilar atual
                    print(f"[DEBUG-PILAR-ATUAL] pilar_atual = {pilar_atual} (tipo: {type(pilar_atual)})")
                    if debug_parafusos:
                        debug_parafusos.info(f"DEBUG: pilar_atual = {pilar_atual} (tipo: {type(pilar_atual)})")
                    
                    if pilar_atual == 1:
                        # PILAR 1: usar parafusos A
                        parafusos_especiais = self._obter_parafusos_especiais_para_uso('a')
                        print(f"[DEBUG-PARAFUSOS] Pilar 1 - parafusos_especiais A: {parafusos_especiais}")
                        robo_logger.subsection("PARAFUSOS ESPECIAIS - PILAR 1 (PARAFUSOS A)")
                    elif pilar_atual == 2:
                        # PILAR 2: usar parafusos E
                        parafusos_especiais = self._obter_parafusos_especiais_para_uso('e')
                        print(f"[DEBUG-PARAFUSOS] Pilar 2 - parafusos_especiais E: {parafusos_especiais}")
                        robo_logger.subsection("PARAFUSOS ESPECIAIS - PILAR 2 (PARAFUSOS E)")
                    else:
                        # Fallback: usar parafusos A
                        parafusos_especiais = self._obter_parafusos_especiais_para_uso('a')
                        print(f"[DEBUG-PARAFUSOS] Fallback - parafusos_especiais A: {parafusos_especiais}")
                        robo_logger.subsection("PARAFUSOS ESPECIAIS - FALLBACK (PARAFUSOS A)")
                    
                    print(f"[DEBUG-CONDICAO] parafusos_especiais: {parafusos_especiais}")
                    print(f"[DEBUG-CONDICAO] len(parafusos_especiais): {len(parafusos_especiais) if parafusos_especiais else 'None'}")
                    print(f"[DEBUG-CONDICAO] bool(parafusos_especiais): {bool(parafusos_especiais)}")
                    
                    if parafusos_especiais:
                        print(f"[DEBUG-CONDICAO] ✅ ENTRANDO NA LÓGICA DE CORREÇÃO!")
                        distancias = parafusos_especiais
                        # CORREÇÃO: As distâncias são as posições dos parafusos, não distâncias entre eles
                        # A quantidade de parafusos é igual ao número de distâncias fornecidas
                        # DEBUG PARAFUSOS - Verificar condição de correção
                        print(f"[DEBUG-CONDICAO] Verificando correção: pilar_atual={pilar_atual}, pilar_atual==2: {pilar_atual == 2}")
                        if debug_parafusos:
                            debug_parafusos.info(f"DEBUG: Verificando correção pilar_atual={pilar_atual}, condição: {pilar_atual == 2}")
                        
                        # CORREÇÃO DEFINITIVA: Para pilar 2 especial, desenhar 2 parafusos a menos
                        if pilar_atual == 2:
                            quantidade_parafusos = max(1, len(distancias) - 2)
                            print(f"[CORREÇÃO-DEFINITIVA] Pilar 2 especial: {len(distancias)} distâncias -> {quantidade_parafusos} parafusos (reduzido em 2)")
                            
                            # DEBUG PARAFUSOS - Log da correção
                            if debug_parafusos:
                                debug_parafusos.parafuso_correcao(
                                    pilar_atual, 
                                    len(distancias), 
                                    quantidade_parafusos, 
                                    "Pilar 2 especial - reduzido em 2"
                                )
                                debug_parafusos.parafuso_info(
                                    pilar_atual, 
                                    quantidade_parafusos, 
                                    distancias, 
                                    "Parafusos especiais com correção"
                                )
                        else:
                            quantidade_parafusos = len(distancias)
                            print(f"[DEBUG-ELSE] Pilar {pilar_atual}: usando quantidade normal {quantidade_parafusos} parafusos")
                            
                            # DEBUG PARAFUSOS - Log normal
                            if debug_parafusos:
                                debug_parafusos.parafuso_info(
                                    pilar_atual, 
                                    quantidade_parafusos, 
                                    distancias, 
                                    "Parafusos especiais normais"
                                )
                        if robo_logger:
                            robo_logger.info(f"Pilar {pilar_atual}: Usando parafusos especiais: {distancias}")
                            robo_logger.info(f"Quantidade de parafusos: {quantidade_parafusos}")
                            robo_logger.info(f"Start X = {posicao_x_parafuso}")
                            print(f"[PARAFUSOS-DETALHADO] Pilar {pilar_atual} - {len(distancias)} distâncias: {distancias}")
                            print(f"[PARAFUSOS-DETALHADO] Isso gerará {quantidade_parafusos} parafusos físicos no desenho")
                    else:
                        print(f"[DEBUG-CONDICAO] ❌ NÃO ENTRANDO NA LÓGICA DE CORREÇÃO - parafusos_especiais vazio!")
                        # Fallback: usar cálculo automático se nenhum valor for especificado
                        comp1 = float(self._globais_pilar_especial.get('comp_1', 0) or 0)
                        larg2 = float(self._globais_pilar_especial.get('larg_2', 0) or 0)
                        # CORREÇÃO DEFINITIVA: Para pilar 2 especial, usar 1 parafuso no fallback
                        if pilar_atual == 2:
                            quantidade_parafusos = 1
                            print(f"[CORREÇÃO-DEFINITIVA] Pilar 2 especial (fallback): usando 1 parafuso")
                            
                            # DEBUG PARAFUSOS - Log da correção fallback
                            if debug_parafusos:
                                debug_parafusos.parafuso_correcao(
                                    pilar_atual, 
                                    2, 
                                    quantidade_parafusos, 
                                    "Pilar 2 especial fallback - reduzido para 1"
                                )
                                debug_parafusos.parafuso_info(
                                    pilar_atual, 
                                    quantidade_parafusos, 
                                    None, 
                                    "Fallback com correção"
                                )
                        else:
                            quantidade_parafusos = 2
                            
                            # DEBUG PARAFUSOS - Log fallback normal
                            if debug_parafusos:
                                debug_parafusos.parafuso_info(
                                    pilar_atual, 
                                    quantidade_parafusos, 
                                    None, 
                                    "Fallback normal"
                                )
                        distancia_entre = comp1 - larg2 - 30.0 - 11.0
                        if distancia_entre < 0:
                            distancia_entre = 0.0
                        distancias = [distancia_entre]
                        if robo_logger:
                            robo_logger.subsection("PARAFUSOS - FALLBACK CÁLCULO AUTOMÁTICO")
                            robo_logger.info(f"Nenhum valor especificado - usando cálculo: {distancia_entre}")
                except Exception:
                    pass

            # Adicionar blocks adicionais para pilares de largura >= 40cm
            if largura_pilar_global >= 40:
                # Obter informações das grades para determinar posições dos blocks
                grade1_valor = float(self.grade1_entry.get() or 0)
                grade2_valor = float(self.grade2_entry.get() or 0)
                grade3_valor = float(self.grade3_entry.get() or 0)
                
                # Determinar quantas grades existem
                grades_existentes = []
                if grade1_valor > 0:
                    grades_existentes.append(1)
                if grade2_valor > 0:
                    grades_existentes.append(2)
                if grade3_valor > 0:
                    grades_existentes.append(3)
                
                if len(grades_existentes) > 0:
                    # Calcular posições das grades
                    posicao_y_a = largura_pilar_global + 2  # Posição da grade A
                    posicao_y_b = -2  # Posição da grade B
                    
                    # EXTREMIDADE ESQUERDA - Primeira grade
                    primeira_grade = grades_existentes[0]
                    posicao_x_esquerda = 0  # Primeira grade sempre começa em 0
                    
                    # Blocks adicionais na extremidade esquerda (movidos 11cm para a esquerda)
                    # Apenas os blocks "de dentro" (entre as grades A e B)
                    
                    # Grade A: 16cm abaixo do block original + 2.4cm mais para baixo
                    script += f"""-INSERT
{self.config_manager.get_config("blocks", "sar_gra_a1")}
{self.x_inicial + posicao_x_esquerda - 11},{self.y_inicial + posicao_y_a + 2.4 - 16 - 2.4}
1
0
;
"""
                    
                    # Grade B: 16cm acima do block original + 2.4cm para cima
                    script += f"""-INSERT
{self.config_manager.get_config("blocks", "sar_gra_b1")}
{self.x_inicial + posicao_x_esquerda - 11},{self.y_inicial + posicao_y_b - 2.4 + 16 + 2.4}
1
0
;
"""
                    
                    # EXTREMIDADE DIREITA - Última grade (dinâmico)
                    ultima_grade = grades_existentes[-1]
                    
                    # Calcular posição X da última grade
                    if ultima_grade == 1:
                        posicao_x_direita = grade1_valor
                        block_a_direita = "sar_gra_a2"
                        block_b_direita = "sar_gra_b2"
                    elif ultima_grade == 2:
                        distancia1 = float(self.distancia1_entry.get() or 0)
                        posicao_x_direita = grade1_valor + distancia1 + grade2_valor
                        if len(grades_existentes) == 1:  # Só grade 2
                            block_a_direita = "sar_gra_a2"
                            block_b_direita = "sar_gra_b2"
                        else:  # Grade 2 é a última
                            block_a_direita = "sar_gra_a2"
                            block_b_direita = "sar_gra_b2"
                    else:  # ultima_grade == 3
                        distancia1 = float(self.distancia1_entry.get() or 0)
                        distancia2 = float(self.distancia2_entry.get() or 0)
                        posicao_x_direita = grade1_valor + distancia1 + grade2_valor + distancia2 + grade3_valor
                        block_a_direita = "sar_gra_a2"
                        block_b_direita = "sar_gra_b2"
                    
                    # Blocks adicionais na extremidade direita (movidos 11cm para a esquerda)
                    # Apenas os blocks "de dentro" (entre as grades A e B)
                    
                    # Grade A: 16cm abaixo do block original + 2.4cm mais para baixo
                    script += f"""-INSERT
{self.config_manager.get_config("blocks", block_a_direita)}
{self.x_inicial + posicao_x_direita - 11},{self.y_inicial + posicao_y_a + 2.4 - 16 - 2.4}
1
0
;
"""
                    
                    # Grade B: 16cm acima do block original + 2.4cm para cima
                    script += f"""-INSERT
{self.config_manager.get_config("blocks", block_b_direita)}
{self.x_inicial + posicao_x_direita - 11},{self.y_inicial + posicao_y_b - 2.4 + 16 + 2.4}
1
0
;
"""

                # Adicionar cota total para pilares entre 40cm e 58cm (sem blocks centrais)
                if largura_pilar_global <= 58:
                    # Definir layer para cotas
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "cota")}

;
"""
                    
                    # Posição X das cotas (3.5cm à esquerda dos blocks da esquerda)
                    posicao_x_cota_esquerda = self.x_inicial + posicao_x_esquerda - 11 + 3.5 - 3.5
                    
                    # Cota total de ponta a ponta (block A ao block B) - apenas para largura entre 40 e 58cm
                    # ELIMINAR COTAS DE SARRAFOS (7cm) PARA MODO ESPECIAL
                    if not (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L'):
                        script += f"""_DIMLINEAR
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_a - 16 + 7}
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_b + 16 - 7}
{posicao_x_cota_esquerda - 20},{(self.y_inicial + posicao_y_a - 16 - 7 + self.y_inicial + posicao_y_b + 16 + 7) / 2}
;
;
"""

                # Adicionar blocks centrais verticais para pilares com largura > 58cm
                # GRADE CENTRAL VERTICAL - Sistema de blocks BCGV
                if largura_pilar_global > 58:
                    if largura_pilar_global > 92:
                        # GRADE CENTRAL VERTICAL - Para pilares > 92cm: 2 blocks centrais em cada lado (nos dois terços)
                        # DESATIVADO: Calcular posições com números inteiros usando a nova função
                        # posicao_y_terco_1, posicao_y_terco_2 = self.calcular_posicoes_blocks_centrais_verticais(posicao_y_a, posicao_y_b)
                        
                        # USAR VALORES FIXOS TEMPORARIAMENTE PARA TESTE
                        posicao_y_terco_1 = (posicao_y_a + posicao_y_b) / 2 - 10  # Posição fixa temporária
                        posicao_y_terco_2 = (posicao_y_a + posicao_y_b) / 2 + 10  # Posição fixa temporária
                        
                        # GRADE CENTRAL VERTICAL - Blocks centrais esquerdos (BCGV) - 2 blocks nos dois terços + 7cm para direita
                        script += f"""-INSERT
{self.config_manager.get_config("blocks", "block_central_grade_vertical")}
{self.x_inicial + posicao_x_esquerda - 11 + 7},{self.y_inicial + posicao_y_terco_1}
1
0
;
"""
                        script += f"""-INSERT
{self.config_manager.get_config("blocks", "block_central_grade_vertical")}
{self.x_inicial + posicao_x_esquerda - 11 + 7},{self.y_inicial + posicao_y_terco_2}
1
0
;
"""
                        
                        # GRADE CENTRAL VERTICAL - Blocks centrais direitos (BCGV) - 2 blocks nos dois terços
                        script += f"""-INSERT
{self.config_manager.get_config("blocks", "block_central_grade_vertical")}
{self.x_inicial + posicao_x_direita - 11},{self.y_inicial + posicao_y_terco_1}
1
0
;
"""
                        script += f"""-INSERT
{self.config_manager.get_config("blocks", "block_central_grade_vertical")}
{self.x_inicial + posicao_x_direita - 11},{self.y_inicial + posicao_y_terco_2}
1
0
;
"""
                        
                        # GRADE CENTRAL VERTICAL - Cotas na esquerda dos blocks da esquerda (2 blocks)
                        # Definir layer para cotas
                        script += f"""_LAYER
S {self.config_manager.get_config("layers", "cota")}

;
"""
                        
                        # Posição X das cotas (3.5cm à esquerda dos blocks da esquerda)
                        posicao_x_cota_esquerda = self.x_inicial + posicao_x_esquerda - 11 + 3.5 - 3.5
                        
                        # Cota entre block A e primeiro central
                        # ELIMINAR COTAS DE SARRAFOS (7cm) PARA MODO ESPECIAL
                        if not (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L'):
                            script += f"""_DIMLINEAR
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_a - 16 + 7}
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_terco_2}
{posicao_x_cota_esquerda - 20},{(self.y_inicial + posicao_y_a - 16 - 7 + self.y_inicial + posicao_y_terco_2) / 2}
;
;
"""
                            
                            # Cota entre os dois centrais
                            script += f"""_DIMLINEAR
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_terco_2}
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_terco_1}
{posicao_x_cota_esquerda - 20},{(self.y_inicial + posicao_y_terco_2 + self.y_inicial + posicao_y_terco_1) / 2}
;
;
"""
                            
                            # Cota entre segundo central e block B
                            script += f"""_DIMLINEAR
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_terco_1}
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_b + 16 - 7}
{posicao_x_cota_esquerda - 20},{(self.y_inicial + posicao_y_terco_1 + self.y_inicial + posicao_y_b + 16 + 7) / 2}
;
;
"""
                            
                            # Cota total de ponta a ponta (block A ao block B)
                            script += f"""_DIMLINEAR
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_a - 16 + 7}
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_b + 16 - 7}
{posicao_x_cota_esquerda - 40},{(self.y_inicial + posicao_y_a - 16 - 7 + self.y_inicial + posicao_y_b + 16 + 7) / 2}
;
;
"""
                        
                    else:
                        # GRADE CENTRAL VERTICAL - Para pilares 58cm < largura <= 92cm: 1 block central em cada lado + 3.5cm para cima
                        # Calcular posição Y central (meio entre as grades A e B) + 3.5cm para cima
                        posicao_y_central = (posicao_y_a + posicao_y_b) / 2 + 3.5
                        
                        # GRADE CENTRAL VERTICAL - Block central esquerdo (BCGV) + 7cm para direita e 3.5cm para cima
                        script += f"""-INSERT
{self.config_manager.get_config("blocks", "block_central_grade_vertical")}
{self.x_inicial + posicao_x_esquerda - 11 + 7},{self.y_inicial + posicao_y_central}
1
0
;
"""
                        
                        # GRADE CENTRAL VERTICAL - Block central direito (BCGV) + 3.5cm para cima
                        script += f"""-INSERT
{self.config_manager.get_config("blocks", "block_central_grade_vertical")}
{self.x_inicial + posicao_x_direita - 11},{self.y_inicial + posicao_y_central}
1
0
;
"""
                        
                        # GRADE CENTRAL VERTICAL - Cotas na esquerda dos blocks da esquerda (1 block)
                        # Definir layer para cotas
                        script += f"""_LAYER
S {self.config_manager.get_config("layers", "cota")}

;
"""
                        
                        # Posição X das cotas (3.5cm à esquerda dos blocks da esquerda)
                        posicao_x_cota_esquerda = self.x_inicial + posicao_x_esquerda - 11 + 3.5 - 3.5
                        
                        # Cota entre block A e central
                        # ELIMINAR COTAS DE SARRAFOS (7cm) PARA MODO ESPECIAL
                        if not (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L'):
                            script += f"""_DIMLINEAR
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_a - 16 + 7}
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_central}
{posicao_x_cota_esquerda - 20},{(self.y_inicial + posicao_y_a - 16 - 7 + self.y_inicial + posicao_y_central) / 2}
;
;
"""
                            
                            # Cota entre central e block B
                            script += f"""_DIMLINEAR
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_central}
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_b + 16 - 7}
{posicao_x_cota_esquerda - 20},{(self.y_inicial + posicao_y_central + self.y_inicial + posicao_y_b + 16 + 7) / 2}
;
;
"""
                            
                            # Cota total de ponta a ponta (block A ao block B)
                            script += f"""_DIMLINEAR
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_a - 16 + 7}
{posicao_x_cota_esquerda},{self.y_inicial + posicao_y_b + 16 - 7}
{posicao_x_cota_esquerda - 40},{(self.y_inicial + posicao_y_a - 16 - 7 + self.y_inicial + posicao_y_b + 16 + 7) / 2}
;
;
"""

            # Adicionar linhas dos parafusos ao script
            posicao_x_parafuso = self.x_inicial - 12  # Ajuste para centralizar com PAI.C
            # Pilar L (Pilar 2): força início 49.5 cm à direita (41 + 8.5)
            if (
                self._globais_pilar_especial
                and self._globais_pilar_especial.get('tipo_pilar') == 'L'
                and getattr(self, 'pilar_especial_ativo_var', None)
                and self.pilar_especial_ativo_var.get()
            ):
                posicao_x_parafuso = self.x_inicial + 49.5
            
            # Aplicar alterações do pilar especial para Parafuso
            posicao_x_parafuso = aplicar_alteracao_pilar_especial(posicao_x_parafuso, 'posicao', 'parafuso', 1, self)
            
            # Condição especial para larguras de 40cm ou mais
            largura_especial = largura_pilar_global >= 40
            # Não aplicar deslocamentos especiais nas extremidades quando Pilar L estiver ativo (para manter regra de posição)
            if self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L':
                largura_especial = False
            
            # DEBUG PARAFUSOS - Log antes do desenho
            if debug_parafusos:
                debug_parafusos.subsection("DESENHANDO PARAFUSOS")
                debug_parafusos.info(f"Quantidade de parafusos a desenhar: {quantidade_parafusos}")
                debug_parafusos.info(f"Pilar atual: {pilar_atual}")
                debug_parafusos.info(f"Distâncias: {distancias if 'distancias' in locals() else 'N/A'}")
            
            # CORREÇÃO DEFINITIVA: Aplicar correção diretamente no loop de desenho
            pilar_atual = getattr(self, 'pilar_atual', 1)
            if pilar_atual == 2:
                # Para pilar 2 especial, desenhar 1 parafuso a menos (mantém 2 parafusos como primeiro e último)
                quantidade_parafusos_corrigida = max(2, quantidade_parafusos - 1)
                print(f"[CORREÇÃO-DIRETA] Pilar 2 especial: {quantidade_parafusos} -> {quantidade_parafusos_corrigida} parafusos (reduzido em 1, mantém 2 como mínimo)")
            else:
                quantidade_parafusos_corrigida = quantidade_parafusos
                print(f"[CORREÇÃO-DIRETA] Pilar {pilar_atual}: usando quantidade normal {quantidade_parafusos_corrigida} parafusos")
            
            for i in range(quantidade_parafusos_corrigida):
                # DEBUG PARAFUSOS - Log de cada parafuso
                if debug_parafusos:
                    debug_parafusos.parafuso_debug(
                        pilar_atual, 
                        f"Desenhando parafuso {i+1}/{quantidade_parafusos_corrigida}", 
                        f"Índice: {i}"
                    )
                
                # Calcular altura dos parafusos com base no comprimento do pilar
                if comprimento_pilar_global < 223:
                    altura_parafuso = largura_pilar_global + 36.8
                else:
                    altura_parafuso = largura_pilar_global + 41.2

                # Centralizar verticalmente com PAI.C
                y_centro = self.y_inicial + largura_pilar_global / 2
                y_inferior = y_centro - altura_parafuso / 2
                y_superior = y_centro + altura_parafuso / 2

                # Definir layer "ESTRUTURA"
                script += f"""_LAYER
S {self.config_manager.get_config("layers", "metal")}

;
"""
                # Ajustar posição do parafuso para condições especiais (largura >= 40cm)
                # CORREÇÃO: Para pilares especiais, calcular posição usando distâncias acumuladas
                if (self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L' and 
                    hasattr(self, '_dados_parafusos_especiais') and self._dados_parafusos_especiais):
                    # Para pilares especiais, usar posição inicial + distâncias acumuladas
                    posicao_x_atual = posicao_x_parafuso
                    for j in range(i):
                        if j < len(distancias):
                            posicao_x_atual += distancias[j]
                else:
                    # Para pilares comuns, usar lógica original
                    posicao_x_atual = posicao_x_parafuso
                    if largura_especial and (i == 0 or i == quantidade_parafusos_corrigida - 1):
                        if i == 0:  # Primeiro parafuso - mover para dentro (2.5cm da parede)
                            posicao_x_atual = self.x_inicial - 14.5  # 2.5cm para fora da parede esquerda
                        else:  # Último parafuso - mover para dentro (2.5cm da parede)
                            posicao_x_atual = self.x_inicial + comprimento_pilar_global + 14.5  # 2.5cm para fora da parede direita
                
                # Verificar se é o primeiro ou último parafuso para condições especiais
                usar_mline = False
                if (i == 0 or i == quantidade_parafusos_corrigida - 1) and largura_especial:
                    # Condições especiais para larguras >= 40cm - primeiro e último parafuso
                    
                    # Verificar o tipo de linha configurado
                    if tipo_linha == "mline":
                        usar_mline = True
                        # Desenhar MLINE de 7cm de espessura ao redor do parafuso
                        script += f"""_mLINE
ST
METAL2
S
7
{posicao_x_atual - 3.5},{y_inferior - 6}
{posicao_x_atual - 3.5},{y_superior + 6}

;
_LAYER
S {self.config_manager.get_config("layers", "hachura")}

;
"""
                    else:
                        # Desenhar retângulo de 7cm ao redor do parafuso (PLINE) - caso normal para largura >= 40cm
                        script += f"""_PLINE
{posicao_x_atual - 3.5},{y_inferior - 6}
{posicao_x_atual + 3.5},{y_inferior - 6}
{posicao_x_atual + 3.5},{y_superior + 6}
{posicao_x_atual - 3.5},{y_superior + 6}
C
;
"""
                    
                    # SEMPRE adicionar retângulo de 1cm para parafusos das extremidades (independente da largura)
                    # Ajustar coordenadas Y para modo mline
                    y_inferior_retangulo = y_inferior - 6
                    y_superior_retangulo = y_superior + 6
                    if tipo_linha == "mline" and largura_pilar_global >= 40:
                        y_inferior_retangulo += 2.4  # Retângulo sobe 2.4cm
                        y_superior_retangulo -= 2.4  # Retângulo desce 2.4cm
                    
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "hachura")}

;
_PLINE
{posicao_x_atual - 0.5},{y_inferior_retangulo}
{posicao_x_atual + 0.5},{y_inferior_retangulo}
{posicao_x_atual + 0.5},{y_superior_retangulo}
{posicao_x_atual - 0.5},{y_superior_retangulo}
C
;
"""
                    
                    # Adicionar retângulo de 7cm centralizado (layer METAL) - apenas se não for mline
                    if tipo_linha != "mline":
                        script += f"""_LAYER
S {self.config_manager.get_config("layers", "metal")}

;
_PLINE
{posicao_x_atual - 3.5},{y_inferior - 6}
{posicao_x_atual + 3.5},{y_inferior - 6}
{posicao_x_atual + 3.5},{y_superior + 6}
{posicao_x_atual - 3.5},{y_superior + 6}
C
;
"""
                    
                    # Adicionar retângulo de 3cm centralizado (layer METAL)
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "metal")}

;
_PLINE
{posicao_x_atual - 1.5},{y_inferior - 6}
{posicao_x_atual + 1.5},{y_inferior - 6}
{posicao_x_atual + 1.5},{y_superior + 6}
{posicao_x_atual - 1.5},{y_superior + 6}
C
;
_LAYER
S {self.config_manager.get_config("layers", "hachura")}

;
"""
                
                elif i == 0 or i == quantidade_parafusos_corrigida - 1:
                    # Primeiro e último parafuso - retângulo central de 1cm da altura total (largura < 40cm)
                    # Ajustar coordenadas Y para modo mline (mesmo para largura < 40cm)
                    y_inferior_retangulo = y_inferior - 6
                    y_superior_retangulo = y_superior + 6
                    if tipo_linha == "mline":
                        y_inferior_retangulo += 2.4  # Retângulo sobe 2.4cm
                        y_superior_retangulo -= 2.4  # Retângulo desce 2.4cm
                    
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "hachura")}

;
_PLINE
{posicao_x_atual - 0.5},{y_inferior_retangulo}
{posicao_x_atual + 0.5},{y_inferior_retangulo}
{posicao_x_atual + 0.5},{y_superior_retangulo}
{posicao_x_atual - 0.5},{y_superior_retangulo}
C
;
"""
                
                else:
                    # Parafusos intermediários - comportamento padrão com três retângulos
                    # Ajustar coordenadas Y para modo mline
                    y_inferior_ajustado = y_inferior - 6
                    y_superior_ajustado = y_superior + 6
                    if tipo_linha == "mline":
                        y_inferior_ajustado += 2.4  # Parte inferior sobe 2.4cm
                        y_superior_ajustado -= 2.4  # Parte superior desce 2.4cm
                    
                    # 1. Retângulo inferior (de y_inferior até self.y_inicial - 2)
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "hachura")}

;
_PLINE
{posicao_x_atual - 0.5},{y_inferior_ajustado}
{posicao_x_atual + 0.5},{y_inferior_ajustado}
{posicao_x_atual + 0.5},{self.y_inicial - 2}
{posicao_x_atual - 0.5},{self.y_inicial - 2}
C
;
"""
                    # 2. Retângulo central (de PAI.A a PAI.B) - linha tracejada
                    script += f""";
_LINETYPE
S
HIDDEN

;
_PLINE
{posicao_x_atual - 0.5},{self.y_inicial - 2}
{posicao_x_atual + 0.5},{self.y_inicial - 2}
{posicao_x_atual + 0.5},{self.y_inicial + largura_pilar_global + 2}
{posicao_x_atual - 0.5},{self.y_inicial + largura_pilar_global + 2}
C
;
_LINETYPE
S
Continuous

;
"""
                    # 3. Retângulo superior (de self.y_inicial + largura_pilar_global + 2 até y_superior)
                    script += f"""_PLINE
{posicao_x_atual - 0.5},{self.y_inicial + largura_pilar_global + 2}
{posicao_x_atual + 0.5},{self.y_inicial + largura_pilar_global + 2}
{posicao_x_atual + 0.5},{y_superior_ajustado}
{posicao_x_atual - 0.5},{y_superior_ajustado}
C
;
"""

                # Desenhar elementos específicos para casos PLINE
                if not usar_mline:
                    # Para parafusos das extremidades: apenas retângulo de 1cm (já desenhado acima)
                    if i == 0 or i == quantidade_parafusos_corrigida - 1:
                        # Parafusos das extremidades: NÃO inserir blocos PAR_CIMA e PAR_BAIXO
                        pass
                    else:
                        # Para parafusos intermediários: inserir blocos e retângulo interno
                        script += f"""-INSERT
{self.config_manager.get_config("blocks", "par_cima")}
{posicao_x_atual},{self.y_inicial + largura_pilar_global}
1
0
;
-INSERT
{self.config_manager.get_config("blocks", "par_baixo")}
{posicao_x_atual},{self.y_inicial}
1
0
;
"""
                        
                        # Desenhar retângulo interno do parafuso (apenas para parafusos intermediários)
                        script += f"""_PLINE
{posicao_x_atual - 1},{self.y_inicial + 1 + (2.4 if self.config_manager.get_config("drawing_options", "grades_com_sarrafo") == "nao" else 0)}
{posicao_x_atual + 1},{self.y_inicial + 1 + (2.4 if self.config_manager.get_config("drawing_options", "grades_com_sarrafo") == "nao" else 0)}
{posicao_x_atual + 1},{self.y_inicial + largura_pilar_global - 1 - (2.4 if self.config_manager.get_config("drawing_options", "grades_com_sarrafo") == "nao" else 0)}
{posicao_x_atual - 1},{self.y_inicial + largura_pilar_global - 1 - (2.4 if self.config_manager.get_config("drawing_options", "grades_com_sarrafo") == "nao" else 0)}
C
;
"""

                # Ajustar posições dos blocks quando grades com sarrafo estiver desabilitado
                y_superior_block = y_superior
                y_inferior_block = y_inferior
                if self.config_manager.get_config("drawing_options", "grades_com_sarrafo") == "nao":
                    y_superior_block -= 2.4  # Block do topo desce 2.4cm
                    y_inferior_block += 2.4  # Block do fundo sobe 2.4cm
                


                # Adicionar bloco PAR.CIM na ponta de cima
                script += f"""-INSERT
{self.config_manager.get_config("blocks", "parafuso_cima")}
{posicao_x_atual},{y_superior_block}
1
0
;
"""

                # Adicionar bloco PAR.BAI na ponta de baixo
                script += f"""-INSERT
{self.config_manager.get_config("blocks", "parafuso_baixo")}
{posicao_x_atual},{y_inferior_block}
1
0
;
"""
                # Definir layer "cotas"
                script += f"""_LAYER
S {self.config_manager.get_config("layers", "cota")}

;
"""

                # Adicionar cota entre parafusos, exceto após o último parafuso
                # ELIMINAR COTAS DE PARAFUSOS PARA PILAR 2 (pilar especial tipo L)
                is_pilar_especial = self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L'
                is_pilar_2 = is_pilar_especial and self.pilar_atual == 2
                
                if i < quantidade_parafusos_corrigida - 1 and not is_pilar_2:
                    # Ajustar pontos das cotas conforme solicitado
                    ponto_esquerdo = posicao_x_atual
                    # Próxima posição calculada a partir do array distancias (que já foi ajustado para Pilar L)
                    proxima_posicao_x = posicao_x_parafuso + distancias[i]
                    ponto_direito = proxima_posicao_x
                    
                    # Ajustar pontos conforme solicitado: primeiro parafuso 1cm para direita, último parafuso 1cm para esquerda
                    if i == 0:  # Primeiro parafuso
                        if not is_pilar_especial or (is_pilar_especial and self.pilar_atual == 1):
                            ponto_esquerdo += 1.0  # Move 1cm para direita
                    
                    if i == quantidade_parafusos_corrigida - 1:  # Último parafuso (correto para qualquer quantidade)
                        if is_pilar_especial and self.pilar_atual == 2:
                            ponto_direito -= 1.5  # Move 1.5cm para esquerda (apenas pilar 2 especial)
                        elif not is_pilar_especial:
                            ponto_direito -= 1.0  # Move 1cm para esquerda (apenas pilares comuns)
                    
                    # CORREÇÃO: Verificar se a distância entre os pontos é maior que zero para evitar cotas de valor 0
                    distancia_cota = abs(ponto_direito - ponto_esquerdo)
                    if distancia_cota > 0.1:  # Só desenhar cota se a distância for maior que 0.1cm
                        # Posição do texto da cota: 30cm para pilares especiais, 15cm para pilares comuns
                        if self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L':
                            posicao_texto_cota = y_inferior - 30
                        else:
                            posicao_texto_cota = y_inferior - 15
                        
                        script += f"""_DIMLINEAR
{ponto_esquerdo},{y_inferior}
{ponto_direito},{y_inferior}
{(ponto_esquerdo + ponto_direito) / 2},{posicao_texto_cota}
;
"""
                    posicao_x_parafuso += distancias[i]
                
                # Adicionar cota extra do último parafuso até a esquina direita do PAI.A (apenas para pilares especiais, pilar 1)
                # CORREÇÃO: Removida condição para pilar 2 - manter apenas para pilar 1
                if self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L' and self.pilar_atual == 1:
                    # Calcular posição do último parafuso
                    posicao_ultimo_parafuso = posicao_x_parafuso
                    
                    # Usar a posição final calculada do PAI.A (end_x_pai_a) que inclui os ajustes
                    esquina_direita_pai_a = end_x_pai_a
                    
                    # CORREÇÃO: Verificar se a distância é maior que zero para evitar cotas de valor 0
                    distancia_extra = abs(esquina_direita_pai_a - posicao_ultimo_parafuso)
                    if distancia_extra > 0.1:  # Só desenhar cota se a distância for maior que 0.1cm
                        # Posição do texto da cota: 30cm para pilares especiais
                        posicao_texto_cota = y_inferior - 30
                        
                        script += f"""_DIMLINEAR
{posicao_ultimo_parafuso},{y_inferior}
{esquina_direita_pai_a},{y_inferior}
{(posicao_ultimo_parafuso + esquina_direita_pai_a) / 2},{posicao_texto_cota}
;
"""
                
                # ELIMINAR COTA EXTRA DO PRIMEIRO PARAFUSO PARA PILAR 2
                # (cota extra do primeiro parafuso até a esquina esquerda do PAI.A - REMOVIDA para pilar 2)
                # if self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L' and self.pilar_atual == 2:
                #     # Calcular posição do primeiro parafuso (posição inicial)
                #     posicao_primeiro_parafuso = self.x_inicial + 49.5  # Posição inicial do primeiro parafuso
                #     
                #     # Usar a posição final calculada do PAI.A (posicao_x_pai_a)
                #     esquina_esquerda_pai_a = posicao_x_pai_a
                #     
                #     # CORREÇÃO: Verificar se a distância é maior que zero para evitar cotas de valor 0
                #     distancia_extra_esquerda = abs(posicao_primeiro_parafuso - esquina_esquerda_pai_a)
                #     if distancia_extra_esquerda > 0.1:  # Só desenhar cota se a distância for maior que 0.1cm
                #         # Posição do texto da cota: mesma altura das cotas dos parafusos existentes (30cm para pilares especiais)
                #         posicao_texto_cota = y_inferior - 30
                #         
                #         script += f"""_DIMLINEAR
                # {esquina_esquerda_pai_a},{y_inferior}
                # {posicao_primeiro_parafuso},{y_inferior}
                # {(esquina_esquerda_pai_a + posicao_primeiro_parafuso) / 2},{posicao_texto_cota}
                # ;
                # """
            
            # ========================================
            # NOVO TRECHO: COTAS PARA PILAR 2 ESPECIAL
            # ========================================
            # Adicionar cotas de parafusos para pilar 2 especial (separado do código existente)
            is_pilar_especial = self._globais_pilar_especial and self._globais_pilar_especial.get('tipo_pilar') == 'L'
            is_pilar_2 = is_pilar_especial and self.pilar_atual == 2
            
            if is_pilar_2 and quantidade_parafusos_corrigida > 1:
                # Calcular posições dos parafusos para as cotas
                posicao_x_atual = self.x_inicial + 49.5  # Posição inicial do primeiro parafuso
                
                # Definir layer "cotas" para pilar 2
                script += f"""_LAYER
S {self.config_manager.get_config("layers", "cota")}

;
"""
                
                # Desenhar cotas entre parafusos para pilar 2 especial
                for i in range(quantidade_parafusos_corrigida - 1):
                    # Ponto esquerdo da cota
                    ponto_esquerdo = posicao_x_atual
                    
                    # Ponto direito da cota (próximo parafuso)
                    if i < len(distancias):
                        proxima_posicao_x = posicao_x_atual + distancias[i]
                    else:
                        proxima_posicao_x = posicao_x_atual + 50  # Fallback
                    ponto_direito = proxima_posicao_x
                    
                    # Ajuste especial para última cota do pilar 2: mover ponto direito 1.5cm para esquerda
                    if i == quantidade_parafusos_corrigida - 2:  # Última cota (penúltimo parafuso)
                        ponto_direito -= 1.5  # Move 1.5cm para esquerda
                    
                    # Verificar se a distância é válida
                    distancia_cota = abs(ponto_direito - ponto_esquerdo)
                    if distancia_cota > 0.1:
                        # Posição do texto da cota
                        posicao_texto_cota = y_inferior - 30
                        
                        # Adicionar cota
                        script += f"""_DIMLINEAR
{ponto_esquerdo},{y_inferior}
{ponto_direito},{y_inferior}
{(ponto_esquerdo + ponto_direito) / 2},{posicao_texto_cota}
;
"""
                    
                    # Atualizar posição para próxima iteração
                    posicao_x_atual = proxima_posicao_x
            
            #finalmente adicionar os textos de nomenclatura e cotas (camada, tamanho, etc)

            # Definir layer "NOMENCLATURA"
            script += f"""_LAYER
S {self.config_manager.get_config("layers", "textos")}

;
"""
            # Adicionar texto com o nome do pilar e suas dimensões (ajustes para pilares especiais)
            if self.config_manager.get_config("drawing_options", "incluir_texto_nome") == "sim":
                comprimento_texto = f"{comprimento_pilar_global:.0f}" if comprimento_pilar_global.is_integer() else f"{comprimento_pilar_global:.1f}"
                largura_texto = f"{largura_pilar_global:.0f}" if largura_pilar_global.is_integer() else f"{largura_pilar_global:.1f}"

                # Verificar se é pilar especial e qual pilar
                eh_pilar_especial = (self._globais_pilar_especial and 
                                   self._globais_pilar_especial.get('tipo_pilar') == 'L' and
                                   getattr(self, 'pilar_especial_ativo_var', None) and
                                   self.pilar_especial_ativo_var.get())
                
                # Verificar modo (NOVA/INI)
                modo_nova = self.config_manager.get_config("drawing_options", "tipo_linha") == "pline"
                
                # Aplicar regras de texto do nome do pilar usando as mesmas variáveis dos painéis
                if desenhar_pai_c and desenhar_pai_d:
                    # PILAR NORMAL: posição padrão
                    script += f"""_MTEXT
{self.x_inicial-100},{self.y_inicial+largura_pilar_global/2}
J MC
0
{nome_pilar}-({comprimento_texto}X{largura_texto})

;
-STYLE
standard

4





;
"""
                elif not desenhar_pai_d:
                    # PILAR 1 ESPECIAL: NÃO desenha texto do nome (PAI.D não desenha)
                    pass  # Não desenha o texto do nome
                elif not desenhar_pai_c:
                    # PILAR 2 ESPECIAL: texto do nome apenas no modo NOVA
                    if modo_nova:
                        # Pilar 2: posição ajustada 25cm para a esquerda
                        script += f"""_MTEXT
{self.x_inicial-125},{self.y_inicial+largura_pilar_global/2}
J MC
0
{nome_pilar}-({comprimento_texto}X{largura_texto})

;
-STYLE
standard

4





;
"""
                    # Modo INI: NÃO desenha texto do nome
            # Configuração dos textos/blocos ABCD (com ajustes para pilares especiais)
            if self.config_manager.get_config("drawing_options", "textos_abcd") == "blocos":
                # Usar blocos TA, TB, TC, TD
                script += f"""-INSERT
{self.config_manager.get_config("blocks", "ta")}
{self.x_inicial+comprimento_pilar_global/2+10},{self.y_inicial+5}
1
0
;
-INSERT
{self.config_manager.get_config("blocks", "tb")}
{self.x_inicial+comprimento_pilar_global/2-10},{self.y_inicial+largura_pilar_global-5}
1
0
;
-INSERT
{self.config_manager.get_config("blocks", "tc")}
{self.x_inicial+5},{self.y_inicial+largura_pilar_global/2-2}
1
0
;
-INSERT
{self.config_manager.get_config("blocks", "td")}
{self.x_inicial+comprimento_pilar_global-6},{self.y_inicial+largura_pilar_global/2-7}
1
0
;
"""
            else:
                # Usar textos originais com ajustes para pilares especiais
                # Usar as mesmas variáveis que controlam os painéis para controlar os textos
                if desenhar_pai_c and desenhar_pai_d:
                    # PILAR NORMAL: textos padrão
                    script += f"""_TEXT
{(self.x_inicial+comprimento_pilar_global) - 3},{self.y_inicial+largura_pilar_global/2 - 7}
0
D
;
_TEXT
{self.x_inicial},{(self.y_inicial+largura_pilar_global/2) - 6}
0
C
;
_TEXT
{(self.x_inicial+comprimento_pilar_global/2) - 7},{self.y_inicial+1}
0
A
;
_TEXT
{(self.x_inicial+comprimento_pilar_global/2) + 7},{self.y_inicial+largura_pilar_global-5}
0
B
;
"""
                elif not desenhar_pai_d:
                    # PILAR 1 ESPECIAL: PAI.D não desenha, PAI.C movido
                    # - Texto "D" NÃO se desenha (PAI.D não desenha)
                    # - Texto "C" movido 2cm para direita e 3cm para cima
                    script += f"""_TEXT
{self.x_inicial + 2},{(self.y_inicial+largura_pilar_global/2) - 6 + 3}
0
C
;
_TEXT
{(self.x_inicial+comprimento_pilar_global/2) - 7},{self.y_inicial+1}
0
A
;
_TEXT
{(self.x_inicial+comprimento_pilar_global/2) + 7},{self.y_inicial+largura_pilar_global-5}
0
B
;
"""
                elif not desenhar_pai_c:
                    # PILAR 2 ESPECIAL: PAI.C não desenha, PAI.D movido
                    # - Texto "C" NÃO se desenha (PAI.C não desenha)
                    # - Texto "A" alterado para "E" e movido 30cm para esquerda
                    # - Texto "B" alterado para "F" e movido 20cm para esquerda
                    # - Texto "D" movido 25cm para esquerda e 3cm para cima
                    script += f"""_TEXT
{(self.x_inicial+comprimento_pilar_global/2) - 7 - 30},{self.y_inicial+1}
0
E
;
_TEXT
{(self.x_inicial+comprimento_pilar_global/2) + 7 - 20},{self.y_inicial+largura_pilar_global-5}
0
F
;
_TEXT
{(self.x_inicial+comprimento_pilar_global) - 3 - 25},{self.y_inicial+largura_pilar_global/2 - 7 + 3}
0
D
;
"""

            #-----SALVAR O ARQUIVO-----

            # Criar diretório "scripts gerados" se não existir
            pavimento = self.pavimento_entry.get().strip()
            # Usar path resolver para obter o caminho correto
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            from utils.robust_path_resolver import robust_path_resolver
            diretorio_base = os.path.join(robust_path_resolver.get_project_root(), "output", "scripts")
            # Ajuste: pasta com sufixo _CIMA
            nome_pasta_pavimento = pavimento.replace(" ", "_") + "_CIMA"
            diretorio_pavimento = os.path.join(diretorio_base, nome_pasta_pavimento)
            os.makedirs(diretorio_pavimento, exist_ok=True)

            # Gerar nome de arquivo único com sufixo _CIMA (sobrescrever se existir)
            nome_pilar = self.nome_pilar_entry.get()
            nome_arquivo_base = os.path.join(diretorio_pavimento, nome_pilar)
            nome_arquivo = f"{nome_arquivo_base}_CIMA.scr"

            # PARAFUSO ADICIONAL (COMPRIMENTO < 30) - TRECHO INDEPENDENTE
            if comprimento_pilar_global < 30:
                # Definir layer "ESTRUTURA"
                script += f"""_LAYER
S {self.config_manager.get_config("layers", "metal")}

;
"""
                # Posição X do parafuso adicional (comprimento + 24 à direita do primeiro parafuso)
                posicao_x_parafuso_adicional = (
                    self.x_inicial
                    - 12
                    + comprimento_pilar_global
                    + 24
                )
                
                # Ajustar posição para condições especiais (largura >= 40cm)
                if largura_especial:
                    posicao_x_parafuso_adicional = self.x_inicial + comprimento_pilar_global + 15.5  # 3.5cm para fora da parede direita

                # Altura do parafuso (igual aos parafusos existentes)
                if comprimento_pilar_global < 223:
                    altura_parafuso = largura_pilar_global + 36.8
                else:
                    altura_parafuso = largura_pilar_global + 41.2

                # Centralizar verticalmente com PAI.C
                y_centro = self.y_inicial + largura_pilar_global / 2
                y_inferior = y_centro - altura_parafuso / 2
                y_superior = y_centro + altura_parafuso / 2

                # Desenho do parafuso adicional (último parafuso)
                usar_mline_adicional = False
                if largura_especial:
                    # Condições especiais para larguras >= 40cm - último parafuso
                    
                    # Verificar o tipo de linha configurado
                    if tipo_linha == "mline":
                        usar_mline_adicional = True
                        # Desenhar MLINE de 7cm de espessura ao redor do parafuso
                        script += f"""_mLINE
ST
METAL2
S
7
{posicao_x_parafuso_adicional - 3.5},{y_inferior - 6}
{posicao_x_parafuso_adicional - 3.5},{y_superior + 6}

;
"""
                    else:
                        # Desenhar retângulo de 7cm ao redor do parafuso (PLINE) - caso normal para largura >= 40cm
                        script += f"""_PLINE
{posicao_x_parafuso_adicional - 3.5},{y_inferior - 6}
{posicao_x_parafuso_adicional + 3.5},{y_inferior - 6}
{posicao_x_parafuso_adicional + 3.5},{y_superior + 6}
{posicao_x_parafuso_adicional - 3.5},{y_superior + 6}
C
;
"""
                    
                    # SEMPRE adicionar retângulo de 1cm para parafuso adicional (independente da largura)
                    # Ajustar coordenadas Y para modo mline
                    y_inferior_adicional = y_inferior - 6
                    y_superior_adicional = y_superior + 6
                    if tipo_linha == "mline" and largura_pilar_global >= 40:
                        y_inferior_adicional += 2.4  # Retângulo sobe 2.4cm
                        y_superior_adicional -= 2.4  # Retângulo desce 2.4cm
                    
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "hachura")}

;
_PLINE
{posicao_x_parafuso_adicional - 0.5},{y_inferior_adicional}
{posicao_x_parafuso_adicional + 0.5},{y_inferior_adicional}
{posicao_x_parafuso_adicional + 0.5},{y_superior_adicional}
{posicao_x_parafuso_adicional - 0.5},{y_superior_adicional}
C
;
"""
                    
                    # Adicionar retângulo de 7cm centralizado (layer METAL) - apenas se não for mline
                    if tipo_linha != "mline":
                        script += f"""_LAYER
S {self.config_manager.get_config("layers", "metal")}

;
_PLINE
{posicao_x_parafuso_adicional - 3.5},{y_inferior - 6}
{posicao_x_parafuso_adicional + 3.5},{y_inferior - 6}
{posicao_x_parafuso_adicional + 3.5},{y_superior + 6}
{posicao_x_parafuso_adicional - 3.5},{y_superior + 6}
C
;
"""
                    
                    # Adicionar retângulo de 3cm centralizado (layer METAL)
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "metal")}

;
_PLINE
{posicao_x_parafuso_adicional - 1.5},{y_inferior - 6}
{posicao_x_parafuso_adicional + 1.5},{y_inferior - 6}
{posicao_x_parafuso_adicional + 1.5},{y_superior + 6}
{posicao_x_parafuso_adicional - 1.5},{y_superior + 6}
C
;
_LAYER
S {self.config_manager.get_config("layers", "hachura")}

;
"""
                else:
                    # Comportamento normal para largura < 40cm - parafuso simples
                    # Ajustar coordenadas Y para modo mline (mesmo para largura < 40cm)
                    y_inferior_adicional = y_inferior - 6
                    y_superior_adicional = y_superior + 6
                    if tipo_linha == "mline":
                        y_inferior_adicional += 2.4  # Retângulo sobe 2.4cm
                        y_superior_adicional -= 2.4  # Retângulo desce 2.4cm
                    
                    script += f"""_LAYER
S {self.config_manager.get_config("layers", "hachura")}

;
_PLINE
{posicao_x_parafuso_adicional - 0.5},{y_inferior_adicional}
{posicao_x_parafuso_adicional + 0.5},{y_inferior_adicional}
{posicao_x_parafuso_adicional + 0.5},{y_superior_adicional}
{posicao_x_parafuso_adicional - 0.5},{y_superior_adicional}
C
;
"""

                # Para parafuso adicional (extremidade): NÃO inserir blocos nem retângulo interno
                # (parafuso adicional é sempre de extremidade, então não precisa de blocos PAR_CIMA/PAR_BAIXO)

                # Parafuso adicional é de extremidade: NÃO inserir blocos PAR.CIM e PAR.BAI
                # Definir layer "ESTRUTURA"
                script += f"""_LAYER
S {self.config_manager.get_config("layers", "cota")}

;
"""
                # Adicionar cota entre o primeiro parafuso e o parafuso adicional
                # Ajustar pontos das cotas: primeiro parafuso 2.5cm para a esquerda, último 3.5cm para a direita
                ponto_esquerdo_adicional = -12 + 1.0  # Primeiro parafuso: 1cm para a direita (2.5cm para a esquerda do original)
                ponto_direito_adicional = posicao_x_parafuso_adicional - 1.0  # Último parafuso: 1cm para a esquerda (3.5cm para a direita do original)
                
                script += f"""_DIMLINEAR
{ponto_esquerdo_adicional},{y_inferior}
{ponto_direito_adicional},{y_inferior}
{(ponto_esquerdo_adicional + ponto_direito_adicional) / 2},{y_inferior - 15}
;
"""

            # Restaurar camada para a camada padrão
            script += """_LAYER
S 0

;
"""
            
            # Adicionar comando scale no final
            # Calcular coordenadas do retângulo de seleção com 50cm de margem
            # Ponto 1: Esquina superior esquerda (x - 50, y + 50)
            # Ponto 2: Extremidade fundo direita (x + comprimento + 50, y - 50)
            ponto1_x = self.x_inicial - 100
            ponto1_y = self.y_inicial + largura_pilar_global + 100
            ponto2_x = self.x_inicial + comprimento_pilar_global + 100
            ponto2_y = self.y_inicial - 100
            
            # Obter fator de escala das configurações
            scale_factor = self.config_manager.get_config("drawing_options", "scale_factor")
            
            # Debug: Log do valor do scale_factor
            self.log_mensagem(f"Debug - Scale factor obtido: {scale_factor} (tipo: {type(scale_factor)})", "info")
            
            # Garantir que o scale_factor seja um número válido
            try:
                scale_factor = float(scale_factor)
            except (ValueError, TypeError):
                raise ValueError(f"Erro: Scale factor inválido '{scale_factor}' nas configurações. Verifique o valor em Configurações > Opções > Fator de Escala.")
            
            # Adicionar parafusos horizontais apenas se largura >= 40cm
            if largura_pilar_global >= 40:
                # Adicionar parafuso horizontal centralizado (entre lados C e D)
                # Posição X: centro do pilar
                posicao_x_horizontal = self.x_inicial + comprimento_pilar_global / 2
                
                # Posição Y: centro do pilar (entre C e D)
                posicao_y_horizontal = self.y_inicial + largura_pilar_global / 2
                
                # Calcular largura do parafuso horizontal (mesmo cálculo dos parafusos verticais)
                if comprimento_pilar_global < 223:
                    largura_parafuso_horizontal = comprimento_pilar_global + 36.8
                else:
                    largura_parafuso_horizontal = comprimento_pilar_global + 41.2
                
                # Calcular coordenadas X (esquerda e direita) - crescer 1.5cm para fora em cada extremidade
                x_esquerda = posicao_x_horizontal - largura_parafuso_horizontal / 2 + 2.4 - 3
                x_direita = posicao_x_horizontal + largura_parafuso_horizontal / 2 - 2.4 + 3
                
                # Definir layer para parafuso horizontal
                script += f"""_LAYER
S {self.config_manager.get_config("layers", "hachura")}

;
"""
                
                # Desenhar retângulo de 1cm horizontal (altura de 1cm) - diminuído 5.4cm de cada lado
                script += f"""_PLINE
{x_esquerda},{posicao_y_horizontal - 0.5}
{x_direita},{posicao_y_horizontal - 0.5}
{x_direita},{posicao_y_horizontal + 0.5}
{x_esquerda},{posicao_y_horizontal + 0.5}
C
;
"""
                
                # Inserir blocos PAR.ESQ e PAR.DIR nas pontas do retângulo de 1cm (movidos 1cm para o centro)
                script += f"""-INSERT
{self.config_manager.get_config("blocks", "parafuso_esquerda")}
{x_esquerda + 1},{posicao_y_horizontal}
1
0
;
-INSERT
{self.config_manager.get_config("blocks", "parafuso_direita")}
{x_direita - 1},{posicao_y_horizontal}
1
0
;
"""

                # Adicionar parafuso horizontal superior (9.5cm abaixo do topo dos parafusos verticais)
                # Calcular posição Y: topo dos parafusos verticais - 9.5cm
                # Topo dos parafusos verticais = y_superior + 6 (do cálculo anterior)
                y_superior_parafusos = self.y_inicial + largura_pilar_global / 2 + (largura_pilar_global + (36.8 if comprimento_pilar_global < 223 else 41.2)) / 2 + 6
                posicao_y_horizontal_superior = y_superior_parafusos - 9.5
                
                # Ajustar posição para modo mline (parafuso do topo desce 2.4cm)
                if tipo_linha == "mline" and largura_pilar_global >= 40:
                    posicao_y_horizontal_superior -= 2.4
                
                # Desenhar retângulo de 1cm horizontal superior
                script += f"""_PLINE
{x_esquerda},{posicao_y_horizontal_superior - 0.5}
{x_direita},{posicao_y_horizontal_superior - 0.5}
{x_direita},{posicao_y_horizontal_superior + 0.5}
{x_esquerda},{posicao_y_horizontal_superior + 0.5}
C
;
"""
                
                # Inserir blocos PAR.ESQ e PAR.DIR nas pontas do parafuso superior (movidos 1cm para o centro)
                script += f"""-INSERT
{self.config_manager.get_config("blocks", "parafuso_esquerda")}
{x_esquerda + 1},{posicao_y_horizontal_superior}
1
0
;
-INSERT
{self.config_manager.get_config("blocks", "parafuso_direita")}
{x_direita - 1},{posicao_y_horizontal_superior}
1
0
;
"""

                # Adicionar parafuso horizontal inferior (9.5cm acima do fundo dos parafusos verticais)
                # Calcular posição Y: fundo dos parafusos verticais + 9.5cm
                # Fundo dos parafusos verticais = y_inferior - 6 (do cálculo anterior)
                y_inferior_parafusos = self.y_inicial + largura_pilar_global / 2 - (largura_pilar_global + (36.8 if comprimento_pilar_global < 223 else 41.2)) / 2 - 6
                posicao_y_horizontal_inferior = y_inferior_parafusos + 9.5
                
                # Ajustar posição para modo mline (parafuso do fundo sobe 2.4cm)
                if tipo_linha == "mline" and largura_pilar_global >= 40:
                    posicao_y_horizontal_inferior += 2.4
                
                # Desenhar retângulo de 1cm horizontal inferior
                script += f"""_PLINE
{x_esquerda},{posicao_y_horizontal_inferior - 0.5}
{x_direita},{posicao_y_horizontal_inferior - 0.5}
{x_direita},{posicao_y_horizontal_inferior + 0.5}
{x_esquerda},{posicao_y_horizontal_inferior + 0.5}
C
;
"""
                
                # Inserir blocos PAR.ESQ e PAR.DIR nas pontas do parafuso inferior (movidos 1cm para o centro)
                script += f"""-INSERT
{self.config_manager.get_config("blocks", "parafuso_esquerda")}
{x_esquerda + 1},{posicao_y_horizontal_inferior}
1
0
;
-INSERT
{self.config_manager.get_config("blocks", "parafuso_direita")}
{x_direita - 1},{posicao_y_horizontal_inferior}
1
0
;
"""

                # Definir layer para cotas
                script += f"""_LAYER
S {self.config_manager.get_config("layers", "cota")}

;
"""

                # Adicionar cotas verticais entre parafusos horizontais (na direita)
                # Posição X das cotas verticais: lado direito do pilar + margem
                posicao_x_cota_vertical = self.x_inicial + comprimento_pilar_global + 15
                
                # Cota entre parafuso superior e central
                # Ponto superior: 3.5cm abaixo do parafuso superior - 11.4cm (desce o ponto de cima)
                # Ponto central: no centro do parafuso central
                ponto_superior_cota = posicao_y_horizontal_superior - 3.5 - 11.4
                ponto_central_cota = posicao_y_horizontal
                
                script += f"""_DIMLINEAR
{posicao_x_cota_vertical},{ponto_superior_cota}
{posicao_x_cota_vertical},{ponto_central_cota}
{posicao_x_cota_vertical + 20},{(ponto_superior_cota + ponto_central_cota) / 2}
;
;
"""

                # Cota entre parafuso central e inferior
                # Ponto central: no centro do parafuso central
                # Ponto inferior: 3.5cm acima do parafuso inferior + 11.4cm (sobe o ponto do fundo)
                ponto_inferior_cota = posicao_y_horizontal_inferior + 3.5 + 11.4
                
                script += f"""_DIMLINEAR
{posicao_x_cota_vertical},{ponto_central_cota}
{posicao_x_cota_vertical},{ponto_inferior_cota}
{posicao_x_cota_vertical + 20},{(ponto_central_cota + ponto_inferior_cota) / 2}
;
;
"""

                # Cota total dos parafusos (do superior ao inferior)
                script += f"""_DIMLINEAR
{posicao_x_cota_vertical},{ponto_superior_cota}
{posicao_x_cota_vertical},{ponto_inferior_cota}
{posicao_x_cota_vertical + 40},{(ponto_superior_cota + ponto_inferior_cota) / 2}
;
;
"""
            script += f""";
_ZOOM
S
0.005
;
"""
            
            # VERIFICAR SE PILAR ROTACIONADO ESTÁ ATIVO
            if robo_logger:
                robo_logger.subsection("DECISÃO DE COMANDO SCALE/ROTATE")
                robo_logger.info("🔄 Verificando qual comando usar (SCALE ou ROTATE)...")
            
            status_rotate = self.pilar_rotacionado_var.get()
            status_scale = self.usar_scale_var.get()
            print(f"DEBUG DECISAO: pilar_rotacionado = {status_rotate}, usar_scale = {status_scale}")
            
            if robo_logger:
                robo_logger.info(f"🔄 Status pilar_rotacionado = {status_rotate}, usar_scale = {status_scale}")
            
            if status_rotate:
                print("DEBUG DECISAO: PILAR ROTACIONADO ATIVO - Usando _ROTATE")
                if robo_logger:
                    robo_logger.info("✅ PILAR ROTACIONADO ATIVO - Usando _ROTATE")
                # Usar _ROTATE quando pilar rotacionado estiver ativo
                script += f"""_ROTATE
{ponto1_x - 50},{ponto1_y + 150}
{ponto2_x + 50},{ponto2_y - 150}

{ponto1_x},{ponto1_y}
{270}

;
"""
            elif status_scale:
                print("DEBUG DECISAO: Usando _SCALE")
                if robo_logger:
                    robo_logger.info("✅ Usando _SCALE")
                
                # Verificar se é pilar especial para usar valores diferentes
                is_pilar_especial = self.pilar_especial_ativo_var.get()
                
                if robo_logger:
                    robo_logger.info(f"🔄 Verificando se é pilar especial: {is_pilar_especial}")
                
                if is_pilar_especial:
                    print("DEBUG DECISAO: Pilar especial - usando valores alterados no _SCALE")
                    if robo_logger:
                        robo_logger.info("✅ Pilar especial - usando valores alterados no _SCALE")
                    # Usar _SCALE com valores alterados para pilar especial
                    script += f"""_SCALE
{ponto1_x - 600},{ponto1_y + 600}
{ponto2_x},{ponto2_y - 600}

{ponto1_x},{ponto1_y}
{scale_factor}


;
"""
                else:
                    print("DEBUG DECISAO: Pilar normal - usando valores padrão no _SCALE")
                    if robo_logger:
                        robo_logger.info("✅ Pilar normal - usando valores padrão no _SCALE")
                    # Usar _SCALE normalmente
                    script += f"""_SCALE
{ponto1_x - 80},{ponto1_y + 130}
{ponto2_x},{ponto2_y - 130}

{ponto1_x},{ponto1_y}
{scale_factor}


;
"""
            else:
                print("DEBUG DECISAO: Sem comando de transformacao (script intermediario)")
                if robo_logger:
                    robo_logger.info("✅ Sem comando de transformação (script intermediário)")
                # Não usar nem ROTATE nem SCALE (para scripts intermediários)
            
            if robo_logger:
                robo_logger.info("✅ Script gerado com sucesso!")
                robo_logger.data_processing("Script gerado", f"Tamanho: {len(script)} caracteres")
                robo_logger.section("FIM DA GERAÇÃO DE SCRIPT CIMA")

            # Normalização final: remover tabs/indentação à esquerda e padronizar comandos
            try:
                linhas_norm = []
                for ln in script.splitlines():
                    ln = ln.replace('\t', '')
                    linhas_norm.append(ln.lstrip())
                script = "\n".join(linhas_norm)
                script = script.replace("\nmline", "\n_MLINE").replace("\r\n", "\n")
                if not script.endswith("\n"):
                    script += "\n"
            except Exception:
                pass

            return script

        except ValueError as e:
            error_msg = f"Erro: Verifique se os valores numéricos são válidos - {str(e)}"
            self.log_mensagem(error_msg, "erro")
            if robo_logger:
                robo_logger.error(error_msg)
            return None
        except Exception as e:
            error_msg = f"Erro ao gerar script: {str(e)}"
            self.log_mensagem(error_msg, "erro")
            if robo_logger:
                robo_logger.error(error_msg)
                robo_logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def gerar_e_salvar_script(self):
        """Gera e salva o script na pasta do pavimento"""
        try:
            # Gerar o script
            script = self.gerar_script()
            
            if script:
                # Criar diretório "scripts gerados" se não existir
                pavimento = self.pavimento_entry.get().strip()
                # Usar path resolver para obter o caminho correto
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.dirname(__file__)))
                from utils.robust_path_resolver import robust_path_resolver
                diretorio_base = os.path.join(robust_path_resolver.get_project_root(), "output", "scripts")
                # Ajuste: pasta com sufixo _CIMA
                nome_pasta_pavimento = pavimento.replace(" ", "_") + "_CIMA"
                diretorio_pavimento = os.path.join(diretorio_base, nome_pasta_pavimento)
                os.makedirs(diretorio_pavimento, exist_ok=True)

                # Gerar nome de arquivo único com sufixo _CIMA
                nome_pilar = self.nome_pilar_entry.get()
                nome_arquivo_base = os.path.join(diretorio_pavimento, nome_pilar)
                nome_arquivo = f"{nome_arquivo_base}_CIMA.scr"
                contador = 1
                while os.path.exists(nome_arquivo):
                    nome_arquivo = f"{nome_arquivo_base}_CIMA-{contador}.scr"
                    contador += 1

                # Salvar script
                with open(nome_arquivo, "w", encoding="utf-16") as f:
                    f.write(script)

                self.resultado_label.config(text=f"Script gerado: {os.path.basename(nome_arquivo)}")
                self.log_mensagem(f"Script salvo em: {nome_arquivo}", "info")
            else:
                self.log_mensagem("Erro: Script não pôde ser gerado", "erro")
                
        except Exception as e:
            self.log_mensagem(f"Erro ao gerar e salvar script: {str(e)}", "erro")

    def calcular_valores(self, comprimento_pilar_str=None, largura_pilar_str=None):
        try:
            self.log_mensagem("Função calcular_valores iniciada", "info")
            
            if comprimento_pilar_str and largura_pilar_str:
                comprimento_pilar = float(comprimento_pilar_str.replace(',', '.'))
                largura_pilar = float(largura_pilar_str.replace(',', '.'))
            else:
                comprimento_pilar = float(self.comprimento_pilar_entry.get().replace(',', '.'))
                largura_pilar = float(self.largura_pilar_entry.get().replace(',', '.'))
            
            # Calcular quantidade de parafusos
            quantidade_parafusos = math.ceil((comprimento_pilar + 24) / 70) + 1

            # Debug: Log da quantidade de parafusos calculada
            self.log_mensagem(f"Debug - Comprimento: {comprimento_pilar}, Qtd Parafusos: {quantidade_parafusos}", "info")

            # Calcular distância entre parafusos
            if quantidade_parafusos > 1:
                distancia_parafusos = (comprimento_pilar + 24) / (quantidade_parafusos - 1)
                distancia_inteira = round(distancia_parafusos)
                total_distancia = distancia_inteira * (quantidade_parafusos - 1)
                diferenca = int((comprimento_pilar + 24) - total_distancia)

                # Debug: Log das distâncias calculadas
                self.log_mensagem(f"Debug - Distância base: {distancia_parafusos:.2f}, Distância inteira: {distancia_inteira}, Diferença: {diferenca}", "info")

                # Distribuir a diferença entre as distâncias do meio
                distancias = [distancia_inteira] * (quantidade_parafusos - 1)
                for i in range(abs(diferenca)):
                    if diferenca > 0:
                        distancias[len(distancias) // 2 + i // 2] += 1
                    else:
                        distancias[len(distancias) // 2 + i // 2] -= 1
                
                # Debug: Log das distâncias finais
                self.log_mensagem(f"Debug - Distâncias finais: {distancias}", "info")
            else:
                distancias = [0]

            # Preencher caixas de texto com distâncias calculadas
            for i, distancia in enumerate(distancias):
                self.parafuso_entries[i].delete(0, tk.END)
                self.parafuso_entries[i].insert(0, str(distancia))
            
            # Calcular valores para as grades
            # Ajuste aqui: Somar 22 ao comprimento do pilar
            comprimento_pilar += 22  # <--- Linha modificada

            if comprimento_pilar <= 120:
                self.grade1_entry.delete(0, tk.END)
                self.grade1_entry.insert(0, str(comprimento_pilar))
                self.distancia1_entry.delete(0, tk.END)
                self.grade2_entry.delete(0, tk.END)
                self.distancia2_entry.delete(0, tk.END)
                self.grade3_entry.delete(0, tk.END)
            else:
                if comprimento_pilar <= 150:
                    comprimento_retangulos = [60, 60]
                    espaco = (comprimento_pilar - 120) / 1
                elif comprimento_pilar <= 180:
                    comprimento_retangulos = [90, 60]
                    espaco = (comprimento_pilar - 150) / 1
                elif comprimento_pilar <= 210:
                    comprimento_retangulos = [90, 90]
                    espaco = (comprimento_pilar - 180) / 1
                elif comprimento_pilar <= 240:
                    comprimento_retangulos = [60, 60, 60]
                    espaco = (comprimento_pilar - 180) / 2
                elif comprimento_pilar <= 270:
                    comprimento_retangulos = [90, 90, 60]
                    espaco = (comprimento_pilar - 240) / 2
                elif comprimento_pilar <= 300:
                    comprimento_retangulos = [90, 90, 90]
                    espaco = (comprimento_pilar - 270) / 2
                elif comprimento_pilar <= 330:
                    comprimento_retangulos = [120, 90, 90]
                    espaco = (comprimento_pilar - 300) / 2
                elif comprimento_pilar <= 360:
                    comprimento_retangulos = [120, 120, 90]
                    espaco = (comprimento_pilar - 330) / 2
                else:
                    comprimento_retangulos = [120, 120, 120]
                    espaco = (comprimento_pilar - 360) / 2

                # Atualizar caixas de texto
                self.grade1_entry.delete(0, tk.END)
                self.grade1_entry.insert(0, str(comprimento_retangulos[0]))
                self.distancia1_entry.delete(0, tk.END)
                self.distancia1_entry.insert(0, str(espaco))
                self.grade2_entry.delete(0, tk.END)
                self.grade2_entry.insert(0, str(comprimento_retangulos[1]))
                if len(comprimento_retangulos) > 2:
                    self.distancia2_entry.delete(0, tk.END)
                    self.distancia2_entry.insert(0, str(espaco))
                    self.grade3_entry.delete(0, tk.END)
                    self.grade3_entry.insert(0, str(comprimento_retangulos[2]))
                else:
                    self.distancia2_entry.delete(0, tk.END)
                    self.grade3_entry.delete(0, tk.END)

            # Atualizar detalhes das grades após o cálculo
            self.atualizar_detalhes_grades(None)

        except ValueError:
            self.log_mensagem("Erro: Verifique os valores de entrada.", "erro")

    def salvar_teste(self):
        """Salva o script gerado no arquivo TESTEPILAR.scr"""
        try:
            # Gerar o script usando o método existente
            script = self.gerar_script()
            
            if script:
                # Resolver todas as configurações antes de salvar
                for layer_key in ["paineis", "sarrafos", "cotas", "textos", "metal", "hachura"]:
                    layer_value = self.config_manager.get_config("layers", layer_key)
                    script = script.replace(f"{{self.config_manager.get_config(\"layers\", \"{layer_key}\")}}", layer_value)
                
                for block_key in ["sar_gra_a1", "sar_gra_a2", "sar_gra_a3", "sar_gra_b1", "sar_gra_b2", "sar_gra_b3", "parafuso_cima", "parafuso_baixo", "parafuso_esquerda", "parafuso_direita", "block_central_grade_vertical"]:
                    block_value = self.config_manager.get_config("blocks", block_key)
                    script = script.replace(f"{{self.config_manager.get_config(\"blocks\", \"{block_key}\")}}", block_value)
                
                # Caminho do arquivo para salvar o script
                # Usar path resolver para obter caminho dinâmico
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.dirname(__file__)))
                from utils.robust_path_resolver import robust_path_resolver
                caminho_arquivo = os.path.join(robust_path_resolver.get_project_root(), "output", "teste_cima.scr")
                
                # Salvar o script no arquivo especificado
                with open(caminho_arquivo, 'w', encoding='utf-16') as arquivo:
                    arquivo.write(script)
                
                self.resultado_label.config(text=f"Script salvo em: {caminho_arquivo}")
            else:
                self.log_mensagem("Erro: Script não pôde ser gerado", "erro")
            
        except Exception as e:
            self.log_mensagem(f"Erro ao salvar script: {str(e)}", "erro")

    def atualizar_status(self, mensagem):
        """Atualiza o status da aplicação com a mensagem fornecida."""
        self.status_label.config(text=mensagem)
        self.log_text.insert(tk.END, mensagem + "\n")
        self.log_text.see(tk.END)

    def conectar_autocad(self):
        try:
            self.atualizar_status("Tentando conectar ao AutoCAD...")
            acad = win32com.client.Dispatch("AutoCAD.Application")
            self.atualizar_status("Conexão com o AutoCAD estabelecida.")
            
            arquivo_dwg = os.path.join(robust_path_resolver.get_project_root(), "templates", "molde_visao_cima.dwg")
            
            # Verificar se o arquivo já está aberto
            doc = None
            for i in range(acad.Documents.Count):
                document = acad.Documents.Item(i)
                if document.FullName.lower() == arquivo_dwg.lower():
                    doc = document
                    break
            
            if doc is None:
                self.atualizar_status(f"Abrindo o arquivo: {arquivo_dwg}")
                doc = acad.Documents.Open(arquivo_dwg)
                self.atualizar_status("Arquivo aberto com sucesso.")
                self.atualizar_status("Aguardando 15 segundos para o arquivo abrir completamente...")
                time.sleep(15)
                self.atualizar_status("Tempo de espera concluído.")
            else:
                self.atualizar_status("O arquivo já está aberto.")
            
            # Selecionar a janela específica do arquivo
            acad.ActiveDocument = doc
            self.atualizar_status("Janela do arquivo selecionada.")
            
            self.atualizar_status("AutoCAD conectado com sucesso.")
            return acad, doc
        except Exception as e:
            self.atualizar_status(f"Erro ao conectar ao AutoCAD: {str(e)}")
            return None, None

    def desenhar_cad(self):
        try:
            self.atualizar_status("Iniciando automação do AutoCAD...")
            
            # Dar um pequeno delay para preparação
            time.sleep(1)
            
            # Tentar encontrar e ativar a janela do AutoCAD
            try:
                # Procurar pela janela do AutoCAD
                janela = pyautogui.getWindowsWithTitle("AutoCAD")
                if janela:
                    janela[0].activate()
                    self.atualizar_status("Janela do AutoCAD ativada")
                else:
                    self.atualizar_status("Janela do AutoCAD não encontrada")
                    return
            except Exception as e:
                self.atualizar_status(f"Erro ao ativar janela do AutoCAD: {str(e)}")
                return
            
            # Dar um tempo para a janela ativar
            time.sleep(0.5)
            
            # Clicar no centro da tela
            screen_width, screen_height = pyautogui.size()
            pyautogui.click(screen_width/2, screen_height/2)
            time.sleep(0.2)
            
            # Sequência de comandos
            pyautogui.write('erase')
            pyautogui.press('enter')
            time.sleep(0.1)
            
            pyautogui.write('all')
            pyautogui.press('enter')
            pyautogui.press('enter')
            time.sleep(0.1)
            
            pyautogui.write('tp')
            pyautogui.press('enter')
            time.sleep(0.1)
            
            pyautogui.write('zoom')
            pyautogui.press('enter')
            time.sleep(0.1)
            
            pyautogui.write('0')
            pyautogui.press(',')
            pyautogui.write('05')
            pyautogui.press('enter')
            
            self.atualizar_status("Comandos executados com sucesso!")
            
        except Exception as e:
            self.atualizar_status(f"Erro durante a automação: {str(e)}")

    def atualizar_preview(self):
        try:
            comprimento_pilar = float(self.comprimento_pilar_entry.get().replace(',', '.'))
            largura_pilar = float(self.largura_pilar_entry.get().replace(',', '.'))
            
            # Resto do código permanece igual, apenas ajustar onde as medidas são exibidas
            # Por exemplo, ao adicionar texto de dimensões:
            
            # Adicionar texto com dimensões
            self.ax.text(-60, largura_pilar/2, 
                        f"{self.nome_pilar_entry.get()}\n({comprimento_pilar:.1f}X{largura_pilar:.1f})", 
                        ha='right', va='center')

            self.ax.clear()

            # Desenhar Pilar Principal (PI)
            self.ax.add_patch(plt.Rectangle((0, 0), comprimento_pilar, largura_pilar, fill=False, edgecolor='blue'))

            # Desenhar Painel C (PAI.C)
            self.ax.add_patch(plt.Rectangle((-2, 0), 2, largura_pilar, fill=False, edgecolor='purple'))
            
            # Desenhar Painel D (PAI.D)
            self.ax.add_patch(plt.Rectangle((comprimento_pilar, 0), 2, largura_pilar, fill=False, edgecolor='purple'))
            
            # Desenhar Painel B (PAI.B)
            self.ax.add_patch(plt.Rectangle((-11, largura_pilar), comprimento_pilar + 22, 2, fill=False, edgecolor='orange'))
            
            # Desenhar Painel A (PAI.A)
            self.ax.add_patch(plt.Rectangle((-11, -2), comprimento_pilar + 22, 2, fill=False, edgecolor='orange'))
            
            # Desenhar Sarrafos Verticais
            if largura_pilar < 30:
                # SAR 1
                self.ax.add_patch(plt.Rectangle((-4.2, 0), 2.2, 7, fill=False, edgecolor='red'))
                # SAR 2
                self.ax.add_patch(plt.Rectangle((-4.2, largura_pilar-7), 2.2, 7, fill=False, edgecolor='red'))
                # SAR 3
                self.ax.add_patch(plt.Rectangle((comprimento_pilar+2, 0), 2.2, 7, fill=False, edgecolor='red'))
                # SAR 4
                self.ax.add_patch(plt.Rectangle((comprimento_pilar+2, largura_pilar-7), 2.2, 7, fill=False, edgecolor='red'))
            else:
                # SAR 1
                self.ax.add_patch(plt.Rectangle((-4.2, 0), 2.2, largura_pilar, fill=False, edgecolor='red'))
                # SAR 3
                self.ax.add_patch(plt.Rectangle((comprimento_pilar+2, 0), 2.2, largura_pilar, fill=False, edgecolor='red'))
            
            # Desenhar Sarrafos Horizontais
            # SAR 5
            self.ax.add_patch(plt.Rectangle((-11, largura_pilar-2), 7, 2.2, fill=False, edgecolor='purple'))
            # SAR 6
            self.ax.add_patch(plt.Rectangle((-11, 0), 7, 2.2, fill=False, edgecolor='purple'))
            # SAR 7
            self.ax.add_patch(plt.Rectangle((comprimento_pilar+4, largura_pilar-2), 7, 2.2, fill=False, edgecolor='purple'))
            # SAR 8
            self.ax.add_patch(plt.Rectangle((comprimento_pilar+4, 0), 7, 2.2, fill=False, edgecolor='purple'))
            
            # Desenhar SAR244+.1 e SAR244+.2 se comprimento_pilar > 222
            if comprimento_pilar > 222:
                # SAR244+.1
                self.ax.add_patch(plt.Rectangle((-11, largura_pilar + 4), comprimento_pilar + 22, 2.2, fill=False, edgecolor='cyan'))
                # SAR244+.2
                self.ax.add_patch(plt.Rectangle((-11, -6.2), comprimento_pilar + 22, 2.2, fill=False, edgecolor='cyan'))
            
            # Desenhar GRA.A e GRA.B usando os valores das caixas de texto
            comprimento_retangulos = [
                float(self.grade1_entry.get() or 0),
                float(self.grade2_entry.get() or 0),
                float(self.grade3_entry.get() or 0)
            ]
            espacos = [
                float(self.distancia1_entry.get() or 0),
                float(self.distancia2_entry.get() or 0)
            ]

            # Desenhar GRA.A usando posições baseadas nos detalhes
            posicao_y_a = -7.2
            grades_ativas = sum(1 for comp in comprimento_retangulos if comp > 0)
            
            for i, comprimento in enumerate(comprimento_retangulos):
                if comprimento > 0:
                    # Usar a posição inicial correta para cada grade
                    posicao_x = self.calcular_posicao_inicial_grade(i)
                    
                    # Desenhar retângulo da GRA.A
                    self.ax.add_patch(plt.Rectangle((posicao_x, posicao_y_a), comprimento, 2.4, fill=False, edgecolor='green'))
                    
                    # Obter posições dos blocos baseado nos detalhes
                    posicoes_blocos = self.obter_posicoes_blocos_por_detalhes(i, is_grade_b=False)
                    
                    # Desenhar blocos das pontas com nova lógica
                    if grades_ativas == 1:
                        # 1 grade: blocks normais nas pontas (vermelho)
                        if len(posicoes_blocos) >= 1:
                            self.ax.add_patch(plt.Rectangle((posicoes_blocos[0], posicao_y_a + 2), 7, 7, fill=False, edgecolor='red'))
                        if len(posicoes_blocos) >= 2:
                            self.ax.add_patch(plt.Rectangle((posicoes_blocos[-1] - 7, posicao_y_a + 2), 7, 7, fill=False, edgecolor='red'))
                    else:
                        # Múltiplas grades: usar lógica baseada na posição
                        if len(posicoes_blocos) >= 1:
                            if i == 0:
                                # Primeira grade: vermelho na esquerda, azul na direita (com ajuste -3.5cm)
                                self.ax.add_patch(plt.Rectangle((posicoes_blocos[0], posicao_y_a + 2), 7, 7, fill=False, edgecolor='red'))
                                if len(posicoes_blocos) >= 2:
                                    self.ax.add_patch(plt.Rectangle((posicoes_blocos[-1] - 3.5, posicao_y_a + 2), 3.5, 7, fill=False, edgecolor='blue'))
                            elif i == grades_ativas - 1:
                                # Última grade: azul na esquerda (0cm), vermelho na direita
                                self.ax.add_patch(plt.Rectangle((posicoes_blocos[0], posicao_y_a + 2), 3.5, 7, fill=False, edgecolor='blue'))
                                if len(posicoes_blocos) >= 2:
                                    self.ax.add_patch(plt.Rectangle((posicoes_blocos[-1] - 7, posicao_y_a + 2), 7, 7, fill=False, edgecolor='red'))
                            else:
                                # Grade do meio: azul em ambas as pontas (0cm esquerda, -3.5cm direita)
                                self.ax.add_patch(plt.Rectangle((posicoes_blocos[0], posicao_y_a + 2), 3.5, 7, fill=False, edgecolor='blue'))
                                if len(posicoes_blocos) >= 2:
                                    self.ax.add_patch(plt.Rectangle((posicoes_blocos[-1] - 3.5, posicao_y_a + 2), 3.5, 7, fill=False, edgecolor='blue'))
                    
                    # Desenhar blocos centrais (sempre azuis)
                    for j, pos_x in enumerate(posicoes_blocos[1:-1], 1):
                        self.ax.add_patch(plt.Rectangle((pos_x, posicao_y_a + 2), 3.5, 7, fill=False, edgecolor='blue'))

            # Desenhar GRA.B usando posições baseadas nos detalhes
            posicao_y_b = largura_pilar + 7.2 + 4
            for i, comprimento in enumerate(comprimento_retangulos):
                if comprimento > 0:
                    # Usar a posição inicial correta para cada grade
                    posicao_x = self.calcular_posicao_inicial_grade(i)
                    
                    # Desenhar retângulo da GRA.B
                    self.ax.add_patch(plt.Rectangle((posicao_x, posicao_y_b), comprimento, 2.4, fill=False, edgecolor='green'))
                    
                    # Obter posições dos blocos baseado nos detalhes
                    posicoes_blocos = self.obter_posicoes_blocos_por_detalhes(i, is_grade_b=True)
                    
                    # Desenhar blocos das pontas com nova lógica
                    if grades_ativas == 1:
                        # 1 grade: blocks normais nas pontas (vermelho)
                        if len(posicoes_blocos) >= 1:
                            self.ax.add_patch(plt.Rectangle((posicoes_blocos[0], posicao_y_b - 7), 7, 7, fill=False, edgecolor='red'))
                        if len(posicoes_blocos) >= 2:
                            self.ax.add_patch(plt.Rectangle((posicoes_blocos[-1] - 7, posicao_y_b - 7), 7, 7, fill=False, edgecolor='red'))
                    else:
                        # Múltiplas grades: usar lógica baseada na posição
                        if len(posicoes_blocos) >= 1:
                            if i == 0:
                                # Primeira grade: vermelho na esquerda, azul na direita (com ajuste -3.5cm)
                                self.ax.add_patch(plt.Rectangle((posicoes_blocos[0], posicao_y_b - 7), 7, 7, fill=False, edgecolor='red'))
                                if len(posicoes_blocos) >= 2:
                                    self.ax.add_patch(plt.Rectangle((posicoes_blocos[-1] - 3.5, posicao_y_b - 7), 3.5, 7, fill=False, edgecolor='blue'))
                            elif i == grades_ativas - 1:
                                # Última grade: azul na esquerda (0cm), vermelho na direita
                                self.ax.add_patch(plt.Rectangle((posicoes_blocos[0], posicao_y_b - 7), 3.5, 7, fill=False, edgecolor='blue'))
                                if len(posicoes_blocos) >= 2:
                                    self.ax.add_patch(plt.Rectangle((posicoes_blocos[-1] - 7, posicao_y_b - 7), 7, 7, fill=False, edgecolor='red'))
                            else:
                                # Grade do meio: azul em ambas as pontas (0cm esquerda, -3.5cm direita)
                                self.ax.add_patch(plt.Rectangle((posicoes_blocos[0], posicao_y_b - 7), 3.5, 7, fill=False, edgecolor='blue'))
                                if len(posicoes_blocos) >= 2:
                                    self.ax.add_patch(plt.Rectangle((posicoes_blocos[-1] - 3.5, posicao_y_b - 7), 3.5, 7, fill=False, edgecolor='blue'))
                    
                    # Desenhar blocos centrais (sempre azuis)
                    for j, pos_x in enumerate(posicoes_blocos[1:-1], 1):
                        self.ax.add_patch(plt.Rectangle((pos_x, posicao_y_b - 7), 3.5, 7, fill=False, edgecolor='blue'))

                    # Adicionar cota da largura
                    self.ax.text(posicao_x + comprimento / 2, posicao_y_b + 40, f"{comprimento:.1f} cm", ha='center', va='bottom')

                    # Adicionar cotas das distâncias entre blocos baseado nos detalhes
                    if i == 0:
                        entries = self.detalhe_grade1_entries
                    elif i == 1:
                        entries = self.detalhe_grade2_entries
                    else:
                        entries = self.detalhe_grade3_entries
                    
                    pos_cota_x = posicao_x
                    for j, entry in enumerate(entries):
                        valor = entry.get().strip()
                        if valor and valor != "0" and float(valor) > 0:
                            distancia = float(valor)
                            self.ax.text(pos_cota_x + distancia/2, posicao_y_b + 15, f"{distancia:.1f}", ha='center', va='bottom', fontsize=8)
                            pos_cota_x += distancia

            # Desenhar METAL.A
            if comprimento_pilar > 222:
                posicao_y_a = -13.6
            else:
                posicao_y_a = -11.4
            
            # Ajustar posição se grades com sarrafo estiver desabilitado
            if self.config_manager.get_config("drawing_options", "grades_com_sarrafo") == "nao":
                posicao_y_a += 2.4  # Desce 2.4cm
                
            posicao_x_a = -31
            comprimento_metal = comprimento_pilar + 62
            largura_metal = 7

            # Estrutura METAL.A
            self.ax.add_patch(plt.Rectangle((posicao_x_a, posicao_y_a), comprimento_metal, -largura_metal, fill=False, edgecolor='black'))

            # Estrutura METAL.AI
            self.ax.add_patch(plt.Rectangle((posicao_x_a, posicao_y_a-2), comprimento_metal, -3, fill=False, edgecolor='gray'))

            # Desenhar METAL.B
            if comprimento_pilar > 222:
                posicao_y_b = largura_pilar + 9.6 + 6 - 2  # Ajuste de 2 cm para baixo
            else:
                posicao_y_b = largura_pilar + 7.4 + 6 - 2  # Ajuste de 2 cm para baixo
            
            # Ajustar posição se grades com sarrafo estiver desabilitado
            if self.config_manager.get_config("drawing_options", "grades_com_sarrafo") == "nao":
                posicao_y_b -= 2.4  # Sobe 2.4cm
                
            posicao_x_b = self.x_inicial - 31

            # Estrutura METAL.B
            self.ax.add_patch(plt.Rectangle((posicao_x_b, posicao_y_b), comprimento_metal, largura_metal, fill=False, edgecolor='black'))

            # Estrutura METAL.BI
            self.ax.add_patch(plt.Rectangle((posicao_x_b, posicao_y_b+2), comprimento_metal, 3, fill=False, edgecolor='gray'))

            # --- Início da lógica de desenho dos parafusos ---
            
            # Posição inicial X para os parafusos
            posicao_x_parafuso = -12
            
            # Condição especial para larguras de 40cm ou mais
            largura_especial = largura_pilar >= 40
            
            # Obter distâncias dos parafusos das caixas de texto
            distancias = [float(entry.get() or 0) for entry in self.parafuso_entries]
            
            # Desenhar os parafusos (exceto o segundo parafuso se comprimento < 30)
            # CORREÇÃO: As distâncias são as posições dos parafusos, não distâncias entre eles
            for i in range(len(distancias)):
                # Ajustar posição do parafuso para condições especiais (largura >= 40cm)
                posicao_x_atual = posicao_x_parafuso
                if largura_especial and (i == 0 or i == len(distancias) - 1):
                    if i == 0:  # Primeiro parafuso - mover para fora (3.5cm da parede)
                        posicao_x_atual = -15.5  # 3.5cm para fora da parede esquerda
                    elif i == len(distancias) - 1:  # Último parafuso - mover para fora (3.5cm da parede)
                        posicao_x_atual = comprimento_pilar + 15.5  # 3.5cm para fora da parede direita
                
                # Calcular altura do parafuso (ajustado para casos < 30 de largura)
                if largura_pilar < 30:
                    altura_parafuso = largura_pilar + 36.8
                else:
                    altura_parafuso = largura_pilar + 41.6

                # Calcular coordenadas Y (centro, inferior e superior)
                y_centro = largura_pilar / 2
                y_inferior = y_centro - altura_parafuso / 2
                y_superior = y_centro + altura_parafuso / 2

                # Desenhar a linha do parafuso, SE COMPRIMENTO >= 30 OU SE NÃO FOR O SEGUNDO PARAFUSO
                if comprimento_pilar >=30 or i != 1:
                    self.ax.plot([posicao_x_atual, posicao_x_atual], [y_inferior, y_superior], color='black', linestyle='--')
                    
                    # Desenhar retângulo ao redor do parafuso para condições especiais (largura >= 40cm)
                    if largura_especial and (i == 0 or i == len(distancias)):
                        # Retângulo de 7cm de espessura (3.5cm para cada lado)
                        self.ax.add_patch(plt.Rectangle((posicao_x_atual - 3.5, y_inferior), 7, altura_parafuso, 
                                                      fill=False, edgecolor='red', linestyle='--'))

                # Atualizar a posição X para o próximo parafuso
                if i < len(distancias):
                    posicao_x_parafuso += distancias[i]

            # Desenhar o segundo parafuso se o comprimento for menor que 30
            if comprimento_pilar < 30:
                # Calcular altura do parafuso (ajustado para casos < 30 de largura)
                if largura_pilar < 30:
                    altura_parafuso = largura_pilar + 36.8
                else:
                    altura_parafuso = largura_pilar + 41.6

                # Calcular coordenadas Y (centro, inferior e superior)
                y_centro = largura_pilar / 2
                y_inferior = y_centro - altura_parafuso / 2
                y_superior = y_centro + altura_parafuso / 2

                # A distância entre os parafusos é o comprimento do pilar + 24
                distancia_entre_parafusos = comprimento_pilar + 24

                # Calcula a nova posição X para o segundo parafuso
                posicao_x_segundo_parafuso = -12 + distancia_entre_parafusos

                # Desenha a linha do segundo parafuso
                self.ax.plot([posicao_x_segundo_parafuso, posicao_x_segundo_parafuso], [y_inferior, y_superior], color='black', linestyle='--')

                # Adiciona a cota entre os dois parafusos
                self.ax.text((posicao_x_parafuso + posicao_x_segundo_parafuso) / 2, y_inferior - 15, f"{distancia_entre_parafusos:.1f} cm", ha='center', va='top')

            # --- Fim da lógica de desenho dos parafusos ---

            # Ajustar limites do gráfico para 20 cm a mais em todas as direções
            self.ax.set_xlim(-60, comprimento_pilar + 100)
            self.ax.set_ylim(-40, largura_pilar + 40)
            self.ax.set_aspect('equal', adjustable='box')
            self.ax.set_facecolor('white')
            
            self.canvas.draw()
        except ValueError:
            pass

    def on_mouse_wheel(self, event):
        scale_factor = 1.1 if event.delta > 0 else 0.9
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        self.ax.set_xlim([x * scale_factor for x in xlim])
        self.ax.set_ylim([y * scale_factor for y in ylim])
        self.canvas.draw()

    def on_mouse_press(self, event):
        # Obter as coordenadas do clique do mouse em termos de dados do gráfico
        self.ax._pan_start = (event.x, event.y)

    def on_mouse_drag(self, event):
        if not hasattr(self.ax, '_pan_start') or self.ax._pan_start is None:
            return

        # Calcular a diferença de movimento do mouse
        dx = event.x - self.ax._pan_start[0]
        dy = event.y - self.ax._pan_start[1]

        # Converter a diferença de pixels para unidades de dados
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        dx_data = dx * (xlim[1] - xlim[0]) / self.canvas_widget.winfo_width()
        dy_data = dy * (ylim[1] - ylim[0]) / self.canvas_widget.winfo_height()

        # Atualizar os limites do grfico
        self.ax.set_xlim([x - dx_data for x in xlim])
        self.ax.set_ylim([y - dy_data for y in ylim])
        self.canvas.draw()

        # Atualizar a posição inicial do mouse
        self.ax._pan_start = (event.x, event.y)

    def on_mouse_release(self, event):
        self.ax._pan_start = None

    def atualizar_e_sincronizar_campo(self, campo, valor, callback=None):
        """Atualiza o valor do campo na interface."""
        try:
            campo.delete(0, tk.END)
            campo.insert(0, valor)
            if callback:
                callback(True)  # Indica sucesso
        except Exception as e:
            if callback:
                callback(False)  # Indica erro
            print(f"Erro ao atualizar campo: {e}")

    def sincronizar_comprimento(self, event):
        """Sincroniza o campo 'comprimento' com a OutraInterface."""
        valor = self.campos['comprimento'].get()  # Obtém o valor do campo 'comprimento'
        self.log_text.insert(tk.END, f"Campo 'comprimento' alterado para: {valor}\n", "info")
        self.master.sincronizacao_sucesso.set(False)  # Resetar a variável
        # Agenda a atualização do campo correspondente na OutraInterface
        self.root.after_idle(
            lambda: self.atualizar_e_sincronizar_campo(
                self.campos['comprimento'],
                valor,
                lambda sucesso: self.master.registrar_sincronizacao(sucesso)  # Callback
            )
        )
        self.root.after_idle(self.verificar_sincronizacao_comprimento)

    def verificar_sincronizacao_comprimento(self):
        """Verifica se a sincronização do campo 'comprimento' foi bem-sucedida."""
        if self.master.sincronizacao_sucesso.get():
            self.log_text.insert(tk.END, "  > Sincronização com 'comprimento_pilar_entry' bem-sucedida.\n", "sucesso")
        else:
            self.log_text.insert(tk.END, "  > Erro ao sincronizar 'comprimento_pilar_entry'.\n", "erro")

    def sincronizar_largura(self, event):
        """Sincroniza o campo 'largura' com a OutraInterface."""
        valor = self.campos['largura'].get()  # Obtém o valor do campo 'largura'
        self.log_text.insert(tk.END, f"Campo 'largura' alterado para: {valor}\n", "info")
        self.master.sincronizacao_sucesso.set(False)  # Resetar a variável
        # Agenda a atualização do campo correspondente na OutraInterface
        self.root.after_idle(
            lambda: self.atualizar_e_sincronizar_campo(
                self.campos['largura'],
                valor,
                lambda sucesso: self.master.registrar_sincronizacao(sucesso)  # Callback
            )
        )
        self.root.after_idle(self.verificar_sincronizacao_largura)

    def verificar_sincronizacao_largura(self):
        """Verifica se a sincronização do campo 'largura' foi bem-sucedida."""
        if self.master.sincronizacao_sucesso.get():
            self.log_text.insert(tk.END, "  > Sincronização com 'largura_pilar_entry' bem-sucedida.\n", "sucesso")
        else:
            self.log_text.insert(tk.END, "  > Erro ao sincronizar 'largura_pilar_entry'.\n", "erro")

    def limpar_campos(self):
        self.nome_pilar_entry.delete(0, tk.END)
        self.comprimento_pilar_entry.delete(0, tk.END)
        self.largura_pilar_entry.delete(0, tk.END)
        self.grade1_entry.delete(0, tk.END)
        self.distancia1_entry.delete(0, tk.END)
        self.grade2_entry.delete(0, tk.END)
        self.distancia2_entry.delete(0, tk.END)
        self.grade3_entry.delete(0, tk.END)
        for entry in self.parafuso_entries:
            entry.delete(0, tk.END)

    def sincronizar_nome(self, event):
        """Sincroniza o campo 'nome_pilar_entry' com a GeradorPilares."""
        valor = self.nome_pilar_entry.get()
        self.atualizar_preview()

    def sincronizar_comprimento(self, event):
        """Sincroniza o campo 'comprimento_pilar_entry' com a GeradorPilares."""
        valor = self.comprimento_pilar_entry.get()
        self.atualizar_preview()

    def sincronizar_largura(self, event):
        """Sincroniza o campo 'largura_pilar_entry' com a GeradorPilares."""
        valor = self.largura_pilar_entry.get()
        self.atualizar_preview()

    def sincronizar_parafuso(self, index):
        """Sincroniza um campo de parafuso específico."""
        try:
            valor = self.parafuso_entries[index].valor_var.get()
            self.log_text.insert(tk.END, f"Campo parafuso P{index+1}-P{index+2} alterado para: {valor}\n", "info")
            self.atualizar_preview()
        except Exception as e:
            self.log_text.insert(tk.END, f"Erro ao sincronizar parafuso P{index+1}-P{index+2}: {e}\n", "erro")

    def atualizar_campo_parafuso(self, index, valor, callback=None):
        """Atualiza o valor de um campo de parafuso específico."""
        try:
            if index < len(self.parafuso_entries):
                entry = self.parafuso_entries[index]
                entry.delete(0, tk.END)
                entry.insert(0, valor)
                if callback:
                    callback(True)
        except Exception as e:
            if callback:
                callback(False)
            print(f"Erro ao atualizar campo de parafuso: {e}")

    def validar_hatch(self, valor):
        """Valida o valor do hatch inserido"""
        try:
            valor = int(valor)
            if valor in [0, 1, 2]:
                return True
            return False
        except ValueError:
            return False

    def converter_valor_hatch(self, valor):
        """Converte o valor numérico do hatch para seu significado"""
        mapeamento = {
            "0": "Nenhum",
            "1": "REAP Inteiro",
            "2": "REAP Cortado"
        }
        return mapeamento.get(str(valor), "Nenhum")

    def salvar_template(self, template_name):
        if template_name:
            # Salvar o template e obter o nome final usado
            nome_original = template_name
            self.config_manager.save_template(template_name, self.config_manager.config)
            
            # Verificar se o nome foi alterado (adicionado sufixo)
            if nome_original in self.config_manager.templates:
                # O nome original foi mantido
                nome_final = nome_original
            else:
                # Procurar pelo template com sufixo
                for nome_template in self.config_manager.templates.keys():
                    if nome_template.startswith(nome_original + "."):
                        nome_final = nome_template
                        break
                else:
                    nome_final = nome_original
            
            self.atualizar_lista_templates()
            
            if nome_final == nome_original:
                messagebox.showinfo("Sucesso", f"Template '{nome_final}' salvo com sucesso!")
            else:
                messagebox.showinfo("Sucesso", f"Template '{nome_original}' já existia. Salvo como '{nome_final}'!")
        else:
            messagebox.showerror("Erro", "Digite um nome para o template")
    
    def carregar_template(self, template_name):
        try:
            if not template_name:
                messagebox.showerror("Erro", "Digite um nome para o template")
                return
                
            if template_name in self.config_manager.templates:
                # Carrega o template mesclando com as configurações padrão
                template_config = self.config_manager.templates[template_name].copy()
                default_config = self.config_manager.get_default_config()
                self.config_manager.config = self.config_manager.merge_configs(default_config, template_config)
                
                # Atualiza os campos da interface sem fechar a janela
                if hasattr(self, 'config_window') and self.config_window.winfo_exists():
                    # Atualiza todos os campos de layers
                    if hasattr(self, 'layer_entries'):
                        for layer, entry in self.layer_entries.items():
                            entry.delete(0, tk.END)
                            entry.insert(0, self.config_manager.get_config("layers", layer))
                    
                    # Atualiza os blocos
                    if hasattr(self, 'block_entries'):
                        for block, entry in self.block_entries.items():
                            entry.delete(0, tk.END)
                            entry.insert(0, self.config_manager.get_config("blocks", block))
                    
                    # Atualiza opções de desenho
                    if hasattr(self, 'scale_entry'):
                        self.scale_entry.delete(0, tk.END)
                        self.scale_entry.insert(0, self.config_manager.get_config("drawing_options", "scale_factor"))
                    
                    if hasattr(self, 'dimstyle_entry'):
                        self.dimstyle_entry.delete(0, tk.END)
                        self.dimstyle_entry.insert(0, self.config_manager.get_config("drawing_options", "dimstyle"))
                    
                    if hasattr(self, 'dimstyle_centro_entry'):
                        self.dimstyle_centro_entry.delete(0, tk.END)
                        self.dimstyle_centro_entry.insert(0, self.config_manager.get_config("drawing_options", "dimstyleCENTRO"))
                    
                    # Atualizar a variável de texto ABCD
                    if hasattr(self, 'texto_abcd_var'):
                        self.texto_abcd_var.set(self.config_manager.get_config("drawing_options", "textos_abcd"))
                    
                    # Atualizar a variável de texto do nome
                    if hasattr(self, 'texto_nome_var'):
                        self.texto_nome_var.set(self.config_manager.get_config("drawing_options", "incluir_texto_nome"))
                    
                    # Atualizar a variável de grades com sarrafo
                    if hasattr(self, 'grades_sarrafo_var'):
                        self.grades_sarrafo_var.set(self.config_manager.get_config("drawing_options", "grades_com_sarrafo"))
                    
                    # Atualizar a variável de tipo de linha
                    if hasattr(self, 'tipo_linha_var'):
                        self.tipo_linha_var.set(self.config_manager.get_config("drawing_options", "tipo_linha"))
                
                messagebox.showinfo("Sucesso", f"Template '{template_name}' carregado!")
            else:
                messagebox.showerror("Erro", f"Template '{template_name}' não encontrado. Templates disponíveis: {', '.join(self.config_manager.templates.keys())}")
        except Exception as e:
            print(f"Erro ao carregar template: {e}")
            messagebox.showerror("Erro", f"Erro ao carregar template: {str(e)}")
    
    def deletar_template(self, template_name):
        if template_name in self.config_manager.templates:
            self.config_manager.delete_template(template_name)
            self.atualizar_lista_templates()
            messagebox.showinfo("Sucesso", f"Template '{template_name}' removido!")
        else:
            messagebox.showerror("Erro", "Template não encontrado")
    
    def atualizar_lista_templates(self):
        try:
            if hasattr(self, 'template_list') and self.template_list.winfo_exists():
                self.template_list.delete(0, tk.END)
                templates = list(self.config_manager.templates.keys())
                for template in templates:
                    self.template_list.insert(tk.END, template)
        except Exception as e:
            print(f"Erro ao atualizar lista de templates: {e}")
    
    def selecionar_template(self, event):
        selection = self.template_list.curselection()
        if selection:
            template_name = self.template_list.get(selection[0])
            self.template_name_entry.delete(0, tk.END)  # Alterado para self.template_name_entry
            self.template_name_entry.insert(0, template_name)  # Alterado para self.template_name_entry

    def verificar_integridade_template(self, template_name):
        """Verifica se um template tem todas as configurações necessárias."""
        if template_name not in self.config_manager.templates:
            return False, "Template não encontrado"
        
        template = self.config_manager.templates[template_name]
        default_config = self.config_manager.get_default_config()
        
        missing_configs = []
        
        # Verificar seções principais
        for section in default_config:
            if section not in template:
                missing_configs.append(f"Seção '{section}' ausente")
            else:
                # Verificar chaves dentro de cada seção
                for key in default_config[section]:
                    if key not in template[section]:
                        missing_configs.append(f"Configuração '{section}.{key}' ausente")
        
        if missing_configs:
            return False, f"Configurações ausentes: {', '.join(missing_configs)}"
        else:
            return True, "Template completo"

    def atualizar_detalhes_grades(self, event):
        """Atualiza os campos de detalhes das grades com as distâncias entre blocos."""
        try:
            # Limpar todos os campos primeiro (mas não aplicar readonly)
            for entries in [self.detalhe_grade1_entries, self.detalhe_grade2_entries, self.detalhe_grade3_entries]:
                for entry in entries:
                    entry.delete(0, tk.END)
            
            # Obter valores das grades
            grades = [
                float(self.grade1_entry.get() or 0),
                float(self.grade2_entry.get() or 0),
                float(self.grade3_entry.get() or 0)
            ]
            
            # NÃO calcular detalhes automaticamente - usar apenas os valores dos campos
            # Os detalhes devem ser preenchidos manualmente pelo usuário
            pass
            
        except ValueError:
            # Se houver erro de conversão, apenas ignore silenciosamente
            pass
    
    def calcular_distancias_blocos_grade(self, comprimento_grade):
        """
        Calcula as distâncias entre os blocos de uma grade específica.
        Retorna uma lista com até 5 distâncias.
        """
        distancias = []
        posicao_x = -11  # Posição inicial (11 cm à esquerda)
        
        if comprimento_grade <= 30:
            # Grade até 30cm: apenas blocos das pontas (B1A.E e B1A.D)
            # Distância total entre os blocos das pontas
            distancias.append(comprimento_grade)
            # Preencher resto com zeros
            distancias.extend([0, 0, 0, 0])
            
        elif 31 <= comprimento_grade <= 60:
            # Grade 31-60cm: 1 bloco central + blocos das pontas
            centro_x = posicao_x + comprimento_grade / 2
            # Arredondamento conforme lógica original
            parte_decimal = centro_x - math.floor(centro_x)
            if parte_decimal >= 0.5:
                centro_x_rounded = math.ceil(centro_x)
            else:
                centro_x_rounded = math.floor(centro_x)
            
            # Distâncias: ponta esquerda -> centro -> ponta direita
            dist1 = centro_x_rounded - posicao_x
            dist2 = (posicao_x + comprimento_grade) - centro_x_rounded
            
            distancias.extend([dist1, dist2, 0, 0, 0])
            
        elif 61 <= comprimento_grade <= 90:
            # Grade 61-90cm: 2 blocos centrais + blocos das pontas
            pos1 = posicao_x + (comprimento_grade / 3)
            pos2 = posicao_x + (2 * comprimento_grade / 3)
            
            # Arredondamento complementar conforme lógica original
            pos1_rounded = math.floor(pos1)
            pos2_rounded = math.ceil(pos2)
            
            # Distâncias entre todos os blocos
            dist1 = pos1_rounded - posicao_x
            dist2 = pos2_rounded - pos1_rounded
            dist3 = (posicao_x + comprimento_grade) - pos2_rounded
            
            distancias.extend([dist1, dist2, dist3, 0, 0])
            
        elif 91 <= comprimento_grade:
            # Grade 91+cm: 3 blocos centrais + blocos das pontas
            pos1 = posicao_x + (comprimento_grade / 4)
            pos2 = posicao_x + (comprimento_grade / 2)  # Central
            pos3 = posicao_x + (3 * comprimento_grade / 4)
            
            # Arredondamento conforme lógica original
            pos1_rounded = math.floor(pos1)
            pos2_rounded = round(pos2)  # Central mantém exato
            pos3_rounded = math.ceil(pos3)
            
            # Distâncias entre todos os blocos
            dist1 = pos1_rounded - posicao_x
            dist2 = pos2_rounded - pos1_rounded
            dist3 = pos3_rounded - pos2_rounded
            dist4 = (posicao_x + comprimento_grade) - pos3_rounded
            
            distancias.extend([dist1, dist2, dist3, dist4, 0])
        
        return distancias

    def atualizar_grade_por_detalhes(self, event):
        """Atualiza o tamanho das grades baseado na soma dos valores dos detalhes."""
        try:
            # Atualizar Grade 1
            total_grade1 = 0
            for entry in self.detalhe_grade1_entries:
                valor = entry.get().strip()
                if valor and valor != "0":
                    total_grade1 += float(valor)
            
            if total_grade1 > 0:
                self.grade1_entry.delete(0, tk.END)
                self.grade1_entry.insert(0, f"{total_grade1:.1f}")
            
            # Atualizar Grade 2
            total_grade2 = 0
            for entry in self.detalhe_grade2_entries:
                valor = entry.get().strip()
                if valor and valor != "0":
                    total_grade2 += float(valor)
            
            if total_grade2 > 0:
                self.grade2_entry.delete(0, tk.END)
                self.grade2_entry.insert(0, f"{total_grade2:.1f}")
            
            # Atualizar Grade 3
            total_grade3 = 0
            for entry in self.detalhe_grade3_entries:
                valor = entry.get().strip()
                if valor and valor != "0":
                    total_grade3 += float(valor)
            
            if total_grade3 > 0:
                self.grade3_entry.delete(0, tk.END)
                self.grade3_entry.insert(0, f"{total_grade3:.1f}")
            
            # Atualizar preview
            self.atualizar_preview()
            
        except ValueError:
            # Se houver erro de conversão, apenas ignore silenciosamente
            pass
    
    def calcular_posicao_inicial_grade(self, index_grade):
        """
        Calcula a posição inicial X de uma grade considerando as grades anteriores e distâncias.
        """
        posicao_x = -11  # Posição inicial base
        
        # Obter valores das grades e distâncias - SEM FALLBACK, deixar dar erro se necessário
        comprimento_retangulos = [
            float(self.grade1_entry.get() or 0),
            float(self.grade2_entry.get() or 0),
            float(self.grade3_entry.get() or 0)
        ]
        espacos = [
            float(self.distancia1_entry.get() or 0),
            float(self.distancia2_entry.get() or 0)
        ]
        
        # Calcular posição acumulativa
        print(f"[DEBUG] calcular_posicao_inicial_grade - index_grade={index_grade}")
        print(f"[DEBUG] comprimento_retangulos={comprimento_retangulos}")
        print(f"[DEBUG] espacos={espacos}")
        
        for i in range(index_grade):
            if comprimento_retangulos[i] > 0:
                posicao_x += comprimento_retangulos[i]
                print(f"[DEBUG] Após grade {i+1} ({comprimento_retangulos[i]}cm): posicao_x={posicao_x}")
                if i < len(espacos):
                    posicao_x += espacos[i]
                    print(f"[DEBUG] Após espaço {i+1} ({espacos[i]}cm): posicao_x={posicao_x}")
        
        print(f"[DEBUG] Posição final calculada: {posicao_x}")
        return posicao_x

    def obter_posicoes_blocos_por_detalhes(self, index_grade, is_grade_b=False):
        """
        Obtém as posições dos blocos baseado nos valores dos detalhes.
        Retorna uma lista de posições X dos blocos.
        
        Args:
            index_grade: Índice da grade (0, 1, 2)
            is_grade_b: Se True, usa os entry fields do Grupo 2 (Grade B)
        """
        print(f"[DEBUG] obter_posicoes_blocos_por_detalhes chamada - index_grade={index_grade}, is_grade_b={is_grade_b}")
        
        # Verificar se é pilar especial e usar campos da aba Pilares Especiais
        eh_pilar_especial = self._verificar_pilar_especial_ativo()
        print(f"[DEBUG] Verificação pilar especial: {eh_pilar_especial}")
        if eh_pilar_especial:
            print(f"[DEBUG] Pilar especial detectado - usando campos da aba Pilares Especiais")
            
            # Mapear index_grade e is_grade_b para as letras corretas das grades especiais
            letra_grade = None
            if index_grade == 0:
                if is_grade_b:
                    letra_grade = 'b'  # Grade B (Pilar 1)
                else:
                    letra_grade = 'a'  # Grade A (Pilar 1)
            elif index_grade == 1:
                if is_grade_b:
                    letra_grade = 'f'  # Grade F (Pilar 2)
                else:
                    letra_grade = 'e'  # Grade E (Pilar 2)
            
            print(f"[DEBUG] Mapeamento: index_grade={index_grade}, is_grade_b={is_grade_b} -> letra_grade={letra_grade}")
            
            if letra_grade:
                # Usar campos da aba Pilares Especiais
                detalhes = []
                campos_encontrados = 0
                
                # Para pilares especiais, usar diretamente a lógica das grades especiais
                # em vez de tentar acessar campos da interface que não existem
                print(f"[DEBUG] Usando lógica das grades especiais para {letra_grade}")
                
                # Usar a mesma lógica das grades especiais: acessar detalhes_grades e detalhes_grades_grupo2
                if is_grade_b:
                    # Grade B: usar detalhes_grades_grupo2
                    if hasattr(self, 'detalhes_grades_grupo2') and self.detalhes_grades_grupo2:
                        for i in range(1, 6):  # 5 detalhes
                            campo_nome = f"detalhe_grade1_{i}_grupo2"  # Grade B = grade1_grupo2
                            valor = self.detalhes_grades_grupo2.get(campo_nome, '0')
                            print(f"[DEBUG] Detalhes grupo2 {campo_nome}: '{valor}'")
                            detalhes.append(valor)
                            if valor and valor != '0':
                                campos_encontrados += 1
                else:
                    # Grade A: usar detalhes_grades
                    if hasattr(self, 'detalhes_grades') and self.detalhes_grades:
                        for i in range(1, 6):  # 5 detalhes
                            campo_nome = f"detalhe_grade1_{i}"  # Grade A = grade1
                            valor = self.detalhes_grades.get(campo_nome, '0')
                            print(f"[DEBUG] Detalhes grupo1 {campo_nome}: '{valor}'")
                            detalhes.append(valor)
                            if valor and valor != '0':
                                campos_encontrados += 1
                
                # Se ainda não encontrou, usar fallback
                if campos_encontrados == 0:
                    print(f"[DEBUG] Nenhum campo da aba Pilares Especiais encontrado, usando fallback")
                    # Não retornar None, continuar para usar a lógica de fallback
                
                print(f"[DEBUG] Detalhes da aba Pilares Especiais ({letra_grade}): {detalhes}")
                
                posicoes = []
                # Usar a posição inicial correta para cada grade - começar na mesma posição X da grade
                posicao_x = self.calcular_posicao_inicial_grade(index_grade)
                print(f"[DEBUG] Posição inicial calculada: {posicao_x}")

                # Sempre adiciona a posição inicial (bloco da ponta esquerda)
                posicoes.append(posicao_x)
                
                # Adiciona posições baseado nos detalhes
                for i, valor in enumerate(detalhes):
                    print(f"[DEBUG] Detalhe {i}: valor='{valor}'")
                    if valor and str(valor) != "0" and float(valor) > 0:
                        # Distâncias de detalhes - usar valor direto sem escala
                        posicao_x += float(valor)
                        posicoes.append(posicao_x)
                        print(f"[DEBUG] Adicionada posição: {posicao_x}")
                
                print(f"[DEBUG] Posições finais: {posicoes}")
                return posicoes
            else:
                print(f"[DEBUG] Nenhum campo da aba Pilares Especiais encontrado, usando fallback")
        
        # Se chegou aqui, usar fallback (campos da aba Dados Gerais)
        print(f"[DEBUG] Usando fallback - campos da aba Dados Gerais")
        
        # Verificar se temos entry fields criados (GUI) ou usar dados diretos
        if hasattr(self, 'detalhe_grade1_entries') and self.detalhe_grade1_entries:
            # Usar entry fields da GUI
            if is_grade_b:
                # Usar entry fields do Grupo 2 (Grade B)
                if index_grade == 0:
                    entries = self.detalhe_grade1_grupo2_entries
                    print(f"[DEBUG] Usando detalhe_grade1_grupo2_entries para Grade B (GUI)")
                elif index_grade == 1:
                    entries = self.detalhe_grade2_grupo2_entries
                    print(f"[DEBUG] Usando detalhe_grade2_grupo2_entries para Grade B (GUI)")
                else:
                    entries = self.detalhe_grade3_grupo2_entries
                    print(f"[DEBUG] Usando detalhe_grade3_grupo2_entries para Grade B (GUI)")
            else:
                # Usar entry fields do Grupo 1 (Grade A)
                if index_grade == 0:
                    entries = self.detalhe_grade1_entries
                    print(f"[DEBUG] Usando detalhe_grade1_entries para Grade A (GUI)")
                elif index_grade == 1:
                    entries = self.detalhe_grade2_entries
                    print(f"[DEBUG] Usando detalhe_grade2_entries para Grade A (GUI)")
                else:
                    entries = self.detalhe_grade3_entries
                    print(f"[DEBUG] Usando detalhe_grade3_entries para Grade A (GUI)")

            print(f"[DEBUG] Entries encontrados: {len(entries) if entries else 0}")

            posicoes = []
            # Usar a posição inicial correta para cada grade - começar na mesma posição X da grade
            posicao_x = self.calcular_posicao_inicial_grade(index_grade)
            print(f"[DEBUG] Posição inicial calculada: {posicao_x}")

            # Sempre adiciona a posição inicial (bloco da ponta esquerda)
            posicoes.append(posicao_x)
            # Adiciona posições baseado nos detalhes
            for i, entry in enumerate(entries):
                valor = entry.get().strip()
                print(f"[DEBUG] Entry {i}: valor='{valor}'")
                if valor and valor != "0" and float(valor) > 0:
                     # Distâncias de detalhes - usar valor direto sem escala
                     posicao_x += float(valor)
                     posicoes.append(posicao_x)
                     print(f"[DEBUG] Adicionada posição: {posicao_x}")

            print(f"[DEBUG] Posições finais: {posicoes}")
            return posicoes
        else:
            # Usar dados diretos (sem GUI)
            print(f"[DEBUG] Usando dados diretos (sem GUI)")
            
            # Obter dados dos detalhes baseado no índice e tipo
            detalhes = []
            if is_grade_b:
                # Usar detalhes do Grupo 2
                if index_grade == 0:
                    detalhes = [
                        getattr(self, 'detalhe_grade1_1_grupo2', '0'),
                        getattr(self, 'detalhe_grade1_2_grupo2', '0'),
                        getattr(self, 'detalhe_grade1_3_grupo2', '0'),
                        getattr(self, 'detalhe_grade1_4_grupo2', '0'),
                        getattr(self, 'detalhe_grade1_5_grupo2', '0')
                    ]
                elif index_grade == 1:
                    detalhes = [
                        getattr(self, 'detalhe_grade2_1_grupo2', '0'),
                        getattr(self, 'detalhe_grade2_2_grupo2', '0'),
                        getattr(self, 'detalhe_grade2_3_grupo2', '0'),
                        getattr(self, 'detalhe_grade2_4_grupo2', '0'),
                        getattr(self, 'detalhe_grade2_5_grupo2', '0')
                    ]
                else:
                    detalhes = [
                        getattr(self, 'detalhe_grade3_1_grupo2', '0'),
                        getattr(self, 'detalhe_grade3_2_grupo2', '0'),
                        getattr(self, 'detalhe_grade3_3_grupo2', '0'),
                        getattr(self, 'detalhe_grade3_4_grupo2', '0'),
                        getattr(self, 'detalhe_grade3_5_grupo2', '0')
                    ]
            else:
                # Usar detalhes do Grupo 1
                if index_grade == 0:
                    detalhes = [
                        getattr(self, 'detalhe_grade1_1', '0'),
                        getattr(self, 'detalhe_grade1_2', '0'),
                        getattr(self, 'detalhe_grade1_3', '0'),
                        getattr(self, 'detalhe_grade1_4', '0'),
                        getattr(self, 'detalhe_grade1_5', '0')
                    ]
                elif index_grade == 1:
                    detalhes = [
                        getattr(self, 'detalhe_grade2_1', '0'),
                        getattr(self, 'detalhe_grade2_2', '0'),
                        getattr(self, 'detalhe_grade2_3', '0'),
                        getattr(self, 'detalhe_grade2_4', '0'),
                        getattr(self, 'detalhe_grade2_5', '0')
                    ]
                else:
                    detalhes = [
                        getattr(self, 'detalhe_grade3_1', '0'),
                        getattr(self, 'detalhe_grade3_2', '0'),
                        getattr(self, 'detalhe_grade3_3', '0'),
                        getattr(self, 'detalhe_grade3_4', '0'),
                        getattr(self, 'detalhe_grade3_5', '0')
                    ]
            
            print(f"[DEBUG] Detalhes obtidos: {detalhes}")
            
            posicoes = []
            # Usar a posição inicial correta para cada grade - começar na mesma posição X da grade
            posicao_x = self.calcular_posicao_inicial_grade(index_grade)
            
            print(f"[DEBUG] Posição inicial calculada: {posicao_x}")
            
            # Sempre adiciona a posição inicial (bloco da ponta esquerda)
            posicoes.append(posicao_x)
            
            # Adiciona posições baseado nos detalhes
            for i, valor in enumerate(detalhes):
                print(f"[DEBUG] Detalhe {i}: valor='{valor}'")
                if valor and str(valor) != "0" and float(valor) > 0:
                    # CORREÇÃO: Distâncias de detalhes são entre blocks consecutivos, não cumulativas
                    # Somar apenas a distância do detalhe atual
                    posicao_x += float(valor)
                    posicoes.append(posicao_x)
                    print(f"[DEBUG] Adicionada posição: {posicao_x} (distância: {float(valor)})")
            
            print(f"[DEBUG] Posições finais: {posicoes}")
            return posicoes

    def _breakdown_grades_total(self, total_ajustado):
        """
        Dado um comprimento AJUSTADO desejado (após fórmulas do Modo L), converte para
        listas de (comprimentos, espacos) usando a lógica universal de grades:
        - Subtrai 22 para obter a medida base, pois a rotina universal soma +22 internamente.
        - Aplica regras de 1/2/3 grades, múltiplos de 5 e distâncias 1..15.
        """
        try:
            if total_ajustado is None:
                return [0.0, 0.0, 0.0], [0.0, 0.0]
            base = float(total_ajustado) - 22.0
            if base <= 0:
                return [0.0, 0.0, 0.0], [0.0, 0.0]

            # DESATIVADO: Lógica universal: soma +22 internamente e decide num_grades, tamanho_grade, distancia
            # num, tamanho, dist = self._calcular_grades_universal(base)
            
            # USAR VALORES FIXOS TEMPORARIAMENTE PARA TESTE
            num, tamanho, dist = 1, base, 0  # 1 grade com tamanho = base, distância = 0

            # Expandir em listas
            comp_list, esp_list = self._expandir_grades_para_listas(num, tamanho, dist)
            return comp_list, esp_list
        except Exception:
            return [0.0, 0.0, 0.0], [0.0, 0.0]

    def _calcular_grades_universal(self, medida_total_base):
        """
        Replica a lógica de calcular_grades_especiais_logica_original:
        - Ajusta com +22
        - Até 122: 1 grade
        - 122..259: 2 grades (máx 122), distância 1..15, tenta múltiplos de 5
        - >259: 3 grades, idem critério
        Retorna (num_grades, tamanho_grade, distancia)
        """
        try:
            medida_total = float(medida_total_base)
            medida_total_ajustada = medida_total + 22.0

            if medida_total_ajustada <= 122:
                return 1, medida_total_ajustada, 0
            elif medida_total_ajustada <= 259:
                tamanho_ideal = min(122, medida_total_ajustada / 2)
                menor = int(tamanho_ideal / 5) * 5
                maior = menor + 5
                dist_menor = medida_total_ajustada - (2 * menor)
                dist_maior = medida_total_ajustada - (2 * maior)

                if maior <= 122 and 1 <= dist_maior <= 15:
                    tamanho = maior
                    dist = dist_maior
                elif 1 <= dist_menor <= 15:
                    tamanho = menor
                    dist = dist_menor
                else:
                    if dist_menor < 1:
                        dist = 1
                        tamanho = int((medida_total_ajustada - dist) / 2)
                        tamanho = round(tamanho / 5) * 5
                    elif dist_maior > 15:
                        dist = 15
                        tamanho = int((medida_total_ajustada - dist) / 2)
                        tamanho = round(tamanho / 5) * 5
                    else:
                        if abs(dist_menor - 15) < abs(dist_maior - 1):
                            tamanho = menor
                            dist = dist_menor
                        else:
                            tamanho = maior
                            dist = dist_maior

                soma_atual = (2 * tamanho) + dist
                if abs(soma_atual - medida_total_ajustada) > 0.1:
                    diferenca = medida_total_ajustada - soma_atual
                    dist = dist + diferenca
                    if dist < 1:
                        dist = 1
                    elif dist > 15:
                        dist = 15
                return 2, tamanho, dist
            else:
                tamanho_ideal = min(122, medida_total_ajustada / 3)
                menor = int(tamanho_ideal / 5) * 5
                maior = menor + 5
                dist_menor = (medida_total_ajustada - (3 * menor)) / 2
                dist_maior = (medida_total_ajustada - (3 * maior)) / 2

                if maior <= 122 and 1 <= dist_maior <= 15:
                    tamanho = maior
                    dist = dist_maior
                elif 1 <= dist_menor <= 15:
                    tamanho = menor
                    dist = dist_menor
                else:
                    if dist_menor < 1:
                        dist = 1
                        tamanho = int((medida_total_ajustada - (2 * dist)) / 3)
                        tamanho = round(tamanho / 5) * 5
                    elif dist_maior > 15:
                        dist = 15
                        tamanho = int((medida_total_ajustada - (2 * dist)) / 3)
                        tamanho = round(tamanho / 5) * 5
                    else:
                        if abs(dist_menor - 15) < abs(dist_maior - 1):
                            tamanho = menor
                            dist = dist_menor
                        else:
                            tamanho = maior
                            dist = dist_maior

                soma_atual = (3 * tamanho) + (2 * dist)
                if abs(soma_atual - medida_total_ajustada) > 0.1:
                    diferenca = medida_total_ajustada - soma_atual
                    dist = dist + (diferenca / 2)
                    if dist < 1:
                        dist = 1
                    elif dist > 15:
                        dist = 15
                return 3, tamanho, dist
        except Exception:
            return 0, 0, 0

    def _expandir_grades_para_listas(self, num, tamanho, dist):
        """Converte (num, tamanho, dist) em ([g1,g2,g3], [d1,d2])."""
        if num <= 0 or tamanho <= 0:
            return [0.0, 0.0, 0.0], [0.0, 0.0]
        if num == 1:
            return [float(tamanho), 0.0, 0.0], [0.0, 0.0]
        if num == 2:
            return [float(tamanho), float(tamanho), 0.0], [float(dist), 0.0]
        # num >= 3
        return [float(tamanho), float(tamanho), float(tamanho)], [float(dist), float(dist)]

    def calcular_posicoes_blocks_centrais_verticais(self, posicao_y_a, posicao_y_b):
        """
        Calcula as posições dos blocks centrais verticais com números inteiros.
        Divide a COTA TOTAL (do block A ao block B) em 3 partes iguais e unifica as frações na distância entre os 2 centrais.
        """
        # Calcular a COTA TOTAL (do block A ao block B)
        # Block A: posicao_y_a - 16 + 7 (16cm abaixo + 7cm do block)
        # Block B: posicao_y_b + 16 - 7 (16cm acima - 7cm do block)
        cota_total_superior = posicao_y_a - 16 + 7
        cota_total_inferior = posicao_y_b + 16 - 7
        
        # Calcular a cota total
        cota_total = cota_total_superior - cota_total_inferior
        
        # Dividir a COTA TOTAL em 3 partes iguais (divisão exata)
        terco_exato = cota_total / 3
        
        # Calcular posições dos terços como números inteiros
        # Primeiro terço: arredondar para baixo
        posicao_y_terco_1 = cota_total_inferior + math.floor(terco_exato)
        # Terceiro terço: arredondar para cima (para compensar)
        posicao_y_terco_2 = cota_total_inferior + math.ceil(2 * terco_exato)
        
        # Calcular as distâncias para verificar se estão corretas
        distancia_1 = posicao_y_terco_1 - cota_total_inferior  # Block A até primeiro central
        distancia_2 = posicao_y_terco_2 - posicao_y_terco_1  # Entre os dois centrais
        distancia_3 = cota_total_superior - posicao_y_terco_2  # Segundo central até Block B
        
        # Verificar se a soma das distâncias é igual à cota total
        soma_distancias = distancia_1 + distancia_2 + distancia_3
        
        # Se houver diferença, ajustar a distância entre os centrais
        if abs(soma_distancias - cota_total) > 0.01:  # Tolerância de 0.01cm
            # Ajustar a distância entre os centrais para compensar
            diferenca = cota_total - soma_distancias
            posicao_y_terco_2 += diferenca
        
        return posicao_y_terco_1, posicao_y_terco_2
    
    def _verificar_pilar_especial_ativo(self):
        """
        Verifica se o pilar especial está ativo.
        CORREÇÃO: Verificar tanto as globais quanto o checkbox pilar_rotacionado_var.
        """


        if robo_logger:
            robo_logger.subsection("VERIFICAÇÃO DE PILAR ESPECIAL ATIVO")
            robo_logger.info("🔄 Verificando se pilar especial está ativo...")
        
        try:
            # Verificar se o checkbox pilar rotacionado está ativo
            pilar_rotacionado_ativo = False
            if hasattr(self, 'pilar_rotacionado_var'):
                pilar_rotacionado_ativo = self.pilar_rotacionado_var.get()
                print(f"[CHECKBOX] Status do checkbox pilar_rotacionado_var: {pilar_rotacionado_ativo}")
                if robo_logger:
                    robo_logger.info(f"🔄 Status do checkbox pilar_rotacionado_var: {pilar_rotacionado_ativo}")

            # Verificar se o checkbox pilar especial ativo está ativo (para o último pilar L)
            pilar_especial_ativo = False
            if hasattr(self, 'pilar_especial_ativo_var'):
                pilar_especial_ativo = self.pilar_especial_ativo_var.get()
                print(f"[CHECKBOX] Status do checkbox pilar_especial_ativo_var: {pilar_especial_ativo}")
                if robo_logger:
                    robo_logger.info(f"🔄 Status do checkbox pilar_especial_ativo_var: {pilar_especial_ativo}")
            
            # Verificar se há globais definidas
            globais_definidas = False
            tipo_pilar = ''
            if hasattr(self, '_globais_pilar_especial') and self._globais_pilar_especial:
                globais_definidas = True
                tipo_pilar = self._globais_pilar_especial.get('tipo_pilar', '')
                print(f"[GLOBAIS] Globais encontradas: {len(self._globais_pilar_especial)} valores, tipo: '{tipo_pilar}'")
                if robo_logger:
                    robo_logger.info(f"🔄 Globais encontradas: {len(self._globais_pilar_especial)} valores, tipo: '{tipo_pilar}'")
                
            # Pilar especial está ativo se:
            # 1. (pilar_rotacionado_ativo AND globais_definidas) OU
            # 2. (pilar_especial_ativo AND globais_definidas AND tipo_pilar == 'L')
            checkbox_ativo = pilar_rotacionado_ativo or (pilar_especial_ativo and tipo_pilar == 'L')

            if checkbox_ativo and globais_definidas and tipo_pilar in ['L', 'T', 'U']:
                print(f"[OK] Pilar especial ATIVO - pilar_rotacionado: {pilar_rotacionado_ativo}, pilar_especial: {pilar_especial_ativo}, globais: {globais_definidas}, tipo: {tipo_pilar}")
                if robo_logger:
                    robo_logger.info(f"✅ Pilar especial ATIVO - pilar_rotacionado: {pilar_rotacionado_ativo}, pilar_especial: {pilar_especial_ativo}, globais: {globais_definidas}, tipo: {tipo_pilar}")
                return True
            else:
                print(f"[INFO] Pilar especial INATIVO - pilar_rotacionado: {pilar_rotacionado_ativo}, pilar_especial: {pilar_especial_ativo}, globais: {globais_definidas}, tipo: '{tipo_pilar}'")
                if robo_logger:
                    robo_logger.info(f"Pilar especial INATIVO - pilar_rotacionado: {pilar_rotacionado_ativo}, pilar_especial: {pilar_especial_ativo}, globais: {globais_definidas}, tipo: '{tipo_pilar}'")
                return False
            
        except Exception as e:
            print(f"[ERRO] Erro ao verificar pilar especial: {str(e)}")
            if robo_logger:
                robo_logger.error(f"Erro ao verificar pilar especial: {str(e)}")
                robo_logger.error(f"Traceback: {traceback.format_exc()}")
            import traceback
            traceback.print_exc()
            return False

# Código para executar a aplicação

if __name__ == "__main__":
    import sys
    if '--config' in sys.argv:
        root = tk.Tk()
        root.withdraw()  # Oculta a janela principal
        app = GeradorPilar(root)
        app.criar_janela_configuracoes()
        root.mainloop()
    elif '--no-gui' in sys.argv:
        # Modo sem interface gráfica para uso programático
        print("Modo sem interface gráfica ativado")
    else:
        app = AplicacaoUnificada()
        app.iniciar()