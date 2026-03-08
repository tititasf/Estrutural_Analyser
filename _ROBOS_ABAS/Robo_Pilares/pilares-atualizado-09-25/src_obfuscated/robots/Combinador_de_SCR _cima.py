
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

def remover_ultimas_linhas(linhas, ultimo_arquivo):
    """
    Retorna todas as linhas sem remover nada.
    """
    return linhas

def editar_final_do_arquivo(arquivo_entrada, arquivo_saida, proximo_arquivo, ultimo_arquivo):
    with open(arquivo_entrada, 'r', encoding='utf-16-le') as file:
        linhas = file.readlines()
    # Remove as últimas 7 linhas se não for o último arquivo
    novas_linhas = remover_ultimas_linhas(linhas, ultimo_arquivo)

    with open(arquivo_saida, 'w', encoding='utf-16-le') as file:
        file.writelines(novas_linhas)
        if proximo_arquivo:
            file.write(";\nSCRIPT\n")
            # Usar caminho absoluto para funcionar em frozen
            caminho_proximo = os.path.abspath(os.path.join(os.path.dirname(arquivo_saida), proximo_arquivo))
            # Converter para formato Windows (barras invertidas) para compatibilidade com AutoCAD
            caminho_proximo_windows = caminho_proximo.replace('/', '\\')
            file.write(f"{caminho_proximo_windows}\n")

def processar_arquivos(diretorio):
    # Cria um diretório para os arquivos combinados
    diretorio_saida = os.path.join(diretorio, 'Combinados')
    os.makedirs(diretorio_saida, exist_ok=True)

    # CORREÇÃO: Filtrar apenas scripts combinados finais para pilares especiais
    # e scripts normais para pilares comuns, EXCLUINDO partes soltas
    arquivos = []
    arquivos_combinados = []
    arquivos_normais = []
    
    # Primeiro, identificar todos os scripts combinados para saber quais pilares especiais existem
    pilares_especiais = set()
    for f in os.listdir(diretorio):
        if f.endswith('_COMBINADO_CIMA.scr'):
            # Extrair nome do pilar (ex: P4_COMBINADO_CIMA.scr -> P4)
            nome_pilar = f.replace('_COMBINADO_CIMA.scr', '')
            pilares_especiais.add(nome_pilar)
            arquivos_combinados.append(os.path.join(diretorio, f))
    
    # Agora processar scripts normais, excluindo partes soltas de pilares especiais
    for f in os.listdir(diretorio):
        if f.endswith('_CIMA.scr') and not f.endswith('_COMBINADO_CIMA.scr'):
            # Verificar se é uma parte solta de pilar especial
            nome_base = f.replace('_CIMA.scr', '')
            # Se o nome base contém um pilar especial conhecido, é uma parte solta
            eh_parte_solta = any(pilar in nome_base for pilar in pilares_especiais)
            
            if not eh_parte_solta:
                # Script normal (pilar comum)
                arquivos_normais.append(os.path.join(diretorio, f))
            else:
                print(f"[COMBINADOR] IGNORANDO parte solta: {f}")
    
    # Priorizar scripts combinados, depois scripts normais
    arquivos = arquivos_combinados + arquivos_normais
    
    # Ordenar arquivos naturalmente
    arquivos = natsorted(arquivos, alg=natsort.ns.IGNORECASE)
    
    print(f"[COMBINADOR] Diretório: {diretorio}")
    print(f"[COMBINADOR] Scripts combinados encontrados: {len(arquivos_combinados)}")
    print(f"[COMBINADOR] Scripts normais encontrados: {len(arquivos_normais)}")
    print(f"[COMBINADOR] Total de arquivos a processar: {len(arquivos)}")
    for i, arquivo in enumerate(arquivos):
        tipo = "COMBINADO" if arquivo in arquivos_combinados else "NORMAL"
        print(f"[COMBINADOR] Arquivo {i+1} ({tipo}): {os.path.basename(arquivo)}")

    for i, caminho_entrada in enumerate(arquivos):
        # Renomeia o arquivo de saída apenas com números sequenciais
        novo_nome = f"{i + 1}.scr"
        caminho_saida = os.path.join(diretorio_saida, novo_nome)
        
        # Define o próximo arquivo para o script
        proximo_arquivo = f"{i + 2}.scr" if i + 1 < len(arquivos) else ''
        
        # Verifica se é o último arquivo
        ultimo_arquivo = (i == len(arquivos) - 1)
        
        editar_final_do_arquivo(caminho_entrada, caminho_saida, proximo_arquivo, ultimo_arquivo)
    
    print(f"[COMBINADOR] Processamento concluído!")
    print(f"[COMBINADOR] Total de arquivos processados: {len(arquivos)}")
    print(f"[COMBINADOR] Arquivos gerados na pasta Combinados:")
    for i in range(len(arquivos)):
        print(f"[COMBINADOR]   {i+1}.scr")
    
    # Messagebox removida para tornar o processo mais dinâmico
    print(">>> ✅ Processamento finalizado com sucesso!")

def selecionar_pasta():
    diretorio = filedialog.askdirectory()
    if diretorio:
        processar_arquivos(diretorio)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Combinador de SCR CIMA")
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
