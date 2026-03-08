
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

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import json
import math
import win32com.client
import pythoncom
import time
try:
    from .funcoes_auxiliares import calcular_aberturas_em_pares, processar_lado_a, processar_lado_b, classificar_linhas_por_lado
except ImportError:
    from funcoes_auxiliares import calcular_aberturas_em_pares, processar_lado_a, processar_lado_b, classificar_linhas_por_lado
import shutil  # Importar o módulo shutil para copiar arquivos
from openpyxl import load_workbook #import para criar excel
import win32gui  # Importar o módulo win32gui para manipular janelas do AutoCAD
import ctypes  # Para verificar o estado do sistema
try:
    from .funcoes_auxiliares_5 import GradeParafusosMixin
except ImportError:
    from funcoes_auxiliares_5 import GradeParafusosMixin

# Garantir prints no terminal em tempo real ao executar este hub
os.environ.setdefault("PYTHONUNBUFFERED", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True, write_through=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(line_buffering=True, write_through=True)
except Exception:
    pass

print("[HUB] Iniciando hub central (aa_corrigido copy 10.py)")

def inicializar_autocad():
    """
    Inicializa a conexão com o AutoCAD de forma robusta, tratando possíveis erros.
    
    Returns:
        tuple: (acad, doc) onde acad é a aplicação AutoCAD e doc é o documento ativo
               ou (None, None) em caso de erro
    """
    try:
        # Inicializar COM em nova thread
        pythoncom.CoInitialize()
        
        # Tentar obter instância existente do AutoCAD
        try:
            acad = win32com.client.GetActiveObject("AutoCAD.Application")
        except:
            # Se não existir, criar nova instância
            try:
                acad = win32com.client.Dispatch("AutoCAD.Application")
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível conectar ao AutoCAD: {str(e)}\nVerifique se o AutoCAD está instalado e aberto.")
                return None, None
        
        # Garantir que o AutoCAD está visível
        acad.Visible = True
        
        # Obter documento ativo
        try:
            doc = acad.ActiveDocument
        except:
            messagebox.showerror("Erro", "Nenhum documento ativo no AutoCAD.\nAbra um arquivo no AutoCAD primeiro.")
            return None, None
            
        return acad, doc
        
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao inicializar AutoCAD: {str(e)}")
        return None, None
    
def verificar_prontidao_autocad(acad, doc, max_tentativas=5, tempo_espera=0.5):
    """
    Verifica se o AutoCAD está pronto para receber comandos
    """
    for _ in range(max_tentativas):
        try:
            if not doc.GetVariable("BUSY"):
                return True
        except:
            pass
        time.sleep(tempo_espera)
    return False

# Exportação explícita de funções e variáveis utilizadas por outros módulos
__all__ = [
    "EXCEL_MAPPING",
    "analisar_coordenadas_retangulo",
    "inicializar_autocad",
    "verificar_prontidao_autocad"
]

# Importar o mapeamento Excel do arquivo dedicado
try:
    from excel_mapping import EXCEL_MAPPING
    print("Mapeamento Excel importado com sucesso do arquivo excel_mapping.py")
except ImportError:
    print("ERRO: Não foi possível importar o mapeamento Excel.")
    # Definir um mapeamento mínimo para fallback
    EXCEL_MAPPING = {
        "nome": 4,
        "comprimento": 6,
        "largura": 7,
        "pavimento": 3,
    }

# Remover o dicionário EXCEL_MAPPING original para evitar duplicação

# Função para formatar valores numéricos de acordo com as regras definidas
def formatar_valor_numerico(valor, casas_decimais=1, campo_nivel=False):
    """
    Formata um valor numérico de acordo com as regras definidas,
    arredondando para o valor mais próximo.
    
    Args:
        valor: O valor numérico a ser formatado
        casas_decimais: Número de casas decimais (padrão: 1)
        campo_nivel: Se True, permite até 2 casas decimais (para campos de nível)
    
    Returns:
        String formatada com o valor numérico arredondado
    """
    if valor is None:
        return ""
    
    try:
        # Converter para float de forma mais eficiente
        if isinstance(valor, (int, float)):
            valor_float = float(valor)
        else:
            valor_float = float(str(valor).replace(',', '.'))
        
        # Ajustar casas decimais para campo de nível
        casas_decimais = 2 if campo_nivel else casas_decimais
        
        # Arredondar e formatar em uma única operação
        valor_arredondado = round(valor_float, casas_decimais)
        
        # Verificar se é um número inteiro
        if valor_arredondado.is_integer():
            return str(int(valor_arredondado))
            
        # Formatar com número específico de casas decimais
        return f"{valor_arredondado:.{casas_decimais}f}"
        
    except (ValueError, TypeError):
        return str(valor) if valor is not None else ""

# Dicionário de mapeamento entre campos do programa e linhas do Excel
EXCEL_MAPPING = {
    # Dados Gerais
    "nome": 4,
    "comprimento": 6,
    "largura": 7,
    "pavimento": 3,
    "pavimento_anterior": 2,
    "nivel_saida": 8,
    "nivel_chegada": 9,
    "nivel_diferencial": 10,
    "altura": 12,

    # Parafusos
    "par_1_2": 173,
    "par_2_3": 174,
    "par_3_4": 175,
    "par_4_5": 176,
    "par_5_6": 177,
    "par_6_7": 178,
    "par_7_8": 179,
    "par_8_9": 180,

    # Grades
    "grade_1": 181,
    "distancia_1": 182,
    "grade_2": 183,
    "distancia_2": 184,
    "grade_3": 185,

    # Painel A
    "laje_A": 13,
    "posicao_laje_A": 14,
    "larg1_A": 15,
    "larg2_A": 16,
    "larg3_A": 17,
    "h1_A": 18,
    "h2_A": 19,
    "h3_A": 20,
    "h4_A": 21,
    "h5_A": 22,

    # Aberturas A Esquerda
    "dist_esq_1_A": 25,
    "larg_esq_1_A": 27,
    "prof_esq_1_A": 26,
    "pos_esq_1_A": 28,
    "dist_esq_2_A": 29,
    "larg_esq_2_A": 31,
    "prof_esq_2_A": 30,
    "pos_esq_2_A": 32,

    # Aberturas A Direita
    "dist_dir_1_A": 33,
    "larg_dir_1_A": 35,
    "prof_dir_1_A": 34,
    "pos_dir_1_A": 36,
    "dist_dir_2_A": 37,
    "larg_dir_2_A": 39,
    "prof_dir_2_A": 38,
    "pos_dir_2_A": 40,

    # Painel B
    "laje_B": 55,
    "posicao_laje_B": 56,
    "larg1_B": 57,
    "larg2_B": 58,
    "larg3_B": 59,
    "h1_B": 60,
    "h2_B": 61,
    "h3_B": 62,
    "h4_B": 63,
    "h5_B": 64,

    # Aberturas B Esquerda
    "dist_esq_1_B": 67,
    "larg_esq_1_B": 69,
    "prof_esq_1_B": 68,
    "pos_esq_1_B": 70,
    "dist_esq_2_B": 71,
    "larg_esq_2_B": 73,
    "prof_esq_2_B": 72,
    "pos_esq_2_B": 74,

    # Aberturas B Direita
    "dist_dir_1_B": 75,
    "larg_dir_1_B": 77,
    "prof_dir_1_B": 76,
    "pos_dir_1_B": 78,
    "dist_dir_2_B": 79,
    "larg_dir_2_B": 81,
    "prof_dir_2_B": 80,
    "pos_dir_2_B": 82,

    # Painel C
    "laje_C": 97,
    "posicao_laje_C": 98,
    "larg1_C": 99,
    "larg2_C": 100,
    "h1_C": 101,
    "h2_C": 102,
    "h3_C": 103,
    "h4_C": 104,

    # Painel D
    "laje_D": 131,
    "posicao_laje_D": 132,
    "larg1_D": 133,
    "larg2_D": 134,
    "h1_D": 135,
    "h2_D": 136,
    "h3_D": 137,
    "h4_D": 138,

    # Detalhes das Grades
    "detalhe_grade1_1": 192,
    "detalhe_grade1_2": 193,
    "detalhe_grade1_3": 194,
    "detalhe_grade1_4": 195,
    "detalhe_grade1_5": 196,
    "detalhe_grade2_1": 197,
    "detalhe_grade2_2": 198,
    "detalhe_grade2_3": 199,
    "detalhe_grade2_4": 200,
    "detalhe_grade2_5": 201,
    "detalhe_grade3_1": 202,
    "detalhe_grade3_2": 203,
    "detalhe_grade3_3": 204,
    "detalhe_grade3_4": 205,
    "detalhe_grade3_5": 206
}

# Função para remover aberturas duplicadas baseado na distância
def remover_aberturas_duplicadas(aberturas, tolerancia=1.0):
    """Remove aberturas duplicadas (com distância e largura muito próximas) e aberturas com largura 0"""
    if not aberturas:
        return []
        
    # Primeiro, remover aberturas com largura 0
    aberturas_validas = []
    for abertura in aberturas:
        distancia, largura = abertura
        if largura > 0:
            aberturas_validas.append(abertura)
        else:
            print(f"  Removendo abertura com largura 0: Distância={distancia:.2f}, Largura={largura:.2f}")
    
    if not aberturas_validas:
        return []
    
    # Ordenar aberturas por distância
    aberturas_ordenadas = sorted(aberturas_validas, key=lambda x: x[0])
    
    # Lista para armazenar aberturas únicas
    aberturas_unicas = []
    
    # Adicionar a primeira abertura
    aberturas_unicas.append(aberturas_ordenadas[0])
    
    # Verificar as demais aberturas
    for abertura in aberturas_ordenadas[1:]:
        distancia, largura = abertura
        
        # Verificar se a abertura é similar a alguma já adicionada
        duplicada = False
        for abertura_unica in aberturas_unicas:
            dist_unica, larg_unica = abertura_unica
            
            # Se a distância e a largura são muito próximas, considerar duplicada
            if (abs(distancia - dist_unica) < tolerancia and 
                abs(largura - larg_unica) < tolerancia):
                print(f"  Removendo abertura duplicada: Distância={distancia:.2f}, Largura={largura:.2f} | Muito próxima de: Distância={dist_unica:.2f}, Largura={larg_unica:.2f}")
                duplicada = True
                break
        
        # Se não for duplicada, adicionar à lista de únicas
        if not duplicada:
            aberturas_unicas.append(abertura)
    
    return aberturas_unicas

def remover_aberturas_duplicadas_complexas(aberturas, tolerancia=1.0):
    """
    Remove aberturas duplicadas de objetos complexos, comparando tipo, coordenadas, largura e distância.
    
    Args:
        aberturas: Lista de dicionários com informações de aberturas
        tolerancia: Tolerância para considerar aberturas como duplicadas (em unidades de coordenadas)
        
    Returns:
        Lista de aberturas sem duplicações
    """
    if not aberturas:
        return []
    
    print("\n>>> Iniciando remoção de aberturas duplicadas complexas...")
    print(f">>> Total inicial: {len(aberturas)} aberturas")
    
    # Primeiro, agrupar aberturas por tipo
    grupos_por_tipo = {}
    for abertura in aberturas:
        tipo = abertura.get("tipo", "")
        if tipo not in grupos_por_tipo:
            grupos_por_tipo[tipo] = []
        grupos_por_tipo[tipo].append(abertura)
    
    # Para cada grupo, ordenar por distância
    for tipo, grupo in grupos_por_tipo.items():
        grupos_por_tipo[tipo] = sorted(grupo, key=lambda a: a.get("distancia", 0))
    
    # Função para verificar se duas aberturas são similares (duplicatas)
    def sao_similares(a1, a2):
        # Se são de tipos diferentes, não são similares
        if a1.get("tipo", "") != a2.get("tipo", ""):
            return False
        
        # Verificar distâncias
        dist1 = a1.get("distancia", 0)
        dist2 = a2.get("distancia", 0)
        dist_diff = abs(dist1 - dist2)
        
        # Verificar larguras
        larg1 = a1.get("largura", 0)
        larg2 = a2.get("largura", 0)
        larg_diff = abs(larg1 - larg2)
        
        # Verificar coordenadas (centralizado no ponto médio da abertura)
        coord1 = a1.get("coord", (0, 0))
        coord2 = a2.get("coord", (0, 0))
        
        x1, y1 = coord1
        x2, y2 = coord2
        
        # Se as coordenadas estão muito próximas, são similares
        dist_coord = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        
        # Para depuração, imprimir detalhes quando as coordenadas são próximas
        if dist_coord <= 100:  # Se estão a até 100 unidades uma da outra
            debug_msg = f">>> COMPARANDO aberturas do tipo {a1.get('tipo', '')}\n"
            debug_msg += f"    A1: dist={dist1:.2f}, larg={larg1:.2f}, coord=({x1:.2f}, {y1:.2f})\n"
            debug_msg += f"    A2: dist={dist2:.2f}, larg={larg2:.2f}, coord=({x2:.2f}, {y2:.2f})\n"
            debug_msg += f"    Diferenças: dist={dist_diff:.2f}, larg={larg_diff:.2f}, coord={dist_coord:.2f}"
            print(debug_msg)
        
        # Critérios para considerar similares:
        # 1. Distância muito próxima (dentro da tolerância)
        # 2. Largura muito próxima (dentro da tolerância)
        # 3. Coordenadas próximas (dentro de 20x a tolerância)
        if dist_diff <= tolerancia and larg_diff <= tolerancia and dist_coord <= 20 * tolerancia:
            print(f">>> DUPLICATA DETECTADA para tipo {a1.get('tipo', '')}")
            return True
        
        return False
    
    # Eliminar duplicatas dentro de cada grupo
    resultados = []
    for tipo, grupo in grupos_por_tipo.items():
        if not grupo:
            continue
        
        aberturas_unicas = [grupo[0]]  # Começar com a primeira
        
        for abertura in grupo[1:]:
            duplicada = False
            
            for existente in aberturas_unicas:
                if sao_similares(abertura, existente):
                    print(f">>> Removendo abertura duplicada: {abertura.get('tipo', '')}")
                    print(f"    Distância={abertura.get('distancia', 0):.2f}, Largura={abertura.get('largura', 0):.2f}")
                    print(f"    Coordenadas={abertura.get('coord', (0, 0))}")
                    print(f"    Muito próxima de: Distância={existente.get('distancia', 0):.2f}, Largura={existente.get('largura', 0):.2f}")
                    print(f"    Coordenadas={existente.get('coord', (0, 0))}")
                    duplicada = True
                    break
            
            if not duplicada:
                aberturas_unicas.append(abertura)
        
        # Adicionar as aberturas únicas ao resultado
        resultados.extend(aberturas_unicas)
    
    print(f">>> Após remoção de duplicatas: {len(resultados)} aberturas restantes")
    
    return resultados

def numero_para_coluna_excel(n):
    resultado = ""
    while n > 0:
        n -= 1
        resultado = chr(65 + (n % 26)) + resultado
        n //= 26
    return resultado

# Função auxiliar para converter coluna Excel em número
def coluna_excel_para_numero(coluna):
    resultado = 0
    for c in coluna.upper():
        resultado = resultado * 26 + (ord(c) - ord('A') + 1)
    return resultado

def get_autocad_selection(prompt_message):
    """
    Obtém a seleção do usuário no AutoCAD.
    
    Args:
        prompt_message: Mensagem a ser exibida para o usuário
    
    Returns:
        A seleção do usuário ou None em caso de erro
    """
    try:
        # Inicializar AutoCAD
        acad, doc = inicializar_autocad()
        if not acad or not doc:
            return None
            
        # Verificar se o AutoCAD está pronto
        if not verificar_prontidao_autocad(acad, doc):
            messagebox.showerror("Erro", "AutoCAD não está respondendo. Tente novamente.")
            return None
            
        # Tornar o AutoCAD visível e ativo
        acad.Visible = True
        acad.ActiveDocument.Activate()
        
        # Solicitar seleção do usuário
        selection = None
        try:
            selection = doc.SelectionSets.Add("TempSel")
            selection.SelectOnScreen()
            return selection
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao obter seleção: {str(e)}")
            return None
        finally:
            # Limpar a seleção temporária
            try:
                if selection:
                    selection.Delete()
            except:
                pass
            
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao interagir com AutoCAD: {str(e)}")
        return None

def get_rectangle_from_selection(selection):
    """
    Extrai um retângulo da seleção do AutoCAD.
    
    Args:
        selection: Objeto de seleção do AutoCAD
        
    Returns:
        Coordenadas do retângulo ou None em caso de erro
    """
    try:
        # Inicializar AutoCAD
        acad, doc = inicializar_autocad()
        if not acad or not doc:
            return None
            
        # Verificar se há seleção
        if not selection or selection.Count == 0:
            messagebox.showerror("Erro", "Nenhum objeto selecionado")
            return None
        
        # Encontrar o retângulo na seleção
        for i in range(selection.Count):
            entity = selection.Item(i)
            if entity.ObjectName == "AcDbPolyline":
                if entity.Closed and entity.Coordinates.Count == 8:  # Retângulo tem 4 vértices (8 coordenadas)
                    coords = entity.Coordinates
                    return {
                        "x_min": min(coords[0::2]),
                        "x_max": max(coords[0::2]),
                        "y_min": min(coords[1::2]),
                        "y_max": max(coords[1::2])
                    }
                    
        messagebox.showerror("Erro", "Nenhum retângulo encontrado na seleção")
        return None
        
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao processar retângulo: {str(e)}")
        return None

def get_lines_from_selection(selection):
    """
    Função aprimorada para extrair linhas de uma seleção do AutoCAD.
    Adicionado melhor suporte para detecção de tipos e processamento de erros.
    """
    try:
        print("\n>>> Identificando linhas entre os objetos selecionados...")
        
        if selection is None:
            print(">>> ERRO: Seleção inválida ou nula!")
            return []
            
        # Verificar se temos objetos na seleção
        try:
            count = selection.Count
            print(f">>> Total de objetos na seleção: {count}")
            if count == 0:
                print(">>> Nenhum objeto na seleção!")
                return []
        except Exception as e:
            print(f">>> ERRO ao acessar a contagem da seleção: {str(e)}")
            return []
        
        # Lista para armazenar linhas encontradas
        lines = []
        line_count = 0
        
        # Processar objetos na seleção
        for i in range(selection.Count):
            try:
                # Obter objeto atual
                entity = selection.Item(i)
                print(f">>> Objeto {i+1} - ", end="")
                
                # Determinar o tipo do objeto
                object_type = "Desconhecido"
                try:
                    if hasattr(entity, 'ObjectName'):
                        object_type = entity.ObjectName
                    elif hasattr(entity, 'EntityType'):
                        object_type = f"EntityType_{entity.EntityType}"
                    elif hasattr(entity, 'EntityTypeName'):
                        object_type = entity.EntityTypeName
                except:
                    pass
                    
                print(f"Tipo: {object_type}")
                
                # Verificar se é uma linha por tipo ou características
                is_line = False
                
                # Verificação por nome/tipo
                if "Line" in object_type or object_type == "AcDbLine":
                    is_line = True
                # Verificação para polilinhas (podem ser linhas retas)
                elif object_type == "AcDbPolyline" and hasattr(entity, 'Coordinates'):
                    coords = entity.Coordinates
                    if len(coords) == 4:  # Início e fim apenas (linha reta)
                        is_line = True
                # Verificação alternativa por propriedades
                elif hasattr(entity, 'StartPoint') and hasattr(entity, 'EndPoint'):
                    is_line = True
                
                # Se for uma linha, processar suas propriedades
                if is_line:
                    line_data = {
                        "index": i,  # Índice original na seleção
                        "type": object_type,
                        "entity": entity  # Referência para o objeto original
                    }
                    
                    # Extrair coordenadas com tratamento de erro para cada método possível
                    try:
                        if hasattr(entity, 'StartPoint') and hasattr(entity, 'EndPoint'):
                            start_point = entity.StartPoint
                            end_point = entity.EndPoint
                            line_data["start_point"] = (start_point[0], start_point[1], start_point[2] if len(start_point) > 2 else 0)
                            line_data["end_point"] = (end_point[0], end_point[1], end_point[2] if len(end_point) > 2 else 0)
                            print(f">>> Linha adicionada (objeto {i+1})")
                            lines.append(line_data)
                            line_count += 1
                        elif hasattr(entity, 'Coordinates'):
                            coords = entity.Coordinates
                            if len(coords) >= 4:
                                # Para polilinhas, extrair primeiro e último ponto
                                if len(coords) == 4:  # Linha simples
                                    line_data["start_point"] = (coords[0], coords[1], 0)
                                    line_data["end_point"] = (coords[2], coords[3], 0)
                                else:  # Polilinha complexa, tratar como múltiplas linhas
                                    # Considerar cada segmento como uma linha separada
                                    for j in range(0, len(coords) - 2, 2):
                                        segment_data = {
                                            "index": i,  # Índice original na seleção
                                            "segment": j // 2,  # Número do segmento
                                            "type": object_type,
                                            "entity": entity,  # Referência para o objeto original
                                            "start_point": (coords[j], coords[j+1], 0),
                                            "end_point": (coords[j+2], coords[j+3], 0)
                                        }
                                        lines.append(segment_data)
                                        line_count += 1
                                    
                                    print(f">>> Polilinha adicionada com {(len(coords) // 2) - 1} segmentos (objeto {i+1})")
                                    continue  # Já adicionamos todos os segmentos
                                
                                print(f">>> Linha adicionada via coordenadas (objeto {i+1})")
                                lines.append(line_data)
                                line_count += 1
                            else:
                                print(f">>> Coordenadas insuficientes para criar uma linha (objeto {i+1})")
                        else:
                            print(f">>> Objeto {i+1} não tem pontos ou coordenadas acessíveis")
                    except Exception as e:
                        print(f">>> ERRO ao processar linha {i+1}: {str(e)}")
                else:
                    print(f">>> Objeto {i+1} não é uma linha")
            except Exception as e:
                print(f">>> ERRO ao processar objeto {i+1}: {str(e)}")
        
        # Resumo final
        print(f">>> Total de linhas identificadas: {line_count}")
        
        return lines
    except Exception as e:
        print(f">>> ERRO GERAL ao processar linhas na seleção: {str(e)}")
        return []

# Função auxiliar para extrair pontos de uma linha ou polyline
def extrair_pontos(line):
    """Extrai os pontos de uma linha ou polyline do AutoCAD"""
    line_points = []
    try:
        # Verificar o tipo do objeto
        object_type = line.ObjectName
        
        # Obter pontos dependendo do tipo de objeto
        if object_type == "AcDbLine":
            start_point = (line.StartPoint[0], line.StartPoint[1])
            end_point = (line.EndPoint[0], line.EndPoint[1])
            line_points = [start_point, end_point]
        elif object_type == "AcDbPolyline":
            # Lidar com polylines - diferentes formas de acessar as coordenadas
            try:
                # Tentar acessar NumberOfVertices (método mais comum)
                num_vertices = line.NumberOfVertices
                for j in range(num_vertices):
                    vertex = line.Coordinate(j)
                    line_points.append((vertex[0], vertex[1]))
            except Exception:
                try:
                    # Segunda tentativa: acessar coordenadas diretamente
                    coords = line.Coordinates
                    if isinstance(coords, tuple) and len(coords) >= 4:  # Pelo menos dois pontos (x,y)
                        for j in range(0, len(coords), 2):
                            if j+1 < len(coords):
                                line_points.append((coords[j], coords[j+1]))
                except Exception:
                    # Terceira tentativa: obter apenas os pontos inicial e final
                    try:
                        if hasattr(line, 'StartPoint') and hasattr(line, 'EndPoint'):
                            start_point = (line.StartPoint[0], line.StartPoint[1])
                            end_point = (line.EndPoint[0], line.EndPoint[1])
                            line_points = [start_point, end_point]
                    except Exception:
                        pass
    except Exception:
        pass
    
    return line_points

def get_line_intersections(rectangle_entity, lines, doc):
    """Calcula as interseções entre um retângulo e um conjunto de linhas"""
    try:
        print("\n>>> Calculando interseções...")
        
        # Inicializar listas vazias para armazenar as linhas classificadas
        lado_a_linhas = []  # Todas as linhas do lado A
        lado_b_linhas = []  # Todas as linhas do lado B
        
        # Conjunto para rastrear linhas já processadas
        linhas_processadas = set()
        
        # Obter as coordenadas do retângulo
        rectangle_coords = extrair_pontos(rectangle_entity)
        if not rectangle_coords or len(rectangle_coords) < 4:
            print(">>> Retângulo inválido! Coordenadas insuficientes.")
            return {"lado_a_esq": [], "lado_a_dir": [], "lado_b_esq": [], "lado_b_dir": [], "is_vertical": True}
        
        # Encontrar os limites do retângulo
        x_coords = [p[0] for p in rectangle_coords]
        y_coords = [p[1] for p in rectangle_coords]
        min_x = min(x_coords)
        max_x = max(x_coords)
        min_y = min(y_coords)
        max_y = max(y_coords)
        
        # Determinar se o retângulo é vertical ou horizontal
        width = max_x - min_x
        height = max_y - min_y
        is_vertical = height > width
        
        # Calcular o ponto médio do retângulo
        midpoint_x = (min_x + max_x) / 2
        midpoint_y = (min_y + max_y) / 2
        
        print("\n>>> ANÁLISE DA ORIENTAÇÃO DO RETÂNGULO:")
        print(f">>> Largura: {width:.2f}")
        print(f">>> Altura: {height:.2f}")
        print(f">>> Orientação: {'Vertical' if is_vertical else 'Horizontal'}")
        print(f">>> Ponto central do retângulo: ({midpoint_x:.2f}, {midpoint_y:.2f})")
        
        if is_vertical:
            print(">>> Lado A está na esquerda")
            print(">>> Lado B está na direita")
        else:
            print(">>> Lado A está em baixo")
            print(">>> Lado B está em cima")
        
        print("\n>>> LIMITES DO RETÂNGULO:")
        print(f">>> X mínimo: {min_x}")
        print(f">>> X máximo: {max_x}")
        print(f">>> Y mínimo: {min_y}")
        print(f">>> Y máximo: {max_y}")
        
        # Tolerância para detecção de linhas próximas às bordas
        tolerance = 0.1
        
        print("\n>>> ANÁLISE DAS LINHAS:")
        
        # ETAPA 1: Classificar as linhas em lado A ou lado B (sem duplicação)
        for i, line in enumerate(lines):
            # Verificar se a linha já foi processada
            if i in linhas_processadas:
                print(f"\n>>> Pulando linha {i+1} - já foi processada anteriormente.")
                continue
                
            print(f"\n>>> Analisando linha {i+1}...")
            
            try:
                # Verificar o tipo do objeto
                object_type = line.ObjectName
                print(f">>> Tipo: {object_type}")
                
                # Ignorar objetos do tipo DimLinear ou AcDbDimension
                if "Dim" in object_type or object_type == "AcDbDimension":
                    print(f">>> Objeto {i+1} é uma dimensão (tipo: {object_type}), ignorando.")
                    continue
                
                # Verificações adicionais para tipos específicos de objetos do AutoCAD
                # que possam representar pontos ou marcas de centro
                if object_type in ["AcDbPoint", "AcDbBlockReference", "AcDbCircle", "AcDbMInsertBlock"]:
                    # Se o objeto é um ponto, um bloco (como cruzeta de centro), um círculo pequeno
                    # ou uma inserção de bloco (símbolo), verificar se está no centro
                    try:
                        if hasattr(line, 'InsertionPoint'):
                            point = line.InsertionPoint
                            point_coords = (point[0], point[1])
                            dist_to_center = ((point_coords[0] - midpoint_x) ** 2 + (point_coords[1] - midpoint_y) ** 2) ** 0.5
                            center_threshold = min(width, height) * 0.25  # 25% da menor dimensão
                            if dist_to_center < center_threshold:
                                print(f">>> Objeto {i+1} é uma marca ou um ponto próximo ao centro do retângulo, ignorando.")
                                continue
                        elif hasattr(line, 'Center'):
                            center = line.Center
                            center_coords = (center[0], center[1])
                            dist_to_center = ((center_coords[0] - midpoint_x) ** 2 + (center_coords[1] - midpoint_y) ** 2) ** 0.5
                            center_threshold = min(width, height) * 0.25  # 25% da menor dimensão
                            # Verificar também o raio para círculos
                            radius = line.Radius if hasattr(line, 'Radius') else 0
                            if dist_to_center < center_threshold or radius < 5:  # Círculos pequenos ou próximos ao centro
                                print(f">>> Objeto {i+1} é um círculo pequeno ou próximo ao centro, ignorando.")
                                continue
                    except Exception as e:
                        print(f">>> Erro ao verificar posição do objeto {i+1}: {str(e)}")
                
                # Se não for um tipo específico que podemos verificar diretamente, extrair pontos
                line_points = []
                
                # Obter pontos dependendo do tipo de objeto
                if object_type == "AcDbLine":
                    start_point = (line.StartPoint[0], line.StartPoint[1])
                    end_point = (line.EndPoint[0], line.EndPoint[1])
                    line_points = [start_point, end_point]
                    print(f">>> Pontos da linha: {start_point} -> {end_point}")
                    
                    # Verificar se é uma linha de marcação central (linha muito curta ou próxima ao centro)
                    dist = ((end_point[0] - start_point[0])**2 + (end_point[1] - start_point[1])**2)**0.5
                    mid_x = (start_point[0] + end_point[0]) / 2
                    mid_y = (start_point[1] + end_point[1]) / 2
                    dist_to_center = ((mid_x - midpoint_x)**2 + (mid_y - midpoint_y)**2)**0.5
                    if dist < 2.0 and dist_to_center < min(width, height) * 0.25:
                        print(f">>> Linha {i+1} é uma marca central (linha curta próxima ao centro), ignorando.")
                        continue
                    
                elif object_type == "AcDbPolyline":
                    # Lidar com polylines - diferentes formas de acessar as coordenadas
                    try:
                        # Tentar acessar NumberOfVertices (método mais comum)
                        num_vertices = line.NumberOfVertices
                        for j in range(num_vertices):
                            vertex = line.Coordinate(j)
                            line_points.append((vertex[0], vertex[1]))
                        print(f">>> Pontos da polyline: {line_points}")
                    except Exception as e1:
                        print(f">>> Erro ao acessar vértices com NumberOfVertices: {str(e1)}")
                        try:
                            # Segunda tentativa: acessar coordenadas diretamente
                            coords = line.Coordinates
                            if isinstance(coords, tuple) and len(coords) >= 4:  # Pelo menos dois pontos (x,y)
                                for j in range(0, len(coords), 2):
                                    if j+1 < len(coords):
                                        line_points.append((coords[j], coords[j+1]))
                                print(f">>> Pontos da polyline por Coordinates: {line_points}")
                            else:
                                print(f">>> Formato de coordenadas inválido: {coords}")
                        except Exception as e2:
                            print(f">>> Erro ao acessar coordenadas: {str(e2)}")
                            # Terceira tentativa: obter apenas os pontos inicial e final
                            try:
                                if hasattr(line, 'StartPoint') and hasattr(line, 'EndPoint'):
                                    start_point = (line.StartPoint[0], line.StartPoint[1])
                                    end_point = (line.EndPoint[0], line.EndPoint[1])
                                    line_points = [start_point, end_point]
                                    print(f">>> Pontos da polyline por StartPoint/EndPoint: {start_point} -> {end_point}")
                                else:
                                    print(">>> Não foi possível obter coordenadas da polyline")
                            except Exception as e3:
                                print(f">>> Erro ao obter pontos inicial e final: {str(e3)}")
                    
                    # Verificar se é uma polyline de marcação central
                    if len(line_points) >= 2:
                        # Verificar se é fechada (primeiro e último pontos iguais)
                        is_closed = line_points[0] == line_points[-1]
                        
                        # Calcular tamanho máximo
                        max_dim = 0
                        for p1 in line_points:
                            for p2 in line_points:
                                dist = ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)**0.5
                                max_dim = max(max_dim, dist)
                        
                        # Calcular centro aproximado
                        avg_x = sum(p[0] for p in line_points) / len(line_points)
                        avg_y = sum(p[1] for p in line_points) / len(line_points)
                        dist_to_center = ((avg_x - midpoint_x)**2 + (avg_y - midpoint_y)**2)**0.5
                        
                        # Se a polyline é pequena, fechada e próxima ao centro, provavelmente é uma marca central
                        if max_dim < min(width, height) * 0.25 and dist_to_center < min(width, height) * 0.25:
                            print(f">>> Polyline {i+1} parece ser uma marca central (pequena e próxima ao centro), ignorando.")
                            continue
                elif object_type == "AcDbPoint" or object_type == "AcDbBlockReference":
                    # Objeto é um ponto ou bloco (como cruzeta de centro), ignorar
                    print(f">>> Objeto {i+1} é um ponto ou bloco, ignorando.")
                    continue
                else:
                    print(f">>> Tipo de objeto não suportado: {object_type}")
                    continue
                
                # Se não conseguirmos extrair pontos, pular esta linha
                if not line_points:
                    print(">>> Não foi possível extrair pontos desta linha, pulando...")
                    continue
                
                # Verificar se a linha tem pontos idênticos (início e fim iguais)
                if len(line_points) >= 2 and line_points[0] == line_points[-1]:
                    print(f">>> Linha {i+1} tem pontos de início e fim idênticos, ignorando: {line_points[0]}")
                    continue
                
                # Verificar se a linha é muito curta (ponto)
                if len(line_points) >= 2:
                    p1 = line_points[0]
                    p2 = line_points[-1]
                    dist = ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2) ** 0.5
                    min_valid_length = 3.0  # Uma linha menor que 3 unidades é provavelmente um ponto ou marca
                    if dist < min_valid_length:
                        print(f">>> Linha {i+1} é muito curta (comprimento = {dist:.2f}), ignorando.")
                        continue
                
                # Verificar se a linha é um ponto central ou está dentro do retângulo
                is_point_inside = True
                for point in line_points:
                    # Um ponto está dentro se suas coordenadas estão dentro dos limites do retângulo
                    # E com uma margem segura das bordas (não muito perto das bordas)
                    margin = min(width, height) * 0.25  # 25% da menor dimensão como margem
                    if not (min_x + margin <= point[0] <= max_x - margin and
                            min_y + margin <= point[1] <= max_y - margin):
                        is_point_inside = False
                        break
                
                # Verificar se o ponto está próximo ao centro do retângulo
                is_near_center = False
                for point in line_points:
                    dist_to_center = ((point[0] - midpoint_x) ** 2 + (point[1] - midpoint_y) ** 2) ** 0.5
                    center_threshold = min(width, height) * 0.25  # 25% da menor dimensão como threshold
                    if dist_to_center < center_threshold:
                        is_near_center = True
                        print(f">>> Ponto {point} está próximo ao centro do retângulo ({midpoint_x:.2f}, {midpoint_y:.2f}), distância = {dist_to_center:.2f}")
                        break
                
                # Se todos os pontos estão dentro do retângulo e longe das bordas,
                # ou se a linha está perto do centro, é provavelmente um ponto central - ignorar
                if (is_point_inside and len(line_points) <= 2) or is_near_center:
                    print(f">>> Linha {i+1} parece ser um ponto central ou está dentro do retângulo, ignorando.")
                    continue
                
                # Verificar interseções com os lados do retângulo
                intersects_a = False
                intersects_b = False
                
                # Extrair os pontos para facilitar o código
                p1 = line_points[0]
                p2 = line_points[-1]
                
                # Verificar interseção ou toque com o lado A
                if is_vertical:
                    # Para um retângulo vertical, lado A é o lado esquerdo (x = min_x)
                    # Verificar se a linha cruza ou toca x = min_x
                    if ((p1[0] <= min_x <= p2[0]) or (p2[0] <= min_x <= p1[0])) or \
                       (abs(p1[0] - min_x) < tolerance and abs(p2[0] - min_x) < tolerance):
                        # Calcular o y no ponto de interseção (ou usar o y existente se já estiver na borda)
                        if abs(p1[0] - p2[0]) < tolerance:  # Linha vertical
                            if abs(p1[0] - min_x) < tolerance:  # Linha vertical coincide com a borda
                                y_intersect = p1[1]  # Usar qualquer ponto y da linha
                                if min_y - tolerance <= y_intersect <= max_y + tolerance:
                                    intersects_a = True
                                    print(f">>> Linha toca ou coincide com o lado A (esquerdo) em y={y_intersect}")
                        else:
                            t = (min_x - p1[0]) / (p2[0] - p1[0])
                            y_intersect = p1[1] + t * (p2[1] - p1[1])
                            if min_y - tolerance <= y_intersect <= max_y + tolerance:
                                intersects_a = True
                                print(f">>> Linha cruza lado A (esquerdo) em y={y_intersect}")
                    # Verificação adicional para pontos próximos ao lado A
                    if min(abs(p[0] - min_x) for p in line_points) < tolerance:
                        print(f">>> VERIFICAÇÃO DIRETA: Ponto {p1} está próximo do lado A (esquerdo)")
                        # Verificar se a linha está dentro da altura do retângulo
                        if any(min_y - tolerance <= p[1] <= max_y + tolerance for p in line_points):
                            intersects_a = True
                            print(f">>> Linha cruza lado A (esquerdo) em y={p1[1]}")
                else:
                    # Para um retângulo horizontal, lado A é o lado inferior (y = min_y)
                    # Verificar se a linha cruza ou toca y = min_y
                    if ((p1[1] <= min_y <= p2[1]) or (p2[1] <= min_y <= p1[1])) or \
                       (abs(p1[1] - min_y) < tolerance and abs(p2[1] - min_y) < tolerance):
                        # Calcular o x no ponto de interseção (ou usar o x existente se já estiver na borda)
                        if abs(p1[1] - p2[1]) < tolerance:  # Linha horizontal
                            if abs(p1[1] - min_y) < tolerance:  # Linha horizontal coincide com a borda
                                x_intersect = p1[0]  # Usar qualquer ponto x da linha
                                if min_x - tolerance <= x_intersect <= max_x + tolerance:
                                    intersects_a = True
                                    print(f">>> Linha toca ou coincide com o lado A (inferior) em x={x_intersect}")
                        else:
                            t = (min_y - p1[1]) / (p2[1] - p1[1])
                            x_intersect = p1[0] + t * (p2[0] - p1[0])
                            if min_x - tolerance <= x_intersect <= max_x + tolerance:
                                intersects_a = True
                                print(f">>> Linha cruza lado A (inferior) em x={x_intersect}")
                    # Verificação adicional para pontos próximos ao lado A
                    if min(abs(p[1] - min_y) for p in line_points) < tolerance:
                        print(f">>> VERIFICAÇÃO DIRETA: Ponto {p1} está próximo do lado A (inferior)")
                        # Verificar se a linha está dentro da largura do retângulo
                        if any(min_x - tolerance <= p[0] <= max_x + tolerance for p in line_points):
                            intersects_a = True
                            print(f">>> Linha cruza lado A (inferior) em x={p1[0]}")
                
                # Verificar interseção ou toque com o lado B
                if is_vertical:
                    # Para um retângulo vertical, lado B é o lado direito (x = max_x)
                    # Verificar se a linha cruza ou toca x = max_x
                    if ((p1[0] <= max_x <= p2[0]) or (p2[0] <= max_x <= p1[0])) or \
                       (abs(p1[0] - max_x) < tolerance and abs(p2[0] - max_x) < tolerance):
                        # Calcular o y no ponto de interseção (ou usar o y existente se já estiver na borda)
                        if abs(p1[0] - p2[0]) < tolerance:  # Linha vertical
                            if abs(p1[0] - max_x) < tolerance:  # Linha vertical coincide com a borda
                                y_intersect = p1[1]  # Usar qualquer ponto y da linha
                                if min_y - tolerance <= y_intersect <= max_y + tolerance:
                                    intersects_b = True
                                    print(f">>> Linha toca ou coincide com o lado B (direito) em y={y_intersect}")
                        else:
                            t = (max_x - p1[0]) / (p2[0] - p1[0])
                            y_intersect = p1[1] + t * (p2[1] - p1[1])
                            if min_y - tolerance <= y_intersect <= max_y + tolerance:
                                intersects_b = True
                                print(f">>> Linha cruza lado B (direito) em y={y_intersect}")
                    # Verificação adicional para pontos próximos ao lado B
                    if min(abs(p[0] - max_x) for p in line_points) < tolerance:
                        print(f">>> VERIFICAÇÃO DIRETA: Ponto {p1} está próximo do lado B (direito)")
                        # Verificar se a linha está dentro da altura do retângulo
                        if any(min_y - tolerance <= p[1] <= max_y + tolerance for p in line_points):
                            intersects_b = True
                            print(f">>> Linha cruza lado B (direito) em y={p1[1]}")
                else:
                    # Para um retângulo horizontal, lado B é o lado superior (y = max_y)
                    # Verificar se a linha cruza ou toca y = max_y
                    if ((p1[1] <= max_y <= p2[1]) or (p2[1] <= max_y <= p1[1])) or \
                       (abs(p1[1] - max_y) < tolerance and abs(p2[1] - max_y) < tolerance):
                        # Calcular o x no ponto de interseção (ou usar o x existente se já estiver na borda)
                        if abs(p1[1] - p2[1]) < tolerance:  # Linha horizontal
                            if abs(p1[1] - max_y) < tolerance:  # Linha horizontal coincide com a borda
                                x_intersect = p1[0]  # Usar qualquer ponto x da linha
                                if min_x - tolerance <= x_intersect <= max_x + tolerance:
                                    intersects_b = True
                                    print(f">>> Linha toca ou coincide com o lado B (superior) em x={x_intersect}")
                        else:
                            t = (max_y - p1[1]) / (p2[1] - p1[1])
                            x_intersect = p1[0] + t * (p2[0] - p1[0])
                            if min_x - tolerance <= x_intersect <= max_x + tolerance:
                                intersects_b = True
                                print(f">>> Linha cruza lado B (superior) em x={x_intersect}")
                    # Verificação adicional para pontos próximos ao lado B
                    if min(abs(p[1] - max_y) for p in line_points) < tolerance:
                        print(f">>> VERIFICAÇÃO DIRETA: Ponto {p1} está próximo do lado B (superior)")
                        # Verificar se a linha está dentro da largura do retângulo
                        if any(min_x - tolerance <= p[0] <= max_x + tolerance for p in line_points):
                            intersects_b = True
                            print(f">>> Linha cruza lado B (superior) em x={p1[0]}")
                
                # Decidir se a linha deve ser atribuída ao lado A ou B (não ambos)
                # Calcular a distância para os lados A e B
                dist_a = float('inf')
                dist_b = float('inf')
                
                # Para retângulos verticais
                if is_vertical:
                    for point in line_points:
                        # Distância para o lado A (esquerdo)
                        dist_a = min(dist_a, abs(point[0] - min_x))
                        # Distância para o lado B (direito)
                        dist_b = min(dist_b, abs(point[0] - max_x))
                # Para retângulos horizontais
                else:
                    for point in line_points:
                        # Distância para o lado A (inferior)
                        dist_a = min(dist_a, abs(point[1] - min_y))
                        # Distância para o lado B (superior)
                        dist_b = min(dist_b, abs(point[1] - max_y))
                
                # Criar um objeto com informações da linha para facilitar o processamento posterior
                info_linha = {
                    "linha": line,
                    "indice": i,  # Armazenar o índice da linha
                    "pontos": line_points,
                    "intersects_a": intersects_a,
                    "intersects_b": intersects_b,
                    "dist_a": dist_a,
                    "dist_b": dist_b
                }
                
                # Nova lógica para determinar de qual lado a linha "chega" ao retângulo
                # Verificar se a linha cruza o retângulo de um lado ao outro
                if intersects_a and intersects_b:
                    # Precisamos determinar de qual lado a linha "chega" (lado de origem)
                    # Calculamos os pontos mais externos da linha (mais distantes do retângulo)
                    ponto_a_mais_externo = None
                    ponto_b_mais_externo = None
                    distancia_a_max = -1
                    distancia_b_max = -1
                    
                    for point in line_points:
                        # Para retângulos verticais, distância em X para os lados A e B
                        if is_vertical:
                            dist_to_a = abs(point[0] - min_x)
                            dist_to_b = abs(point[0] - max_x)
                        # Para retângulos horizontais, distância em Y para os lados A e B
                        else:
                            dist_to_a = abs(point[1] - min_y)
                            dist_to_b = abs(point[1] - max_y)
                        
                        # Determinar qual é o ponto mais externo em relação a cada lado
                        # Um ponto é "externo" se estiver fora do retângulo
                        is_outside_a = (is_vertical and point[0] < min_x) or (not is_vertical and point[1] < min_y)
                        is_outside_b = (is_vertical and point[0] > max_x) or (not is_vertical and point[1] > max_y)
                        
                        if is_outside_a and dist_to_a > distancia_a_max:
                            distancia_a_max = dist_to_a
                            ponto_a_mais_externo = point
                        
                        if is_outside_b and dist_to_b > distancia_b_max:
                            distancia_b_max = dist_to_b
                            ponto_b_mais_externo = point
                    
                    # Se temos pontos externos para os dois lados, precisamos determinar qual é o mais externo
                    if ponto_a_mais_externo and ponto_b_mais_externo:
                        print(f">>> Linha {i+1} cruza o retângulo completamente. Determinando o lado de chegada...")
                        if distancia_a_max >= distancia_b_max:
                            print(f">>> Linha {i+1} chega pelo lado A (distância externa: {distancia_a_max:.2f})")
                            lado_a_linhas.append(info_linha)
                            linhas_processadas.add(i)  # Marcar a linha como processada
                        else:
                            print(f">>> Linha {i+1} chega pelo lado B (distância externa: {distancia_b_max:.2f})")
                            lado_b_linhas.append(info_linha)
                            linhas_processadas.add(i)  # Marcar a linha como processada
                    elif ponto_a_mais_externo:
                        print(f">>> Linha {i+1} chega pelo lado A (único ponto externo)")
                        lado_a_linhas.append(info_linha)
                        linhas_processadas.add(i)  # Marcar a linha como processada
                    elif ponto_b_mais_externo:
                        print(f">>> Linha {i+1} chega pelo lado B (único ponto externo)")
                        lado_b_linhas.append(info_linha)
                        linhas_processadas.add(i)  # Marcar a linha como processada
                    else:
                        # Caso em que a linha está inteiramente dentro do retângulo mas toca ambos os lados
                        # Neste caso, usar a distância mínima para decidir
                        print(f">>> Linha {i+1} está dentro do retângulo, mas toca ambos os lados")
                        if dist_a <= dist_b:
                            print(f">>> Linha {i+1} atribuída ao lado A (mais próxima)")
                            lado_a_linhas.append(info_linha)
                            linhas_processadas.add(i)  # Marcar a linha como processada
                        else:
                            print(f">>> Linha {i+1} atribuída ao lado B (mais próxima)")
                            lado_b_linhas.append(info_linha)
                            linhas_processadas.add(i)  # Marcar a linha como processada
                # Se a linha intersecta apenas um lado, atribuí-la a esse lado
                elif intersects_a:
                    # Verificar se a linha está completamente fora do retângulo
                    is_outside = True
                    for point in line_points:
                        # Se algum ponto estiver dentro ou na borda do retângulo, a linha não é externa
                        if (min_x - tolerance <= point[0] <= max_x + tolerance and
                            min_y - tolerance <= point[1] <= max_y + tolerance):
                            is_outside = False
                            break
                    
                    # Marcar a linha como externa se necessário
                    if is_outside:
                        info_linha["is_outside"] = True
                        print(f">>> Linha {i+1} marcada como EXTERNA ao retângulo (lado A)")
                    
                    lado_a_linhas.append(info_linha)
                    linhas_processadas.add(i)  # Marcar a linha como processada
                    print(f">>> Linha {i+1} atribuída ao lado A (apenas intersecta A)")
                elif intersects_b:
                    # Verificar se a linha está completamente fora do retângulo
                    is_outside = True
                    for point in line_points:
                        # Se algum ponto estiver dentro ou na borda do retângulo, a linha não é externa
                        if (min_x - tolerance <= point[0] <= max_x + tolerance and
                            min_y - tolerance <= point[1] <= max_y + tolerance):
                            is_outside = False
                            break
                    
                    # Marcar a linha como externa se necessário
                    if is_outside:
                        info_linha["is_outside"] = True
                        print(f">>> Linha {i+1} marcada como EXTERNA ao retângulo (lado B)")
                    
                    lado_b_linhas.append(info_linha)
                    linhas_processadas.add(i)  # Marcar a linha como processada
                    print(f">>> Linha {i+1} atribuída ao lado B (apenas intersecta B)")
                # Se por algum motivo não detectamos interseção, verificar se a linha está muito próxima de um lado
                elif min(dist_a, dist_b) < 0.5:  # Apenas se estiver muito próxima (menos de 0,5 unidades)
                    if dist_a <= dist_b:
                        lado_a_linhas.append(info_linha)
                        linhas_processadas.add(i)  # Marcar a linha como processada
                        print(f">>> Linha {i+1} atribuída ao lado A - muito próxima (distância={dist_a:.2f})")
                    else:
                        lado_b_linhas.append(info_linha)
                        linhas_processadas.add(i)  # Marcar a linha como processada
                        print(f">>> Linha {i+1} atribuída ao lado B - muito próxima (distância={dist_b:.2f})")
                else:
                    # NOVA LÓGICA: Verificar se é uma linha externa (fora do retângulo, sem tocá-lo)
                    # Verificar se ambos os pontos estão fora do retângulo
                    is_outside_rect = True
                    for point in line_points:
                        # Um ponto está dentro se está dentro dos limites do retângulo (com tolerância)
                        if (min_x - tolerance <= point[0] <= max_x + tolerance and
                            min_y - tolerance <= point[1] <= max_y + tolerance):
                            is_outside_rect = False
                            break
                    
                    if is_outside_rect:
                        # Ignorar linhas externas ao retângulo
                        print(f">>> Linha {i+1} ignorada por ser externa ao retângulo (distância A={dist_a:.2f}, distância B={dist_b:.2f})")
                        continue
                    else:
                        print(f">>> Linha {i+1} ignorada - está fora do retângulo e muito distante (dist_a={dist_a:.2f}, dist_b={dist_b:.2f})")
                
            except Exception as e:
                print(f">>> ERRO ao processar linha {i+1}: {str(e)}")
                continue
        
        print("\n>>> RESULTADO DA CLASSIFICAÇÃO DE LINHAS:")
        print(f">>> Lado A: {len(lado_a_linhas)} linhas")
        print(f">>> Lado B: {len(lado_b_linhas)} linhas")
        
        # ETAPA 2: Separar as linhas de cada lado em esquerda e direita
        lado_a_esquerda = []
        lado_a_direita = []
        lado_b_esquerda = []
        lado_b_direita = []
        
        # Conjunto para rastrear índices de linhas já classificadas em esquerda/direita
        linhas_classificadas_esq_dir = set()
        
        # Para depuração - imprimir as coordenadas de cada linha
        print("\n>>> DETALHAMENTO DE TODAS AS LINHAS PARA DEPURAÇÃO:")
        for lado, lista_linhas in [("A", lado_a_linhas), ("B", lado_b_linhas)]:
            for i, info in enumerate(lista_linhas):
                print(f">>> Lado {lado}, Linha {i+1} (Índice original {info['indice']+1}):")
                pontos = info["pontos"]
                for j, ponto in enumerate(pontos):
                    print(f">>>   Ponto {j+1}: ({ponto[0]:.2f}, {ponto[1]:.2f})")
        
        # Classificar linhas do lado A como esquerda ou direita
        print("\n>>> CLASSIFICAÇÃO DE LINHAS DO LADO A:")
        for info in lado_a_linhas:
            # Verificar se a linha já foi classificada
            if info["indice"] in linhas_classificadas_esq_dir:
                print(f">>> Pulando linha {info['indice']+1} - já foi classificada como esquerda/direita.")
                continue
                
            line_points = info["pontos"]
            # Para depuração
            print(f">>> Analisando Lado A - Linha {info['indice']+1}:")
            for j, point in enumerate(line_points):
                print(f">>>   Ponto {j+1}: ({point[0]:.2f}, {point[1]:.2f})")
                
            # Calcular distâncias da linha até as bordas esquerda e direita do retângulo
            dist_esquerda = float('inf')
            dist_direita = float('inf')
            
            if is_vertical:
                # Para retângulo vertical, esquerda é relativo à parte inferior (min_y) e direita é relativo à parte superior (max_y)
                for point in line_points:
                    # Quanto mais próximo do min_y (parte inferior), mais está à "esquerda"
                    # Quanto mais próximo do max_y (parte superior), mais está à "direita"
                    dist_esquerda = min(dist_esquerda, abs(point[1] - min_y))
                    dist_direita = min(dist_direita, abs(point[1] - max_y))
                
                print(f">>> Linha A: dist_bottom={dist_esquerda:.2f}, dist_top={dist_direita:.2f}")
            else:
                # Para retângulo horizontal, esquerda e direita são literais
                for point in line_points:
                    dist_esquerda = min(dist_esquerda, abs(point[0] - min_x))
                    dist_direita = min(dist_direita, abs(point[0] - max_x))
                
                print(f">>> Linha A: dist_left={dist_esquerda:.2f}, dist_right={dist_direita:.2f}")
            
            # Classificar baseado na menor distância
            if is_vertical:
                # Para retângulo vertical, manter a lógica original
                if dist_esquerda <= dist_direita:
                    lado_destino = lado_a_esquerda
                    lado_alternativo = lado_a_direita
                    nome_lado = "A-esquerda"
                    nome_lado_alt = "A-direita"
                else:
                    lado_destino = lado_a_direita
                    lado_alternativo = lado_a_esquerda
                    nome_lado = "A-direita"
                    nome_lado_alt = "A-esquerda"
            else:
                # Para retângulo horizontal, NÃO inverter a lógica para o lado A
                # Quando olhamos para o lado A (inferior), esquerda é min_x e direita é max_x
                if dist_esquerda <= dist_direita:
                    lado_destino = lado_a_esquerda  # min_x corresponde à esquerda (visão correta)
                    lado_alternativo = lado_a_direita
                    nome_lado = "A-esquerda"
                    nome_lado_alt = "A-direita"
                else:
                    lado_destino = lado_a_direita  # max_x corresponde à direita (visão correta)
                    lado_alternativo = lado_a_esquerda
                    nome_lado = "A-direita"
                    nome_lado_alt = "A-esquerda"
            
            # Verificar se já temos uma linha classificada com essa distância aproximada
            tem_linha_similar = False
            for outra_info in lado_destino:
                outra_pontos = outra_info["pontos"]
                if is_vertical:
                    dist = abs(outra_pontos[0][1] - line_points[0][1])
                else:
                    dist = abs(outra_pontos[0][0] - line_points[0][0])
                
                # Se a distância entre as duas linhas for muito pequena, considerar como similares
                if dist < 1.0:  # Tolerância de 1 unidade
                    tem_linha_similar = True
                    print(f">>> ATENÇÃO: Detectada linha similar já classificada como {nome_lado}, distância={dist:.2f}")
                    break
            
            if not tem_linha_similar:
                lado_destino.append(info)
                linhas_classificadas_esq_dir.add(info["indice"])  # Marcar como classificada
                print(f">>> Linha classificada como lado {nome_lado} (dist_esq={dist_esquerda:.2f}, dist_dir={dist_direita:.2f})")
            else:
                # Tentar classificar como alternativa se já existe uma linha similar
                lado_alternativo.append(info)
                linhas_classificadas_esq_dir.add(info["indice"])  # Marcar como classificada
                print(f">>> Linha classificada como lado {nome_lado_alt} (alternativa) por já existir uma similar em {nome_lado}")
        
        # Classificar linhas do lado B como esquerda ou direita
        print("\n>>> CLASSIFICAÇÃO DE LINHAS DO LADO B:")
        for info in lado_b_linhas:
            # Verificar se a linha já foi classificada
            if info["indice"] in linhas_classificadas_esq_dir:
                print(f">>> Pulando linha {info['indice']+1} - já foi classificada como esquerda/direita.")
                continue
                
            # Se a linha é externa, dar tratamento especial (sempre colocar como esquerda por padrão)
            if info.get("is_outside", False):
                line_points = info["pontos"]
                print(f">>> Linha {info['indice']+1} é externa ao retângulo")
                
                # Para depuração
                for j, point in enumerate(line_points):
                    print(f">>>   Ponto {j+1}: ({point[0]:.2f}, {point[1]:.2f})")
                
                # Verificar se já temos uma linha externa em algum dos lados
                tem_externa_esquerda = any(l.get("is_outside", False) for l in lado_b_esquerda)
                tem_externa_direita = any(l.get("is_outside", False) for l in lado_b_direita)
                
                if not tem_externa_esquerda and not tem_externa_direita:
                    # Se não temos linha externa em nenhum lado, verificar distância para decidir
                    dist_esquerda = float('inf')
                    dist_direita = float('inf')
                    
                    if is_vertical:
                        # Para retângulo vertical, esquerda é relativo à parte inferior (min_y) e direita à parte superior (max_y)
                        for point in line_points:
                            dist_esquerda = min(dist_esquerda, abs(point[1] - min_y))
                            dist_direita = min(dist_direita, abs(point[1] - max_y))
                    else:
                        # Para retângulo horizontal, esquerda e direita são literais
                        for point in line_points:
                            dist_esquerda = min(dist_esquerda, abs(point[0] - min_x))
                            dist_direita = min(dist_direita, abs(point[0] - max_x))
                    
                    if is_vertical:
                        # Para retângulo vertical, manter a lógica original
                        if dist_esquerda <= dist_direita:
                            lado_b_esquerda.append(info)
                            linhas_classificadas_esq_dir.add(info["indice"])
                            print(f">>> Linha externa classificada como lado B - ESQUERDA (dist_esq={dist_esquerda:.2f}, dist_dir={dist_direita:.2f})")
                        else:
                            lado_b_direita.append(info)
                            linhas_classificadas_esq_dir.add(info["indice"])
                            print(f">>> Linha externa classificada como lado B - DIREITA (dist_esq={dist_esquerda:.2f}, dist_dir={dist_direita:.2f})")
                    else:
                        # Para retângulo horizontal, INVERTER a lógica
                        if dist_esquerda <= dist_direita:
                            lado_b_direita.append(info)  # Invertido: min_x corresponde à direita
                            linhas_classificadas_esq_dir.add(info["indice"])
                            print(f">>> Linha externa classificada como lado B - DIREITA (dist_esq={dist_esquerda:.2f}, dist_dir={dist_direita:.2f})")
                        else:
                            lado_b_esquerda.append(info)  # Invertido: max_x corresponde à esquerda
                            linhas_classificadas_esq_dir.add(info["indice"])
                            print(f">>> Linha externa classificada como lado B - ESQUERDA (dist_esq={dist_esquerda:.2f}, dist_dir={dist_direita:.2f})")
                else:
                    # Se já temos uma linha externa em um dos lados, colocar no outro lado
                    if tem_externa_esquerda:
                        lado_b_direita.append(info)
                        linhas_classificadas_esq_dir.add(info["indice"])
                        print(f">>> Linha externa classificada como lado B - DIREITA (já existe linha externa à esquerda)")
                    else:
                        lado_b_esquerda.append(info)
                        linhas_classificadas_esq_dir.add(info["indice"])
                        print(f">>> Linha externa classificada como lado B - ESQUERDA (já existe linha externa à direita)")
                
                continue  # Continuar para o próximo item, não precisamos processar mais esta linha
            
            line_points = info["pontos"]
            # Para depuração
            print(f">>> Analisando Lado B - Linha {info['indice']+1}:")
            for j, point in enumerate(line_points):
                print(f">>>   Ponto {j+1}: ({point[0]:.2f}, {point[1]:.2f})")
                
            # Calcular distâncias da linha até as bordas esquerda e direita do retângulo
            dist_esquerda = float('inf')
            dist_direita = float('inf')
            
            if is_vertical:
                # Para retângulo vertical, esquerda é relativo à parte inferior (min_y) e direita é relativo à parte superior (max_y)
                for point in line_points:
                    # Quanto mais próximo do min_y (parte inferior), mais está à "esquerda"
                    # Quanto mais próximo do max_y (parte superior), mais está à "direita"
                    dist_esquerda = min(dist_esquerda, abs(point[1] - min_y))
                    dist_direita = min(dist_direita, abs(point[1] - max_y))
                
                print(f">>> Linha B: dist_bottom={dist_esquerda:.2f}, dist_top={dist_direita:.2f}")
            else:
                # Para retângulo horizontal, esquerda e direita são literais
                for point in line_points:
                    dist_esquerda = min(dist_esquerda, abs(point[0] - min_x))
                    dist_direita = min(dist_direita, abs(point[0] - max_x))
                
                print(f">>> Linha B: dist_left={dist_esquerda:.2f}, dist_right={dist_direita:.2f}")
            
            # Classificar baseado na menor distância
            if is_vertical:
                # Para retângulo vertical, manter a lógica original
                if dist_esquerda <= dist_direita:
                    lado_destino = lado_b_esquerda
                    lado_alternativo = lado_b_direita
                    nome_lado = "B-esquerda"
                    nome_lado_alt = "B-direita"
                else:
                    lado_destino = lado_b_direita
                    lado_alternativo = lado_b_esquerda
                    nome_lado = "B-direita"
                    nome_lado_alt = "B-esquerda"
            else:
                # Para retângulo horizontal, INVERTER a lógica
                if dist_esquerda <= dist_direita:
                    lado_destino = lado_b_direita  # Invertido: min_x corresponde à direita
                    lado_alternativo = lado_b_esquerda
                    nome_lado = "B-direita"
                    nome_lado_alt = "B-esquerda"
                else:
                    lado_destino = lado_b_esquerda  # Invertido: max_x corresponde à esquerda
                    lado_alternativo = lado_b_direita
                    nome_lado = "B-esquerda"
                    nome_lado_alt = "B-direita"
            
            # Verificar se já temos uma linha classificada com essa distância aproximada
            tem_linha_similar = False
            for outra_info in lado_destino:
                outra_pontos = outra_info["pontos"]
                if is_vertical:
                    dist = abs(outra_pontos[0][1] - line_points[0][1])
                else:
                    dist = abs(outra_pontos[0][0] - line_points[0][0])
                
                # Se a distância entre as duas linhas for muito pequena, considerar como similares
                if dist < 1.0:  # Tolerância de 1 unidade
                    tem_linha_similar = True
                    print(f">>> ATENÇÃO: Detectada linha similar já classificada como {nome_lado}, distância={dist:.2f}")
                    break
            
            if not tem_linha_similar:
                lado_destino.append(info)
                linhas_classificadas_esq_dir.add(info["indice"])  # Marcar como classificada
                print(f">>> Linha classificada como lado {nome_lado} (dist_esq={dist_esquerda:.2f}, dist_dir={dist_direita:.2f})")
            else:
                # Tentar classificar como alternativa se já existe uma linha similar
                lado_alternativo.append(info)
                linhas_classificadas_esq_dir.add(info["indice"])  # Marcar como classificada
                print(f">>> Linha classificada como lado {nome_lado_alt} (alternativa) por já existir uma similar em {nome_lado}")
        
        print("\n>>> LINHAS CLASSIFICADAS:")
        print(f">>> Lado A - Esquerda: {len(lado_a_esquerda)} linhas")
        print(f">>> Lado A - Direita: {len(lado_a_direita)} linhas")
        print(f">>> Lado B - Esquerda: {len(lado_b_esquerda)} linhas")
        print(f">>> Lado B - Direita: {len(lado_b_direita)} linhas")
        
        # ETAPA 3: Ordenar as linhas em cada grupo pela posição
        # Ordenar por Y para retângulos verticais, por X para horizontais
        if is_vertical:
            lado_a_esquerda.sort(key=lambda info: info["pontos"][0][1])
            lado_a_direita.sort(key=lambda info: info["pontos"][0][1])
            lado_b_esquerda.sort(key=lambda info: info["pontos"][0][1])
            lado_b_direita.sort(key=lambda info: info["pontos"][0][1])
        else:
            lado_a_esquerda.sort(key=lambda info: info["pontos"][0][0])
            lado_a_direita.sort(key=lambda info: info["pontos"][0][0])
            lado_b_esquerda.sort(key=lambda info: info["pontos"][0][0])
            lado_b_direita.sort(key=lambda info: info["pontos"][0][0])
        
        # ETAPA 4: Calcular aberturas processando as linhas em pares
        lado_a_esq_aberturas = []
        lado_a_dir_aberturas = []
        lado_b_esq_aberturas = []
        lado_b_dir_aberturas = []
        
        # ETAPA 4.1: Classificar linhas usando a função auxiliar
        print("\n>>> CLASSIFICANDO LINHAS POR LADO E POSIÇÃO:")
        # Criar listas de todas as linhas com informações de lado e posição
        todas_linhas = []
        # Adicionar linhas do lado A
        for info in lado_a_linhas:
            info["lado"] = "A"  # Adicionar informação de lado
            # Verificar se a linha já tem posição definida
            if "posicao" not in info:
                # Verificar se a linha está na lista de esquerda ou direita
                if info in lado_a_esquerda:
                    info["posicao"] = "esquerda"
                elif info in lado_a_direita:
                    info["posicao"] = "direita"
                else:
                    info["posicao"] = "indefinida"
            todas_linhas.append(info)
        # Adicionar linhas do lado B
        for info in lado_b_linhas:
            info["lado"] = "B"  # Adicionar informação de lado
            # Verificar se a linha já tem posição definida
            if "posicao" not in info:
                # Verificar se a linha está na lista de esquerda ou direita
                if info in lado_b_esquerda:
                    info["posicao"] = "esquerda"
                elif info in lado_b_direita:
                    info["posicao"] = "direita"
                else:
                    info["posicao"] = "indefinida"
            todas_linhas.append(info)
        
        # Definir o retângulo para classificação
        retangulo = (min_x, min_y, max_x, max_y)
        
        # Classificar linhas usando a função auxiliar
        linhas_lado_a, linhas_lado_b, min_coord_a, max_coord_a, min_coord_b, max_coord_b = classificar_linhas_por_lado(
            todas_linhas, is_vertical, retangulo
        )
        
        # Usando a função processar_aberturas para lidar com ambos os lados A e B
        print("\n>>> PROCESSANDO TODOS OS LADOS USANDO processar_aberturas:")
        # Importar a função se ainda não estiver disponível
        from funcoes_auxiliares import processar_aberturas
        
        # Chamar a função que centraliza todo o processamento e aplica a inversão para horizontais
        resultados = processar_aberturas(
            linhas_lado_a, linhas_lado_b, is_vertical, 
            min_coord_a, max_coord_a, min_coord_b, max_coord_b
        )
        
        # Extrair os resultados do dicionário
        lado_a_esq_aberturas = resultados["A_esq"]
        lado_a_dir_aberturas = resultados["A_dir"]
        lado_b_esq_aberturas = resultados["B_esq"]
        lado_b_dir_aberturas = resultados["B_dir"]
        
        # Exibir resultados
        print(f"\n>>> RESULTADO FINAL - ABERTURAS ENCONTRADAS:")
        print(f">>> Lado A - Esquerda: {len(lado_a_esq_aberturas)} aberturas")
        for i, (distancia, largura) in enumerate(lado_a_esq_aberturas):
            print(f"  A-Esq {i+1}: Distância = {distancia:.2f}, Largura = {largura:.2f}")
            
        print(f">>> Lado A - Direita: {len(lado_a_dir_aberturas)} aberturas")
        for i, (distancia, largura) in enumerate(lado_a_dir_aberturas):
            print(f"  A-Dir {i+1}: Distância = {distancia:.2f}, Largura = {largura:.2f}")
            
        print(f">>> Lado B - Esquerda: {len(lado_b_esq_aberturas)} aberturas")
        for i, (distancia, largura) in enumerate(lado_b_esq_aberturas):
            print(f"  B-Esq {i+1}: Distância = {distancia:.2f}, Largura = {largura:.2f}")
            
        print(f">>> Lado B - Direita: {len(lado_b_dir_aberturas)} aberturas")
        for i, (distancia, largura) in enumerate(lado_b_dir_aberturas):
            print(f"  B-Dir {i+1}: Distância = {distancia:.2f}, Largura = {largura:.2f}")
        
        # Remover os blocos antigos onde chamávamos processar_lado_a e processar_lado_b diretamente
        # ...
        
        return {
            "lado_a_esq": lado_a_esq_aberturas,
            "lado_a_dir": lado_a_dir_aberturas,
            "lado_b_esq": lado_b_esq_aberturas,
            "lado_b_dir": lado_b_dir_aberturas,
            "is_vertical": is_vertical
        }
        
    except Exception as e:
        print(f">>> ERRO ao calcular interseções: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "lado_a_esq": [],
            "lado_a_dir": [],
            "lado_b_esq": [],
            "lado_b_dir": [],
            "is_vertical": True
        }

