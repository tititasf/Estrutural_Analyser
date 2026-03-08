
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

import openpyxl
import os
import sys
import time
import traceback

# Configurar caminhos usando sistema robusto
def setup_robots_path():
    """Configura o path para os robôs de forma robusta"""
    try:
        from config_paths import ROBOTS_DIR
        return ROBOTS_DIR
    except ImportError:
        # Fallback para nova estrutura
        script_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.abspath(os.path.join(script_dir, "..", "robots"))  # "robots" não "Robos"

robos_dir = setup_robots_path()

# Adicionar diretório dos robôs ao path de forma confiável
if robos_dir not in sys.path:
    sys.path.insert(0, robos_dir)

print(f"Diretório de robôs adicionado ao path: {robos_dir}")
print(f"Path atual: {sys.path}")

# Verificar se o arquivo existe fisicamente
robo_path = os.path.join(robos_dir, "Robo_Pilar_ABCD.py")
if not os.path.exists(robo_path):
    print(f"ERRO: O arquivo Robo_Pilar_ABCD.py não foi encontrado em {robos_dir}")
    print(f"Arquivos disponíveis no diretório:")
    for arquivo in os.listdir(robos_dir):
        print(f"  - {arquivo}")
    sys.exit(1)
else:
    print(f"Arquivo Robo_Pilar_ABCD.py encontrado em: {robo_path}")

# Importar bibliotecas necessárias
try:
    # Importar módulos necessários que o Robo_Pilar_ABCD.py usa
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    import logging
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import math
    import json
    from datetime import datetime
    
    # Tentar importar win32com.client, mas continuar mesmo se falhar
    try:
        import win32com.client
        import pyautogui
        print("Módulos win32com e pyautogui importados com sucesso.")
    except ImportError:
        print("AVISO: Módulos win32com.client ou pyautogui não estão instalados.")
        print("Algumas funcionalidades relacionadas ao AutoCAD podem não funcionar.")
    
    # Configuração de logging
    log_file = os.path.join(os.path.dirname(robos_dir), "pilares.log")
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file), 
            logging.StreamHandler()
        ]
    )
    
    # Realizar a importação do módulo Robo_Pilar_ABCD
    print("Tentando importar AplicacaoUnificada do módulo Robo_Pilar_ABCD...")
    
    # Usar importlib para importação mais controlada
    import importlib.util
    spec = importlib.util.spec_from_file_location("Robo_Pilar_ABCD", robo_path)
    robo_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(robo_module)
    
    # Agora extrair a classe AplicacaoUnificada do módulo carregado
    AplicacaoUnificada = robo_module.AplicacaoUnificada
    print("Importação realizada com sucesso!")
    
except ImportError as e:
    print(f"Erro ao importar: {e}")
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    print(f"Erro desconhecido: {e}")
    traceback.print_exc()
    sys.exit(1)

def _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, painel_letra, max_linhas, max_colunas):
    """Função auxiliar para preencher hatchs do Excel"""
    for i in range(max_linhas):
        for j in range(max_colunas):
            campo_hatch = f"hatch_l{i+1}_h{j+2}_{painel_letra}"
            if campo_hatch in linhas_abcd:
                valor = sheet[f'{coluna}{linhas_abcd[campo_hatch]}'].value
                print(f"[DEBUG] Painel {painel_letra.upper()} - {campo_hatch} (linha {linhas_abcd[campo_hatch]}), valor do Excel: {valor}, campo interface: [{i}][{j}]")
                if valor is not None:
                    if painel_letra == 'a':
                        gerador.hatch_opcoes_a[i][j].set(str(valor))
                    elif painel_letra == 'b':
                        gerador.hatch_opcoes_b[i][j].set(str(valor))
                    elif painel_letra == 'c':
                        gerador.hatch_opcoes_c[i][j].set(str(valor))
                    elif painel_letra == 'd':
                        gerador.hatch_opcoes_d[i][j].set(str(valor))

