
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
from tkinter import filedialog, messagebox
from natsort import natsorted
import natsort
from collections import defaultdict
import re
import time

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

def ler_conteudo_script(caminho_arquivo):
    with open(caminho_arquivo, 'r', encoding='utf-16-le') as file:
        return file.read()

def extrair_nome_texto(conteudo):
    # Procura por comandos _TEXT ou TEXT no script e retorna o nome (linha seguinte)
    linhas = conteudo.split('\n')
    for i, linha in enumerate(linhas):
        if linha.strip().startswith('_TEXT') or linha.strip().startswith('TEXT'):
            # O nome está na terceira linha após o comando (padrão dos seus arquivos)
            if i + 3 < len(linhas):
                return linhas[i + 3].strip()
    return None

def extrair_coordenadas_texto(conteudo):
    # Procura por comandos _TEXT ou TEXT no script e retorna as coordenadas
    linhas = conteudo.split('\n')
    for i, linha in enumerate(linhas):
        if linha.strip().startswith('_TEXT') or linha.strip().startswith('TEXT'):
            # As coordenadas estão na segunda linha após o comando
            if i + 2 < len(linhas):
                return linhas[i + 2].strip()
    return None

def remover_todos_textos(conteudo):
    # Remove todos os blocos de _TEXT ou TEXT (com 4 linhas cada)
    linhas = conteudo.split('\n')
    resultado = []
    i = 0
    while i < len(linhas):
        if linhas[i].strip().startswith('_TEXT') or linhas[i].strip().startswith('TEXT'):
            i += 4  # pula o bloco inteiro
        else:
            resultado.append(linhas[i])
            i += 1
    return '\n'.join(resultado)

def substituir_nome_texto(conteudo, novo_nome):
    # Substitui o bloco _TEXT/TEXT pelo novo bloco com todos os nomes, preservando as coordenadas originais
    linhas = conteudo.split('\n')
    resultado = []
    i = 0
    substituido = False
    while i < len(linhas):
        if not substituido and (linhas[i].strip().startswith('_TEXT') or linhas[i].strip().startswith('TEXT')):
            # Preservar as coordenadas originais
            coordenadas_originais = None
            if i + 2 < len(linhas):
                coordenadas_originais = linhas[i + 2].strip()
            
            # Usar coordenadas originais se disponíveis, senão usar padrão
            coordenadas_finais = coordenadas_originais if coordenadas_originais else '-10.0,0.0'
            
            # Substitui o bloco inteiro por um novo bloco
            resultado.append(';')
            resultado.append('_TEXT')
            resultado.append(coordenadas_finais)
            resultado.append('90')
            resultado.append(novo_nome)
            resultado.append(';')
            i += 4  # pula o bloco antigo
            substituido = True
        else:
            resultado.append(linhas[i])
            i += 1
    return '\n'.join(resultado)

def editar_final_do_arquivo(arquivo_entrada, arquivo_saida, proximo_arquivo):
    with open(arquivo_entrada, 'r', encoding='utf-16-le') as file:
        linhas = file.readlines()

    # Processar apenas as últimas 6 linhas
    ultimas_linhas = linhas[-6:]
    novas_linhas = linhas[:-6]

    # Remove linhas em branco, que contenham apenas ";", "-LAYER" ou "S Painéis" nas últimas 6 linhas
    while ultimas_linhas and (ultimas_linhas[-1].strip() in ["", ";", "-LAYER", "S Painéis"]):
        ultimas_linhas.pop()

    # Verifica se o último comando é _LAYER nas últimas 5 linhas
    ultimo_comando_layer = False
    for linha in reversed(ultimas_linhas[-5:]):
        if "_LAYER" in linha:
            ultimo_comando_layer = True
            break

    novas_linhas.extend(ultimas_linhas)

    with open(arquivo_saida, 'w', encoding='utf-16-le') as file:
        file.writelines(novas_linhas)
        if proximo_arquivo:
            if ultimo_comando_layer:
                file.write("\n")  # Adiciona linha em branco se o último comando for _LAYER
            # Usar caminho absoluto para funcionar em frozen
            caminho_proximo = os.path.abspath(os.path.join(os.path.dirname(arquivo_saida), proximo_arquivo))
            # Converter para formato Windows (barras invertidas) para compatibilidade com AutoCAD
            caminho_proximo_windows = caminho_proximo.replace('/', '\\')
            file.write(f"SCRIPT\n{caminho_proximo_windows}\n")