def get_text_objects(selection):
    """Extrai objetos de texto da seleção do AutoCAD e categoriza-os"""
    try:
        print("\n>>> Procurando textos na seleção...")
        print(f">>> Total de objetos na seleção: {selection.Count}")
        
        texts = []
        for i in range(selection.Count):
            entity = selection.Item(i)
            print(f">>> Analisando objeto {i+1}...")
            
            # Verificar o tipo do objeto
            object_type = entity.ObjectName if hasattr(entity, 'ObjectName') else "Desconhecido"
            print(f">>> Tipo do objeto: {object_type}")
            
            # Verificar se é um texto (AcDbText, AcDbMText ou similares)
            is_text = False
            if "Text" in object_type:
                is_text = True
            
            # Se for um texto, obter seu conteúdo e posição
            if is_text:
                try:
                    text_content = None
                    text_position = None
                    
                    # Para texto simples
                    if hasattr(entity, 'TextString'):
                        text_content = entity.TextString
                    # Para texto múltiplo
                    elif hasattr(entity, 'Text'):
                        text_content = entity.Text
                        
                    # Obter a posição
                    if hasattr(entity, 'InsertionPoint'):
                        text_position = entity.InsertionPoint
                    elif hasattr(entity, 'Location'):
                        text_position = entity.Location
                        
                    if text_content and text_position:
                        # Categorizar o texto
                        text_category = categorize_text(text_content)
                        
                        # Criar um objeto com informações do texto
                        text_info = {
                            "content": text_content,
                            "position": (text_position[0], text_position[1]),
                            "entity": entity,
                            "category": text_category
                        }
                        texts.append(text_info)
                        print(f">>> Texto encontrado: '{text_content}' em ({text_position[0]:.2f}, {text_position[1]:.2f}), categoria: {text_category}")
                except Exception as e:
                    print(f">>> Erro ao processar texto: {str(e)}")
            else:
                print(f">>> Objeto {i+1} não é um texto")
        
        print(f">>> Total de textos encontrados: {len(texts)}")
        
        # Se não encontrou nenhum texto, criar um objeto de texto com "0" como valor
        if not texts:
            print(">>> Nenhum texto encontrado na seleção, criando texto padrão com valor '0'")
            default_text = {
                "content": "0",
                "position": (0, 0),  # Posição fictícia
                "entity": None,
                "category": "laje"
            }
            texts.append(default_text)
            
        return texts
    except Exception as e:
        print(f">>> ERRO ao processar textos: {str(e)}")
        # Mesmo em caso de erro, retornar um texto padrão
        print(">>> Retornando texto padrão com valor '0' após erro")
        default_text = {
            "content": "0",
            "position": (0, 0),  # Posição fictícia
            "entity": None,
            "category": "laje"
        }
        return [default_text]