def _preencher_interface_principal_com_dados_efgh_excel(sheet, coluna, linhas_abcd, interface_principal, gerador):
    """
    Lê os dados dos painéis E, F, G, H do Excel e preenche na interface_principal
    para que _preencher_robo_com_dados_efgh possa acessá-los corretamente.
    Esta função é chamada ANTES de _preencher_robo_com_dados_efgh quando processa pelo pavimento.
    """
    try:
        print("[PREENCHER_EFGH_EXCEL] Lendo dados dos painéis E,F,G,H do Excel...")
        
        # Verificar se há dados do pilar especial no Excel (linha 1000+)
        linha_base_especial = 999
        
        try:
            # CORREÇÃO: Ler dados do pilar especial da coluna A (1), não da coluna atual
            # O Conector salva os dados na coluna A (1) nas linhas 1000+
            coluna_dados_especial = 'A'  # Coluna 1 onde o Conector salva os dados
            tipo_especial = sheet[f'{coluna_dados_especial}{linha_base_especial + 2}'].value
            comp_1 = sheet[f'{coluna_dados_especial}{linha_base_especial + 3}'].value
            comp_2 = sheet[f'{coluna_dados_especial}{linha_base_especial + 4}'].value
            larg_1 = sheet[f'{coluna_dados_especial}{linha_base_especial + 6}'].value
            larg_2 = sheet[f'{coluna_dados_especial}{linha_base_especial + 7}'].value
            
            # Converter para float, usando 0 se None
            comp_1 = float(comp_1) if comp_1 is not None else 0
            comp_2 = float(comp_2) if comp_2 is not None else 0
            larg_1 = float(larg_1) if larg_1 is not None else 0
            larg_2 = float(larg_2) if larg_2 is not None else 0
            
            print(f"[PREENCHER_EFGH_EXCEL] Dados do pilar especial lidos: tipo={tipo_especial}, comp_1={comp_1}, comp_2={comp_2}, larg_1={larg_1}, larg_2={larg_2}")
            
            # Preencher na interface_principal se os campos existirem
            # CORREÇÃO: Suportar tanto StringVar (.set()) quanto Entry (.delete/.insert())
            def preencher_campo(objeto, valor):
                """Preenche campo suportando StringVar ou Entry"""
                try:
                    # Tentar .set() primeiro (StringVar)
                    if hasattr(objeto, 'set'):
                        objeto.set(str(valor))
                        return True
                    # Tentar .delete/.insert (Entry)
                    elif hasattr(objeto, 'delete') and hasattr(objeto, 'insert'):
                        objeto.delete(0, 'end')
                        objeto.insert(0, str(valor))
                        return True
                except Exception as e:
                    print(f"[PREENCHER_EFGH_EXCEL] Erro ao preencher campo: {e}")
                return False
            
            # Painel E: usa comp_1
            if hasattr(interface_principal, 'larg1_E'):
                if preencher_campo(interface_principal.larg1_E, comp_1):
                    print(f"[PREENCHER_EFGH_EXCEL] larg1_E = {comp_1}")
            if hasattr(interface_principal, 'larg2_E'):
                preencher_campo(interface_principal.larg2_E, '0')
            
            # Painel F: usa comp_2
            if hasattr(interface_principal, 'larg1_F'):
                if preencher_campo(interface_principal.larg1_F, comp_2):
                    print(f"[PREENCHER_EFGH_EXCEL] larg1_F = {comp_2}")
            if hasattr(interface_principal, 'larg2_F'):
                preencher_campo(interface_principal.larg2_F, '0')
            
            # Painel G: usa larg_1
            if hasattr(interface_principal, 'larg1_G'):
                if preencher_campo(interface_principal.larg1_G, larg_1):
                    print(f"[PREENCHER_EFGH_EXCEL] larg1_G = {larg_1}")
            if hasattr(interface_principal, 'larg2_G'):
                preencher_campo(interface_principal.larg2_G, '0')
            
            # Painel H: usa larg_2
            if hasattr(interface_principal, 'larg1_H'):
                if preencher_campo(interface_principal.larg1_H, larg_2):
                    print(f"[PREENCHER_EFGH_EXCEL] larg1_H = {larg_2}")
            if hasattr(interface_principal, 'larg2_H'):
                preencher_campo(interface_principal.larg2_H, '0')
            
            # Se os campos não existirem na interface_principal, preencher diretamente no gerador
            # como fallback, criando atributos temporários no gerador
            if not hasattr(interface_principal, 'larg1_E'):
                print(f"[PREENCHER_EFGH_EXCEL] Campo larg1_E não encontrado na interface_principal, criando no gerador como fallback")
                if not hasattr(gerador, 'dados_efgh_temp'):
                    gerador.dados_efgh_temp = {}
                gerador.dados_efgh_temp['larg1_E'] = str(comp_1)
                gerador.dados_efgh_temp['larg1_F'] = str(comp_2)
                gerador.dados_efgh_temp['larg1_G'] = str(larg_1)
                gerador.dados_efgh_temp['larg1_H'] = str(larg_2)
            
            # CORREÇÃO: Ler lajes e alturas dos painéis E, F, G, H do Excel e preencher na interface principal
            # Esses dados são salvos no Excel temporário pelo Conector quando o pilar especial está ativo
            try:
                from ..utils.excel_mapping import EXCEL_MAPPING
            except ImportError:
                import sys
                import os
                utils_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'utils')
                if utils_path not in sys.path:
                    sys.path.insert(0, utils_path)
                from excel_mapping import EXCEL_MAPPING
            
            for letra in ['E', 'F', 'G', 'H']:
                # Ler laje do Excel
                campo_laje = f'laje_{letra}'
                linha_laje = EXCEL_MAPPING.get(campo_laje)
                if linha_laje and hasattr(interface_principal, campo_laje):
                    try:
                        valor_laje = sheet[f'{coluna}{linha_laje}'].value
                        if valor_laje is None:
                            valor_laje = '0'
                        if preencher_campo(getattr(interface_principal, campo_laje), valor_laje):
                            print(f"[PREENCHER_EFGH_EXCEL] {campo_laje} = {valor_laje} (do Excel)")
                    except Exception as e:
                        print(f"[PREENCHER_EFGH_EXCEL] Erro ao ler {campo_laje} do Excel: {e}")
                
                # Ler posição da laje do Excel
                campo_pos = f'posicao_laje_{letra}'
                linha_pos = EXCEL_MAPPING.get(campo_pos)
                if linha_pos and hasattr(interface_principal, campo_pos):
                    try:
                        valor_pos = sheet[f'{coluna}{linha_pos}'].value
                        if valor_pos is None:
                            valor_pos = '0'
                        if preencher_campo(getattr(interface_principal, campo_pos), valor_pos):
                            print(f"[PREENCHER_EFGH_EXCEL] {campo_pos} = {valor_pos} (do Excel)")
                    except Exception as e:
                        print(f"[PREENCHER_EFGH_EXCEL] Erro ao ler {campo_pos} do Excel: {e}")
                
                # Ler alturas do Excel (h1_E, h2_E, h3_E, h4_E, h5_E, etc.)
                for altura_num in range(1, 6):  # h1 até h5
                    campo_altura = f'h{altura_num}_{letra}'
                    linha_altura = EXCEL_MAPPING.get(campo_altura)
                    if linha_altura and hasattr(interface_principal, campo_altura):
                        try:
                            valor_altura = sheet[f'{coluna}{linha_altura}'].value
                            if valor_altura is None:
                                valor_altura = '0'
                            if preencher_campo(getattr(interface_principal, campo_altura), valor_altura):
                                print(f"[PREENCHER_EFGH_EXCEL] {campo_altura} = {valor_altura} (do Excel)")
                        except Exception as e:
                            print(f"[PREENCHER_EFGH_EXCEL] Erro ao ler {campo_altura} do Excel: {e}")
            
            print("[PREENCHER_EFGH_EXCEL] Dados dos painéis E,F,G,H preenchidos")
            return True
            
        except Exception as e:
            print(f"[PREENCHER_EFGH_EXCEL] Erro ao ler dados do Excel: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback: tentar calcular a partir dos valores já no gerador
            try:
                comp_atual = float(gerador.campos['comprimento'].get() or 0)
                larg_atual = float(gerador.campos['largura'].get() or 0)
                
                # Usar função helper para preencher campos (suporta StringVar e Entry)
                if hasattr(interface_principal, 'larg1_E'):
                    preencher_campo(interface_principal.larg1_E, comp_atual / 2)
                if hasattr(interface_principal, 'larg1_F'):
                    preencher_campo(interface_principal.larg1_F, comp_atual / 2)
                if hasattr(interface_principal, 'larg1_G'):
                    preencher_campo(interface_principal.larg1_G, larg_atual / 2)
                if hasattr(interface_principal, 'larg1_H'):
                    preencher_campo(interface_principal.larg1_H, larg_atual / 2)
                
                print(f"[PREENCHER_EFGH_EXCEL] Usando fallback: E=F={comp_atual/2}, G=H={larg_atual/2}")
                return True
            except Exception as e2:
                print(f"[PREENCHER_EFGH_EXCEL] Erro no fallback: {e2}")
                return False
            
    except Exception as e:
        print(f"[PREENCHER_EFGH_EXCEL] ERRO ao preencher interface_principal com dados EFGH: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def _preencher_robo_com_dados_efgh(gerador, interface_principal):
    """
    Preenche os campos do robô (A,B,C,D) com os dados calculados dos painéis E,F,G,H.
    Isso permite que o Script 2 use dimensões diferentes do Script 1.
    """
    try:
        print("[PREENCHER_EFGH] Iniciando preenchimento dos dados E,F,G,H no robô...")
        
        # LIMPAR CAMPOS DE HATCH ANTES DE PREENCHER COM DADOS E-F-G-H
        print("[PREENCHER_EFGH] Limpando campos de hatch do Script 1...")
        for painel in ['a', 'b', 'c', 'd']:
            if hasattr(gerador, f'hatch_opcoes_{painel}'):
                hatch_opcoes = getattr(gerador, f'hatch_opcoes_{painel}')
                for linha in hatch_opcoes:
                    for var in linha:
                        var.set("0")  # Limpar todos os hatches
                print(f"[PREENCHER_EFGH] Campos de hatch do painel {painel.upper()} limpos")
        
        # CORRIGIDO: Atualizar campos globais do robô com valores dos painéis E,F,G,H
        print("[PREENCHER_EFGH] Atualizando campos globais do robô...")
        
        # Inicializar variáveis com valores padrão
        comp_e = '0'
        comp_f = '0'
        larg_g = '0'
        larg_h = '0'
        
        # CORREÇÃO: Calcular comprimento total dos painéis E e F (A e B do Script 2)
        # Usar os valores corretos dos painéis E e F (não larg1_E e larg1_F)
        try:
            comp_e = interface_principal.larg1_E.get() or '0'  # Largura do painel E
            comp_f = interface_principal.larg1_F.get() or '0'  # Largura do painel F
        except (AttributeError, KeyError):
            # Fallback: usar dados temporários do gerador se interface_principal não tiver os campos
            if hasattr(gerador, 'dados_efgh_temp'):
                comp_e = gerador.dados_efgh_temp.get('larg1_E', '0')
                comp_f = gerador.dados_efgh_temp.get('larg1_F', '0')
                print(f"[PREENCHER_EFGH] Usando dados temporários: E={comp_e}, F={comp_f}")
            else:
                # Último fallback: usar comprimento dividido por 2
                comp_atual = float(gerador.campos['comprimento'].get() or 0)
                comp_e = str(comp_atual / 2)
                comp_f = str(comp_atual / 2)
                print(f"[PREENCHER_EFGH] Usando fallback para E e F: {comp_e}, {comp_f}")
        try:
            comprimento_total = float(comp_e) + float(comp_f)
            gerador.campos['comprimento'].delete(0, 'end')
            gerador.campos['comprimento'].insert(0, str(comprimento_total))
            print(f"[PREENCHER_EFGH] Comprimento global atualizado: {comprimento_total} (E={comp_e} + F={comp_f})")
        except (ValueError, AttributeError) as e:
            print(f"[PREENCHER_EFGH] Erro ao atualizar comprimento: {e}")
        
        # CORREÇÃO: Calcular largura total dos painéis G e H (C e D do Script 2)
        # Usar os valores corretos dos painéis G e H (não larg1_G e larg1_H)
        try:
            larg_g = interface_principal.larg1_G.get() or '0'  # Largura do painel G
            larg_h = interface_principal.larg1_H.get() or '0'  # Largura do painel H
        except (AttributeError, KeyError):
            # Fallback: usar dados temporários do gerador se interface_principal não tiver os campos
            if hasattr(gerador, 'dados_efgh_temp'):
                larg_g = gerador.dados_efgh_temp.get('larg1_G', '0')
                larg_h = gerador.dados_efgh_temp.get('larg1_H', '0')
                print(f"[PREENCHER_EFGH] Usando dados temporários: G={larg_g}, H={larg_h}")
            else:
                # Último fallback: usar largura dividida por 2
                larg_atual = float(gerador.campos['largura'].get() or 0)
                larg_g = str(larg_atual / 2)
                larg_h = str(larg_atual / 2)
                print(f"[PREENCHER_EFGH] Usando fallback para G e H: {larg_g}, {larg_h}")
        try:
            largura_total = float(larg_g) + float(larg_h)
            gerador.campos['largura'].delete(0, 'end')
            gerador.campos['largura'].insert(0, str(largura_total))
            print(f"[PREENCHER_EFGH] Largura global atualizada: {largura_total} (G={larg_g} + H={larg_h})")
        except (ValueError, AttributeError) as e:
            print(f"[PREENCHER_EFGH] Erro ao atualizar largura: {e}")
        
        # Mapear E→A, F→B, G→C, H→D
        mapeamento = {'E': 'a', 'F': 'b', 'G': 'c', 'H': 'd'}
        
        for letra_orig, letra_dest in mapeamento.items():
            print(f"[PREENCHER_EFGH] Processando painel {letra_orig} → {letra_dest}...")
            
            # Preencher larguras
            # CORRIGIDO: Robô ABCD só tem comp1 e comp2, não comp3!
            max_larguras = 2  # Todos os painéis têm apenas 2 larguras no robô ABCD
            for i in range(1, max_larguras + 1):
                campo_nome = f"larg{i}_{letra_orig}"
                valor = '0'
                
                # Tentar ler da interface_principal primeiro
                try:
                    if hasattr(interface_principal, campo_nome):
                        valor = getattr(interface_principal, campo_nome).get()
                        if valor in [None, '']:
                            valor = '0'
                    else:
                        # Fallback: usar dados temporários do gerador
                        if hasattr(gerador, 'dados_efgh_temp'):
                            valor = gerador.dados_efgh_temp.get(campo_nome, '0')
                            print(f"[PREENCHER_EFGH]   Usando dados temporários para {campo_nome} = {valor}")
                        else:
                            # Último fallback: usar apenas para i=1 e calcular baseado no que já foi lido
                            if i == 1:
                                if letra_orig == 'E':
                                    valor = comp_e if 'comp_e' in locals() else '0'
                                elif letra_orig == 'F':
                                    valor = comp_f if 'comp_f' in locals() else '0'
                                elif letra_orig == 'G':
                                    valor = larg_g if 'larg_g' in locals() else '0'
                                elif letra_orig == 'H':
                                    valor = larg_h if 'larg_h' in locals() else '0'
                            else:
                                valor = '0'
                except (AttributeError, KeyError) as e:
                    print(f"[PREENCHER_EFGH]   Aviso ao ler {campo_nome}: {e}, usando '0'")
                    valor = '0'
                
                # Preencher no robô
                try:
                    if letra_dest in ['c', 'd']:
                        gerador.campos_cd[f'comp{i}_{letra_dest}'].delete(0, 'end')
                        gerador.campos_cd[f'comp{i}_{letra_dest}'].insert(0, valor)
                    else:
                        gerador.campos_ab[f'comp{i}_{letra_dest}'].delete(0, 'end')
                        gerador.campos_ab[f'comp{i}_{letra_dest}'].insert(0, valor)
                    
                    print(f"[PREENCHER_EFGH]   comp{i}_{letra_dest} = {valor}")
                except (KeyError, AttributeError) as e:
                    print(f"[PREENCHER_EFGH]   Erro ao preencher comp{i}_{letra_dest}: {e}")
            
            # Preencher alturas
            max_alturas = 5 if letra_dest in ['a', 'b'] else 4
            for i in range(1, max_alturas + 1):
                campo_nome = f"h{i}_{letra_orig}"
                if hasattr(interface_principal, campo_nome):
                    valor = getattr(interface_principal, campo_nome).get()
                    if valor in [None, '']:
                        valor = '0'
                    
                    # Preencher no robô
                    _lista_alt = gerador.campos_altura.get(letra_dest, [])
                    if (i - 1) < len(_lista_alt):
                        _lista_alt[i-1].delete(0, 'end')
                        _lista_alt[i-1].insert(0, valor)
                        print(f"[PREENCHER_EFGH]   h{i}_{letra_dest} = {valor}")
            
            # CORRIGIDO: Painéis E,F,G,H usam os mesmos campos de laje dos painéis A,B,C,D
            # E→A, F→B, G→C, H→D
            campo_laje_orig = f"laje_{letra_dest.upper()}"
            if hasattr(interface_principal, campo_laje_orig):
                valor_laje = getattr(interface_principal, campo_laje_orig).get()
                if valor_laje in [None, '']:
                    valor_laje = '0'
                gerador.campos[f'laje_{letra_dest}'].delete(0, 'end')
                gerador.campos[f'laje_{letra_dest}'].insert(0, valor_laje)
                print(f"[PREENCHER_EFGH]   laje_{letra_dest} = {valor_laje} (de {campo_laje_orig})")
            else:
                print(f"[PREENCHER_EFGH]   Campo {campo_laje_orig} não encontrado, usando valor padrão")
                gerador.campos[f'laje_{letra_dest}'].delete(0, 'end')
                gerador.campos[f'laje_{letra_dest}'].insert(0, '0')
            
            # CORRIGIDO: Painéis E,F,G,H usam os mesmos campos de posição de laje dos painéis A,B,C,D
            campo_pos_orig = f"posicao_laje_{letra_dest.upper()}"
            if hasattr(interface_principal, campo_pos_orig):
                valor_pos = getattr(interface_principal, campo_pos_orig).get()
                if hasattr(gerador, f'pos_laje_{letra_dest}'):
                    getattr(gerador, f'pos_laje_{letra_dest}').set(valor_pos)
                    print(f"[PREENCHER_EFGH]   pos_laje_{letra_dest} = {valor_pos} (de {campo_pos_orig})")
            else:
                print(f"[PREENCHER_EFGH]   Campo {campo_pos_orig} não encontrado, usando valor padrão")
                if hasattr(gerador, f'pos_laje_{letra_dest}'):
                    getattr(gerador, f'pos_laje_{letra_dest}').set('0')
            
            # NOVO: Coletar aberturas dos painéis E-F-G-H para criar globais
            # Os painéis E-F-G-H não têm campos de abertura próprios, então vamos criar globais
            print(f"[PREENCHER_EFGH]   Coletando aberturas do painel {letra_orig} para globais...")
            aberturas = ['esq1', 'esq2', 'dir1', 'dir2']
            for abertura in aberturas:
                # Para cada tipo de dado da abertura
                for tipo in ['dist', 'prof', 'larg', 'pos']:
                    # CORRIGIDO: Usar os nomes corretos dos campos criados na interface
                    # Os campos são criados como dist_esq_1_E, larg_esq_1_E, etc.
                    prefixo = 'esq' if abertura.startswith('esq') else 'dir'
                    numero = abertura[-1]  # 1 ou 2
                    campo_nome_orig = f"{tipo}_{prefixo}_{numero}_{letra_orig}"
                    
                    # Verificar se o campo existe na interface principal
                    if hasattr(interface_principal, campo_nome_orig):
                        valor_abertura = getattr(interface_principal, campo_nome_orig).get()
                        if valor_abertura in [None, '']:
                            valor_abertura = '0'
                        
                        # Criar global para abertura do painel E-F-G-H
                        global_nome = f"abertura_{abertura}_{tipo}_{letra_orig.lower()}"
                        if not hasattr(gerador, 'aberturas_globais_efgh'):
                            gerador.aberturas_globais_efgh = {}
                        gerador.aberturas_globais_efgh[global_nome] = valor_abertura
                        print(f"[PREENCHER_EFGH]     GLOBAL {global_nome} = {valor_abertura} (de {campo_nome_orig})")
                    else:
                        # Campo não existe, usar valor padrão
                        valor_abertura = '0'
                        global_nome = f"abertura_{abertura}_{tipo}_{letra_orig.lower()}"
                        if not hasattr(gerador, 'aberturas_globais_efgh'):
                            gerador.aberturas_globais_efgh = {}
                        gerador.aberturas_globais_efgh[global_nome] = valor_abertura
                        print(f"[PREENCHER_EFGH]     GLOBAL {global_nome} = {valor_abertura} (padrão - campo {campo_nome_orig} não encontrado)")
            
            # Preencher aberturas no robô usando as globais criadas
            print(f"[PREENCHER_EFGH]   Preenchendo aberturas no robô usando globais...")
            for abertura in aberturas:
                for tipo in ['dist', 'prof', 'larg', 'pos']:
                    # Nome da global (ex: abertura_esq1_dist_e)
                    global_nome = f"abertura_{abertura}_{tipo}_{letra_orig.lower()}"
                    
                    # Nome do campo no robô (ex: abertura_esq1_dist_a)
                    campo_nome_dest = f"abertura_{abertura}_{tipo}_{letra_dest}"
                    
                    # Usar valor da global
                    if hasattr(gerador, 'aberturas_globais_efgh') and global_nome in gerador.aberturas_globais_efgh:
                        valor_abertura = gerador.aberturas_globais_efgh[global_nome]
                        if campo_nome_dest in gerador.campos:
                            gerador.campos[campo_nome_dest].delete(0, 'end')
                            gerador.campos[campo_nome_dest].insert(0, valor_abertura)
                            print(f"[PREENCHER_EFGH]     {campo_nome_dest} = {valor_abertura} (de global {global_nome})")
                        else:
                            print(f"[PREENCHER_EFGH]     Campo {campo_nome_dest} não encontrado no robô")
                    else:
                        print(f"[PREENCHER_EFGH]     Global {global_nome} não encontrada")
            
            # NOVO: Coletar hatches dos painéis E-F-G-H para criar globais
            print(f"[PREENCHER_EFGH]   Coletando hatches do painel {letra_orig} para globais...")
            if not hasattr(gerador, 'hatches_globais_efgh'):
                gerador.hatches_globais_efgh = {}
            
            # Obter número de painéis individuais para esta letra
            if hasattr(interface_principal, '_obter_numero_paineis_individuais'):
                num_paineis = interface_principal._obter_numero_paineis_individuais(letra_orig)
            else:
                # Fallback: usar valores padrão baseados na letra (ambiente de teste)
                print(f"[PREENCHER_EFGH] Método _obter_numero_paineis_individuais não disponível, usando padrão")
                if letra_orig in ['E', 'F']:
                    num_paineis = 3  # E e F geralmente têm 3 painéis
                else:
                    num_paineis = 2  # G e H geralmente têm 2 painéis
                print(f"[PREENCHER_EFGH] Usando num_paineis padrão: {num_paineis}")
            for i in range(1, num_paineis + 1):
                painel_id = f"{letra_orig.lower()}_{i}"
                hachura_var_name = f"hachura_{painel_id}"
                
                if hasattr(interface_principal, hachura_var_name):
                    hachura_var = getattr(interface_principal, hachura_var_name)
                    valor_hatch = hachura_var.get()
                    if valor_hatch in [None, '']:
                        valor_hatch = '0'
                    
                    # Criar global para hatch do painel E-F-G-H
                    global_hatch_nome = f"hatch_{painel_id}"
                    gerador.hatches_globais_efgh[global_hatch_nome] = valor_hatch
                    print(f"[PREENCHER_EFGH]     GLOBAL HATCH {global_hatch_nome} = {valor_hatch}")
                else:
                    # Campo não existe, usar valor padrão
                    valor_hatch = '0'
                    global_hatch_nome = f"hatch_{painel_id}"
                    gerador.hatches_globais_efgh[global_hatch_nome] = valor_hatch
                    print(f"[PREENCHER_EFGH]     GLOBAL HATCH {global_hatch_nome} = {valor_hatch} (padrão - campo {hachura_var_name} não encontrado)")
        
        print("[PREENCHER_EFGH] Preenchimento concluído com sucesso!")
        return True
    except Exception as e:
        print(f"[PREENCHER_EFGH] ERRO ao preencher dados E,F,G,H: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def _distribuir_largura_especial(largura_total):
    """
    Distribui a largura total nos 3 campos (comp1, comp2, comp3) 
    com máximo de 244 por campo.
    
    Exemplos:
    - 300 -> [244, 56, 0]
    - 200 -> [200, 0, 0]
    - 500 -> [244, 244, 12]
    """
    max_por_campo = 244
    campos = [0, 0, 0]
    restante = largura_total
    
    for i in range(3):
        if restante <= 0:
            break
        if restante >= max_por_campo:
            campos[i] = max_por_campo
            restante -= max_por_campo
        else:
            campos[i] = restante
            restante = 0
    
    return campos

def _gerar_script_com_dados_especiais(gerador, interface_principal, usar_paineis_efgh=False, usar_parafusos_especiais=False, letra_parafuso='A', ajustar_x_offset=False, sufixo_nome=''):
    """
    Função helper para gerar script com dados específicos do pilar especial.
    
    Args:
        gerador: Instância do gerador de scripts
        interface_principal: Interface principal com dados do pilar especial
        usar_paineis_efgh: Se True, usa painéis E,F,G,H; se False, usa A,B,C,D
        usar_parafusos_especiais: Se True, usa parafusos da aba Pilares Especiais
        letra_parafuso: Letra do parafuso ('A' ou 'E')
        ajustar_x_offset: Se True, ajusta coordenada X +1585
        sufixo_nome: Sufixo para o nome do arquivo (ex: '2')
    """
    try:
        print(f"\n[PILAR_ESPECIAL] ========================================")
        print(f"[PILAR_ESPECIAL] INICIANDO GERAÇÃO DE SCRIPT")
        print(f"[PILAR_ESPECIAL] ========================================")
        print(f"[PILAR_ESPECIAL] Parâmetros recebidos:")
        print(f"  - usar_paineis_efgh: {usar_paineis_efgh}")
        print(f"  - usar_parafusos_especiais: {usar_parafusos_especiais}")
        print(f"  - letra_parafuso: {letra_parafuso}")
        print(f"  - ajustar_x_offset: {ajustar_x_offset}")
        print(f"  - sufixo_nome: '{sufixo_nome}'")
        
        # Verificar se gerador e interface existem
        if not gerador or not interface_principal:
            print(f"[PILAR_ESPECIAL] ERRO: Gerador ou interface principal não disponível")
            return None
            
        print(f"[PILAR_ESPECIAL] Verificando gerador...")
        print(f"  - gerador existe: {gerador is not None}")
        print(f"  - gerador.campos existe: {hasattr(gerador, 'campos')}")
        print(f"  - interface_principal existe: {interface_principal is not None}")
        print(f"  - ativar_pilar_especial existe: {hasattr(interface_principal, 'ativar_pilar_especial')}")
        if hasattr(interface_principal, 'ativar_pilar_especial'):
            print(f"  - pilar especial ativo: {interface_principal.ativar_pilar_especial.get()}")
        
        # Preencher dados básicos (nome, comprimento, largura, etc.)
        print(f"[PILAR_ESPECIAL] Preenchendo dados básicos...")
        
        # Verificar se é pilar especial
        is_pilar_especial = hasattr(interface_principal, 'ativar_pilar_especial') and interface_principal.ativar_pilar_especial.get()
        print(f"[PILAR_ESPECIAL] É pilar especial: {is_pilar_especial}")
        print(f"[PILAR_ESPECIAL] hasattr ativar_pilar_especial: {hasattr(interface_principal, 'ativar_pilar_especial')}")
        if hasattr(interface_principal, 'ativar_pilar_especial'):
            print(f"[PILAR_ESPECIAL] ativar_pilar_especial.get(): {interface_principal.ativar_pilar_especial.get()}")
        
        # Nome do pilar - PRIORIDADE: Ler do gerador que foi preenchido com o valor correto do Excel
        # Se não estiver no gerador, tentar ler da interface_principal
        nome_pilar = None
        
        # PRIMEIRO: Tentar ler do gerador (que foi preenchido com o valor correto da coluna atual)
        if hasattr(gerador, 'campos') and 'nome' in gerador.campos:
            nome_pilar = gerador.campos['nome'].get().strip()
            print(f"[PILAR_ESPECIAL] Nome do pilar lido do GERADOR (valor correto do Excel): '{nome_pilar}'")
        
        # SEGUNDO: Se não estiver no gerador, tentar ler da interface_principal
        if not nome_pilar and hasattr(interface_principal, 'nome_pilar'):
            try:
                nome_pilar = interface_principal.nome_pilar.get().strip()
                print(f"[PILAR_ESPECIAL] Nome do pilar lido da INTERFACE PRINCIPAL: '{nome_pilar}'")
            except:
                pass
        
        # VALIDAÇÃO: Verificar se o nome do pilar está correto
        if not nome_pilar or not str(nome_pilar).strip():
            print(f"[PILAR_ESPECIAL] ⚠️ ERRO: Nome do pilar vazio ou inválido: '{nome_pilar}'")
            return None
        
        print(f"[VALIDACAO] Nome do pilar confirmado: '{nome_pilar}'")
        print(f"  - Valor lido: {nome_pilar}")
        
        # SEMPRE usar nome_pilar diretamente para garantir consistência
        # Não criar nome_final para evitar confusão (P8 gerar P9)
        
        if 'nome' in gerador.campos:
            gerador.campos['nome'].delete(0, 'end')
            gerador.campos['nome'].insert(0, nome_pilar)  # Usar nome_pilar diretamente
            print(f"  - Nome preenchido com sucesso no gerador!")
        else:
            print(f"  - ERRO: Campo 'nome' não encontrado no gerador")
            return None
        
        # Dados básicos - usar gerador que já foi preenchido, ou tentar interface se disponível
        # O gerador já foi preenchido anteriormente com os dados corretos do Excel
        campos_para_preencher = ['comprimento', 'largura', 'pavimento', 'nivel_saida', 'nivel_chegada', 'altura']
        for campo in campos_para_preencher:
            # Tentar usar gerador (já preenchido)
            if campo in gerador.campos and hasattr(gerador.campos[campo], 'get'):
                valor_gerador = gerador.campos[campo].get()
                if valor_gerador:
                    print(f"  Usando valor do gerador para {campo}: {valor_gerador}")
                    continue
            
            # Se não houver valor no gerador, tentar interface_principal (apenas se o atributo existir)
            campo_interface = campo
            if campo == 'pavimento':
                campo_interface = 'pavimento_var'
            
            if hasattr(interface_principal, campo_interface):
                try:
                    valor = getattr(interface_principal, campo_interface).get()
                    print(f"  Preenchendo {campo} da interface: {valor}")
                    if campo in gerador.campos:
                        gerador.campos[campo].delete(0, 'end')
                        gerador.campos[campo].insert(0, str(valor))
                except (AttributeError, TypeError) as e:
                    print(f"  ⚠️ Não foi possível preencher {campo} da interface: {e}")
                    # Continuar sem preencher este campo
            else:
                print(f"  ⚠️ Campo {campo_interface} não encontrado na interface_principal (pode ser ambiente de teste)")
        
        # Preencher parafusos
        if usar_parafusos_especiais:
            print(f"Preenchendo parafusos especiais da letra {letra_parafuso}...")
            
            # Criar globais de parafusos especiais A para Script 1
            if not usar_paineis_efgh:  # Apenas para Script 1
                print(f"[GLOBAIS_PARAFUSOS] Criando globais de parafusos especiais A para Script 1...")
                gerador.parafusos_globais_especiais_a = []
                for i in range(1, 9):  # par_a_1 a par_a_8
                    campo_parafuso = f"par_a_{i}"
                    if hasattr(interface_principal, campo_parafuso):
                        valor = getattr(interface_principal, campo_parafuso).get()
                        valor_float = float(valor) if valor and valor != '' else 0.0
                        gerador.parafusos_globais_especiais_a.append(valor_float)
                        print(f"  [GLOBAL] parafuso_a_{i}: {valor_float}")
                    else:
                        gerador.parafusos_globais_especiais_a.append(0.0)
                        print(f"  [GLOBAL] parafuso_a_{i}: 0.0 (campo não encontrado)")
                
                print(f"[GLOBAIS_PARAFUSOS] Globais criadas: {gerador.parafusos_globais_especiais_a}")
            
            # Criar globais de parafusos especiais E e F para Script 2
            if usar_paineis_efgh:  # Apenas para Script 2
                print(f"[GLOBAIS_PARAFUSOS] Criando globais de parafusos especiais E e F para Script 2...")
                
                # Criar globais de parafusos E
                gerador.parafusos_globais_especiais_e = []
                for i in range(1, 9):  # par_e_1 a par_e_8
                    campo_parafuso = f"par_e_{i}"
                    if hasattr(interface_principal, campo_parafuso):
                        valor = getattr(interface_principal, campo_parafuso).get()
                        valor_float = float(valor) if valor and valor != '' else 0.0
                        gerador.parafusos_globais_especiais_e.append(valor_float)
                        print(f"  [GLOBAL E] parafuso_e_{i}: {valor_float}")
                    else:
                        gerador.parafusos_globais_especiais_e.append(0.0)
                        print(f"  [GLOBAL E] parafuso_e_{i}: 0.0 (campo não encontrado)")
                
                # Criar globais de parafusos F
                gerador.parafusos_globais_especiais_f = []
                for i in range(1, 9):  # par_f_1 a par_f_8
                    campo_parafuso = f"par_f_{i}"
                    if hasattr(interface_principal, campo_parafuso):
                        valor = getattr(interface_principal, campo_parafuso).get()
                        valor_float = float(valor) if valor and valor != '' else 0.0
                        gerador.parafusos_globais_especiais_f.append(valor_float)
                        print(f"  [GLOBAL F] parafuso_f_{i}: {valor_float}")
                    else:
                        gerador.parafusos_globais_especiais_f.append(0.0)
                        print(f"  [GLOBAL F] parafuso_f_{i}: 0.0 (campo não encontrado)")
                
                print(f"[GLOBAIS_PARAFUSOS] Globais E criadas: {gerador.parafusos_globais_especiais_e}")
                print(f"[GLOBAIS_PARAFUSOS] Globais F criadas: {gerador.parafusos_globais_especiais_f}")
            
            for i in range(1, 9):  # par_1 a par_8
                campo_parafuso = f"par_{letra_parafuso.lower()}_{i}"
                if hasattr(interface_principal, campo_parafuso):
                    valor = getattr(interface_principal, campo_parafuso).get()
                    if i-1 < len(gerador.parafuso_entries):
                        gerador.parafuso_entries[i-1].delete(0, 'end')
                        gerador.parafuso_entries[i-1].insert(0, valor)
                        print(f"  Preenchendo {campo_parafuso}: {valor}")
        else:
            print(f"Preenchendo parafusos normais...")
            for i in range(1, 9):
                campo_parafuso = f"parafuso_p{i}_p{i+1}"
                if hasattr(interface_principal, campo_parafuso):
                    valor = getattr(interface_principal, campo_parafuso).get()
                    if i-1 < len(gerador.parafuso_entries):
                        gerador.parafuso_entries[i-1].delete(0, 'end')
                        gerador.parafuso_entries[i-1].insert(0, valor)
                        print(f"  Preenchendo {campo_parafuso}: {valor}")
        
        # Preencher dados dos painéis
        if usar_paineis_efgh:
            print(f"Preenchendo dados dos painéis E, F, G, H...")
            paineis_originais = ['E', 'F', 'G', 'H']
            paineis_destino = ['A', 'B', 'C', 'D']
            print(f"[DEBUG] Mapeamento: E→A, F→B, G→C, H→D")
        else:
            print(f"Preenchendo dados dos painéis A, B, C, D...")
            paineis_originais = ['A', 'B', 'C', 'D']
            paineis_destino = ['A', 'B', 'C', 'D']
            print(f"[DEBUG] Mapeamento: A→A, B→B, C→C, D→D")
        
        for i, (orig, dest) in enumerate(zip(paineis_originais, paineis_destino)):
            print(f"Preenchendo dados do Painel {dest} (fonte: {orig})...")
            
            # Para Script 2 (E,F,G,H), preencher com zeros pois as globais já foram calculadas
            # Os painéis E,F,G,H não precisam de larguras/alturas específicas no script
            # pois as globais calculadas já definem as dimensões corretas
            if usar_paineis_efgh:
                print(f"  [SCRIPT2] Usando globais calculadas para painel {orig} -> {dest}")
                
                # CORRIGIDO: NÃO sobrescrever lajes no Script 2
                # As lajes já foram preenchidas corretamente pela função _preencher_robo_com_dados_efgh
                # Apenas manter os valores já preenchidos
                valor_laje_atual = gerador.campos[f'laje_{dest.lower()}'].get()
                print(f"  [SCRIPT2] Laje_{dest.lower()} já preenchida: {valor_laje_atual}")
                
                # Posição da laje também já foi preenchida
                if hasattr(gerador, f'pos_laje_{dest.lower()}'):
                    valor_pos_atual = getattr(gerador, f'pos_laje_{dest.lower()}').get()
                    print(f"  [SCRIPT2] Pos_laje_{dest.lower()} já preenchida: {valor_pos_atual}")
                
                # Larguras - usar dados já preenchidos (as globais já foram aplicadas)
                # CORRIGIDO: Robô ABCD só tem comp1 e comp2, não comp3!
                max_larguras = 2  # Todos os painéis têm apenas 2 larguras no robô ABCD
                for j in range(1, max_larguras + 1):
                    if dest.lower() in ['c', 'd']:
                        valor_larg = gerador.campos_cd[f'comp{j}_{dest.lower()}'].get()
                    else:
                        valor_larg = gerador.campos_ab[f'comp{j}_{dest.lower()}'].get()
                    
                    if valor_larg in [None, '']:
                        valor_larg = '0'
                    
                    print(f"  [SCRIPT2] Comp{j}_{dest.lower()}: {valor_larg} (globais aplicadas)")
                
                # Alturas - usar dados já preenchidos (as globais já foram aplicadas)
                max_alturas = 5 if dest.lower() in ['a', 'b'] else 4
                for j in range(1, max_alturas + 1):
                    _lista_alt = gerador.campos_altura.get(dest.lower(), [])
                    if (j - 1) < len(_lista_alt):
                        valor_alt = _lista_alt[j-1].get()
                        if valor_alt in [None, '']:
                            valor_alt = '0'
                        print(f"  [SCRIPT2] Altura {dest.lower()}[{j}]: {valor_alt} (globais aplicadas)")
                    else:
                        print(f"  [DEBUG] Altura {dest.lower()}[{j}] inexistente, pulando")
            else:
                # Script 1 (A,B,C,D) - usar dados já preenchidos no robô
                print(f"  [SCRIPT1] Usando dados já preenchidos no robô para painel {orig} -> {dest}")
                
                # Laje - usar dados já preenchidos
                valor_laje = gerador.campos[f'laje_{dest.lower()}'].get()
                if valor_laje in [None, '']:
                    valor_laje = '0'
                print(f"  [SCRIPT1] Laje {dest.lower()}: {valor_laje}")
                
                # Posição da laje - usar dados já preenchidos
                if hasattr(gerador, f'pos_laje_{dest.lower()}'):
                    valor_pos = getattr(gerador, f'pos_laje_{dest.lower()}').get()
                    print(f"  [SCRIPT1] Posição laje {dest.lower()}: {valor_pos}")
                
                # Larguras - usar dados já preenchidos
                # CORRIGIDO: Robô ABCD só tem comp1 e comp2, não comp3!
                max_larguras = 2  # Todos os painéis têm apenas 2 larguras no robô ABCD
                for j in range(1, max_larguras + 1):
                    if dest.lower() in ['c', 'd']:
                        valor_larg = gerador.campos_cd[f'comp{j}_{dest.lower()}'].get()
                    else:
                        valor_larg = gerador.campos_ab[f'comp{j}_{dest.lower()}'].get()
                    
                    if valor_larg in [None, '']:
                        valor_larg = '0'
                    
                    print(f"  [SCRIPT1] Comp{j}_{dest.lower()}: {valor_larg}")
                
                # Alturas - usar dados já preenchidos
                max_alturas = 5 if dest.lower() in ['a', 'b'] else 4
                for j in range(1, max_alturas + 1):
                    _lista_alt = gerador.campos_altura.get(dest.lower(), [])
                    if (j - 1) < len(_lista_alt):
                        valor_alt = _lista_alt[j-1].get()
                        if valor_alt in [None, '']:
                            valor_alt = '0'
                        print(f"  [SCRIPT1] Altura {dest.lower()}[{j}]: {valor_alt}")
                    else:
                        print(f"  [DEBUG] Altura {dest.lower()}[{j}] inexistente, pulando")
        
        # Ajustar offset X se necessário
        if ajustar_x_offset:
            print(f"[PILAR_ESPECIAL] Aplicando offset X +1585...")
            # CORREÇÃO: Aplicar offset X +1585 APENAS aos painéis principais, não a todos os elementos
            # Salvar x_inicial original para restaurar depois
            if hasattr(gerador, 'x_inicial'):
                x_original = gerador.x_inicial
                gerador.x_inicial = x_original + 1585
                print(f"  - X original: {x_original}, X ajustado: {gerador.x_inicial}")
                # Armazenar o offset para restaurar depois
                gerador._offset_x_aplicado = 1585
                gerador._x_inicial_original = x_original
            else:
                print(f"  - AVISO: Atributo x_inicial não encontrado no gerador")
                # Tentar outros atributos possíveis
                if hasattr(gerador, 'x_base'):
                    x_original = gerador.x_base
                    gerador.x_base = x_original + 1585
                    print(f"  - X base original: {x_original}, X base ajustado: {gerador.x_base}")
                elif hasattr(gerador, 'posicao_x'):
                    x_original = gerador.posicao_x
                    gerador.posicao_x = x_original + 1585
                    print(f"  - Posição X original: {x_original}, Posição X ajustada: {gerador.posicao_x}")
                else:
                    print(f"  - ERRO: Não foi possível encontrar atributo de coordenada X no gerador")
                    print(f"  - Atributos disponíveis: {[attr for attr in dir(gerador) if 'x' in attr.lower()]}")
        
        # Criar 8 variáveis globais para larguras dos painéis A-H
        print(f"[GLOBAIS_LARGURAS] Criando 8 variáveis globais de larguras...")
        larguras_globais = {}
        
        if usar_paineis_efgh:
            print(f"[GLOBAIS_LARGURAS] Script 2 - Coletando larguras E, F, G, H...")
            # Mapear E→A, F→B, G→C, H→D
            # CORRIGIDO: Armazenar com as chaves A,B,C,D (não E,F,G,H) pois o robô ABCD usa A,B,C,D
            mapeamento = {'e': 'a', 'f': 'b', 'g': 'c', 'h': 'd'}
            for painel_orig, painel_dest in mapeamento.items():
                try:
                    # Coletar larguras dos campos do robô ABCD
                    if painel_dest in ['a', 'b']:
                        # Painéis A e B têm 2 campos de largura (comp1 e comp2)
                        larg1 = float(gerador.campos_ab[f'comp1_{painel_dest}'].get() or 0)
                        larg2 = float(gerador.campos_ab[f'comp2_{painel_dest}'].get() or 0)
                    else:
                        # Painéis C e D têm 2 campos de largura
                        larg1 = float(gerador.campos_cd[f'comp1_{painel_dest}'].get() or 0)
                        larg2 = float(gerador.campos_cd[f'comp2_{painel_dest}'].get() or 0)
                    
                    largura_total = larg1 + larg2
                    # CORRIGIDO: Usar painel_dest (a,b,c,d) ao invés de painel_orig (e,f,g,h)
                    larguras_globais[painel_dest] = largura_total
                    print(f"  - GLOBAL_{painel_orig.upper()}→{painel_dest.upper()}: {larg1} + {larg2} = {largura_total}")
                except (ValueError, AttributeError) as e:
                    print(f"  - Erro ao coletar larguras do painel {painel_orig.upper()}: {e}")
                    larguras_globais[painel_dest] = 0
        else:
            print(f"[GLOBAIS_LARGURAS] Script 1 - Coletando larguras A, B, C, D...")
            # Coletar larguras padrão (A, B, C, D)
            for painel in ['a', 'b', 'c', 'd']:
                try:
                    if painel in ['a', 'b']:
                        # Painéis A e B têm 3 campos de largura (comp1, comp2 e comp3)
                        larg1 = float(gerador.campos_ab[f'comp1_{painel}'].get() or 0)
                        larg2 = float(gerador.campos_ab[f'comp2_{painel}'].get() or 0)
                        larg3 = float(gerador.campos_ab[f'comp3_{painel}'].get() or 0)
                    else:
                        # Painéis C e D têm 2 campos de largura
                        larg1 = float(gerador.campos_cd[f'comp1_{painel}'].get() or 0)
                        larg2 = float(gerador.campos_cd[f'comp2_{painel}'].get() or 0)
                    
                    if painel in ['a', 'b']:
                        print(f"  - DEBUG: Processando painel {painel.upper()}")
                        print(f"  - DEBUG: is_pilar_especial = {is_pilar_especial}")
                        print(f"  - DEBUG: painel == 'b' = {painel == 'b'}")
                        print(f"  - DEBUG: painel == 'b' and is_pilar_especial = {painel == 'b' and is_pilar_especial}")
                        
                        # Para painel B especial, usar grade B total + 2 APENAS se for pilar especial
                        # MAS apenas se os campos ainda não foram preenchidos no robô
                        if painel == 'b' and is_pilar_especial:
                            print(f"  - DEBUG: Aplicando grade B especial para painel B (pilar especial ativo)")
                            
                            # IMPORTANTE: Se os campos do robô já estão preenchidos, usar esses valores
                            # ao invés de tentar ler da interface (que pode estar vazia no momento)
                            
                            # Verificar se comp1_b do robô já tem valor significativo
                            comp1_valor = float(gerador.campos_ab['comp1_b'].get() or 0)
                            
                            if comp1_valor > 0:
                                # Campos já preenchidos no robô - usar valores normais
                                print(f"  - DEBUG: Campos do robô já preenchidos (comp1_b={comp1_valor}), usando valores normais")
                                largura_total = larg1 + larg2 + larg3
                                larguras_distribuidas = _distribuir_largura_especial(largura_total)
                            else:
                                # Campos vazios - aplicar Grade B especial da interface
                                print(f"  - DEBUG: Campos do robô vazios, tentando Grade B especial da interface")
                                try:
                                    # Verificar se os campos existem na interface
                                    grade1_b = 0
                                    grade2_b = 0
                                    grade3_b = 0
                                    dist1_b = 0
                                    dist2_b = 0
                                    
                                    if hasattr(interface_principal, 'grade_b_1'):
                                        grade1_b = float(interface_principal.grade_b_1.get() or 0)
                                    if hasattr(interface_principal, 'grade_b_2'):
                                        grade2_b = float(interface_principal.grade_b_2.get() or 0)
                                    if hasattr(interface_principal, 'grade_b_3'):
                                        grade3_b = float(interface_principal.grade_b_3.get() or 0)
                                    if hasattr(interface_principal, 'dist_b_1'):
                                        dist1_b = float(interface_principal.dist_b_1.get() or 0)
                                    if hasattr(interface_principal, 'dist_b_2'):
                                        dist2_b = float(interface_principal.dist_b_2.get() or 0)
                                    
                                    grade_b_total = grade1_b + grade2_b + grade3_b + dist1_b + dist2_b + 2
                                    print(f"  - GRADE_B_ESPECIAL: {grade1_b} + {grade2_b} + {grade3_b} + {dist1_b} + {dist2_b} + 2 = {grade_b_total}")
                                    
                                    # Se a grade B especial retornar só 2cm, usar valores normais do robô
                                    if grade_b_total <= 2:
                                        print(f"  - AVISO: Grade B especial retornou apenas {grade_b_total}cm, usando valores normais")
                                        largura_total = larg1 + larg2 + larg3
                                    else:
                                        largura_total = grade_b_total
                                    
                                    # Distribuir grade B total nos 3 campos (máximo 244 por campo)
                                    larguras_distribuidas = _distribuir_largura_especial(largura_total)
                                    
                                except (ValueError, AttributeError) as e:
                                    print(f"  - ERRO ao calcular grade B especial: {e}, usando valores normais")
                                    # Fallback para valores normais
                                    largura_total = larg1 + larg2 + larg3
                                    larguras_distribuidas = _distribuir_largura_especial(largura_total)
                        else:
                            # Painel A ou B normal: usar valores normais
                            print(f"  - DEBUG: Usando valores normais para painel {painel.upper()}")
                            largura_total = larg1 + larg2 + larg3
                            larguras_distribuidas = _distribuir_largura_especial(largura_total)
                        
                        # Aplicar distribuição nos campos do robô
                        gerador.campos_ab[f'comp1_{painel}'].delete(0, 'end')
                        gerador.campos_ab[f'comp1_{painel}'].insert(0, str(larguras_distribuidas[0]))
                        gerador.campos_ab[f'comp2_{painel}'].delete(0, 'end')
                        gerador.campos_ab[f'comp2_{painel}'].insert(0, str(larguras_distribuidas[1]))
                        gerador.campos_ab[f'comp3_{painel}'].delete(0, 'end')
                        gerador.campos_ab[f'comp3_{painel}'].insert(0, str(larguras_distribuidas[2]))
                        
                        larguras_globais[painel] = largura_total
                        if painel == 'b' and is_pilar_especial:
                            print(f"  - GLOBAL_{painel.upper()}: largura_total = {largura_total}")
                        else:
                            print(f"  - GLOBAL_{painel.upper()}: {larg1} + {larg2} + {larg3} = {largura_total}")
                        print(f"  - DISTRIBUIÇÃO_{painel.upper()}: {larguras_distribuidas}")
                    else:
                        largura_total = larg1 + larg2
                        larguras_globais[painel] = largura_total
                        print(f"  - GLOBAL_{painel.upper()}: {larg1} + {larg2} = {largura_total}")
                except (ValueError, AttributeError) as e:
                    print(f"  - Erro ao coletar larguras do painel {painel.upper()}: {e}")
                    larguras_globais[painel] = 0
        
        # Enviar as globais para o gerador
        print(f"[GLOBAIS_LARGURAS] Enviando globais para o gerador...")
        gerador.larguras_globais = larguras_globais
        
        # CRÍTICO: SEMPRE resetar flag ANTES de definir para evitar persistência entre scripts/pilares
        # O mesmo gerador é reutilizado para todos os pilares, então a flag pode ter sido definida anteriormente
        if hasattr(gerador, 'usar_paineis_efgh'):
            flag_anterior = gerador.usar_paineis_efgh
            print(f"[PILAR_ESPECIAL] Flag usar_paineis_efgh anterior: {flag_anterior} (será resetada)")
            # FORÇAR reset para False primeiro
            gerador.usar_paineis_efgh = False
        else:
            print(f"[PILAR_ESPECIAL] Flag usar_paineis_efgh não existe, criando como False")
            gerador.usar_paineis_efgh = False
        
        # Agora definir o valor correto baseado no parâmetro
        gerador.usar_paineis_efgh = usar_paineis_efgh
        print(f"[PILAR_ESPECIAL] Flag usar_paineis_efgh definida para: {usar_paineis_efgh}")
        print(f"[PILAR_ESPECIAL] Validação: gerador.usar_paineis_efgh = {gerador.usar_paineis_efgh}")
        
        # Gerar o script
        print(f"[PILAR_ESPECIAL] Gerando script...")
        print(f"  - Chamando gerador.gerar_script()...")
        print(f"  - Verificação FINAL antes de gerar: gerador.usar_paineis_efgh = {getattr(gerador, 'usar_paineis_efgh', 'NÃO EXISTE')}")
        
        try:
            # CORREÇÃO: Para Script 2 (sufixo_nome='2'), não salvar automaticamente para evitar sobrescrever Script 1
            # Para Script 1 (sufixo_nome=''), salvar automaticamente é OK
            salvar_automatico = not sufixo_nome  # True se sufixo_nome estiver vazio (Script 1), False se tiver sufixo (Script 2)
            script_content = gerador.gerar_script(salvar_arquivo=salvar_automatico)
            if script_content:
                print(f"  - Script gerado com sucesso!")
                
                # Salvar o script
                # Usar path resolver para obter o caminho correto
                import sys
                sys.path.append(os.path.dirname(os.path.dirname(__file__)))
                from utils.robust_path_resolver import robust_path_resolver
                
                # Tentar ler pavimento da interface_principal, com fallback para o gerador
                try:
                    if hasattr(interface_principal, 'pavimento_var'):
                        pavimento = interface_principal.pavimento_var.get()
                    elif hasattr(gerador, 'campos') and 'pavimento' in gerador.campos:
                        pavimento = gerador.campos['pavimento'].get()
                    else:
                        pavimento = "SEM_PAVIMENTO"
                        print(f"[PILAR_ESPECIAL] Aviso: pavimento não encontrado, usando '{pavimento}'")
                except (AttributeError, KeyError) as e:
                    print(f"[PILAR_ESPECIAL] Erro ao ler pavimento: {e}, usando 'SEM_PAVIMENTO'")
                    pavimento = "SEM_PAVIMENTO"
                
                # Usar path resolver para garantir o caminho correto
                diretorio_base = os.path.join(robust_path_resolver.get_project_root(), "output", "scripts")
                nome_pasta_pavimento = str(pavimento).replace(" ", "_")
                if not nome_pasta_pavimento.upper().endswith("_ABCD"):
                    nome_pasta_pavimento += "_ABCD"
                
                pasta_pavimento = os.path.join(diretorio_base, nome_pasta_pavimento)
                os.makedirs(pasta_pavimento, exist_ok=True)
                
                # VALIDAÇÃO: SEMPRE usar nome_pilar diretamente para garantir consistência
                # Isso evita problemas como P8 gerar P9 ou P82 não aparecer
                if sufixo_nome:
                    nome_arquivo = f"{nome_pilar}_ABCD{sufixo_nome}.scr"
                else:
                    nome_arquivo = f"{nome_pilar}_ABCD.scr"
                
                print(f"[VALIDACAO] Nome do arquivo gerado: '{nome_arquivo}' (pilar: '{nome_pilar}', sufixo: '{sufixo_nome}')")
                
                caminho_script = os.path.join(pasta_pavimento, nome_arquivo)
                
                # CORREÇÃO: Salvar manualmente apenas se não foi salvo automaticamente (Script 2)
                # Se foi salvo automaticamente (Script 1), apenas verificar se o caminho está correto
                if not salvar_automatico:
                    # Garantir que o script termine com nova linha para o AutoCAD processar corretamente
                    if script_content and not script_content.endswith('\r\n'):
                        # Normalizar para terminar com \r\n (nova linha do Windows)
                        script_content = script_content.rstrip('\n').rstrip('\r') + '\r\n'
                    
                    # Salvar com UTF-16 LE (com BOM) para compatibilidade com AutoCAD
                    with open(caminho_script, 'wb') as f:
                        # Adicionar BOM UTF-16 LE
                        f.write(b'\xFF\xFE')
                        # Converter conteúdo para UTF-16 LE
                        f.write(script_content.encode('utf-16-le'))
                    
                    print(f"  - Script salvo como: {nome_arquivo}")
                else:
                    # Script 1 foi salvo automaticamente, apenas verificar se o caminho está correto
                    caminho_esperado = os.path.join(pasta_pavimento, nome_arquivo)
                    if os.path.exists(caminho_esperado):
                        print(f"  - Script salvo automaticamente como: {nome_arquivo}")
                        caminho_script = caminho_esperado
                    else:
                        print(f"[PILAR_ESPECIAL] Aviso: Script 1 não encontrado no caminho esperado, salvando manualmente...")
                        # Garantir que o script termine com nova linha para o AutoCAD processar corretamente
                        if script_content and not script_content.endswith('\r\n'):
                            script_content = script_content.rstrip('\n').rstrip('\r') + '\r\n'
                        
                        # Salvar com UTF-16 LE (com BOM) para compatibilidade com AutoCAD
                        with open(caminho_script, 'wb') as f:
                            f.write(b'\xFF\xFE')
                            f.write(script_content.encode('utf-16-le'))
                        
                        print(f"  - Script salvo como: {nome_arquivo}")
                print(f"[PILAR_ESPECIAL] ========================================")
                print(f"[PILAR_ESPECIAL] SCRIPT GERADO COM SUCESSO!")
                print(f"[PILAR_ESPECIAL] ========================================")
                
                # CORREÇÃO: Restaurar x_inicial original após gerar o script
                if ajustar_x_offset and hasattr(gerador, '_offset_x_aplicado'):
                    print(f"[PILAR_ESPECIAL] Restaurando x_inicial original...")
                    gerador.x_inicial = gerador._x_inicial_original
                    print(f"  - X restaurado para: {gerador.x_inicial}")
                    # Limpar variáveis temporárias
                    delattr(gerador, '_offset_x_aplicado')
                    delattr(gerador, '_x_inicial_original')
                
                # IMPORTANTE: Resetar flag após gerar o script para evitar persistência entre scripts
                print(f"[PILAR_ESPECIAL] Resetando flag usar_paineis_efgh após gerar script")
                gerador.usar_paineis_efgh = False
                print(f"[PILAR_ESPECIAL] Flag resetada: {gerador.usar_paineis_efgh}")
                
                return caminho_script
            else:
                print(f"  - ERRO: Script não foi gerado")
                return None
                
        except Exception as e:
            print(f"  - ERRO ao gerar script: {e}")
            import traceback
            traceback.print_exc()
            return None
            
    except Exception as e:
        print(f"[PILAR_ESPECIAL] ERRO geral: {e}")
        import traceback
        traceback.print_exc()
        return None

def preencher_campos_e_gerar_scripts(caminho_arquivo_excel, coluna_especifica=None, interface_principal=None, gerar_pelo_pavimento=False):
    """
    Lê os dados da primeira aba de uma planilha Excel, preenche os campos da interface
    ABCD e gera os scripts .scr correspondentes.

    Args:
        caminho_arquivo_excel: O caminho para o arquivo Excel.
        coluna_especifica: A coluna específica a ser processada.
    """

    try:
        # Carrega a planilha
        workbook = openpyxl.load_workbook(caminho_arquivo_excel, data_only=True)
        sheet = workbook.worksheets[0]  # Obtém a primeira aba

        # Mapeamento de linhas para campos da interface ABCD
        # Baseado no mapeamento do arquivo aa copy 6
        linhas_abcd = {
            'nome': 4,                 # Nome do pilar
            'pavimento': 3,            # Pavimento
            'nivel_saida': 8,          # Nível de Saída
            'nivel_chegada': 9,        # Nível de Chegada
            'comprimento': 6,          # Comprimento
            'largura': 7,              # Largura
            'altura': 12,              # Altura
            
            # Painéis
            'laje_a': 13,              # Laje A
            'laje_b': 55,              # Laje B
            'laje_c': 97,              # Laje C
            'laje_d': 131,             # Laje D
            'laje_e': 250,             # Laje E (Pilar Especial)
            'laje_f': 260,             # Laje F (Pilar Especial)
            'laje_g': 270,             # Laje G (Pilar Especial)
            'laje_h': 280,             # Laje H (Pilar Especial)
            
            # Posições das lajes
            'posicao_laje_a': 14,      # Posição Laje A
            'posicao_laje_b': 56,      # Posição Laje B
            'posicao_laje_c': 98,      # Posição Laje C
            'posicao_laje_d': 132,     # Posição Laje D
            'posicao_laje_e': 251,     # Posição Laje E (Pilar Especial)
            'posicao_laje_f': 261,     # Posição Laje F (Pilar Especial)
            'posicao_laje_g': 271,     # Posição Laje G (Pilar Especial)
            'posicao_laje_h': 281,     # Posição Laje H (Pilar Especial)
            
            # Parafusos
            'parafuso_p1_p2': 173,  # Atualizado para P1-P2
            'parafuso_p2_p3': 174,  
            'parafuso_p3_p4': 175,  
            'parafuso_p4_p5': 176,  
            'parafuso_p5_p6': 177,  
            'parafuso_p6_p7': 178,  
            'parafuso_p7_p8': 179,  
            'parafuso_p8_p9': 180,  # Adicionado para P8-P9
            
            # Painel A - Larguras e Alturas
            'largura_1_painel_a': 15,  # Largura 1 A
            'largura_2_painel_a': 16,  # Largura 2 A
            'largura_3_painel_a': 17,  # Largura 3 A
            'altura_1_painel_a': 18,   # Altura 1 A
            'altura_2_painel_a': 19,   # Altura 2 A
            'altura_3_painel_a': 20,   # Altura 3 A
            'altura_4_painel_a': 21,   # Altura 4 A
            'altura_5_painel_a': 22,   # Altura 5 A

            # Aberturas A Esquerda
            'abertura_esq1_dist_a': 25,  # Distância Abertura 1 Esquerda A
            'abertura_esq1_prof_a': 26,  # Profundidade Abertura 1 Esquerda A
            'abertura_esq1_larg_a': 27,  # Largura Abertura 1 Esquerda A
            'abertura_esq1_pos_a': 28,   # Posição Abertura 1 Esquerda A
            'abertura_esq2_dist_a': 29,  # Distância Abertura 2 Esquerda A
            'abertura_esq2_prof_a': 30,  # Profundidade Abertura 2 Esquerda A
            'abertura_esq2_larg_a': 31,  # Largura Abertura 2 Esquerda A
            'abertura_esq2_pos_a': 32,   # Posição Abertura 2 Esquerda A

            # Aberturas A Direita
            'abertura_dir1_dist_a': 33,  # Distância Abertura 1 Direita A
            'abertura_dir1_prof_a': 34,  # Profundidade Abertura 1 Direita A
            'abertura_dir1_larg_a': 35,  # Largura Abertura 1 Direita A
            'abertura_dir1_pos_a': 36,   # Posição Abertura 1 Direita A
            'abertura_dir2_dist_a': 37,  # Distância Abertura 2 Direita A
            'abertura_dir2_prof_a': 38,  # Profundidade Abertura 2 Direita A
            'abertura_dir2_larg_a': 39,  # Largura Abertura 2 Direita A
            'abertura_dir2_pos_a': 40,   # Posição Abertura 2 Direita A
            
            # Hatch Painel A
            'hatch_l1_h2_a': 43,
            'hatch_l1_h3_a': 44,
            'hatch_l1_h4_a': 45,
            'hatch_l1_h5_a': 46,
            'hatch_l2_h2_a': 47,
            'hatch_l2_h3_a': 48,
            'hatch_l2_h4_a': 49,
            'hatch_l2_h5_a': 50,
            'hatch_l3_h2_a': 51,
            'hatch_l3_h3_a': 52,
            'hatch_l3_h4_a': 53,
            'hatch_l3_h5_a': 54,
            
            # Painel B - Larguras e Alturas
            'largura_1_painel_b': 57,  # Largura 1 B
            'largura_2_painel_b': 58,  # Largura 2 B
            'largura_3_painel_b': 59,  # Largura 3 B
            'altura_1_painel_b': 60,   # Altura 1 B
            'altura_2_painel_b': 61,   # Altura 2 B
            'altura_3_painel_b': 62,   # Altura 3 B
            'altura_4_painel_b': 63,   # Altura 4 B
            'altura_5_painel_b': 64,   # Altura 5 B

            # Aberturas B Esquerda
            'abertura_esq1_pos_b': 70,   # Posição Abertura 1 Esquerda B
            'abertura_esq1_dist_b': 67,  # Distância Abertura 1 Esquerda B
            'abertura_esq1_larg_b': 69,  # Largura Abertura 1 Esquerda B
            'abertura_esq1_prof_b': 68,  # Profundidade Abertura 1 Esquerda B
            'abertura_esq2_pos_b': 74,   # Posição Abertura 2 Esquerda B
            'abertura_esq2_dist_b': 71,  # Distância Abertura 2 Esquerda B
            'abertura_esq2_larg_b': 73,  # Largura Abertura 2 Esquerda B
            'abertura_esq2_prof_b': 72,  # Profundidade Abertura 2 Esquerda B

            # Aberturas B Direita
            'abertura_dir1_pos_b': 78,   # Posição Abertura 1 Direita B
            'abertura_dir1_dist_b': 75,  # Distância Abertura 1 Direita B
            'abertura_dir1_larg_b': 77,  # Largura Abertura 1 Direita B
            'abertura_dir1_prof_b': 76,  # Profundidade Abertura 1 Direita B
            'abertura_dir2_pos_b': 82,   # Posição Abertura 2 Direita B
            'abertura_dir2_dist_b': 79,  # Distância Abertura 2 Direita B
            'abertura_dir2_larg_b': 81,  # Largura Abertura 2 Direita B
            'abertura_dir2_prof_b': 80,  # Profundidade Abertura 2 Direita B
            
            # Hatch Painel B
            'hatch_l1_h2_b': 85,
            'hatch_l1_h3_b': 86,
            'hatch_l1_h4_b': 87,
            'hatch_l1_h5_b': 88,
            'hatch_l2_h2_b': 89,
            'hatch_l2_h3_b': 90,
            'hatch_l2_h4_b': 91,
            'hatch_l2_h5_b': 92,
            'hatch_l3_h2_b': 93,
            'hatch_l3_h3_b': 94,
            'hatch_l3_h4_b': 95,
            'hatch_l3_h5_b': 96,
            
            # Painel C - Larguras e Alturas
            'larg1_C': 99,    # Largura 1 C
            'larg2_C': 100,   # Largura 2 C
            'h1_C': 101,      # Altura 1 C
            'h2_C': 102,      # Altura 2 C
            'h3_C': 103,      # Altura 3 C
            'h4_C': 104,      # Altura 4 C
            
            # Aberturas C Esquerda e Direita
            'abertura_esq1_dist_c': 108,
            'abertura_esq1_prof_c': 109,
            'abertura_esq1_larg_c': 110,
            'abertura_esq1_pos_c': 111,
            'abertura_esq2_dist_c': 112,
            'abertura_esq2_prof_c': 113,
            'abertura_esq2_larg_c': 114,
            'abertura_esq2_pos_c': 115,
            'abertura_dir1_dist_c': 116,
            'abertura_dir1_prof_c': 117,
            'abertura_dir1_larg_c': 118,
            'abertura_dir1_pos_c': 119,
            'abertura_dir2_dist_c': 120,
            'abertura_dir2_prof_c': 121,
            'abertura_dir2_larg_c': 122,
            'abertura_dir2_pos_c': 123,
            
            # Hatch Painel C
            'hatch_l1_h2_c': 125,
            'hatch_l1_h3_c': 126,
            'hatch_l1_h4_c': 127,
            'hatch_l2_h2_c': 128,
            'hatch_l2_h3_c': 129,
            'hatch_l2_h4_c': 130,
            
            # Painel D - Larguras e Alturas
            'larg1_D': 133,  # Largura 1 D
            'larg2_D': 134,  # Largura 2 D
            'h1_D': 135,     # Altura 1 D
            'h2_D': 136,     # Altura 2 D
            'h3_D': 137,     # Altura 3 D
            'h4_D': 138,     # Altura 4 D
            
            # Aberturas D Esquerda e Direita
            'abertura_esq1_pos_d': 145,
            'abertura_esq1_dist_d': 142,
            'abertura_esq1_larg_d': 144,
            'abertura_esq1_prof_d': 143,
            'abertura_esq2_pos_d': 149,
            'abertura_esq2_dist_d': 146,
            'abertura_esq2_larg_d': 148,
            'abertura_esq2_prof_d': 147,
            'abertura_dir1_pos_d': 153,
            'abertura_dir1_dist_d': 150,
            'abertura_dir1_larg_d': 152,
            'abertura_dir1_prof_d': 151,
            'abertura_dir2_pos_d': 157,
            'abertura_dir2_dist_d': 154,
            'abertura_dir2_larg_d': 156,
            'abertura_dir2_prof_d': 155,
            
            # Hatch Painel D
            'hatch_l1_h2_d': 159,
            'hatch_l1_h3_d': 160,
            'hatch_l1_h4_d': 161,
            'hatch_l2_h2_d': 162,
            'hatch_l2_h3_d': 163,
            'hatch_l2_h4_d': 164,
            
            # Painel E (Pilar Especial) - Larguras e Alturas
            'largura_1_painel_e': 252,  # Largura 1 E
            'largura_2_painel_e': 253,  # Largura 2 E
            'largura_3_painel_e': 254,  # Largura 3 E
            'altura_1_painel_e': 255,   # Altura 1 E
            'altura_2_painel_e': 256,   # Altura 2 E
            'altura_3_painel_e': 257,   # Altura 3 E
            'altura_4_painel_e': 258,   # Altura 4 E
            'altura_5_painel_e': 259,   # Altura 5 E
            
            # Painel F (Pilar Especial) - Larguras e Alturas
            'largura_1_painel_f': 262,  # Largura 1 F
            'largura_2_painel_f': 263,  # Largura 2 F
            'largura_3_painel_f': 264,  # Largura 3 F
            'altura_1_painel_f': 265,   # Altura 1 F
            'altura_2_painel_f': 266,   # Altura 2 F
            'altura_3_painel_f': 267,   # Altura 3 F
            'altura_4_painel_f': 268,   # Altura 4 F
            'altura_5_painel_f': 269,   # Altura 5 F
            
            # Painel G (Pilar Especial) - Larguras e Alturas
            'largura_1_painel_g': 272,  # Largura 1 G
            'largura_2_painel_g': 273,  # Largura 2 G
            'largura_3_painel_g': 274,  # Largura 3 G
            'altura_1_painel_g': 275,   # Altura 1 G
            'altura_2_painel_g': 276,   # Altura 2 G
            'altura_3_painel_g': 277,   # Altura 3 G
            'altura_4_painel_g': 278,   # Altura 4 G
            'altura_5_painel_g': 279,   # Altura 5 G
            
            # Painel H (Pilar Especial) - Larguras e Alturas
            'largura_1_painel_h': 282,  # Largura 1 H
            'largura_2_painel_h': 283,  # Largura 2 H
            'largura_3_painel_h': 284,  # Largura 3 H
            'altura_1_painel_h': 285,   # Altura 1 H
            'altura_2_painel_h': 286,   # Altura 2 H
            'altura_3_painel_h': 287,   # Altura 3 H
            'altura_4_painel_h': 288,   # Altura 4 H
            'altura_5_painel_h': 289,   # Altura 5 H
            
            # Aberturas de Laje A (1=laje, 0=normal)
            'abertura_laje_esq1_a': 224,  # Abertura Laje Esquerda 1 A
            'abertura_laje_esq2_a': 225,  # Abertura Laje Esquerda 2 A
            'abertura_laje_dir1_a': 226,  # Abertura Laje Direita 1 A
            'abertura_laje_dir2_a': 227,  # Abertura Laje Direita 2 A
            
            # Aberturas de Laje B (1=laje, 0=normal)
            'abertura_laje_esq1_b': 228,  # Abertura Laje Esquerda 1 B
            'abertura_laje_esq2_b': 229,  # Abertura Laje Esquerda 2 B
            'abertura_laje_dir1_b': 230,  # Abertura Laje Direita 1 B
            'abertura_laje_dir2_b': 231,  # Abertura Laje Direita 2 B
            
            # Aberturas de Laje C (1=laje, 0=normal)
            'abertura_laje_esq1_c': 232,  # Abertura Laje Esquerda 1 C
            'abertura_laje_esq2_c': 233,  # Abertura Laje Esquerda 2 C
            'abertura_laje_dir1_c': 234,  # Abertura Laje Direita 1 C
            'abertura_laje_dir2_c': 235,  # Abertura Laje Direita 2 C
            
            # Aberturas de Laje D (1=laje, 0=normal)
            'abertura_laje_esq1_d': 236,  # Abertura Laje Esquerda 1 D
            'abertura_laje_esq2_d': 237,  # Abertura Laje Esquerda 2 D
            'abertura_laje_dir1_d': 238,  # Abertura Laje Direita 1 D
            'abertura_laje_dir2_d': 239,  # Abertura Laje Direita 2 D
        }

        coluna_base = 'E'  # Coluna inicial para os dados dos pilares
        coluna_base_idx = ord(coluna_base) - ord('A')
        colunas_vazias = 0
        parar_busca = False

        # Função para converter índice numérico para letra de coluna (suporta AA, AB, etc.)
        def coluna_para_letra(col_idx):
            letra = ''
            while col_idx >= 0:
                letra = chr(ord('A') + (col_idx % 26)) + letra
                col_idx = col_idx // 26 - 1
            return letra
            
        # Função para converter letra de coluna para índice numérico
        def letra_para_coluna(letra):
            col_idx = 0
            for i, char in enumerate(reversed(letra)):
                col_idx += (ord(char) - ord('A') + 1) * (26 ** i)
            return col_idx - 1

        # Se uma coluna específica foi fornecida, processar apenas essas colunas
        if coluna_especifica:
            # Suportar lista separada por vírgula (ex: "E,F,G")
            if isinstance(coluna_especifica, str) and "," in coluna_especifica:
                letras = [c.strip() for c in coluna_especifica.split(",") if c.strip()]
                colunas_a_processar = [letra_para_coluna(c) for c in letras]
                print(f"Processando colunas {','.join(letras)}")
            else:
                colunas_a_processar = [letra_para_coluna(coluna_especifica)]
                print(f"Processando apenas a coluna {coluna_especifica}")
        else:
            # Caso contrário, iterar por todas as colunas a partir da coluna base
            colunas_a_processar = range(coluna_base_idx, sheet.max_column)
            print(f"Processando todas as colunas a partir de {coluna_base}")

        # Converter colunas_a_processar para lista para poder verificar se é a última
        colunas_lista = list(colunas_a_processar) if not isinstance(colunas_a_processar, list) else colunas_a_processar
        total_colunas = len(colunas_lista)
        colunas_processadas = 0
        
        # Itera pelas colunas a processar
        for col_idx in colunas_a_processar:
            if parar_busca:
                break

            coluna = coluna_para_letra(col_idx)
            colunas_processadas += 1
            eh_ultima_coluna = (colunas_processadas == total_colunas)
            
            # Verifica se a coluna tem um nome de pilar
            nome_pilar = sheet[f'{coluna}{linhas_abcd["nome"]}'].value
            
            # VALIDAÇÃO: Garantir que o nome do pilar está correto e não vazio
            if nome_pilar:
                nome_pilar = str(nome_pilar).strip()  # Converter para string e remover espaços
                if not nome_pilar:
                    print(f"[VALIDACAO] ⚠️ AVISO: Nome do pilar vazio após limpeza para coluna {coluna}, pulando...")
                    continue
                
                print(f"[VALIDACAO] Nome do pilar lido do Excel: '{nome_pilar}' (coluna: {coluna}, linha: {linhas_abcd['nome']})")
                colunas_vazias = 0  # Reinicia a contagem de colunas vazias
                
                # Iniciar a aplicação ABCD
                app = AplicacaoUnificada()
                # Acesse o gerador de pilar através da aplicação
                gerador = app.gerador_pilares
                
                # Passar referência da interface principal se disponível
                if hasattr(gerador, 'master'):
                    if interface_principal:
                        gerador.master = interface_principal
                        print(f"✅ Interface principal passada como parâmetro e definida como master")
                    else:
                        gerador.master = app
                        print(f"⚠️ Interface principal não fornecida, usando AplicacaoUnificada como master")

                # 1. Preencher dados básicos
                print(f"Preenchendo dados básicos para o pilar '{nome_pilar}'")
                
                # Nome do pilar
                valor = sheet[f'{coluna}{linhas_abcd["nome"]}'].value
                if valor is not None:
                    valor = str(valor).strip()  # Garantir que é string e sem espaços
                    print(f"  Preenchendo nome: '{valor}' (coluna: {coluna})")
                    
                    # VALIDAÇÃO: Verificar se o valor corresponde ao nome_pilar lido anteriormente
                    if valor != nome_pilar:
                        print(f"[VALIDACAO] ⚠️ AVISO: Nome do pilar inconsistente! Lido: '{nome_pilar}', Valor na linha {linhas_abcd['nome']}: '{valor}'")
                        print(f"[VALIDACAO] Usando nome_pilar original: '{nome_pilar}'")
                        valor = nome_pilar  # Usar o nome_pilar lido anteriormente
                    
                    gerador.campos['nome'].delete(0, 'end')
                    gerador.campos['nome'].insert(0, valor)
                    print(f"[VALIDACAO] Nome do pilar preenchido no gerador: '{valor}'")
                
                # Comprimento
                valor = sheet[f'{coluna}{linhas_abcd["comprimento"]}'].value
                if valor is not None:
                    print(f"  Preenchendo comprimento: {valor}")
                    gerador.campos['comprimento'].delete(0, 'end')
                    gerador.campos['comprimento'].insert(0, valor)
                
                # Largura
                valor = sheet[f'{coluna}{linhas_abcd["largura"]}'].value
                if valor is not None:
                    print(f"  Preenchendo largura: {valor}")
                    gerador.campos['largura'].delete(0, 'end')
                    gerador.campos['largura'].insert(0, valor)
                
                # Pavimento
                valor = sheet[f'{coluna}{linhas_abcd["pavimento"]}'].value
                if valor is not None:
                    print(f"  Preenchendo pavimento: {valor}")
                    gerador.campos['pavimento'].delete(0, 'end')
                    gerador.campos['pavimento'].insert(0, valor)
                
                # Nível de Saída
                valor_saida = sheet[f'{coluna}{linhas_abcd["nivel_saida"]}'].value
                if valor_saida is not None:
                    print(f"  Preenchendo nivel_saida: {valor_saida}")
                    gerador.campos['nivel_saida'].delete(0, 'end')
                    gerador.campos['nivel_saida'].insert(0, valor_saida)
                
                # Nível de Chegada
                valor_chegada = sheet[f'{coluna}{linhas_abcd["nivel_chegada"]}'].value
                if valor_chegada is not None:
                    print(f"  Preenchendo nivel_chegada: {valor_chegada}")
                    gerador.campos['nivel_chegada'].delete(0, 'end')
                    gerador.campos['nivel_chegada'].insert(0, valor_chegada)
                
                # Altura (ler do Excel, se não houver, calcular)
                valor_altura = sheet[f'{coluna}{linhas_abcd["altura"]}'].value
                if valor_altura is not None:
                    print(f"  Preenchendo altura: {valor_altura}")
                    gerador.campos['altura'].delete(0, 'end')
                    altura_str = str(valor_altura).replace('.', ',')
                    gerador.campos['altura'].insert(0, altura_str)
                elif valor_saida is not None and valor_chegada is not None:
                    altura_calculada = (valor_chegada - valor_saida) * 100
                    print(f"  Calculando altura automaticamente: {altura_calculada}")
                    gerador.campos['altura'].delete(0, 'end')
                    altura_str = str(altura_calculada).replace('.', ',')
                    gerador.campos['altura'].insert(0, altura_str)
                else:
                    print("  AVISO: Campo 'altura' não encontrado e não foi possível calcular automaticamente.")

                # Preencher campos de parafusos
                print("Preenchendo campos de parafusos...")
                parafusos_ordem = [
                    'parafuso_p1_p2',
                    'parafuso_p2_p3',
                    'parafuso_p3_p4',
                    'parafuso_p4_p5',
                    'parafuso_p5_p6',
                    'parafuso_p6_p7',
                    'parafuso_p7_p8',
                    'parafuso_p8_p9'
                ]
                for i, parafuso in enumerate(parafusos_ordem):
                    if parafuso in linhas_abcd and i < len(gerador.parafuso_entries):
                        valor = sheet[f'{coluna}{linhas_abcd[parafuso]}'].value
                        if valor is not None:
                            gerador.parafuso_entries[i].delete(0, 'end')
                            gerador.parafuso_entries[i].insert(0, valor)
                            print(f"  Preenchendo {parafuso}: {valor}")
                        else:
                            gerador.parafuso_entries[i].delete(0, 'end')
                            gerador.parafuso_entries[i].insert(0, "0")
                            print(f"  {parafuso} vazio, preenchendo com 0")

                # 2. Preencher dados do Painel A
                print("Preenchendo dados do Painel A...")
                
                # Preencher laje para o Painel A
                valor = sheet[f'{coluna}{linhas_abcd["laje_a"]}'].value
                if valor is not None:
                    print(f"  Preenchendo laje_a: {valor}")
                    gerador.campos['laje_a'].delete(0, 'end')
                    gerador.campos['laje_a'].insert(0, valor)
                
                # Posição da laje A
                valor = sheet[f'{coluna}{linhas_abcd["posicao_laje_a"]}'].value
                if valor is not None:
                    print(f"  Preenchendo posicao_laje_a: {valor}")
                    gerador.pos_laje_a.set(valor)
                
                # Preencher larguras do Painel A
                valor = sheet[f'{coluna}{linhas_abcd["largura_1_painel_a"]}'].value
                if valor is not None:
                    print(f"  Preenchendo largura_1_painel_a: {valor}")
                    gerador.campos_ab['comp1_a'].delete(0, 'end')
                    gerador.campos_ab['comp1_a'].insert(0, valor)
                
                valor = sheet[f'{coluna}{linhas_abcd["largura_2_painel_a"]}'].value
                if valor is not None:
                    print(f"  Preenchendo largura_2_painel_a: {valor}")
                    gerador.campos_ab['comp2_a'].delete(0, 'end')
                    gerador.campos_ab['comp2_a'].insert(0, valor)
                
                valor = sheet[f'{coluna}{linhas_abcd["largura_3_painel_a"]}'].value
                if valor is not None:
                    print(f"  Preenchendo largura_3_painel_a: {valor}")
                    gerador.campos_ab['comp3_a'].delete(0, 'end')
                    gerador.campos_ab['comp3_a'].insert(0, valor)
                
                # Preencher alturas do Painel A
                for i in range(1, 6):
                    campo_excel = f"altura_{i}_painel_a"
                    if campo_excel in linhas_abcd:
                        valor = sheet[f'{coluna}{linhas_abcd[campo_excel]}'].value
                        if valor is not None:
                            print(f"  Preenchendo {campo_excel}: {valor}")
                            gerador.campos_altura['a'][i-1].delete(0, 'end')
                            gerador.campos_altura['a'][i-1].insert(0, valor)
                # Preencher hatchs do Painel A
                # Priorizar dados salvos da interface se disponível
                if interface_principal and hasattr(interface_principal, 'pilares_salvos'):
                    # Buscar dados do pilar atual
                    try:
                        if hasattr(interface_principal, 'excel_column'):
                            numero_pilar = interface_principal.excel_column.get().strip()
                        else:
                            numero_pilar = coluna
                    except (AttributeError, KeyError):
                        numero_pilar = coluna
                    # Buscar pilar com nome completo (incluindo pavimento)
                    pilar_encontrado = None
                    for pilar_key in interface_principal.pilares_salvos.keys():
                        if pilar_key.startswith(numero_pilar + '_'):
                            pilar_encontrado = pilar_key
                            break
                    
                    if pilar_encontrado:
                        dados_pilar = interface_principal.pilares_salvos[pilar_encontrado]
                        if 'dados' in dados_pilar and 'hachura_paineis' in dados_pilar['dados']:
                            hachura_data = dados_pilar['dados']['hachura_paineis']
                            if 'A' in hachura_data:
                                print(f"[HATCH INTERFACE] Usando dados salvos da interface para Painel A")
                                for painel_key, valor_hatch in hachura_data['A'].items():
                                    if painel_key.startswith('painel_'):
                                        painel_num = int(painel_key.replace('painel_', ''))
                                        if painel_num <= 5:  # Máximo 5 painéis
                                            # Mapear para o sistema de hatch do robô
                                            # painel_num-1 é o índice (0-based)
                                            # Usar valor_hatch para a primeira coluna (j=0)
                                            if painel_num-1 < len(gerador.hatch_opcoes_a):
                                                gerador.hatch_opcoes_a[painel_num-1][0].set(str(valor_hatch))
                                                print(f"[HATCH INTERFACE] Painel A[{painel_num-1}][0] = {valor_hatch}")
                            else:
                                print(f"[HATCH INTERFACE] Dados de hachura para A não encontrados, usando Excel")
                                _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'a', 5, 3)
                        else:
                            print(f"[HATCH INTERFACE] Dados de hachura não encontrados, usando Excel")
                            _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'a', 5, 3)
                    else:
                        print(f"[HATCH INTERFACE] Pilar {numero_pilar} não encontrado, usando Excel")
                        _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'a', 5, 3)
                else:
                    print(f"[HATCH INTERFACE] Interface principal não disponível, usando Excel")
                    _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'a', 5, 3)
                # Preencher hatchs do Painel B
                if interface_principal and hasattr(interface_principal, 'pilares_salvos'):
                    try:
                        numero_pilar = interface_principal.excel_column.get().strip() if hasattr(interface_principal, 'excel_column') else coluna
                    except (AttributeError, KeyError):
                        numero_pilar = coluna
                    # Buscar pilar com nome completo (incluindo pavimento)
                    pilar_encontrado = None
                    for pilar_key in interface_principal.pilares_salvos.keys():
                        if pilar_key.startswith(numero_pilar + '_'):
                            pilar_encontrado = pilar_key
                            break
                    
                    if pilar_encontrado:
                        dados_pilar = interface_principal.pilares_salvos[pilar_encontrado]
                        if 'dados' in dados_pilar and 'hachura_paineis' in dados_pilar['dados']:
                            hachura_data = dados_pilar['dados']['hachura_paineis']
                            if 'B' in hachura_data:
                                print(f"[HATCH INTERFACE] Usando dados salvos da interface para Painel B")
                                for painel_key, valor_hatch in hachura_data['B'].items():
                                    if painel_key.startswith('painel_'):
                                        painel_num = int(painel_key.replace('painel_', ''))
                                        if painel_num <= 5:
                                            if painel_num-1 < len(gerador.hatch_opcoes_b):
                                                gerador.hatch_opcoes_b[painel_num-1][0].set(str(valor_hatch))
                                                print(f"[HATCH INTERFACE] Painel B[{painel_num-1}][0] = {valor_hatch}")
                            else:
                                _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'b', 5, 3)
                        else:
                            _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'b', 5, 3)
                    else:
                        _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'b', 5, 3)
                else:
                    _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'b', 5, 3)
                # Preencher hatchs do Painel C
                if interface_principal and hasattr(interface_principal, 'pilares_salvos'):
                    try:
                        numero_pilar = interface_principal.excel_column.get().strip() if hasattr(interface_principal, 'excel_column') else coluna
                    except (AttributeError, KeyError):
                        numero_pilar = coluna
                    # Buscar pilar com nome completo (incluindo pavimento)
                    pilar_encontrado = None
                    for pilar_key in interface_principal.pilares_salvos.keys():
                        if pilar_key.startswith(numero_pilar + '_'):
                            pilar_encontrado = pilar_key
                            break
                    
                    if pilar_encontrado:
                        dados_pilar = interface_principal.pilares_salvos[pilar_encontrado]
                        if 'dados' in dados_pilar and 'hachura_paineis' in dados_pilar['dados']:
                            hachura_data = dados_pilar['dados']['hachura_paineis']
                            if 'C' in hachura_data:
                                print(f"[HATCH INTERFACE] Usando dados salvos da interface para Painel C")
                                for painel_key, valor_hatch in hachura_data['C'].items():
                                    if painel_key.startswith('painel_'):
                                        painel_num = int(painel_key.replace('painel_', ''))
                                        if painel_num <= 4:
                                            if painel_num-1 < len(gerador.hatch_opcoes_c):
                                                gerador.hatch_opcoes_c[painel_num-1][0].set(str(valor_hatch))
                                                print(f"[HATCH INTERFACE] Painel C[{painel_num-1}][0] = {valor_hatch}")
                            else:
                                _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'c', 4, 2)
                        else:
                            _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'c', 4, 2)
                    else:
                        _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'c', 4, 2)
                else:
                    _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'c', 4, 2)
                # Preencher hatchs do Painel D
                if interface_principal and hasattr(interface_principal, 'pilares_salvos'):
                    try:
                        numero_pilar = interface_principal.excel_column.get().strip() if hasattr(interface_principal, 'excel_column') else coluna
                    except (AttributeError, KeyError):
                        numero_pilar = coluna
                    # Buscar pilar com nome completo (incluindo pavimento)
                    pilar_encontrado = None
                    for pilar_key in interface_principal.pilares_salvos.keys():
                        if pilar_key.startswith(numero_pilar + '_'):
                            pilar_encontrado = pilar_key
                            break
                    
                    if pilar_encontrado:
                        dados_pilar = interface_principal.pilares_salvos[pilar_encontrado]
                        if 'dados' in dados_pilar and 'hachura_paineis' in dados_pilar['dados']:
                            hachura_data = dados_pilar['dados']['hachura_paineis']
                            if 'D' in hachura_data:
                                print(f"[HATCH INTERFACE] Usando dados salvos da interface para Painel D")
                                for painel_key, valor_hatch in hachura_data['D'].items():
                                    if painel_key.startswith('painel_'):
                                        painel_num = int(painel_key.replace('painel_', ''))
                                        if painel_num <= 4:
                                            if painel_num-1 < len(gerador.hatch_opcoes_d):
                                                gerador.hatch_opcoes_d[painel_num-1][0].set(str(valor_hatch))
                                                print(f"[HATCH INTERFACE] Painel D[{painel_num-1}][0] = {valor_hatch}")
                            else:
                                _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'd', 4, 2)
                        else:
                            _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'd', 4, 2)
                    else:
                        _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'd', 4, 2)
                else:
                    _preencher_hatch_excel(gerador, sheet, coluna, linhas_abcd, 'd', 4, 2)
                
                # Abertura A Esquerda 1
                pos_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_pos_a"]}'].value
                dist_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_dist_a"]}'].value
                larg_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_larg_a"]}'].value
                prof_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_prof_a"]}'].value
                print(f"\nProcessando Abertura A Esquerda 1:")
                print(f"  Valores lidos do Excel:")
                print(f"    Posição: {pos_esq} (linha {linhas_abcd['abertura_esq1_pos_a']})")
                print(f"    Distância: {dist_esq} (linha {linhas_abcd['abertura_esq1_dist_a']})")
                print(f"    Largura: {larg_esq} (linha {linhas_abcd['abertura_esq1_larg_a']})")
                print(f"    Profundidade: {prof_esq} (linha {linhas_abcd['abertura_esq1_prof_a']})")
                
                # Preencher 0 se o valor for None
                pos_esq = pos_esq if pos_esq is not None else 0
                dist_esq = dist_esq if dist_esq is not None else 0
                larg_esq = larg_esq if larg_esq is not None else 0
                prof_esq = prof_esq if prof_esq is not None else 0
                
                print(f"  Valores após tratamento:")
                print(f"    Posição: {pos_esq}")
                print(f"    Distância: {dist_esq}")
                print(f"    Largura: {larg_esq}")
                print(f"    Profundidade: {prof_esq}")
                
                gerador.campos['abertura_esq1_pos_a'].delete(0, 'end')
                gerador.campos['abertura_esq1_pos_a'].insert(0, pos_esq)
                gerador.campos['abertura_esq1_dist_a'].delete(0, 'end')
                gerador.campos['abertura_esq1_dist_a'].insert(0, dist_esq)
                gerador.campos['abertura_esq1_larg_a'].delete(0, 'end')
                gerador.campos['abertura_esq1_larg_a'].insert(0, larg_esq)
                gerador.campos['abertura_esq1_prof_a'].delete(0, 'end')
                gerador.campos['abertura_esq1_prof_a'].insert(0, prof_esq)
                
                # Abertura A Esquerda 2
                pos_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_pos_a"]}'].value
                dist_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_dist_a"]}'].value
                larg_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_larg_a"]}'].value
                prof_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_prof_a"]}'].value
                print(f"\nProcessando Abertura A Esquerda 2:")
                print(f"  Valores lidos do Excel:")
                print(f"    Posição: {pos_esq} (linha {linhas_abcd['abertura_esq2_pos_a']})")
                print(f"    Distância: {dist_esq} (linha {linhas_abcd['abertura_esq2_dist_a']})")
                print(f"    Largura: {larg_esq} (linha {linhas_abcd['abertura_esq2_larg_a']})")
                print(f"    Profundidade: {prof_esq} (linha {linhas_abcd['abertura_esq2_prof_a']})")
                
                # Preencher 0 se o valor for None
                pos_esq = pos_esq if pos_esq is not None else 0
                dist_esq = dist_esq if dist_esq is not None else 0
                larg_esq = larg_esq if larg_esq is not None else 0
                prof_esq = prof_esq if prof_esq is not None else 0
                
                print(f"  Valores após tratamento:")
                print(f"    Posição: {pos_esq}")
                print(f"    Distância: {dist_esq}")
                print(f"    Largura: {larg_esq}")
                print(f"    Profundidade: {prof_esq}")
                
                gerador.campos['abertura_esq2_pos_a'].delete(0, 'end')
                gerador.campos['abertura_esq2_pos_a'].insert(0, pos_esq)
                gerador.campos['abertura_esq2_dist_a'].delete(0, 'end')
                gerador.campos['abertura_esq2_dist_a'].insert(0, dist_esq)
                gerador.campos['abertura_esq2_larg_a'].delete(0, 'end')
                gerador.campos['abertura_esq2_larg_a'].insert(0, larg_esq)
                gerador.campos['abertura_esq2_prof_a'].delete(0, 'end')
                gerador.campos['abertura_esq2_prof_a'].insert(0, prof_esq)
                
                # Abertura A Direita 1
                pos_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_pos_a"]}'].value
                dist_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_dist_a"]}'].value
                larg_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_larg_a"]}'].value
                prof_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_prof_a"]}'].value
                print(f"\nProcessando Abertura A Direita 1:")
                print(f"  Valores lidos do Excel:")
                print(f"    Posição: {pos_dir} (linha {linhas_abcd['abertura_dir1_pos_a']})")
                print(f"    Distância: {dist_dir} (linha {linhas_abcd['abertura_dir1_dist_a']})")
                print(f"    Largura: {larg_dir} (linha {linhas_abcd['abertura_dir1_larg_a']})")
                print(f"    Profundidade: {prof_dir} (linha {linhas_abcd['abertura_dir1_prof_a']})")
                
                # Preencher 0 se o valor for None
                pos_dir = pos_dir if pos_dir is not None else 0
                dist_dir = dist_dir if dist_dir is not None else 0
                larg_dir = larg_dir if larg_dir is not None else 0
                prof_dir = prof_dir if prof_dir is not None else 0
                
                print(f"  Valores após tratamento:")
                print(f"    Posição: {pos_dir}")
                print(f"    Distância: {dist_dir}")
                print(f"    Largura: {larg_dir}")
                print(f"    Profundidade: {prof_dir}")
                
                gerador.campos['abertura_dir1_pos_a'].delete(0, 'end')
                gerador.campos['abertura_dir1_pos_a'].insert(0, pos_dir)
                gerador.campos['abertura_dir1_dist_a'].delete(0, 'end')
                gerador.campos['abertura_dir1_dist_a'].insert(0, dist_dir)
                gerador.campos['abertura_dir1_larg_a'].delete(0, 'end')
                gerador.campos['abertura_dir1_larg_a'].insert(0, larg_dir)
                gerador.campos['abertura_dir1_prof_a'].delete(0, 'end')
                gerador.campos['abertura_dir1_prof_a'].insert(0, prof_dir)
                
                # Abertura A Direita 2
                pos_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_pos_a"]}'].value
                dist_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_dist_a"]}'].value
                larg_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_larg_a"]}'].value
                prof_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_prof_a"]}'].value
                print(f"\nProcessando Abertura A Direita 2:")
                print(f"  Valores lidos do Excel:")
                print(f"    Posição: {pos_dir} (linha {linhas_abcd['abertura_dir2_pos_a']})")
                print(f"    Distância: {dist_dir} (linha {linhas_abcd['abertura_dir2_dist_a']})")
                print(f"    Largura: {larg_dir} (linha {linhas_abcd['abertura_dir2_larg_a']})")
                print(f"    Profundidade: {prof_dir} (linha {linhas_abcd['abertura_dir2_prof_a']})")
                
                # Preencher 0 se o valor for None
                pos_dir = pos_dir if pos_dir is not None else 0
                dist_dir = dist_dir if dist_dir is not None else 0
                larg_dir = larg_dir if larg_dir is not None else 0
                prof_dir = prof_dir if prof_dir is not None else 0
                
                print(f"  Valores após tratamento:")
                print(f"    Posição: {pos_dir}")
                print(f"    Distância: {dist_dir}")
                print(f"    Largura: {larg_dir}")
                print(f"    Profundidade: {prof_dir}")
                
                gerador.campos['abertura_dir2_pos_a'].delete(0, 'end')
                gerador.campos['abertura_dir2_pos_a'].insert(0, pos_dir)
                gerador.campos['abertura_dir2_dist_a'].delete(0, 'end')
                gerador.campos['abertura_dir2_dist_a'].insert(0, dist_dir)
                gerador.campos['abertura_dir2_larg_a'].delete(0, 'end')
                gerador.campos['abertura_dir2_larg_a'].insert(0, larg_dir)
                gerador.campos['abertura_dir2_prof_a'].delete(0, 'end')
                gerador.campos['abertura_dir2_prof_a'].insert(0, prof_dir)
                
                # Preencher campos de abertura de laje do Painel A
                print("Preenchendo campos de abertura de laje do Painel A...")
                
                # DEBUG DETALHADO: Verificar mapeamento e valores
                print("🔍 DEBUG DETALHADO ABERTURAS LAJE A:")
                print(f"  Coluna sendo usada: {coluna}")
                print(f"  Mapeamento das linhas:")
                aberturas_laje_a = ['esq1', 'esq2', 'dir1', 'dir2']
                for abertura in aberturas_laje_a:
                    campo_excel = f"abertura_laje_{abertura}_a"
                    if campo_excel in linhas_abcd:
                        linha = linhas_abcd[campo_excel]
                        print(f"    {campo_excel}: linha {linha}")
                        
                        # Verificar valor na célula
                        valor = sheet[f'{coluna}{linha}'].value
                        print(f"    Valor lido: '{valor}' (tipo: {type(valor)})")
                        
                        # Verificar se a célula está vazia ou tem conteúdo
                        if valor is None:
                            print(f"    ⚠️  Célula {coluna}{linha} está VAZIA")
                        else:
                            print(f"    ✅ Célula {coluna}{linha} contém: '{valor}'")
                        
                        # Definir valor
                        if valor is not None:
                            print(f"  Preenchendo {campo_excel}: {valor}")
                            gerador.abertura_laje['a'][abertura].set(str(valor))
                        else:
                            print(f"  Definindo {campo_excel} como '0' (célula vazia)")
                            gerador.abertura_laje['a'][abertura].set("0")
                    else:
                        print(f"    ❌ {campo_excel}: NÃO MAPEADO no linhas_abcd")
                        gerador.abertura_laje['a'][abertura].set("0")
                
                # Verificar valores finais e refletir nos campos tipo_ da interface do gerador
                print("🔍 VALORES FINAIS DEFINIDOS A:")
                for abertura in aberturas_laje_a:
                    valor_final = gerador.abertura_laje['a'][abertura].get()
                    print(f"  abertura_laje_{abertura}_a: '{valor_final}'")
                    try:
                        # abertura: esq1/esq2/dir1/dir2 -> construir nome do campo tipo_esq_1_A ...
                        lado = 'esq' if abertura.startswith('esq') else 'dir'
                        num = abertura[-1]
                        campo_tipo_nome = f"tipo_{lado}_{num}_A"
                        if hasattr(gerador.master, campo_tipo_nome):
                            campo_tipo = getattr(gerador.master, campo_tipo_nome)
                            if hasattr(campo_tipo, 'delete') and hasattr(campo_tipo, 'insert'):
                                campo_tipo.delete(0, 'end')
                                campo_tipo.insert(0, '1' if str(valor_final).strip() == '1' else '0')
                    except Exception:
                        pass
                
                print("\nProcessamento das aberturas do Painel A concluído!")
                
                # 3. Preencher dados do Painel B
                print("Preenchendo dados do Painel B...")
                
                # Preencher laje para o Painel B
                valor = sheet[f'{coluna}{linhas_abcd["laje_b"]}'].value
                if valor is not None:
                    print(f"  Preenchendo laje_b: {valor}")
                    gerador.campos['laje_b'].delete(0, 'end')
                    gerador.campos['laje_b'].insert(0, valor)
                
                # Posição da laje B
                valor = sheet[f'{coluna}{linhas_abcd["posicao_laje_b"]}'].value
                if valor is not None:
                    print(f"  Preenchendo posicao_laje_b: {valor}")
                    gerador.pos_laje_b.set(valor)
                
                # Preencher larguras do Painel B
                valor = sheet[f'{coluna}{linhas_abcd["largura_1_painel_b"]}'].value
                if valor is not None:
                    print(f"  Preenchendo largura_1_painel_b: {valor}")
                    gerador.campos_ab['comp1_b'].delete(0, 'end')
                    gerador.campos_ab['comp1_b'].insert(0, valor)
                
                valor = sheet[f'{coluna}{linhas_abcd["largura_2_painel_b"]}'].value
                if valor is not None:
                    print(f"  Preenchendo largura_2_painel_b: {valor}")
                    gerador.campos_ab['comp2_b'].delete(0, 'end')
                    gerador.campos_ab['comp2_b'].insert(0, valor)
                
                valor = sheet[f'{coluna}{linhas_abcd["largura_3_painel_b"]}'].value
                if valor is not None:
                    print(f"  Preenchendo largura_3_painel_b: {valor}")
                    gerador.campos_ab['comp3_b'].delete(0, 'end')
                    gerador.campos_ab['comp3_b'].insert(0, valor)
                
                # Preencher alturas do Painel B
                for i in range(1, 6):
                    campo_excel = f"altura_{i}_painel_b"
                    if campo_excel in linhas_abcd:
                        valor = sheet[f'{coluna}{linhas_abcd[campo_excel]}'].value
                        if valor is not None:
                            print(f"  Preenchendo {campo_excel}: {valor}")
                            gerador.campos_altura['b'][i-1].delete(0, 'end')
                            gerador.campos_altura['b'][i-1].insert(0, valor)
                # Preencher hatchs do Painel B
                hatchs_b = [
                    ['hatch_l1_h2_b', 'hatch_l1_h3_b', 'hatch_l1_h4_b', 'hatch_l1_h5_b'],
                    ['hatch_l2_h2_b', 'hatch_l2_h3_b', 'hatch_l2_h4_b', 'hatch_l2_h5_b'],
                    ['hatch_l3_h2_b', 'hatch_l3_h3_b', 'hatch_l3_h4_b', 'hatch_l3_h5_b'],
                ]
                for i, linha_hatch in enumerate(hatchs_b):
                    for j, campo_hatch in enumerate(linha_hatch):
                        if campo_hatch in linhas_abcd:
                            valor = sheet[f'{coluna}{linhas_abcd[campo_hatch]}'].value
                            print(f"[DEBUG] Painel B - {campo_hatch} (linha {linhas_abcd[campo_hatch]}), valor do Excel: {valor}, campo interface: [{i}][{j}]")
                            if valor is not None:
                                if i < len(gerador.hatch_opcoes_b) and j < len(gerador.hatch_opcoes_b[i]):
                                    gerador.hatch_opcoes_b[i][j].set(str(valor))
                                else:
                                    print(f"[DEBUG] Painel B - hatch_l{i+1}_h{j+2}_b (linha {linha}), valor do Excel: {valor}, campo interface: [{i}][{j}]")
                
                # Abertura B Esquerda 1
                pos_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_pos_b"]}'].value
                dist_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_dist_b"]}'].value
                larg_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_larg_b"]}'].value
                prof_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_prof_b"]}'].value
                print(f"\nProcessando Abertura B Esquerda 1:")
                print(f"  Valores lidos do Excel:")
                print(f"    Posição: {pos_esq} (linha {linhas_abcd['abertura_esq1_pos_b']})")
                print(f"    Distância: {dist_esq} (linha {linhas_abcd['abertura_esq1_dist_b']})")
                print(f"    Largura: {larg_esq} (linha {linhas_abcd['abertura_esq1_larg_b']})")
                print(f"    Profundidade: {prof_esq} (linha {linhas_abcd['abertura_esq1_prof_b']})")
                
                # Preencher 0 se o valor for None
                pos_esq = pos_esq if pos_esq is not None else 0
                dist_esq = dist_esq if dist_esq is not None else 0
                larg_esq = larg_esq if larg_esq is not None else 0
                prof_esq = prof_esq if prof_esq is not None else 0
                
                print(f"  Valores após tratamento:")
                print(f"    Posição: {pos_esq}")
                print(f"    Distância: {dist_esq}")
                print(f"    Largura: {larg_esq}")
                print(f"    Profundidade: {prof_esq}")
                
                gerador.campos['abertura_esq1_pos_b'].delete(0, 'end')
                gerador.campos['abertura_esq1_pos_b'].insert(0, pos_esq)
                gerador.campos['abertura_esq1_dist_b'].delete(0, 'end')
                gerador.campos['abertura_esq1_dist_b'].insert(0, dist_esq)
                gerador.campos['abertura_esq1_larg_b'].delete(0, 'end')
                gerador.campos['abertura_esq1_larg_b'].insert(0, larg_esq)
                gerador.campos['abertura_esq1_prof_b'].delete(0, 'end')
                gerador.campos['abertura_esq1_prof_b'].insert(0, prof_esq)
                
                # Abertura B Esquerda 2
                pos_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_pos_b"]}'].value
                dist_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_dist_b"]}'].value
                larg_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_larg_b"]}'].value
                prof_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_prof_b"]}'].value
                print(f"\nProcessando Abertura B Esquerda 2:")
                print(f"  Valores lidos do Excel:")
                print(f"    Posição: {pos_esq} (linha {linhas_abcd['abertura_esq2_pos_b']})")
                print(f"    Distância: {dist_esq} (linha {linhas_abcd['abertura_esq2_dist_b']})")
                print(f"    Largura: {larg_esq} (linha {linhas_abcd['abertura_esq2_larg_b']})")
                print(f"    Profundidade: {prof_esq} (linha {linhas_abcd['abertura_esq2_prof_b']})")
                
                # Preencher 0 se o valor for None
                pos_esq = pos_esq if pos_esq is not None else 0
                dist_esq = dist_esq if dist_esq is not None else 0
                larg_esq = larg_esq if larg_esq is not None else 0
                prof_esq = prof_esq if prof_esq is not None else 0
                
                print(f"  Valores após tratamento:")
                print(f"    Posição: {pos_esq}")
                print(f"    Distância: {dist_esq}")
                print(f"    Largura: {larg_esq}")
                print(f"    Profundidade: {prof_esq}")
                
                gerador.campos['abertura_esq2_pos_b'].delete(0, 'end')
                gerador.campos['abertura_esq2_pos_b'].insert(0, pos_esq)
                gerador.campos['abertura_esq2_dist_b'].delete(0, 'end')
                gerador.campos['abertura_esq2_dist_b'].insert(0, dist_esq)
                gerador.campos['abertura_esq2_larg_b'].delete(0, 'end')
                gerador.campos['abertura_esq2_larg_b'].insert(0, larg_esq)
                gerador.campos['abertura_esq2_prof_b'].delete(0, 'end')
                gerador.campos['abertura_esq2_prof_b'].insert(0, prof_esq)
                
                # Abertura B Direita 1
                pos_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_pos_b"]}'].value
                dist_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_dist_b"]}'].value
                larg_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_larg_b"]}'].value
                prof_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_prof_b"]}'].value
                print(f"\nProcessando Abertura B Direita 1:")
                print(f"  Valores lidos do Excel:")
                print(f"    Posição: {pos_dir} (linha {linhas_abcd['abertura_dir1_pos_b']})")
                print(f"    Distância: {dist_dir} (linha {linhas_abcd['abertura_dir1_dist_b']})")
                print(f"    Largura: {larg_dir} (linha {linhas_abcd['abertura_dir1_larg_b']})")
                print(f"    Profundidade: {prof_dir} (linha {linhas_abcd['abertura_dir1_prof_b']})")
                
                # Preencher 0 se o valor for None
                pos_dir = pos_dir if pos_dir is not None else 0
                dist_dir = dist_dir if dist_dir is not None else 0
                larg_dir = larg_dir if larg_dir is not None else 0
                prof_dir = prof_dir if prof_dir is not None else 0
                
                print(f"  Valores após tratamento:")
                print(f"    Posição: {pos_dir}")
                print(f"    Distância: {dist_dir}")
                print(f"    Largura: {larg_dir}")
                print(f"    Profundidade: {prof_dir}")
                
                gerador.campos['abertura_dir1_pos_b'].delete(0, 'end')
                gerador.campos['abertura_dir1_pos_b'].insert(0, pos_dir)
                gerador.campos['abertura_dir1_dist_b'].delete(0, 'end')
                gerador.campos['abertura_dir1_dist_b'].insert(0, dist_dir)
                gerador.campos['abertura_dir1_larg_b'].delete(0, 'end')
                gerador.campos['abertura_dir1_larg_b'].insert(0, larg_dir)
                gerador.campos['abertura_dir1_prof_b'].delete(0, 'end')
                gerador.campos['abertura_dir1_prof_b'].insert(0, prof_dir)
                
                # Abertura B Direita 2
                pos_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_pos_b"]}'].value
                dist_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_dist_b"]}'].value
                larg_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_larg_b"]}'].value
                prof_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_prof_b"]}'].value
                print(f"\nProcessando Abertura B Direita 2:")
                print(f"  Valores lidos do Excel:")
                print(f"    Posição: {pos_dir} (linha {linhas_abcd['abertura_dir2_pos_b']})")
                print(f"    Distância: {dist_dir} (linha {linhas_abcd['abertura_dir2_dist_b']})")
                print(f"    Largura: {larg_dir} (linha {linhas_abcd['abertura_dir2_larg_b']})")
                print(f"    Profundidade: {prof_dir} (linha {linhas_abcd['abertura_dir2_prof_b']})")
                
                # Preencher 0 se o valor for None
                pos_dir = pos_dir if pos_dir is not None else 0
                dist_dir = dist_dir if dist_dir is not None else 0
                larg_dir = larg_dir if larg_dir is not None else 0
                prof_dir = prof_dir if prof_dir is not None else 0
                
                print(f"  Valores após tratamento:")
                print(f"    Posição: {pos_dir}")
                print(f"    Distância: {dist_dir}")
                print(f"    Largura: {larg_dir}")
                print(f"    Profundidade: {prof_dir}")
                
                gerador.campos['abertura_dir2_pos_b'].delete(0, 'end')
                gerador.campos['abertura_dir2_pos_b'].insert(0, pos_dir)
                gerador.campos['abertura_dir2_dist_b'].delete(0, 'end')
                gerador.campos['abertura_dir2_dist_b'].insert(0, dist_dir)
                gerador.campos['abertura_dir2_larg_b'].delete(0, 'end')
                gerador.campos['abertura_dir2_larg_b'].insert(0, larg_dir)
                gerador.campos['abertura_dir2_prof_b'].delete(0, 'end')
                gerador.campos['abertura_dir2_prof_b'].insert(0, prof_dir)
                
                # Preencher campos de abertura de laje do Painel B
                print("Preenchendo campos de abertura de laje do Painel B...")
                
                # DEBUG DETALHADO: Verificar mapeamento e valores
                print("🔍 DEBUG DETALHADO ABERTURAS LAJE B:")
                print(f"  Coluna sendo usada: {coluna}")
                print(f"  Mapeamento das linhas:")
                aberturas_laje_b = ['esq1', 'esq2', 'dir1', 'dir2']
                for abertura in aberturas_laje_b:
                    campo_excel = f"abertura_laje_{abertura}_b"
                    if campo_excel in linhas_abcd:
                        linha = linhas_abcd[campo_excel]
                        print(f"    {campo_excel}: linha {linha}")
                        
                        # Verificar valor na célula
                        valor = sheet[f'{coluna}{linha}'].value
                        print(f"    Valor lido: '{valor}' (tipo: {type(valor)})")
                        
                        # Verificar se a célula está vazia ou tem conteúdo
                        if valor is None:
                            print(f"    ⚠️  Célula {coluna}{linha} está VAZIA")
                        else:
                            print(f"    ✅ Célula {coluna}{linha} contém: '{valor}'")
                        
                        # Definir valor
                        if valor is not None:
                            print(f"  Preenchendo {campo_excel}: {valor}")
                            gerador.abertura_laje['b'][abertura].set(str(valor))
                        else:
                            print(f"  Definindo {campo_excel} como '0' (célula vazia)")
                            gerador.abertura_laje['b'][abertura].set("0")
                    else:
                        print(f"    ❌ {campo_excel}: NÃO MAPEADO no linhas_abcd")
                        gerador.abertura_laje['b'][abertura].set("0")
                
                # Verificar valores finais e refletir nos campos tipo_ da interface do gerador
                print("🔍 VALORES FINAIS DEFINIDOS B:")
                for abertura in aberturas_laje_b:
                    valor_final = gerador.abertura_laje['b'][abertura].get()
                    print(f"  abertura_laje_{abertura}_b: '{valor_final}'")
                    try:
                        lado = 'esq' if abertura.startswith('esq') else 'dir'
                        num = abertura[-1]
                        campo_tipo_nome = f"tipo_{lado}_{num}_B"
                        if hasattr(gerador.master, campo_tipo_nome):
                            campo_tipo = getattr(gerador.master, campo_tipo_nome)
                            if hasattr(campo_tipo, 'delete') and hasattr(campo_tipo, 'insert'):
                                campo_tipo.delete(0, 'end')
                                campo_tipo.insert(0, '1' if str(valor_final).strip() == '1' else '0')
                    except Exception:
                        pass
                
                print("\nProcessamento das aberturas do Painel B concluído!")
                
                # 4. Preencher dados do Painel C
                print("Preenchendo dados do Painel C...")
                
                # Preencher laje para o Painel C
                valor = sheet[f'{coluna}{linhas_abcd["laje_c"]}'].value
                if valor is not None:
                    print(f"  Preenchendo laje_c: {valor}")
                    gerador.campos['laje_c'].delete(0, 'end')
                    gerador.campos['laje_c'].insert(0, valor)
                
                # Posição da laje C
                valor = sheet[f'{coluna}{linhas_abcd["posicao_laje_c"]}'].value
                if valor is not None:
                    print(f"  Preenchendo posicao_laje_c: {valor}")
                    gerador.pos_laje_c.set(valor)
                
                # Preencher larguras do Painel C
                valor = sheet[f'{coluna}{linhas_abcd["larg1_C"]}'].value
                if valor is not None:
                    print(f"  Preenchendo largura_1_painel_c: {valor}")
                    gerador.campos_cd['comp1_c'].delete(0, 'end')
                    gerador.campos_cd['comp1_c'].insert(0, valor)
                
                valor = sheet[f'{coluna}{linhas_abcd["larg2_C"]}'].value
                if valor is not None:
                    print(f"  Preenchendo largura_2_painel_c: {valor}")
                    gerador.campos_cd['comp2_c'].delete(0, 'end')
                    gerador.campos_cd['comp2_c'].insert(0, valor)
                
                # Preencher alturas do Painel C
                for i in range(1, 5):  # Painéis C e D têm 4 alturas
                    campo_excel = f"h{i}_C"
                    if campo_excel in linhas_abcd:
                        valor = sheet[f'{coluna}{linhas_abcd[campo_excel]}'].value
                        if valor is not None:
                            print(f"  Preenchendo {campo_excel}: {valor}")
                            gerador.campos_altura['c'][i-1].delete(0, 'end')
                            gerador.campos_altura['c'][i-1].insert(0, valor)
                # Preencher hatchs do Painel C
                hatchs_c = [
                    ['hatch_l1_h2_c', 'hatch_l1_h3_c', 'hatch_l1_h4_c'],
                    ['hatch_l2_h2_c', 'hatch_l2_h3_c', 'hatch_l2_h4_c'],
                ]
                for i, linha_hatch in enumerate(hatchs_c):
                    for j, campo_hatch in enumerate(linha_hatch):
                        if campo_hatch in linhas_abcd:
                            valor = sheet[f'{coluna}{linhas_abcd[campo_hatch]}'].value
                            print(f"[DEBUG] Painel C - {campo_hatch} (linha {linhas_abcd[campo_hatch]}), valor do Excel: {valor}, campo interface: [{i}][{j}]")
                            # Protege o acesso ao campo de hatch
                            if i < len(gerador.hatch_opcoes_c) and j < len(gerador.hatch_opcoes_c[i]):
                                if valor is not None:
                                    gerador.hatch_opcoes_c[i][j].set(str(valor))
                            else:
                                print(f"[DEBUG] Painel C - hatch_l{i+1}_h{j+2}_c (linha {linhas_abcd[campo_hatch]}), valor do Excel: {valor}, campo interface: [{i}][{j}]")
                
                # Abertura C Esquerda 1
                pos_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_pos_c"]}'].value
                dist_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_dist_c"]}'].value
                larg_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_larg_c"]}'].value
                prof_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_prof_c"]}'].value
                print(f"  Lendo Abertura Esquerda 1 C:")
                print(f"    Posição: {pos_esq} (linha {linhas_abcd['abertura_esq1_pos_c']})")
                print(f"    Distância: {dist_esq} (linha {linhas_abcd['abertura_esq1_dist_c']})")
                print(f"    Largura: {larg_esq} (linha {linhas_abcd['abertura_esq1_larg_c']})")
                print(f"    Profundidade: {prof_esq} (linha {linhas_abcd['abertura_esq1_prof_c']})")
                
                # Preencher 0 se o valor for None
                pos_esq = pos_esq if pos_esq is not None else 0
                dist_esq = dist_esq if dist_esq is not None else 0
                larg_esq = larg_esq if larg_esq is not None else 0
                prof_esq = prof_esq if prof_esq is not None else 0
                
                print(f"  Preenchendo Abertura Esquerda 1 C:")
                gerador.campos['abertura_esq1_pos_c'].delete(0, 'end')
                gerador.campos['abertura_esq1_pos_c'].insert(0, pos_esq)
                print(f"    Posição preenchida: {pos_esq}")
                
                gerador.campos['abertura_esq1_dist_c'].delete(0, 'end')
                gerador.campos['abertura_esq1_dist_c'].insert(0, dist_esq)
                print(f"    Distância preenchida: {dist_esq}")
                
                gerador.campos['abertura_esq1_larg_c'].delete(0, 'end')
                gerador.campos['abertura_esq1_larg_c'].insert(0, larg_esq)
                print(f"    Largura preenchida: {larg_esq}")
                
                gerador.campos['abertura_esq1_prof_c'].delete(0, 'end')
                gerador.campos['abertura_esq1_prof_c'].insert(0, prof_esq)
                print(f"    Profundidade preenchida: {prof_esq}")
                
                # Abertura C Esquerda 2
                pos_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_pos_c"]}'].value
                dist_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_dist_c"]}'].value
                larg_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_larg_c"]}'].value
                prof_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_prof_c"]}'].value
                if pos_esq is not None:
                    print(f"  Abertura Esquerda 2 C: Pos={pos_esq}, Dist={dist_esq}, Larg={larg_esq}, Prof={prof_esq}")
                    gerador.campos['abertura_esq2_pos_c'].delete(0, 'end')
                    gerador.campos['abertura_esq2_pos_c'].insert(0, pos_esq)
                    
                    if dist_esq is not None:
                        gerador.campos['abertura_esq2_dist_c'].delete(0, 'end')
                        gerador.campos['abertura_esq2_dist_c'].insert(0, dist_esq)
                    
                    if larg_esq is not None:
                        gerador.campos['abertura_esq2_larg_c'].delete(0, 'end')
                        gerador.campos['abertura_esq2_larg_c'].insert(0, larg_esq)
                    
                    if prof_esq is not None:
                        gerador.campos['abertura_esq2_prof_c'].delete(0, 'end')
                        gerador.campos['abertura_esq2_prof_c'].insert(0, prof_esq)
                
                # Abertura C Direita 1
                pos_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_pos_c"]}'].value
                dist_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_dist_c"]}'].value
                larg_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_larg_c"]}'].value
                prof_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_prof_c"]}'].value
                if pos_dir is not None:
                    print(f"  Abertura Direita 1 C: Pos={pos_dir}, Dist={dist_dir}, Larg={larg_dir}, Prof={prof_dir}")
                    gerador.campos['abertura_dir1_pos_c'].delete(0, 'end')
                    gerador.campos['abertura_dir1_pos_c'].insert(0, pos_dir)
                    
                    if dist_dir is not None:
                        gerador.campos['abertura_dir1_dist_c'].delete(0, 'end')
                        gerador.campos['abertura_dir1_dist_c'].insert(0, dist_dir)
                    
                    if larg_dir is not None:
                        gerador.campos['abertura_dir1_larg_c'].delete(0, 'end')
                        gerador.campos['abertura_dir1_larg_c'].insert(0, larg_dir)
                    
                    if prof_dir is not None:
                        gerador.campos['abertura_dir1_prof_c'].delete(0, 'end')
                        gerador.campos['abertura_dir1_prof_c'].insert(0, prof_dir)
                
                # Abertura C Direita 2
                pos_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_pos_c"]}'].value
                dist_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_dist_c"]}'].value
                larg_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_larg_c"]}'].value
                prof_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_prof_c"]}'].value
                if pos_dir is not None:
                    print(f"  Abertura Direita 2 C: Pos={pos_dir}, Dist={dist_dir}, Larg={larg_dir}, Prof={prof_dir}")
                    gerador.campos['abertura_dir2_pos_c'].delete(0, 'end')
                    gerador.campos['abertura_dir2_pos_c'].insert(0, pos_dir)
                    
                    if dist_dir is not None:
                        gerador.campos['abertura_dir2_dist_c'].delete(0, 'end')
                        gerador.campos['abertura_dir2_dist_c'].insert(0, dist_dir)
                    
                    if larg_dir is not None:
                        gerador.campos['abertura_dir2_larg_c'].delete(0, 'end')
                        gerador.campos['abertura_dir2_larg_c'].insert(0, larg_dir)
                    
                    if prof_dir is not None:
                        gerador.campos['abertura_dir2_prof_c'].delete(0, 'end')
                        gerador.campos['abertura_dir2_prof_c'].insert(0, prof_dir)
                
                # Preencher campos de abertura de laje do Painel C
                print("Preenchendo campos de abertura de laje do Painel C...")
                
                # DEBUG DETALHADO: Verificar mapeamento e valores
                print("🔍 DEBUG DETALHADO ABERTURAS LAJE C:")
                print(f"  Coluna sendo usada: {coluna}")
                print(f"  Mapeamento das linhas:")
                aberturas_laje_c = ['esq1', 'esq2', 'dir1', 'dir2']
                for abertura in aberturas_laje_c:
                    campo_excel = f"abertura_laje_{abertura}_c"
                    if campo_excel in linhas_abcd:
                        linha = linhas_abcd[campo_excel]
                        print(f"    {campo_excel}: linha {linha}")
                        
                        # Verificar valor na célula
                        valor = sheet[f'{coluna}{linha}'].value
                        print(f"    Valor lido: '{valor}' (tipo: {type(valor)})")
                        
                        # Verificar se a célula está vazia ou tem conteúdo
                        if valor is None:
                            print(f"    ⚠️  Célula {coluna}{linha} está VAZIA")
                        else:
                            print(f"    ✅ Célula {coluna}{linha} contém: '{valor}'")
                        
                        # Definir valor
                        if valor is not None:
                            print(f"  Preenchendo {campo_excel}: {valor}")
                            gerador.abertura_laje['c'][abertura].set(str(valor))
                        else:
                            print(f"  Definindo {campo_excel} como '0' (célula vazia)")
                            gerador.abertura_laje['c'][abertura].set("0")
                    else:
                        print(f"    ❌ {campo_excel}: NÃO MAPEADO no linhas_abcd")
                        gerador.abertura_laje['c'][abertura].set("0")
                
                # Verificar valores finais e refletir nos campos tipo_ da interface do gerador
                print("🔍 VALORES FINAIS DEFINIDOS:")
                for abertura in aberturas_laje_c:
                    valor_final = gerador.abertura_laje['c'][abertura].get()
                    print(f"  abertura_laje_{abertura}_c: '{valor_final}'")
                    try:
                        lado = 'esq' if abertura.startswith('esq') else 'dir'
                        num = abertura[-1]
                        campo_tipo_nome = f"tipo_{lado}_{num}_C"
                        if hasattr(gerador.master, campo_tipo_nome):
                            campo_tipo = getattr(gerador.master, campo_tipo_nome)
                            if hasattr(campo_tipo, 'delete') and hasattr(campo_tipo, 'insert'):
                                campo_tipo.delete(0, 'end')
                                campo_tipo.insert(0, '1' if str(valor_final).strip() == '1' else '0')
                    except Exception:
                        pass
                
                # 5. Preencher dados do Painel D
                print("Preenchendo dados do Painel D...")
                
                # Preencher laje para o Painel D
                valor = sheet[f'{coluna}{linhas_abcd["laje_d"]}'].value
                if valor is not None:
                    print(f"  Preenchendo laje_d: {valor}")
                    gerador.campos['laje_d'].delete(0, 'end')
                    gerador.campos['laje_d'].insert(0, valor)
                
                # Posição da laje D
                valor = sheet[f'{coluna}{linhas_abcd["posicao_laje_d"]}'].value
                if valor is not None:
                    print(f"  Preenchendo posicao_laje_d: {valor}")
                    gerador.pos_laje_d.set(valor)
                
                # Preencher larguras do Painel D
                valor = sheet[f'{coluna}{linhas_abcd["larg1_D"]}'].value
                if valor is not None:
                    print(f"  Preenchendo largura_1_painel_d: {valor}")
                    gerador.campos_cd['comp1_d'].delete(0, 'end')
                    gerador.campos_cd['comp1_d'].insert(0, valor)
                
                valor = sheet[f'{coluna}{linhas_abcd["larg2_D"]}'].value
                if valor is not None:
                    print(f"  Preenchendo largura_2_painel_d: {valor}")
                    gerador.campos_cd['comp2_d'].delete(0, 'end')
                    gerador.campos_cd['comp2_d'].insert(0, valor)
                
                # Preencher alturas do Painel D
                for i in range(1, 5):  # Painéis C e D têm 4 alturas
                    campo_excel = f"h{i}_D"
                    if campo_excel in linhas_abcd:
                        valor = sheet[f'{coluna}{linhas_abcd[campo_excel]}'].value
                        if valor is not None:
                            print(f"  Preenchendo {campo_excel}: {valor}")
                            gerador.campos_altura['d'][i-1].delete(0, 'end')
                            gerador.campos_altura['d'][i-1].insert(0, valor)
                # Preencher hatchs do Painel D
                hatchs_d = [
                    ['hatch_l1_h2_d', 'hatch_l1_h3_d', 'hatch_l1_h4_d'],
                    ['hatch_l2_h2_d', 'hatch_l2_h3_d', 'hatch_l2_h4_d'],
                ]
                for i, linha_hatch in enumerate(hatchs_d):
                    for j, campo_hatch in enumerate(linha_hatch):
                        if campo_hatch in linhas_abcd:
                            valor = sheet[f'{coluna}{linhas_abcd[campo_hatch]}'].value
                            print(f"[DEBUG] Painel D - {campo_hatch} (linha {linhas_abcd[campo_hatch]}), valor do Excel: {valor}, campo interface: [{i}][{j}]")
                            # Protege o acesso ao campo de hatch
                            if i < len(gerador.hatch_opcoes_d) and j < len(gerador.hatch_opcoes_d[i]):
                                if valor is not None:
                                    gerador.hatch_opcoes_d[i][j].set(str(valor))
                            else:
                                print(f"[DEBUG] Painel D - hatch_l{i+1}_h{j+2}_d (linha {linhas_abcd[campo_hatch]}), valor do Excel: {valor}, campo interface: [{i}][{j}]")
                
                # Abertura D Esquerda 1
                pos_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_pos_d"]}'].value
                dist_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_dist_d"]}'].value
                larg_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_larg_d"]}'].value
                prof_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq1_prof_d"]}'].value
                print(f"  Lendo Abertura Esquerda 1 D:")
                print(f"    Posição: {pos_esq} (linha {linhas_abcd['abertura_esq1_pos_d']})")
                print(f"    Distância: {dist_esq} (linha {linhas_abcd['abertura_esq1_dist_d']})")
                print(f"    Largura: {larg_esq} (linha {linhas_abcd['abertura_esq1_larg_d']})")
                print(f"    Profundidade: {prof_esq} (linha {linhas_abcd['abertura_esq1_prof_d']})")
                
                # Preencher 0 se o valor for None
                pos_esq = pos_esq if pos_esq is not None else 0
                dist_esq = dist_esq if dist_esq is not None else 0
                larg_esq = larg_esq if larg_esq is not None else 0
                prof_esq = prof_esq if prof_esq is not None else 0
                
                print(f"  Preenchendo Abertura Esquerda 1 D:")
                gerador.campos['abertura_esq1_pos_d'].delete(0, 'end')
                gerador.campos['abertura_esq1_pos_d'].insert(0, pos_esq)
                print(f"    Posição preenchida: {pos_esq}")
                
                gerador.campos['abertura_esq1_dist_d'].delete(0, 'end')
                gerador.campos['abertura_esq1_dist_d'].insert(0, dist_esq)
                print(f"    Distância preenchida: {dist_esq}")
                
                gerador.campos['abertura_esq1_larg_d'].delete(0, 'end')
                gerador.campos['abertura_esq1_larg_d'].insert(0, larg_esq)
                print(f"    Largura preenchida: {larg_esq}")
                
                gerador.campos['abertura_esq1_prof_d'].delete(0, 'end')
                gerador.campos['abertura_esq1_prof_d'].insert(0, prof_esq)
                print(f"    Profundidade preenchida: {prof_esq}")
                
                # Abertura D Esquerda 2
                pos_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_pos_d"]}'].value
                dist_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_dist_d"]}'].value
                larg_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_larg_d"]}'].value
                prof_esq = sheet[f'{coluna}{linhas_abcd["abertura_esq2_prof_d"]}'].value
                if pos_esq is not None:
                    print(f"  Abertura Esquerda 2 D: Pos={pos_esq}, Dist={dist_esq}, Larg={larg_esq}, Prof={prof_esq}")
                    gerador.campos['abertura_esq2_pos_d'].delete(0, 'end')
                    gerador.campos['abertura_esq2_pos_d'].insert(0, pos_esq)
                    
                    if dist_esq is not None:
                        gerador.campos['abertura_esq2_dist_d'].delete(0, 'end')
                        gerador.campos['abertura_esq2_dist_d'].insert(0, dist_esq)
                    
                    if larg_esq is not None:
                        gerador.campos['abertura_esq2_larg_d'].delete(0, 'end')
                        gerador.campos['abertura_esq2_larg_d'].insert(0, larg_esq)
                    
                    if prof_esq is not None:
                        gerador.campos['abertura_esq2_prof_d'].delete(0, 'end')
                        gerador.campos['abertura_esq2_prof_d'].insert(0, prof_esq)
                
                # Abertura D Direita 1
                pos_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_pos_d"]}'].value
                dist_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_dist_d"]}'].value
                larg_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_larg_d"]}'].value
                prof_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir1_prof_d"]}'].value
                if pos_dir is not None:
                    print(f"  Abertura Direita 1 D: Pos={pos_dir}, Dist={dist_dir}, Larg={larg_dir}, Prof={prof_dir}")
                    gerador.campos['abertura_dir1_pos_d'].delete(0, 'end')
                    gerador.campos['abertura_dir1_pos_d'].insert(0, pos_dir)
                    
                    if dist_dir is not None:
                        gerador.campos['abertura_dir1_dist_d'].delete(0, 'end')
                        gerador.campos['abertura_dir1_dist_d'].insert(0, dist_dir)
                    
                    if larg_dir is not None:
                        gerador.campos['abertura_dir1_larg_d'].delete(0, 'end')
                        gerador.campos['abertura_dir1_larg_d'].insert(0, larg_dir)
                    
                    if prof_dir is not None:
                        gerador.campos['abertura_dir1_prof_d'].delete(0, 'end')
                        gerador.campos['abertura_dir1_prof_d'].insert(0, prof_dir)
                
                # Abertura D Direita 2
                pos_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_pos_d"]}'].value
                dist_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_dist_d"]}'].value
                larg_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_larg_d"]}'].value
                prof_dir = sheet[f'{coluna}{linhas_abcd["abertura_dir2_prof_d"]}'].value
                if pos_dir is not None:
                    print(f"  Abertura Direita 2 D: Pos={pos_dir}, Dist={dist_dir}, Larg={larg_dir}, Prof={prof_dir}")
                    gerador.campos['abertura_dir2_pos_d'].delete(0, 'end')
                    gerador.campos['abertura_dir2_pos_d'].insert(0, pos_dir)
                    
                    if dist_dir is not None:
                        gerador.campos['abertura_dir2_dist_d'].delete(0, 'end')
                        gerador.campos['abertura_dir2_dist_d'].insert(0, dist_dir)
                    
                    if larg_dir is not None:
                        gerador.campos['abertura_dir2_larg_d'].delete(0, 'end')
                        gerador.campos['abertura_dir2_larg_d'].insert(0, larg_dir)
                    
                    if prof_dir is not None:
                        gerador.campos['abertura_dir2_prof_d'].delete(0, 'end')
                        gerador.campos['abertura_dir2_prof_d'].insert(0, prof_dir)
                
                # Preencher campos de abertura de laje do Painel D
                print("Preenchendo campos de abertura de laje do Painel D...")
                
                # DEBUG DETALHADO: Verificar mapeamento e valores
                print("🔍 DEBUG DETALHADO ABERTURAS LAJE D:")
                print(f"  Coluna sendo usada: {coluna}")
                print(f"  Mapeamento das linhas:")
                aberturas_laje_d = ['esq1', 'esq2', 'dir1', 'dir2']
                for abertura in aberturas_laje_d:
                    campo_excel = f"abertura_laje_{abertura}_d"
                    if campo_excel in linhas_abcd:
                        linha = linhas_abcd[campo_excel]
                        print(f"    {campo_excel}: linha {linha}")
                        
                        # Verificar valor na célula
                        valor = sheet[f'{coluna}{linha}'].value
                        print(f"    Valor lido: '{valor}' (tipo: {type(valor)})")
                        
                        # Verificar se a célula está vazia ou tem conteúdo
                        if valor is None:
                            print(f"    ⚠️  Célula {coluna}{linha} está VAZIA")
                        else:
                            print(f"    ✅ Célula {coluna}{linha} contém: '{valor}'")
                        
                        # Definir valor
                        if valor is not None:
                            print(f"  Preenchendo {campo_excel}: {valor}")
                            gerador.abertura_laje['d'][abertura].set(str(valor))
                        else:
                            print(f"  Definindo {campo_excel} como '0' (célula vazia)")
                            gerador.abertura_laje['d'][abertura].set("0")
                    else:
                        print(f"    ❌ {campo_excel}: NÃO MAPEADO no linhas_abcd")
                        gerador.abertura_laje['d'][abertura].set("0")
                
                # Verificar valores finais e refletir nos campos tipo_ da interface do gerador
                print("🔍 VALORES FINAIS DEFINIDOS D:")
                for abertura in aberturas_laje_d:
                    valor_final = gerador.abertura_laje['d'][abertura].get()
                    print(f"  abertura_laje_{abertura}_d: '{valor_final}'")
                    try:
                        lado = 'esq' if abertura.startswith('esq') else 'dir'
                        num = abertura[-1]
                        campo_tipo_nome = f"tipo_{lado}_{num}_D"
                        if hasattr(gerador.master, campo_tipo_nome):
                            campo_tipo = getattr(gerador.master, campo_tipo_nome)
                            if hasattr(campo_tipo, 'delete') and hasattr(campo_tipo, 'insert'):
                                campo_tipo.delete(0, 'end')
                                campo_tipo.insert(0, '1' if str(valor_final).strip() == '1' else '0')
                    except Exception:
                        pass
                
                # 6. Gerar o script diretamente
                print("Gerando script ABCD...")
                
                # VERIFICAR SE PILAR ESPECIAL ESTÁ ATIVO - LER DO EXCEL PARA ESTA COLUNA ESPECÍFICA
                pilar_especial_ativo = False
                # CORREÇÃO: O Conector salva o checkbox na coluna 1 (A), não na coluna atual
                # Primeiro tentar ler do Excel (linha 1000, coluna A)
                try:
                    linha_checkbox = 1000  # Linha onde o checkbox de pilar especial está armazenado
                    coluna_checkbox = 'A'  # CORREÇÃO: O Conector salva na coluna A (1), não na coluna atual
                    coluna_idx = letra_para_coluna(coluna)  # Converter coluna para número para debug
                    print(f"[PILAR_ESPECIAL] Lendo checkbox para pilar '{nome_pilar}' (coluna: {coluna}, índice: {coluna_idx}, linha: {linha_checkbox})")
                    print(f"[PILAR_ESPECIAL] CORREÇÃO: Lendo checkbox da coluna A (onde o Conector salva), não da coluna {coluna}")
                    valor_checkbox = sheet[f'{coluna_checkbox}{linha_checkbox}'].value
                    print(f"[PILAR_ESPECIAL] Valor lido do Excel (linha {linha_checkbox}, coluna {coluna_checkbox}): {valor_checkbox} (tipo: {type(valor_checkbox)})")
                    
                    # DEBUG: Verificar todas as colunas para diagnosticar
                    print(f"[PILAR_ESPECIAL] DEBUG: Verificando checkbox em todas as colunas (linha {linha_checkbox}):")
                    for col_debug in ['E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P']:
                        try:
                            valor_debug = sheet[f'{col_debug}{linha_checkbox}'].value
                            nome_debug = sheet[f'{col_debug}{linhas_abcd["nome"]}'].value
                            print(f"[PILAR_ESPECIAL]   Coluna {col_debug}: nome='{nome_debug}', checkbox={valor_debug}")
                        except:
                            pass
                    
                    # CORREÇÃO: Se o checkbox estiver vazio/None/zero, usar fallback da interface principal ANTES de converter
                    if valor_checkbox is None or (isinstance(valor_checkbox, (int, float)) and valor_checkbox == 0):
                        print(f"[PILAR_ESPECIAL] Checkbox vazio ou zero no Excel, tentando fallback da interface principal...")
                        if interface_principal and hasattr(interface_principal, 'ativar_pilar_especial'):
                            pilar_especial_ativo = interface_principal.ativar_pilar_especial.get()
                            print(f"[PILAR_ESPECIAL] Fallback usando interface principal: {pilar_especial_ativo}")
                        else:
                            print(f"[PILAR_ESPECIAL] Interface principal não disponível, assumindo pilar normal")
                            pilar_especial_ativo = False
                    else:
                        # Converter valor para booleano considerando vários formatos possíveis
                        if isinstance(valor_checkbox, bool):
                            pilar_especial_ativo = valor_checkbox
                        elif isinstance(valor_checkbox, (int, float)):
                            pilar_especial_ativo = bool(valor_checkbox) and valor_checkbox != 0
                        elif isinstance(valor_checkbox, str):
                            valor_str = valor_checkbox.strip().upper()
                            pilar_especial_ativo = valor_str in ('1', 'TRUE', 'SIM', 'S', 'YES', 'Y')
                        else:
                            pilar_especial_ativo = bool(valor_checkbox)
                        
                        print(f"[PILAR_ESPECIAL] Lido do Excel (linha {linha_checkbox}, coluna {coluna_checkbox}): {pilar_especial_ativo}")
                except Exception as e:
                    print(f"[PILAR_ESPECIAL] Aviso ao ler checkbox do Excel: {e}")
                    import traceback
                    traceback.print_exc()
                    # Fallback: ler da interface principal se disponível
                    if interface_principal and hasattr(interface_principal, 'ativar_pilar_especial'):
                        pilar_especial_ativo = interface_principal.ativar_pilar_especial.get()
                        print(f"[PILAR_ESPECIAL] Fallback usando interface principal: {pilar_especial_ativo}")
                    else:
                        print(f"[PILAR_ESPECIAL] Nenhum checkbox encontrado, assumindo pilar normal")
                        pilar_especial_ativo = False
                
                print(f"[PILAR_ESPECIAL] Pilar especial ativo (FINAL): {pilar_especial_ativo}")
                print(f"[VALIDACAO] Nome do pilar: '{nome_pilar}' (coluna: {coluna})")
                
                # VALIDAÇÃO FINAL: Verificar se o nome do pilar no gerador corresponde ao esperado
                nome_no_gerador = gerador.campos['nome'].get().strip() if 'nome' in gerador.campos else None
                if nome_no_gerador != nome_pilar:
                    print(f"[VALIDACAO] ⚠️ AVISO: Nome do pilar no gerador ('{nome_no_gerador}') diferente do esperado ('{nome_pilar}')")
                    print(f"[VALIDACAO] Corrigindo nome no gerador para '{nome_pilar}'")
                    gerador.campos['nome'].delete(0, 'end')
                    gerador.campos['nome'].insert(0, nome_pilar)
                
                if pilar_especial_ativo:
                    print(f"\n[PILAR_ESPECIAL] ==========================================")
                    print(f"[PILAR_ESPECIAL] DETECTADO PILAR ESPECIAL - GERANDO 2 SCRIPTS")
                    print(f"[PILAR_ESPECIAL] ==========================================\n")
                    
                    # CRÍTICO: Resetar flag ANTES de tudo para evitar persistência de pilares anteriores
                    print(f"[PILAR_ESPECIAL] Resetando flag usar_paineis_efgh ANTES de gerar Script 1")
                    if hasattr(gerador, 'usar_paineis_efgh'):
                        print(f"[PILAR_ESPECIAL] Flag anterior: {gerador.usar_paineis_efgh}")
                        gerador.usar_paineis_efgh = False
                    else:
                        gerador.usar_paineis_efgh = False
                    print(f"[PILAR_ESPECIAL] Flag resetada para Script 1: {gerador.usar_paineis_efgh}")
                    
                    # SALVAR VALORES ORIGINAIS antes de gerar Script 1
                    comprimento_original = gerador.campos['comprimento'].get()
                    largura_original = gerador.campos['largura'].get()
                    print(f"[PILAR_ESPECIAL] Valores originais salvos: comprimento={comprimento_original}, largura={largura_original}")
                    
                    # VALIDAÇÃO: Garantir que o nome do pilar no gerador está correto antes de gerar Script 1
                    nome_pilar_gerador = gerador.campos['nome'].get().strip() if 'nome' in gerador.campos else None
                    if nome_pilar_gerador != nome_pilar:
                        print(f"[VALIDACAO] ⚠️ AVISO: Corrigindo nome do pilar no gerador antes de gerar Script 1")
                        print(f"[VALIDACAO]   - Esperado: '{nome_pilar}' (da coluna {coluna})")
                        print(f"[VALIDACAO]   - Atual no gerador: '{nome_pilar_gerador}'")
                        gerador.campos['nome'].delete(0, 'end')
                        gerador.campos['nome'].insert(0, nome_pilar)
                        print(f"[VALIDACAO]   - Corrigido para: '{nome_pilar}'")
                    
                    # Verificar flag ANTES de chamar _gerar_script_com_dados_especiais
                    print(f"[PILAR_ESPECIAL] Verificação ANTES de gerar Script 1: usar_paineis_efgh = {getattr(gerador, 'usar_paineis_efgh', 'NÃO EXISTE')}")
                    
                    # SCRIPT 1: Painéis A,B,C,D + Parafusos A
                    script1_path = _gerar_script_com_dados_especiais(
                        gerador=gerador,
                        interface_principal=interface_principal,
                        usar_paineis_efgh=False,
                        usar_parafusos_especiais=True,
                        letra_parafuso='A',
                        ajustar_x_offset=False,
                        sufixo_nome=''
                    )
                    
                    # ANTES DO SCRIPT 2: Preencher interface_principal com dados E,F,G,H do Excel
                    # e depois preencher robô com esses dados calculados
                    print(f"[PILAR_ESPECIAL] Lendo dados dos painéis E,F,G,H do Excel e preenchendo interface_principal...")
                    _preencher_interface_principal_com_dados_efgh_excel(sheet, coluna, linhas_abcd, interface_principal, gerador)
                    
                    print(f"[PILAR_ESPECIAL] Preenchendo robô com dados E,F,G,H para Script 2...")
                    _preencher_robo_com_dados_efgh(gerador, interface_principal)
                    
                    # DEPOIS DE PREENCHER DADOS E,F,G,H: RELER dados básicos do Excel (altura, pavimento, niveis)
                    # IMPORTANTE: NÃO reler comprimento e largura aqui porque foram calculados por _preencher_robo_com_dados_efgh
                    # Isso garante que altura, pavimento e níveis estejam corretos para o Script 2
                    print(f"[PILAR_ESPECIAL] RELENDO dados básicos do Excel para Script 2 (altura, pavimento, niveis)...")
                    
                    # Reler apenas dados que NÃO são calculados a partir de E,F,G,H
                    campos_basicos = {
                        'altura': linhas_abcd.get('altura', 12),
                        'pavimento': linhas_abcd.get('pavimento', 3),
                        'nivel_saida': linhas_abcd.get('nivel_saida', 8),
                        'nivel_chegada': linhas_abcd.get('nivel_chegada', 9)
                    }
                    
                    for campo, linha_excel in campos_basicos.items():
                        try:
                            valor = sheet[f'{coluna}{linha_excel}'].value
                            if valor is not None:
                                print(f"[PILAR_ESPECIAL] Relendo {campo} do Excel: {valor}")
                                if campo in gerador.campos:
                                    gerador.campos[campo].delete(0, 'end')
                                    gerador.campos[campo].insert(0, str(valor))
                                    print(f"[PILAR_ESPECIAL] ✅ {campo} atualizado no gerador para Script 2: {valor}")
                                else:
                                    print(f"[PILAR_ESPECIAL] ⚠️ Campo {campo} não encontrado no gerador")
                            else:
                                print(f"[PILAR_ESPECIAL] ⚠️ Valor {campo} vazio no Excel (linha {linha_excel}, coluna {coluna})")
                        except Exception as e:
                            print(f"[PILAR_ESPECIAL] ⚠️ Erro ao reler {campo} do Excel: {e}")
                    
                    # VALIDAÇÃO: Garantir que o nome do pilar no gerador está correto antes de gerar Script 2
                    nome_pilar_gerador_script2 = gerador.campos['nome'].get().strip() if 'nome' in gerador.campos else None
                    if nome_pilar_gerador_script2 != nome_pilar:
                        print(f"[VALIDACAO] ⚠️ AVISO: Corrigindo nome do pilar no gerador antes de gerar Script 2")
                        print(f"[VALIDACAO]   - Esperado: '{nome_pilar}' (da coluna {coluna})")
                        print(f"[VALIDACAO]   - Atual no gerador: '{nome_pilar_gerador_script2}'")
                        gerador.campos['nome'].delete(0, 'end')
                        gerador.campos['nome'].insert(0, nome_pilar)
                        print(f"[VALIDACAO]   - Corrigido para: '{nome_pilar}'")
                    
                    # SCRIPT 2: Painéis E,F,G,H + Parafusos E + Offset X
                    # Se gerar_pelo_pavimento=True, NÃO aplicar offset X (o ordenador vai cuidar da ordenação)
                    ajustar_x_offset_script2 = not gerar_pelo_pavimento
                    print(f"[PILAR_ESPECIAL] gerar_pelo_pavimento={gerar_pelo_pavimento}, ajustar_x_offset_script2={ajustar_x_offset_script2}")
                    script2_path = _gerar_script_com_dados_especiais(
                        gerador=gerador,
                        interface_principal=interface_principal,
                        usar_paineis_efgh=True,
                        usar_parafusos_especiais=True,
                        letra_parafuso='E',
                        ajustar_x_offset=ajustar_x_offset_script2,
                        sufixo_nome='2'
                    )
                    
                    # RESTAURAR VALORES ORIGINAIS após gerar Script 2
                    print(f"[PILAR_ESPECIAL] Restaurando valores originais...")
                    gerador.campos['comprimento'].delete(0, 'end')
                    gerador.campos['comprimento'].insert(0, comprimento_original)
                    gerador.campos['largura'].delete(0, 'end')
                    gerador.campos['largura'].insert(0, largura_original)
                    print(f"[PILAR_ESPECIAL] Valores restaurados: comprimento={comprimento_original}, largura={largura_original}")
                    
                    print(f"\n[PILAR_ESPECIAL] ==========================================")
                    print(f"[PILAR_ESPECIAL] SCRIPTS GERADOS COM SUCESSO!")
                    print(f"[PILAR_ESPECIAL] Script 1: {script1_path}")
                    print(f"[PILAR_ESPECIAL] Script 2: {script2_path}")
                    print(f"[PILAR_ESPECIAL] ==========================================\n")
                    
                    # Usar o script 1 como script_abcd para compatibilidade
                    script_abcd = "DUAL_SCRIPT"  # Marcador para indicar que são 2 scripts
                    nome_arquivo_abcd = script1_path
                else:
                    # COMPORTAMENTO NORMAL: Gerar 1 script apenas
                    try:
                        print(f"[DEBUG] Chamando gerador.gerar_script() para pilar {nome_pilar}")
                        script_abcd = gerador.gerar_script()
                        print(f"[DEBUG] Script gerado com sucesso. Tamanho: {len(script_abcd) if script_abcd else 0} caracteres")
                    except Exception as e:
                        print(f"[DEBUG] ERRO ao gerar script: {e}")
                        import traceback
                        traceback.print_exc()
                        script_abcd = None
                
                # Inicializar variáveis para uso posterior
                nome_arquivo_base = None
                if not pilar_especial_ativo:
                    nome_arquivo_abcd = None
                
                # Verificar se o script foi gerado com sucesso
                if script_abcd is None:
                    print("Erro ao gerar o script. Verifique o log para mais detalhes.")
                elif pilar_especial_ativo:
                    # Pilar especial: scripts já foram salvos pela função helper
                    # NÃO salvar novamente para evitar duplicação
                    print(f"[PILAR_ESPECIAL] Scripts já salvos. Pulando salvamento adicional.")
                    try:
                        print(f"[PILAR_ESPECIAL] Script 1: {script1_path}")
                        print(f"[PILAR_ESPECIAL] Script 2: {script2_path}")
                    except NameError:
                        print(f"[PILAR_ESPECIAL] Aviso: Variáveis script1_path ou script2_path não encontradas")
                    # Não usar continue aqui - apenas não salvar o script novamente
                else:
                    # Criar diretórios e salvar o script NORMAL
                    # Usar path resolver para obter o caminho correto
                    import sys
                    import os
                    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
                    from utils.robust_path_resolver import robust_path_resolver
                    diretorio_base = os.path.join(robust_path_resolver.get_project_root(), "output", "scripts")

                    # Obter o pavimento (linha 3) para usar como nome da pasta
                    pavimento = sheet[f'{coluna}{linhas_abcd["pavimento"]}'].value
                    if not pavimento:
                        pavimento = "SEM_PAVIMENTO"

                    # Formatar o nome da pasta: substituir espaços por "_" e adicionar "_ABCD" (evitar duplicidade)
                    nome_pasta_pavimento = str(pavimento).replace(" ", "_")
                    if not nome_pasta_pavimento.upper().endswith("_ABCD"):
                        nome_pasta_pavimento += "_ABCD"

                    # Criar a pasta do pavimento se não existir
                    diretorio_pavimento = os.path.join(diretorio_base, nome_pasta_pavimento)
                    os.makedirs(diretorio_pavimento, exist_ok=True)

                    print(f"Salvando na pasta do pavimento: {diretorio_pavimento}")

                    # Criar nome do arquivo baseado no nome do pilar
                    nome_arquivo_base = os.path.join(diretorio_pavimento, str(nome_pilar))
                    nome_arquivo_abcd = f"{nome_arquivo_base}_ABCD.scr"

                    # Garantir que o script termine com nova linha para o AutoCAD processar corretamente
                    if script_abcd and not script_abcd.endswith('\r\n'):
                        # Normalizar para terminar com \r\n (nova linha do Windows)
                        script_abcd = script_abcd.rstrip('\n').rstrip('\r') + '\r\n'
                    
                    # Sempre sobrescrever o arquivo, não criar sufixos (UTF-16 LE com BOM)
                    with open(nome_arquivo_abcd, 'wb') as f:
                        # Adicionar BOM UTF-16 LE
                        f.write(b'\xFF\xFE')
                        # Converter conteúdo para UTF-16 LE
                        f.write(script_abcd.encode('utf-16-le'))

                    print(f"Script ABCD gerado para o pilar '{nome_pilar}' no pavimento '{pavimento}':")
                    print(f"  - {nome_arquivo_abcd}")
                
                # Encerra a interface gráfica APENAS se for a última coluna ou se houver apenas uma coluna
                # Isso evita destruir a aplicação quando múltiplas colunas estão sendo processadas (pavimento)
                if eh_ultima_coluna or total_colunas == 1:
                    try:
                        if app and app.root and app.root.winfo_exists():
                            app.root.destroy()
                            print(f"[DEBUG] Aplicação destruída após processar última coluna.")
                    except Exception as e:
                        print(f"[DEBUG] Aplicação já foi destruída ou não existe: {e}")
                else:
                    # Para múltiplas colunas, apenas fecha a janela mas mantém a aplicação para o combinador
                    try:
                        if app and app.root:
                            app.root.withdraw()  # Esconde a janela ao invés de destruir
                            print(f"[DEBUG] Janela escondida (pavimento com múltiplas colunas).")
                    except Exception as e:
                        print(f"[DEBUG] Erro ao esconder janela: {e}")

            else:
                print(f"Pulando coluna {coluna}: nome do pilar em branco.")
                colunas_vazias += 1
                if colunas_vazias >= 10:
                    print(f"Parando a busca após 10 colunas vazias consecutivas a partir da coluna {coluna}.")
                    parar_busca = True

        print("Fim do processamento da planilha.")

    except Exception as e:
        print(f"Erro ao processar a planilha: {e}")
        import traceback
        traceback.print_exc()

# Exemplo de uso:
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Automação ABCD - Geração de Scripts SCR")
    parser.add_argument("excel", nargs="?", help="Caminho do arquivo Excel")
    parser.add_argument("colunas", nargs="?", help="Colunas a serem processadas (ex: E,F,G)")
    parser.add_argument("pavimento", nargs="?", help="Pavimento a ser processado (opcional)")
    args = parser.parse_args()

    if args.excel:
        caminho_arquivo_excel = args.excel
        colunas = args.colunas.split(",") if args.colunas else None
        pavimento = args.pavimento
        print(f"[HEADLESS] Processando arquivo: {caminho_arquivo_excel}, colunas: {colunas}, pavimento: {pavimento}")
        if colunas:
            for coluna in colunas:
                print(f"Processando coluna {coluna}")
                preencher_campos_e_gerar_scripts(caminho_arquivo_excel, coluna_especifica=coluna, interface_principal=None)
        else:
            preencher_campos_e_gerar_scripts(caminho_arquivo_excel, interface_principal=None)
        print("Processamento concluído com sucesso!")
    else:
        # Modo antigo: interface gráfica
        pass  # main() removido para evitar erro de variável indefinida