def adicionar_script_ao_final(arquivo, proximo_arquivo):
    tentativas = 0
    while tentativas < 100:
        try:
            with open(arquivo, 'a', encoding='utf-16-le') as file:
                file.write('SCRIPT\n')
                # Usar caminho absoluto para funcionar em frozen
                caminho_proximo = os.path.abspath(os.path.join(os.path.dirname(arquivo), proximo_arquivo))
                # Converter para formato Windows (barras invertidas) para compatibilidade com AutoCAD
                caminho_proximo_windows = caminho_proximo.replace('/', '\\')
                file.write(f"{caminho_proximo_windows}\n")
            break
        except PermissionError:
            tentativas += 1
            time.sleep(0.05)  # espera 50ms antes de tentar novamente
            if tentativas == 100:
                raise

def processar_arquivos(diretorio):
    print(f"Processando diretório: {diretorio}")
    diretorio_saida = os.path.join(diretorio, 'Combinados')
    os.makedirs(diretorio_saida, exist_ok=True)
    
    # Obter lista de arquivos
    arquivos_brutos = [os.path.join(diretorio, f) for f in os.listdir(diretorio) if f.endswith('.scr')]
    
    # Função de ordenação customizada para garantir ordem correta dos scripts GRADES
    # Ordem: A, B, E, F, G, H para cada item
    def ordenar_scripts_grades(arquivo):
        nome = os.path.basename(arquivo)
        # Remover extensão
        base = nome.replace('.scr', '')
        
        # Verificar se é script com sufixo de letra (ex: P1.A, P4.E)
        # Padrão: NOME.LETRA (ex: P1.A, P4.E)
        match = re.match(r'^(.+)\.([A-H])$', base)
        if match:
            # É script com sufixo de letra
            nome_item = match.group(1)  # Ex: "P1" ou "P4"
            letra = match.group(2).upper()  # Ex: "A", "B", "E", "F", "G", "H"
            
            # Ordem das letras: A=1, B=2, E=3, F=4, G=5, H=6
            ordem_letras = {'A': 1, 'B': 2, 'E': 3, 'F': 4, 'G': 5, 'H': 6}
            ordem_num = ordem_letras.get(letra, 99)  # 99 para letras não mapeadas
            
            # Retornar tupla: (nome_item, ordem_letra) para ordenar corretamente
            return (nome_item, ordem_num)
        else:
            # É script sem sufixo de letra (comportamento padrão)
            return (base, 0)
    
    # Ordenar usando a função customizada
    # Primeiro agrupar por nome do item, depois ordenar por letra
    arquivos_por_item = {}
    for arquivo in arquivos_brutos:
        nome_item, ordem_letra = ordenar_scripts_grades(arquivo)
        if nome_item not in arquivos_por_item:
            arquivos_por_item[nome_item] = []
        arquivos_por_item[nome_item].append((arquivo, ordem_letra))
    
    # Ordenar itens naturalmente
    itens_ordenados = natsorted(arquivos_por_item.keys(), alg=natsort.ns.IGNORECASE)
    
    # Ordenar arquivos: primeiro por item (naturalmente), depois por letra (A, B, E, F, G, H)
    arquivos = []
    for item in itens_ordenados:
        # Ordenar arquivos deste item por ordem_letra
        arquivos_do_item = sorted(arquivos_por_item[item], key=lambda x: x[1])
        arquivos.extend([arquivo for arquivo, _ in arquivos_do_item])
    
    print(f"Arquivos encontrados: {len(arquivos)}")
    for i, arq in enumerate(arquivos, 1):
        print(f"  {i}: {os.path.basename(arq)}")
    
    # DEBUG: Agrupamento de scripts idênticos
    print(f"\n>>> [COMBINADOR_DEBUG] Iniciando agrupamento de scripts idênticos...")
    scripts_identicos = defaultdict(list)
    for caminho in arquivos:
        conteudo = ler_conteudo_script(caminho)
        nome_arquivo = os.path.basename(caminho)
        print(f"\n>>> [COMBINADOR_DEBUG] Processando: {nome_arquivo}")
        print(f">>> [COMBINADOR_DEBUG] Conteúdo lido (primeiras 200 chars): {conteudo[:200]}")
        nome_texto = extrair_nome_texto(conteudo)
        if nome_texto:
            print(f">>> [COMBINADOR_DEBUG] TEXT extraído: {nome_texto}")
        else:
            print(">>> [COMBINADOR_DEBUG] ATENÇÃO: Nenhum comando TEXT encontrado!")
        conteudo_sem_texto = remover_todos_textos(conteudo)
        print(f">>> [COMBINADOR_DEBUG] Conteúdo sem TEXT (primeiras 200 chars): {conteudo_sem_texto[:200]}")
        print(f">>> [COMBINADOR_DEBUG] Hash do conteúdo (primeiros 50 chars): {hash(conteudo_sem_texto[:50])}")
        scripts_identicos[conteudo_sem_texto].append((caminho, nome_texto))
    
    print(f"\n>>> [COMBINADOR_DEBUG] ==========================================")
    print(f">>> [COMBINADOR_DEBUG] RESULTADO DO AGRUPAMENTO:")
    print(f">>> [COMBINADOR_DEBUG] Total de grupos de scripts idênticos: {len(scripts_identicos)}")
    print(f">>> [COMBINADOR_DEBUG] Total de arquivos originais: {len(arquivos)}")
    print(f">>> [COMBINADOR_DEBUG] ==========================================")
    
    for idx, (conteudo, arquivos_grupo) in enumerate(scripts_identicos.items(), 1):
        print(f"\n>>> [COMBINADOR_DEBUG] Grupo {idx}: {len(arquivos_grupo)} arquivo(s) idêntico(s)")
        for caminho, nome in arquivos_grupo:
            print(f">>> [COMBINADOR_DEBUG]   - {os.path.basename(caminho)} com TEXT: {nome}")
        if len(arquivos_grupo) > 1:
            print(f">>> [COMBINADOR_DEBUG]   ⚠️ ATENÇÃO: Estes arquivos têm conteúdo idêntico (sem TEXT)")
            print(f">>> [COMBINADOR_DEBUG]   ✅ Mas serão processados SEPARADAMENTE (cada painel é único)")
    scripts_processados = []
    for conteudo, arquivos_grupo in scripts_identicos.items():
        # CORREÇÃO: Para pavimento, NÃO unificar scripts idênticos
        # Cada script deve ser processado separadamente, mesmo que tenha conteúdo idêntico
        # Apenas o nome TEXT muda, mas cada script representa um painel diferente (A, B, E, F, G, H)
        if len(arquivos_grupo) > 1:
            print(f">>> [COMBINADOR_DEBUG] Grupo com {len(arquivos_grupo)} arquivos idênticos detectado")
            print(f">>> [COMBINADOR_DEBUG] ⚠️ IMPORTANTE: Processando cada arquivo SEPARADAMENTE (não unificando)")
            print(f">>> [COMBINADOR_DEBUG] Motivo: Cada script representa um painel diferente (A, B, E, F, G, H)")
            
            # Processar cada arquivo separadamente (NÃO unificar)
            for caminho_entrada, nome_texto in arquivos_grupo:
                novo_nome = f"{len(scripts_processados) + 1}.scr"
                caminho_saida = os.path.join(diretorio_saida, novo_nome)
                proximo_arquivo = f"{len(scripts_processados) + 2}.scr" if len(scripts_processados) + 1 < len(arquivos) else ''
                editar_final_do_arquivo(caminho_entrada, caminho_saida, proximo_arquivo)
                scripts_processados.append(caminho_saida)
                print(f">>> [COMBINADOR_DEBUG]   ✅ Processado separadamente: {os.path.basename(caminho_entrada)} -> {novo_nome}")
        else:
            caminho_entrada, _ = arquivos_grupo[0]
            novo_nome = f"{len(scripts_processados) + 1}.scr"
            caminho_saida = os.path.join(diretorio_saida, novo_nome)
            proximo_arquivo = f"{len(scripts_processados) + 2}.scr" if len(scripts_processados) + 1 < len(arquivos) else ''
            editar_final_do_arquivo(caminho_entrada, caminho_saida, proximo_arquivo)
            scripts_processados.append(caminho_saida)
    print(f"Scripts processados: {scripts_processados}")
    # Messagebox removida para tornar o processo mais dinâmico
    print(f">>> ✅ Processamento finalizado com sucesso! Scripts originais: {len(arquivos)}, Scripts após combinação: {len(scripts_processados)}")
    # REMOVIDO: adicionar_script_ao_final não é mais necessário pois editar_final_do_arquivo já adiciona o comando SCRIPT

def selecionar_pasta():
    diretorio = filedialog.askdirectory()
    if diretorio:
        processar_arquivos(diretorio)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Combinador de SCR GRADES")
    parser.add_argument("diretorio", nargs="?", help="Diretório dos scripts SCR")
    args = parser.parse_args()
    if args.diretorio:
        processar_arquivos(args.diretorio)
    else:
        # Modo antigo: interface gráfica
        janela = tk.Tk()
        janela.title("Combinador de SCR")
        janela.geometry("300x150")
        botao_selecionar = tk.Button(janela, text="Selecionar Pasta", command=selecionar_pasta)
        botao_selecionar.pack(pady=50)
        janela.mainloop()