def categorize_text(text_content):
    """Categoriza o texto de acordo com seu conteúdo"""
    if not text_content:
        return "unknown"
    
    # Remover espaços no início e fim
    text_content = text_content.strip()
    
    # Verificar se é um nome de viga (V seguido de número)
    if text_content.startswith("V") and len(text_content) > 1 and any(c.isdigit() for c in text_content[1:]):
        return "viga"
    
    # Verificar se é formato (numeroxnumero)
    if text_content.startswith("(") and text_content.endswith(")") and "x" in text_content:
        parts = text_content[1:-1].split("x")
        if len(parts) == 2 and all(all(c.isdigit() for c in part) for part in parts):
            return "dimensao"
    
    # Verificar se é um nome de pilar (P seguido de número)
    if text_content.startswith("P") and len(text_content) > 1 and any(c.isdigit() for c in text_content[1:]):
        return "pilar"
    
    # Verificar se é um texto de profundidade (formato n/n)
    if "/" in text_content:
        parts = text_content.replace(" ", "").split("/")
        if len(parts) == 2 and all(part.replace(".", "").isdigit() for part in parts):
            return "profundidade"
    
    # Outros textos
    return "outro"

def extract_depth_from_text(text_content):
    """
    Extrai a profundidade de um texto dado.
    
    Args:
        text_content: Conteúdo do texto a ser analisado
    
    Returns:
        Profundidade extraída ou None se não for encontrada
    """
    if not text_content:
        return None
    
    # Remover espaços em branco extras
    text_content = text_content.strip()
    
    # Verificar se o texto tem formato n/n (número/número)
    if "/" in text_content:
        parts = text_content.split("/")
        if len(parts) == 2 and parts[1].strip().isdigit():
            print(f">>> Profundidade encontrada (formato n/n): {parts[1].strip()}")
            return int(parts[1].strip())
    
    # Verificar se o texto é apenas um número
    if text_content.isdigit():
        print(f">>> Profundidade encontrada (formato numérico): {text_content}")
        return int(text_content)
    
    # Remover prefixos comuns
    prefixos = ['PROF.', 'PROF', 'P=', 'P =', 'P= ', 'P = ', 'PROFUNDIDADE', 'PROFUNDIDADE=', 'PROFUNDIDADE =']
    for prefixo in prefixos:
        if text_content.upper().startswith(prefixo):
            # Remover o prefixo e pegar apenas os dígitos
            valor = text_content[len(prefixo):].strip()
            if valor.isdigit():
                print(f">>> Profundidade encontrada (com prefixo {prefixo}): {valor}")
                return int(valor)
    
    # Se não encontrou com os padrões acima, tentar extrair números com regex
    import re
    numeros = re.findall(r'\d+', text_content)
    if numeros:
        print(f">>> Profundidade encontrada (extraída com regex): {numeros[0]}")
        return int(numeros[0])
    
    # Se chegou até aqui, não foi possível extrair um valor numérico
    print(f">>> Não foi possível extrair profundidade do texto: '{text_content}'")
    return None

