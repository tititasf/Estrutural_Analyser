
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
import re
import tkinter as tk
from tkinter import filedialog, messagebox
from natsort import natsorted
import natsort

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
                file.write("\n;\n")  # Adiciona linha em branco e ";" se o último comando for _LAYER
            file.write(";\nSCRIPT\n")
            # Usar caminho absoluto para funcionar em frozen
            caminho_proximo = os.path.abspath(os.path.join(os.path.dirname(arquivo_saida), proximo_arquivo))
            # Converter para formato Windows (barras invertidas) para compatibilidade com AutoCAD
            caminho_proximo_windows = caminho_proximo.replace('/', '\\')
            file.write(f"{caminho_proximo_windows}\n")


def processar_arquivos(diretorio, mostrar_mensagem=True):
    """
    Processa arquivos SCR no diretório especificado.
    
    Args:
        diretorio: Diretório contendo os arquivos .scr
        mostrar_mensagem: Se True, mostra messagebox ao final (modo interativo).
                         Se False, apenas imprime no console (modo subprocess).
    """
    # Cria um diretório para os arquivos combinados
    diretorio_saida = os.path.join(diretorio, 'Combinados')
    os.makedirs(diretorio_saida, exist_ok=True)

    # Obtem a lista completa de arquivos com caminhos completos
    arquivos_brutos = [os.path.join(diretorio, f) for f in os.listdir(diretorio) if f.endswith('.scr')]
    
    # Função de ordenação customizada para garantir que script 1 venha antes do script 2
    def ordenar_scripts(arquivo):
        nome = os.path.basename(arquivo)
        # Remover extensão
        base = nome.replace('.scr', '')
        
        # Verificar se é script 2 do especial (termina com número após _ABCD)
        # Ex: P4_ABCD2.scr -> base = "P4_ABCD2"
        match = re.match(r'^(.+_ABCD)(\d+)$', base)
        if match:
            # É script 2 (ou 3, 4, etc) do especial
            prefixo = match.group(1)  # Ex: "P4_ABCD"
            sufixo_num = int(match.group(2))  # Ex: 2
            # Retornar tupla: (prefixo, sufixo_num) para ordenar corretamente
            # Script 1 (sem sufixo) terá sufixo_num = 0 implicitamente
            return (prefixo, sufixo_num)
        else:
            # É script normal ou script 1 do especial (sem sufixo numérico)
            # Retornar tupla com sufixo_num = 0 para garantir que venha antes dos scripts com sufixo
            return (base, 0)
    
    # Ordenar usando natsorted com a função customizada
    # Isso garante que P4_ABCD.scr (sufixo_num=0) venha antes de P4_ABCD2.scr (sufixo_num=2)
    # e também garante ordenação natural (P1, P2, P10 em vez de P1, P10, P2)
    # Primeiro agrupar por prefixo, depois ordenar prefixos naturalmente, depois ordenar por sufixo_num
    # Primeiro agrupar por prefixo usando natsorted
    arquivos_por_prefixo = {}
    for arquivo in arquivos_brutos:
        prefixo, sufixo_num = ordenar_scripts(arquivo)
        if prefixo not in arquivos_por_prefixo:
            arquivos_por_prefixo[prefixo] = []
        arquivos_por_prefixo[prefixo].append((arquivo, sufixo_num))
    
    # Ordenar prefixos naturalmente
    prefixos_ordenados = natsorted(arquivos_por_prefixo.keys(), alg=natsort.ns.IGNORECASE)
    
    # Ordenar arquivos: primeiro por prefixo (naturalmente), depois por sufixo_num
    arquivos = []
    for prefixo in prefixos_ordenados:
        # Ordenar arquivos deste prefixo por sufixo_num
        arquivos_do_prefixo = sorted(arquivos_por_prefixo[prefixo], key=lambda x: x[1])
        arquivos.extend([arquivo for arquivo, _ in arquivos_do_prefixo])

    print(f">>> [CONECTOR] Arquivos .scr encontrados: {len(arquivos)}")
    for arquivo in arquivos:
        print(f">>> [CONECTOR]   - {os.path.basename(arquivo)}")

    for i, caminho_entrada in enumerate(arquivos):
        # Renomeia o arquivo de saída apenas com números sequenciais
        novo_nome = f"{i + 1}.scr"
        caminho_saida = os.path.join(diretorio_saida, novo_nome)
        
        # Define o próximo arquivo para o script
        proximo_arquivo = f"{i + 2}.scr" if i + 1 < len(arquivos) else ''
        
        editar_final_do_arquivo(caminho_entrada, caminho_saida, proximo_arquivo)
    
    print(f">>> [CONECTOR] Processamento finalizado com sucesso! {len(arquivos)} arquivos processados.")
    
    # Mostrar messagebox apenas se solicitado (modo interativo)
    if mostrar_mensagem:
        try:
            messagebox.showinfo("Concluído", "Processamento finalizado com sucesso!")
        except Exception as e:
            # Se houver erro ao mostrar messagebox (ex: aplicação destruída), apenas imprime
            print(f">>> [CONECTOR] Aviso: Não foi possível mostrar mensagem: {e}")

def selecionar_pasta():
    diretorio = filedialog.askdirectory()
    if diretorio:
        processar_arquivos(diretorio, mostrar_mensagem=True)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Combinador de SCR ABCD")
    parser.add_argument("diretorio", nargs="?", help="Diretório dos scripts SCR")
    args = parser.parse_args()
    if args.diretorio:
        # Modo subprocess: não mostrar messagebox para evitar conflitos com aplicação principal
        processar_arquivos(args.diretorio, mostrar_mensagem=False)
    else:
        # Modo antigo: interface gráfica (interativo)
        janela = tk.Tk()
        janela.title("Combinador de SCR")
        janela.geometry("300x150")
        botao_selecionar = tk.Button(janela, text="Selecionar Pasta", command=lambda: processar_arquivos(selecionar_pasta(), mostrar_mensagem=True))
        botao_selecionar.pack(pady=50)
        janela.mainloop()