def extract_laje_value_from_text(text_content):
    """
    Extrai um valor numérico de um texto no formato n/n (extrai o segundo número) 
    ou no formato d=n (extrai o número após o igual).
    Aplica incrementos: +4 para formato n/n e +2 para formato d=n.
    
    Args:
        text_content: Conteúdo do texto a ser analisado
    
    Returns:
        Valor numérico extraído (com incremento) ou None se não for encontrado
    """
    if not text_content:
        return None
    
    # Remover espaços em branco extras
    text_content = text_content.strip()
    
    # Verificar se o texto é exatamente "0"
    if text_content == "0":
        print(">>> Valor de laje padrão '0' encontrado")
        return "0"
    
    # Verificar se o texto tem formato n/n (número/número)
    if "/" in text_content:
        parts = text_content.split("/")
        if len(parts) == 2 and parts[1].strip().replace('.', '', 1).isdigit():
            # Extrair o valor numérico
            valor_original = parts[1].strip()
            
            # Converter para número, adicionar incremento e converter de volta para string
            try:
                valor_numerico = float(valor_original)
                valor_incrementado = valor_numerico + 4  # Incremento de +4 para formato n/n
                
                # Se o valor era inteiro, retornar como inteiro
                if valor_original.isdigit():
                    valor_final = str(int(valor_incrementado))
                else:
                    valor_final = str(valor_incrementado)
                    
                print(f">>> Valor encontrado (formato n/n): {valor_original} → {valor_final} (+4)")
                return valor_final
            except:
                print(f">>> Erro ao incrementar valor: {valor_original}")
                return valor_original
    
    # Verificar se o texto tem formato d=n (d=número)
    if "=" in text_content:
        parts = text_content.split("=")
        if len(parts) == 2 and parts[1].strip().replace('.', '', 1).isdigit():
            # Extrair o valor numérico
            valor_original = parts[1].strip()
            
            # Converter para número, adicionar incremento e converter de volta para string
            try:
                valor_numerico = float(valor_original)
                valor_incrementado = valor_numerico + 2  # Incremento de +2 para formato d=n
                
                # Se o valor era inteiro, retornar como inteiro
                if valor_original.isdigit():
                    valor_final = str(int(valor_incrementado))
                else:
                    valor_final = str(valor_incrementado)
                    
                print(f">>> Valor encontrado (formato d=n): {valor_original} → {valor_final} (+2)")
                return valor_final
            except:
                print(f">>> Erro ao incrementar valor: {valor_original}")
                return valor_original
    
    # Verificar se o texto é apenas um número
    if text_content.replace('.', '', 1).isdigit():
        print(f">>> Valor encontrado (formato numérico direto): {text_content}")
        return text_content
    
    print(f">>> Nenhum valor numérico encontrado no texto: '{text_content}'")
    return None

def assign_texts_to_openings(openings, texts):
    """Associa textos às aberturas com base na proximidade"""
    result = {}
    
    # Verificar se há aberturas e textos
    if not openings or not texts:
        return result
    
    print("\n>>> Associando textos às aberturas...")
    
    # Para cada abertura, encontrar o texto mais próximo
    for opening_type, opening_list in openings.items():
        if opening_type not in result:
            result[opening_type] = []
            
        for opening in opening_list:
            closest_text = None
            min_distance = float('inf')
            
            # Coordenadas da abertura (média dos pontos)
            opening_x = sum(p[0] for p in opening["pontos"]) / len(opening["pontos"])
            opening_y = sum(p[1] for p in opening["pontos"]) / len(opening["pontos"])
            
            # Encontrar o texto mais próximo
            for text in texts:
                text_x, text_y = text["position"]
                distance = ((text_x - opening_x) ** 2 + (text_y - opening_y) ** 2) ** 0.5
                
                if distance < min_distance:
                    min_distance = distance
                    closest_text = text
            
            # Se encontrou um texto próximo, extrair a profundidade
            depth = None
            if closest_text and min_distance < 100:  # Limitar a distância máxima
                depth = extract_depth_from_text(closest_text["content"])
                print(f">>> Abertura {opening_type} associada ao texto '{closest_text['content']}' (distância: {min_distance:.2f})")
                print(f">>> Profundidade extraída: {depth}")
            
            # Adicionar à lista de resultados
            result[opening_type].append({
                "opening": opening,
                "text": closest_text,
                "depth": depth,
                "distance": min_distance if closest_text else None
            })
    
    return result

def rastrear_textos_proximidade_linhas(aberturas, textos, tolerancia_distancia=300.0, rectangle_coords=None):
    """
    Rastreia textos próximos às linhas de abertura
    
    Args:
        aberturas: Lista de aberturas com coordenadas
        textos: Lista de objetos de texto encontrados
        tolerancia_distancia: Distância máxima para considerar um texto próximo (unidades do AutoCAD)
        rectangle_coords: Coordenadas do retângulo para verificar a proximidade
    
    Returns:
        Lista de aberturas atualizada com as profundidades
    """
    if not rectangle_coords or len(rectangle_coords) < 4:
        print(">>> Coordenadas do retângulo inválidas")
        return aberturas
    
    # Extrair dimensões do retângulo
    rect_min_x = min(p[0] for p in rectangle_coords)
    rect_max_x = max(p[0] for p in rectangle_coords)
    rect_min_y = min(p[1] for p in rectangle_coords)
    rect_max_y = max(p[1] for p in rectangle_coords)
    
    largura = rect_max_x - rect_min_x
    altura = rect_max_y - rect_min_y
    
    print(f">>> Coordenadas do retângulo: ({rect_min_x:.2f}, {rect_min_y:.2f}) - ({rect_max_x:.2f}, {rect_max_y:.2f})")
    print(f">>> Dimensões: Largura={largura:.2f}, Altura={altura:.2f}")
    
    # Determinar a orientação do retângulo
    is_vertical = altura > largura
    
    if is_vertical:
        print(">>> Orientação: VERTICAL")
        return rastrear_textos_retangulo_vertical(aberturas, textos, tolerancia_distancia, rectangle_coords)
    else:
        print(">>> Orientação: HORIZONTAL")
        # Processar aberturas horizontais e então inverter as profundidades do lado A e B
        aberturas_processadas = rastrear_textos_retangulo_horizontal(aberturas, textos, tolerancia_distancia, rectangle_coords)
        # Aplicar a inversão de profundidades para lado A em retângulos horizontais
        aberturas_processadas = inverter_profundidades_lado_a_horizontal(aberturas_processadas)
        # Aplicar a inversão de profundidades para lado B em retângulos horizontais
        aberturas_processadas = inverter_profundidades_lado_b_horizontal(aberturas_processadas)
        return aberturas_processadas

def rastrear_textos_retangulo_vertical(aberturas, textos, tolerancia_distancia=300.0, rectangle_coords=None):
    """
    Rastreia textos próximos às linhas de abertura para retângulos VERTICAIS
    
    Args:
        aberturas: Lista de aberturas com coordenadas
        textos: Lista de objetos de texto encontrados
        tolerancia_distancia: Distância máxima para considerar um texto próximo (unidades do AutoCAD)
        rectangle_coords: Coordenadas do retângulo para verificar a proximidade
    
    Returns:
        Lista de aberturas atualizada com as profundidades
    """
    print("\n>>> Processando retângulo VERTICAL")
    print(f">>> Tolerância de distância: {tolerancia_distancia} (30 cm de distância perpendicular à linha)")
    
    # Extrair limites do retângulo
    rect_min_x = min(p[0] for p in rectangle_coords)
    rect_max_x = max(p[0] for p in rectangle_coords)
    rect_min_y = min(p[1] for p in rectangle_coords)
    rect_max_y = max(p[1] for p in rectangle_coords)
    
    # Aumentar a tolerância para verificação de lado (de 100 para 200 unidades = 20cm)
    margem_lado = 200  # 20cm de margem
    tolerancia_distancia_aumentada = tolerancia_distancia * 1.5  # 45cm para casos difíceis
    
    # Definir lados A (esquerda) e B (direita) para retângulo vertical
    lado_a_x = rect_min_x  # Lado A (esquerdo)
    lado_b_x = rect_max_x  # Lado B (direito)
    
    print(f">>> Área do retângulo: ({rect_min_x:.2f}, {rect_min_y:.2f}) - ({rect_max_x:.2f}, {rect_max_y:.2f})")
    print(f">>> Lado A (esquerdo): x < {rect_min_x + margem_lado:.2f}")
    print(f">>> Lado B (direito): x > {rect_max_x - margem_lado:.2f}")
    print(f">>> Margem de verificação de lado: {margem_lado} unidades (20cm)")
    
    # Filtrar apenas textos de profundidade
    textos_profundidade = [texto for texto in textos if texto["category"] == "profundidade"]
    print(f">>> Total de textos de profundidade encontrados: {len(textos_profundidade)}")
    
    if not textos_profundidade:
        print(">>> Nenhum texto de profundidade encontrado.")
        return aberturas
    
    # Imprimir informações de todos os textos de profundidade
    print("\n>>> TEXTOS DE PROFUNDIDADE DISPONÍVEIS:")
    for i, texto in enumerate(textos_profundidade):
        content = texto["content"]
        prof = extract_depth_from_text(content)
        pos_x, pos_y = texto["position"]
        
        # Determinar em qual lado o texto está
        lado_texto = "A (esquerdo)" if pos_x < rect_min_x + margem_lado else "B (direito)" if pos_x > rect_max_x - margem_lado else "CENTRO"
        print(f">>> Texto {i+1}: '{content}' (profundidade: {prof}) - Posição: ({pos_x:.2f}, {pos_y:.2f}) - Lado: {lado_texto}")
    
    # Imprimir informações de todas as aberturas
    print("\n>>> ABERTURAS A PROCESSAR:")
    for i, abertura in enumerate(aberturas):
        tipo = abertura.get("tipo", "")
        coord = abertura.get("coord", (0, 0))
        larg = abertura.get("largura", 0)
        dist = abertura.get("distancia", 0)
        is_horiz = abertura.get("is_horizontal", True)
        
        lado_abertura = ""
        if tipo.startswith("A_"):
            lado_abertura = "A"
        elif tipo.startswith("B_"):
            lado_abertura = "B"
        else:
            print(f">>> ALERTA: Abertura {tipo} não tem prefixo de lado A_ ou B_. Será ignorada.")
            continue
            
        print(f">>> Abertura {i+1}: {tipo} - Lado: {lado_abertura} - Coordenadas: {coord} - Largura: {larg:.2f} - Distância: {dist:.2f} - Horizontal: {is_horiz}")
    
    # Criar uma cópia da lista de textos para poder remover itens já utilizados
    textos_disponiveis = textos_profundidade.copy()
    
    # Função para calcular a distância de um ponto a uma linha definida por dois pontos
    def distancia_ponto_linha(x, y, x1, y1, x2, y2):
        # Caso especial: linha vertical
        if abs(x2 - x1) < 0.001:
            return abs(x - x1)
        
        # Caso especial: linha horizontal
        if abs(y2 - y1) < 0.001:
            return abs(y - y1)
        
        # Caso geral: calcular distância perpendicular
        # Fórmula: d = |Ax + By + C| / sqrt(A² + B²), onde Ax + By + C = 0 é a equação da linha
        A = y2 - y1
        B = x1 - x2
        C = x2 * y1 - x1 * y2
        
        return abs(A * x + B * y + C) / ((A ** 2 + B ** 2) ** 0.5)
    
    # Função para verificar se um ponto está próximo à linha
    def ponto_proximo_ao_segmento(x, y, x1, y1, x2, y2, tolerancia):
        # Calcular distância perpendicular à linha
        dist_perp = distancia_ponto_linha(x, y, x1, y1, x2, y2)
        
        # Consideramos apenas a distância perpendicular, ignorando se o ponto está dentro da extensão do segmento
        # pois agora estamos trabalhando com linhas infinitas (linha projetada)
        return dist_perp <= tolerancia, dist_perp
    
    # Para cada abertura, procurar textos próximos em todas as direções
    for abertura in aberturas:
        # Obter pontos da abertura
        pontos = abertura.get("pontos", [])
        if not pontos or len(pontos) < 2:
            # Usar as coordenadas e largura para criar os pontos
            coord = abertura.get("coord", (0, 0))
            largura_abertura = abertura.get("largura", 0)
            is_horiz = abertura.get("is_horizontal", True)
            
            # Criar pontos para a abertura
            if is_horiz:
                # Linha horizontal: pontos à esquerda e direita
                meio_largura = largura_abertura / 2
                x_centro, y_centro = coord
                ponto1 = (x_centro - meio_largura, y_centro)
                ponto2 = (x_centro + meio_largura, y_centro)
            else:
                # Linha vertical: pontos acima e abaixo
                meio_largura = largura_abertura / 2
                x_centro, y_centro = coord
                ponto1 = (x_centro, y_centro - meio_largura)
                ponto2 = (x_centro, y_centro + meio_largura)
            
            pontos = [ponto1, ponto2]
            abertura["pontos"] = pontos
            print(f">>> Pontos criados para abertura {abertura.get('tipo', '')}: {ponto1}, {ponto2}")
        
        # Obter coordenadas e tipo da abertura
        tipo = abertura.get("tipo", "")
        is_horiz = abertura.get("is_horizontal", True)
        
        # Verificar o lado da abertura (A: esquerda, B: direita)
        lado_abertura = ""
        if tipo.startswith("A_"):
            lado_abertura = "A"
        elif tipo.startswith("B_"):
            lado_abertura = "B"
        else:
            print(f">>> ALERTA: Abertura {tipo} não tem prefixo de lado A_ ou B_. Será ignorada.")
            continue
        
        print(f"\n>>> Processando abertura {tipo} (Lado {lado_abertura})")
        
        # Calcular o ponto médio para referência (usando pontos reais da abertura)
        x_medio = sum(p[0] for p in pontos) / len(pontos)
        y_medio = sum(p[1] for p in pontos) / len(pontos)
        print(f">>> Ponto médio da abertura: ({x_medio:.2f}, {y_medio:.2f})")
        
        # Determinar em qual lado do retângulo está a abertura (para retângulo vertical)
        lado_x = lado_a_x if lado_abertura == "A" else lado_b_x
        
        # Encontrar o texto de profundidade mais próximo
        texto_mais_proximo = None
        menor_pontuacao = float('inf')
        profundidade = None
        indice_texto_mais_proximo = -1
        
        # Extrair as coordenadas exatas dos pontos da abertura
        if len(pontos) >= 2:
            ponto1, ponto2 = pontos[0], pontos[1]
            x1, y1 = ponto1
            x2, y2 = ponto2
            print(f">>> Linha real: ({x1:.2f}, {y1:.2f}) - ({x2:.2f}, {y2:.2f})")
        else:
            # Usar uma linha estendida se não tiver pontos suficientes (este caso não deve ocorrer mais)
            extensao = 100000  # Praticamente infinito para capturar textos em qualquer ponto
            
            if is_horiz:
                # Linha horizontal (esquerda para direita)
                x1, y1 = x_medio - extensao, y_medio
                x2, y2 = x_medio + extensao, y_medio
            else:
                # Linha vertical (baixo para cima)
                x1, y1 = x_medio, y_medio - extensao
                x2, y2 = x_medio, y_medio + extensao
            
            print(f">>> Linha estendida: ({x1:.2f}, {y1:.2f}) - ({x2:.2f}, {y2:.2f})")
        
        print(f">>> Linha {'horizontal' if is_horiz else 'vertical'}")
        print(f">>> Tolerância perpendicular: {tolerancia_distancia:.1f} unidades (30 cm)")
        print(f">>> Tolerância aumentada para casos difíceis: {tolerancia_distancia_aumentada:.1f} unidades (45 cm)")
        
        # Primeiro, tente com tolerância normal e verificação de lado
        texto_encontrado = False
        
        # Processar apenas textos ainda disponíveis
        for i, texto in enumerate(textos_disponiveis):
            text_x, text_y = texto["position"]
            
            # FILTRO DE LADO para retângulo vertical:
            # Para aberturas no lado A (esquerdo), considerar apenas textos à esquerda do retângulo
            # Para aberturas no lado B (direito), considerar apenas textos à direita do retângulo
            if lado_abertura == "A" and text_x > rect_min_x + margem_lado:  # Margem de 20cm
                print(f">>> Texto '{texto['content']}' ignorado - está no lado errado (deve estar à esquerda)")
                continue
            
            if lado_abertura == "B" and text_x < rect_max_x - margem_lado:  # Margem de 20cm
                print(f">>> Texto '{texto['content']}' ignorado - está no lado errado (deve estar à direita)")
                continue
            
            # Verificar se o texto está próximo à linha da abertura
            esta_proximo, dist = ponto_proximo_ao_segmento(
                text_x, text_y, x1, y1, x2, y2, tolerancia_distancia
            )
            
            # Se não está próximo, nem continuar a verificação
            if not esta_proximo:
                print(f">>> Texto '{texto['content']}' muito distante: {dist:.1f} > {tolerancia_distancia:.1f}")
                continue
            
            # Se chegou até aqui, o texto está próximo
            # Calcular pontuação (apenas distância, sem ajustes)
            pontuacao = dist
            
            content = texto["content"]
            text_x, text_y = texto["position"]
            print(f">>> Avaliando texto '{content}' em ({text_x:.1f}, {text_y:.1f}): Dist={dist:.1f}, Proximidade=OK, Lado={lado_abertura}")
            
            if pontuacao < menor_pontuacao:
                menor_pontuacao = pontuacao
                texto_mais_proximo = texto
                profundidade = extract_depth_from_text(texto["content"])
                indice_texto_mais_proximo = i
                print(f">>> - Novo melhor texto: '{content}' (distância: {dist:.1f})")
                texto_encontrado = True
        
        # Se não encontrou texto com a tolerância normal, tente com tolerância aumentada
        if not texto_encontrado:
            print(f">>> Nenhum texto encontrado com tolerância normal. Tentando com tolerância aumentada ({tolerancia_distancia_aumentada:.1f})...")
            
            for i, texto in enumerate(textos_disponiveis):
                text_x, text_y = texto["position"]
                
                # Ainda mantém o filtro de lado, mas verifica com tolerância aumentada
                if lado_abertura == "A" and text_x > rect_min_x + margem_lado:
                    continue
                
                if lado_abertura == "B" and text_x < rect_max_x - margem_lado:
                    continue
                
                # Verificar com tolerância aumentada
                esta_proximo, dist = ponto_proximo_ao_segmento(
                    text_x, text_y, x1, y1, x2, y2, tolerancia_distancia_aumentada
                )
                
                if not esta_proximo:
                    continue
                
                content = texto["content"]
                print(f">>> [Tolerância aumentada] Avaliando texto '{content}': Dist={dist:.1f}, Proximidade=OK")
                
                pontuacao = dist
                if pontuacao < menor_pontuacao:
                    menor_pontuacao = pontuacao
                    texto_mais_proximo = texto
                    profundidade = extract_depth_from_text(texto["content"])
                    indice_texto_mais_proximo = i
                    print(f">>> - Novo melhor texto: '{content}' (distância: {dist:.1f})")
                    texto_encontrado = True
        
        if texto_mais_proximo and profundidade is not None:
            # Adicionar a profundidade à abertura
            abertura["profundidade"] = profundidade
            text_x, text_y = texto_mais_proximo["position"]
            dist_centro = ((text_x - x_medio) ** 2 + (text_y - y_medio) ** 2) ** 0.5
            print(f">>> ASSOCIADO - Abertura {abertura.get('tipo', '')} com texto '{texto_mais_proximo['content']}'")
            print(f">>> Distância: {dist_centro:.2f} - Profundidade: {profundidade}")
            
            # Remover o texto utilizado da lista de disponíveis
            if indice_texto_mais_proximo >= 0:
                del textos_disponiveis[indice_texto_mais_proximo]
                print(f">>> Texto '{texto_mais_proximo['content']}' removido da lista. Restantes: {len(textos_disponiveis)}")
        else:
            print(f">>> ALERTA: Nenhum texto de profundidade encontrado para a abertura {abertura.get('tipo', '')}")
            print(f">>> Verifique se o texto está próximo à abertura e no lado correto do retângulo")
    
    return aberturas

def rastrear_textos_retangulo_horizontal(aberturas, textos, tolerancia_distancia=300.0, rectangle_coords=None):
    """
    Rastreia textos próximos às linhas de abertura para retângulos HORIZONTAIS
    
    Args:
        aberturas: Lista de aberturas com coordenadas
        textos: Lista de objetos de texto encontrados
        tolerancia_distancia: Distância máxima para considerar um texto próximo (unidades do AutoCAD)
        rectangle_coords: Coordenadas do retângulo para verificar a proximidade
    
    Returns:
        Lista de aberturas atualizada com as profundidades
    """
    print("\n>>> Processando retângulo HORIZONTAL")
    print(f">>> Tolerância de distância: {tolerancia_distancia} (30 cm de distância perpendicular à linha)")
    
    # Extrair limites do retângulo
    rect_min_x = min(p[0] for p in rectangle_coords)
    rect_max_x = max(p[0] for p in rectangle_coords)
    rect_min_y = min(p[1] for p in rectangle_coords)
    rect_max_y = max(p[1] for p in rectangle_coords)
    
    # Aumentar a tolerância para verificação de lado (de 100 para 200 unidades = 20cm)
    margem_lado = 200  # 20cm de margem
    tolerancia_distancia_aumentada = tolerancia_distancia * 1.5  # 45cm para casos difíceis
    
    # Definir lados A (inferior) e B (superior) para retângulo horizontal
    lado_a_y = rect_min_y  # Lado A (inferior) está embaixo
    lado_b_y = rect_max_y  # Lado B (superior) está em cima
    
    print(f">>> Área do retângulo: ({rect_min_x:.2f}, {rect_min_y:.2f}) - ({rect_max_x:.2f}, {rect_max_y:.2f})")
    print(f">>> Lado A (inferior): y < {rect_min_y + margem_lado:.2f}")
    print(f">>> Lado B (superior): y > {rect_max_y - margem_lado:.2f}")
    print(f">>> Margem de verificação de lado: {margem_lado} unidades (20cm)")
    
    # Filtrar apenas textos de profundidade
    textos_profundidade = [texto for texto in textos if texto["category"] == "profundidade"]
    print(f">>> Total de textos de profundidade encontrados: {len(textos_profundidade)}")
    
    if not textos_profundidade:
        print(">>> Nenhum texto de profundidade encontrado.")
        return aberturas
    
    # Imprimir informações de todos os textos de profundidade
    print("\n>>> TEXTOS DE PROFUNDIDADE DISPONÍVEIS:")
    for i, texto in enumerate(textos_profundidade):
        content = texto["content"]
        prof = extract_depth_from_text(content)
        pos_x, pos_y = texto["position"]
        
        # Determinar em qual lado o texto está
        lado_texto = "B (superior)" if pos_y > rect_max_y - margem_lado else "A (inferior)" if pos_y < rect_min_y + margem_lado else "CENTRO"
        print(f">>> Texto {i+1}: '{content}' (profundidade: {prof}) - Posição: ({pos_x:.2f}, {pos_y:.2f}) - Lado: {lado_texto}")
    
    # Imprimir informações de todas as aberturas
    print("\n>>> ABERTURAS A PROCESSAR:")
    for i, abertura in enumerate(aberturas):
        tipo = abertura.get("tipo", "")
        coord = abertura.get("coord", (0, 0))
        larg = abertura.get("largura", 0)
        dist = abertura.get("distancia", 0)
        is_horiz = abertura.get("is_horizontal", True)
        
        lado_abertura = ""
        if tipo.startswith("A_"):
            lado_abertura = "A"
        elif tipo.startswith("B_"):
            lado_abertura = "B"
        else:
            print(f">>> ALERTA: Abertura {tipo} não tem prefixo de lado A_ ou B_. Será ignorada.")
            continue
            
        print(f">>> Abertura {i+1}: {tipo} - Lado: {lado_abertura} - Coordenadas: {coord} - Largura: {larg:.2f} - Distância: {dist:.2f} - Horizontal: {is_horiz}")
    
    # Criar uma cópia da lista de textos para poder remover itens já utilizados
    textos_disponiveis = textos_profundidade.copy()
    
    # Função para calcular a distância de um ponto a uma linha definida por dois pontos
    def distancia_ponto_linha(x, y, x1, y1, x2, y2):
        # Caso especial: linha vertical
        if abs(x2 - x1) < 0.001:
            return abs(x - x1)
        
        # Caso especial: linha horizontal
        if abs(y2 - y1) < 0.001:
            return abs(y - y1)
        
        # Caso geral: calcular distância perpendicular
        # Fórmula: d = |Ax + By + C| / sqrt(A² + B²), onde Ax + By + C = 0 é a equação da linha
        A = y2 - y1
        B = x1 - x2
        C = x2 * y1 - x1 * y2
        
        return abs(A * x + B * y + C) / ((A ** 2 + B ** 2) ** 0.5)
    
    # Função para verificar se um ponto está próximo à linha
    def ponto_proximo_ao_segmento(x, y, x1, y1, x2, y2, tolerancia):
        # Calcular distância perpendicular à linha
        dist_perp = distancia_ponto_linha(x, y, x1, y1, x2, y2)
        
        # Consideramos apenas a distância perpendicular, ignorando se o ponto está dentro da extensão do segmento
        # pois agora estamos trabalhando com linhas infinitas (linha projetada)
        return dist_perp <= tolerancia, dist_perp
    
    # Para cada abertura, procurar textos próximos em todas as direções
    for abertura in aberturas:
        # Obter pontos da abertura
        pontos = abertura.get("pontos", [])
        if not pontos or len(pontos) < 2:
            # Usar as coordenadas e largura para criar os pontos
            coord = abertura.get("coord", (0, 0))
            largura_abertura = abertura.get("largura", 0)
            is_horiz = abertura.get("is_horizontal", True)
            
            # Criar pontos para a abertura
            if is_horiz:
                # Linha horizontal: pontos à esquerda e direita
                meio_largura = largura_abertura / 2
                x_centro, y_centro = coord
                ponto1 = (x_centro - meio_largura, y_centro)
                ponto2 = (x_centro + meio_largura, y_centro)
            else:
                # Linha vertical: pontos acima e abaixo
                meio_largura = largura_abertura / 2
                x_centro, y_centro = coord
                ponto1 = (x_centro, y_centro - meio_largura)
                ponto2 = (x_centro, y_centro + meio_largura)
            
            pontos = [ponto1, ponto2]
            abertura["pontos"] = pontos
            print(f">>> Pontos criados para abertura {abertura.get('tipo', '')}: {ponto1}, {ponto2}")
        
        # Obter coordenadas e tipo da abertura
        tipo = abertura.get("tipo", "")
        is_horiz = abertura.get("is_horizontal", True)
        
        # Verificar o lado da abertura (A: superior, B: inferior)
        lado_abertura = ""
        if tipo.startswith("A_"):
            lado_abertura = "A"
        elif tipo.startswith("B_"):
            lado_abertura = "B"
        else:
            print(f">>> ALERTA: Abertura {tipo} não tem prefixo de lado A_ ou B_. Será ignorada.")
            continue
        
        print(f"\n>>> Processando abertura {tipo} (Lado {lado_abertura})")
        
        # Calcular o ponto médio para referência (usando pontos reais da abertura)
        x_medio = sum(p[0] for p in pontos) / len(pontos)
        y_medio = sum(p[1] for p in pontos) / len(pontos)
        print(f">>> Ponto médio da abertura: ({x_medio:.2f}, {y_medio:.2f})")
        
        # Determinar em qual lado do retângulo está a abertura (para retângulo horizontal)
        lado_y = lado_a_y if lado_abertura == "A" else lado_b_y
        
        # Encontrar o texto de profundidade mais próximo
        texto_mais_proximo = None
        menor_pontuacao = float('inf')
        profundidade = None
        indice_texto_mais_proximo = -1
        
        # Extrair as coordenadas exatas dos pontos da abertura
        if len(pontos) >= 2:
            ponto1, ponto2 = pontos[0], pontos[1]
            x1, y1 = ponto1
            x2, y2 = ponto2
            print(f">>> Linha real: ({x1:.2f}, {y1:.2f}) - ({x2:.2f}, {y2:.2f})")
        else:
            # Usar uma linha estendida se não tiver pontos suficientes (este caso não deve ocorrer mais)
            extensao = 100000  # Praticamente infinito para capturar textos em qualquer ponto
            
            if is_horiz:
                # Linha horizontal (esquerda para direita)
                x1, y1 = x_medio - extensao, y_medio
                x2, y2 = x_medio + extensao, y_medio
            else:
                # Linha vertical (baixo para cima)
                x1, y1 = x_medio, y_medio - extensao
                x2, y2 = x_medio, y_medio + extensao
            
            print(f">>> Linha estendida: ({x1:.2f}, {y1:.2f}) - ({x2:.2f}, {y2:.2f})")
        
        print(f">>> Linha {'horizontal' if is_horiz else 'vertical'}")
        print(f">>> Tolerância perpendicular: {tolerancia_distancia:.1f} unidades (30 cm)")
        print(f">>> Tolerância aumentada para casos difíceis: {tolerancia_distancia_aumentada:.1f} unidades (45 cm)")
        
        # Primeiro, tente com tolerância normal e verificação de lado
        texto_encontrado = False
        
        # Processar apenas textos ainda disponíveis
        for i, texto in enumerate(textos_disponiveis):
            text_x, text_y = texto["position"]
            
            # FILTRO DE LADO para retângulo horizontal:
            # Para aberturas no lado A (inferior), considerar apenas textos ABAIXO do retângulo
            # Para aberturas no lado B (superior), considerar apenas textos ACIMA do retângulo
            if lado_abertura == "A":
                # Para lado A (inferior), queremos textos ABAIXO do retângulo (text_y < rect_min_y)
                if not (text_y < rect_min_y):
                    print(f">>> Texto '{texto['content']}' ignorado - não está abaixo do lado A (deve estar abaixo do retângulo)")
                    continue
            
            if lado_abertura == "B":
                # Para lado B (superior), queremos textos ACIMA do retângulo (text_y > rect_max_y)
                if not (text_y > rect_max_y):
                    print(f">>> Texto '{texto['content']}' ignorado - não está acima do lado B (deve estar acima do retângulo)")
                    continue
            
            # Verificar se o texto está próximo à linha da abertura
            esta_proximo, dist = ponto_proximo_ao_segmento(
                text_x, text_y, x1, y1, x2, y2, tolerancia_distancia
            )
            
            # Se não está próximo, nem continuar a verificação
            if not esta_proximo:
                print(f">>> Texto '{texto['content']}' muito distante: {dist:.1f} > {tolerancia_distancia:.1f}")
                continue
            
            # Se chegou até aqui, o texto está próximo
            # Calcular pontuação (apenas distância, sem ajustes)
            pontuacao = dist
            
            content = texto["content"]
            text_x, text_y = texto["position"]
            print(f">>> Avaliando texto '{content}' em ({text_x:.1f}, {text_y:.1f}): Dist={dist:.1f}, Proximidade=OK, Lado={lado_abertura}")
            
            if pontuacao < menor_pontuacao:
                menor_pontuacao = pontuacao
                texto_mais_proximo = texto
                profundidade = extract_depth_from_text(texto["content"])
                indice_texto_mais_proximo = i
                print(f">>> - Novo melhor texto: '{content}' (distância: {dist:.1f})")
                texto_encontrado = True
        
        # Se não encontrou texto com a tolerância normal, tente com tolerância aumentada
        if not texto_encontrado:
            print(f">>> Nenhum texto encontrado com tolerância normal. Tentando com tolerância aumentada ({tolerancia_distancia_aumentada:.1f})...")
            
            for i, texto in enumerate(textos_disponiveis):
                text_x, text_y = texto["position"]
                
                # Ainda mantém o filtro de lado, mas verifica com tolerância aumentada
                if lado_abertura == "A":
                    # Para lado A (inferior), queremos textos ABAIXO do retângulo (text_y < rect_min_y)
                    if not (text_y < rect_min_y):
                        print(f">>> Texto '{texto['content']}' ignorado - não está abaixo do lado A (deve estar abaixo do retângulo)")
                        continue
                
                if lado_abertura == "B":
                    # Para lado B (superior), queremos textos ACIMA do retângulo (text_y > rect_max_y)
                    if not (text_y > rect_max_y):
                        print(f">>> Texto '{texto['content']}' ignorado - não está acima do lado B (deve estar acima do retângulo)")
                        continue
                
                # Verificar com tolerância aumentada
                esta_proximo, dist = ponto_proximo_ao_segmento(
                    text_x, text_y, x1, y1, x2, y2, tolerancia_distancia_aumentada
                )
                
                if not esta_proximo:
                    continue
                
                content = texto["content"]
                print(f">>> [Tolerância aumentada] Avaliando texto '{content}': Dist={dist:.1f}, Proximidade=OK")
                
                pontuacao = dist
                if pontuacao < menor_pontuacao:
                    menor_pontuacao = pontuacao
                    texto_mais_proximo = texto
                    profundidade = extract_depth_from_text(texto["content"])
                    indice_texto_mais_proximo = i
                    print(f">>> - Novo melhor texto: '{content}' (distância: {dist:.1f})")
                    texto_encontrado = True
        
        if texto_mais_proximo and profundidade is not None:
            # Adicionar a profundidade à abertura
            abertura["profundidade"] = profundidade
            text_x, text_y = texto_mais_proximo["position"]
            dist_centro = ((text_x - x_medio) ** 2 + (text_y - y_medio) ** 2) ** 0.5
            print(f">>> ASSOCIADO - Abertura {abertura.get('tipo', '')} com texto '{texto_mais_proximo['content']}'")
            print(f">>> Distância: {dist_centro:.2f} - Profundidade: {profundidade}")
            
            # Remover o texto utilizado da lista de disponíveis
            if indice_texto_mais_proximo >= 0:
                del textos_disponiveis[indice_texto_mais_proximo]
                print(f">>> Texto '{texto_mais_proximo['content']}' removido da lista. Restantes: {len(textos_disponiveis)}")
        else:
            print(f">>> ALERTA: Nenhum texto de profundidade encontrado para a abertura {abertura.get('tipo', '')}")
            print(f">>> Verifique se o texto está próximo à abertura e no lado correto do retângulo")
    
    return aberturas

def inverter_profundidades_lado_a_horizontal(aberturas):
    """
    Inverte as profundidades das aberturas do lado A para retângulos horizontais.
    Esta função corrige o problema de inversão dos lados esquerdo e direito feito
    pela função processar_aberturas, mas que não estava sendo refletido nas profundidades.
    
    Args:
        aberturas: Lista de aberturas já processadas com suas profundidades
        
    Returns:
        Lista de aberturas com as profundidades corrigidas para o lado A
    """
    print("\n>>> Invertendo profundidades para o lado A (retângulo horizontal):")
    
    # Separar aberturas por tipo
    aberturas_a_esq = []
    aberturas_a_dir = []
    aberturas_outros = []
    
    # Classificar aberturas
    for abertura in aberturas:
        tipo = abertura.get("tipo", "")
        
        if tipo.startswith("A_esq"):
            aberturas_a_esq.append(abertura)
        elif tipo.startswith("A_dir"):
            aberturas_a_dir.append(abertura)
        else:
            aberturas_outros.append(abertura)
    
    # Verificar se temos aberturas de ambos os lados
    if not aberturas_a_esq or not aberturas_a_dir:
        print(">>> Não há pares suficientes para inverter no lado A")
        return aberturas
    
    # Mapear profundidades
    profundidades_a_esq = {}
    profundidades_a_dir = {}
    
    # Coletar profundidades atuais
    for abertura in aberturas_a_esq:
        indice = abertura.get("indice", 0)
        profundidade = abertura.get("profundidade")
        if profundidade is not None:
            profundidades_a_esq[indice] = profundidade
            print(f">>> Profundidade original A_esq[{indice}]: {profundidade}")
    
    for abertura in aberturas_a_dir:
        indice = abertura.get("indice", 0)
        profundidade = abertura.get("profundidade")
        if profundidade is not None:
            profundidades_a_dir[indice] = profundidade
            print(f">>> Profundidade original A_dir[{indice}]: {profundidade}")
    
    # Inverter profundidades
    for abertura in aberturas_a_esq:
        indice = abertura.get("indice", 0)
        # Obter profundidade correspondente do lado A_dir
        if indice in profundidades_a_dir:
            prof_original = abertura.get("profundidade")
            abertura["profundidade"] = profundidades_a_dir[indice]
            print(f">>> Abertura A_esq[{indice}]: Profundidade alterada de {prof_original} para {abertura['profundidade']}")
    
    for abertura in aberturas_a_dir:
        indice = abertura.get("indice", 0)
        # Obter profundidade correspondente do lado A_esq
        if indice in profundidades_a_esq:
            prof_original = abertura.get("profundidade")
            abertura["profundidade"] = profundidades_a_esq[indice]
            print(f">>> Abertura A_dir[{indice}]: Profundidade alterada de {prof_original} para {abertura['profundidade']}")
    
    # Reconstruir a lista de aberturas
    return aberturas_a_esq + aberturas_a_dir + aberturas_outros

def inverter_profundidades_lado_b_horizontal(aberturas):
    """
    Inverte as profundidades das aberturas do lado B para retângulos horizontais.
    Esta função corrige o problema de inversão dos lados esquerdo e direito feito
    pela função processar_aberturas, mas que não estava sendo refletido nas profundidades.
    
    Args:
        aberturas: Lista de aberturas já processadas com suas profundidades
        
    Returns:
        Lista de aberturas com as profundidades corrigidas para o lado B
    """
    print("\n>>> Invertendo profundidades para o lado B (retângulo horizontal):")
    
    # Separar aberturas por tipo
    aberturas_b_esq = []
    aberturas_b_dir = []
    aberturas_outros = []
    
    # Classificar aberturas
    for abertura in aberturas:
        tipo = abertura.get("tipo", "")
        
        if tipo.startswith("B_esq"):
            aberturas_b_esq.append(abertura)
        elif tipo.startswith("B_dir"):
            aberturas_b_dir.append(abertura)
        else:
            aberturas_outros.append(abertura)
    
    # Verificar se temos aberturas de ambos os lados
    if not aberturas_b_esq or not aberturas_b_dir:
        print(">>> Não há pares suficientes para inverter no lado B")
        return aberturas
    
    # Mapear profundidades
    profundidades_b_esq = {}
    profundidades_b_dir = {}
    
    # Coletar profundidades atuais
    for abertura in aberturas_b_esq:
        indice = abertura.get("indice", 0)
        profundidade = abertura.get("profundidade")
        if profundidade is not None:
            profundidades_b_esq[indice] = profundidade
            print(f">>> Profundidade original B_esq[{indice}]: {profundidade}")
    
    for abertura in aberturas_b_dir:
        indice = abertura.get("indice", 0)
        profundidade = abertura.get("profundidade")
        if profundidade is not None:
            profundidades_b_dir[indice] = profundidade
            print(f">>> Profundidade original B_dir[{indice}]: {profundidade}")
    
    # Inverter profundidades
    for abertura in aberturas_b_esq:
        indice = abertura.get("indice", 0)
        # Obter profundidade correspondente do lado B_dir
        if indice in profundidades_b_dir:
            prof_original = abertura.get("profundidade")
            abertura["profundidade"] = profundidades_b_dir[indice]
            print(f">>> Abertura B_esq[{indice}]: Profundidade alterada de {prof_original} para {abertura['profundidade']}")
    
    for abertura in aberturas_b_dir:
        indice = abertura.get("indice", 0)
        # Obter profundidade correspondente do lado B_esq
        if indice in profundidades_b_esq:
            prof_original = abertura.get("profundidade")
            abertura["profundidade"] = profundidades_b_esq[indice]
            print(f">>> Abertura B_dir[{indice}]: Profundidade alterada de {prof_original} para {abertura['profundidade']}")
    
    # Reconstruir a lista de aberturas
    return aberturas_b_esq + aberturas_b_dir + aberturas_outros

def extract_dimensions_from_text(text_content):
    """
    Extrai dimensões de um texto no formato (XxY) e retorna comprimento (maior valor) e largura (menor valor).
    
    Args:
        text_content: Conteúdo do texto no formato (XxY)
        
    Returns:
        Tupla (comprimento, largura) onde comprimento é sempre o maior valor
        ou None se o formato não for válido
    """
    if not text_content:
        return None
    
    # Remover espaços em branco extras
    text_content = text_content.strip()
    
    # Verificar se o texto tem formato (XxY)
    if text_content.startswith("(") and text_content.endswith(")") and "x" in text_content:
        # Extrair os valores numéricos
        content = text_content[1:-1]  # Remover parênteses
        parts = content.split("x")
        
        if len(parts) == 2:
            try:
                # Converter para números
                dim1 = float(parts[0].strip())
                dim2 = float(parts[1].strip())
                
                # Determinar qual é o maior (comprimento) e qual é o menor (largura)
                comprimento = max(dim1, dim2)
                largura = min(dim1, dim2)
                
                print(f">>> Dimensões extraídas: Comprimento={comprimento:.2f}, Largura={largura:.2f}")
                return (comprimento, largura)
            except ValueError:
                pass
    
    return None

# Aqui vamos usar if name == main para iniciar a aplicação sem importar PilarAnalyzer
if __name__ == "__main__":
    # Importar o módulo dinamicamente para evitar referência circular
    import sys
    import importlib.util
    import os
    
    # Obter o diretório atual do script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    module_path = os.path.join(current_dir, "funcoes_auxiliares_2.py")
    
    # Verificar se o arquivo existe
    if not os.path.exists(module_path):
        print(f"ERRO: Arquivo não encontrado: {module_path}")
        sys.exit(1)
    
    # Carregar o módulo diretamente do caminho atual
    spec = importlib.util.spec_from_file_location("funcoes_auxiliares_2", module_path)
    
    if not spec:
        print(f"ERRO: Não foi possível criar especificação para o módulo: {module_path}")
        sys.exit(1)
    
    func_aux_2 = importlib.util.module_from_spec(spec)
    sys.modules["funcoes_auxiliares_2"] = func_aux_2
    
    try:
        spec.loader.exec_module(func_aux_2)
        print("Módulo funcoes_auxiliares_2 carregado com sucesso!")
        
        # Importar e configurar o módulo funcoes_auxiliares_3 para usar set_excel_mapping
        import funcoes_auxiliares_3
        
        # Exportar EXCEL_MAPPING para o módulo importado
        print("Exportando EXCEL_MAPPING para o módulo funcoes_auxiliares_3...")
        if hasattr(funcoes_auxiliares_3, 'set_excel_mapping'):
            funcoes_auxiliares_3.set_excel_mapping(EXCEL_MAPPING)
            print("EXCEL_MAPPING exportado com sucesso!")
        else:
            print("AVISO: Função set_excel_mapping não encontrada no módulo funcoes_auxiliares_3")

        # Como alternativa, definir o EXCEL_MAPPING no espaço de nomes do módulo
        func_aux_2.EXCEL_MAPPING = EXCEL_MAPPING
        print("EXCEL_MAPPING definido diretamente no módulo!")
    except Exception as e:
        print(f"ERRO ao carregar módulo: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Iniciar a aplicação
    try:
        print("🎯 Criando instância do PilarAnalyzer...")
        app = func_aux_2.PilarAnalyzer()
        print("✅ Instância criada com sucesso!")
        
        # Obter e injetar credit_manager na instância da aplicação
        try:
            # Adicionar o diretório src ao path para importar core
            import sys
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            src_dir = os.path.dirname(current_dir)  # src/utils -> src
            if src_dir not in sys.path:
                sys.path.insert(0, src_dir)
            
            from core.credit_system import obter_gerenciador_creditos
            credit_manager = obter_gerenciador_creditos()
            if credit_manager:
                # Usar o método definido na classe para injetar o credit_manager
                sucesso = app.definir_credit_manager(credit_manager)
                if sucesso:
                    print("✅ CreditManager injetado na aplicação principal")
                else:
                    print("⚠️ Falha ao injetar CreditManager")
            else:
                print("⚠️ CreditManager não disponível")
        except Exception as e:
            print(_get_obf_str("credit"))
            import traceback
            traceback.print_exc()
        
        # Verificar se a janela foi criada corretamente
        print(f"🔍 Verificando janela: título='{app.title()}', geometria='{app.geometry()}'")
        print(f"🔍 Janela existe: {app.winfo_exists()}")
        print(f"🔍 Widgets filhos: {len(app.winfo_children())}")
        
        # Forçar a janela a aparecer
        print("🔧 Configurando visibilidade da janela...")
        app.deiconify()  # Garantir que não está minimizada
        app.lift()
        app.attributes('-topmost', True)
        app.after(100, lambda: app.attributes('-topmost', False))
        app.focus_force()
        app.update()  # Forçar atualização
        
        print("🖥️ Iniciando mainloop da interface...")
        app.mainloop()
        print("✅ Interface encerrada normalmente")
    except Exception as e:
        print(f"❌ ERRO ao iniciar aplicação: {str(e)}")
        import traceback
        traceback.print_exc() 