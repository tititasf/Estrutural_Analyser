import os
import re
def natural_sort_key(s):
    """Chave para ordenação natural (ex: V1, V2, V10 em vez de V1, V10, V2)."""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', str(s))]
import tkinter as tk
from tkinter import filedialog
import time
import sys

def selecionar_diretorio():
    # Se passado argumento na linha de comando, usar ele
    if len(sys.argv) > 1:
        return sys.argv[1]
    root = tk.Tk()
    root.withdraw()  # Esconde a janela principal do tkinter
    diretorio = filedialog.askdirectory(title="Selecione a pasta com os arquivos SCR")
    return diretorio if diretorio else None

def editar_final_do_arquivo(arquivo_entrada, arquivo_saida, proximo_arquivo):
    # Leitura com retentativa
    for tentativa in range(1, 101):
        try:
            with open(arquivo_entrada, 'r', encoding='utf-16-le') as file:
                linhas = file.readlines()
            break
        except PermissionError as e:
            print(f"[Tentativa {tentativa}/100] ERRO de acesso ao ler {arquivo_entrada}: {e}")
            time.sleep(0.1)
    else:
        print(f"[FALHA] Não foi possível acessar {arquivo_entrada} após 100 tentativas!")
        return
    # Processamento igual
    ultimas_linhas = linhas[-6:]
    novas_linhas = linhas[:-6]
    while ultimas_linhas and (ultimas_linhas[-1].strip() in ["", ";", "-LAYER", "S Painéis"]):
        ultimas_linhas.pop()
    novas_linhas.extend(ultimas_linhas)
    ultimas_30_linhas = linhas[-5:] if len(linhas) >= 5 else linhas
    tem_cota = any('cota' in linha.lower() for linha in ultimas_30_linhas)
    # Escrita com retentativa
    for tentativa in range(1, 101):
        try:
            with open(arquivo_saida, 'w', encoding='utf-16-le') as file:
                file.writelines(novas_linhas)
                if proximo_arquivo:
                    if tem_cota:
                        file.write("\n;\n_SCRIPT\n")
                    else:
                        file.write(";\n_SCRIPT\n")
                    file.write(f"{proximo_arquivo}\n")
            break
        except PermissionError as e:
            print(f"[Tentativa {tentativa}/100] ERRO de acesso ao salvar {arquivo_saida}: {e}")
            time.sleep(0.1)
    else:
        print(f"[FALHA] Não foi possível salvar {arquivo_saida} após 100 tentativas!")

def processar_arquivos(diretorio):
    if not diretorio:
        print("Nenhum diretório selecionado. Operação cancelada.")
        return

    # Cria um diretório para os arquivos combinados
    diretorio_saida = os.path.join(diretorio, 'Combinados')
    os.makedirs(diretorio_saida, exist_ok=True)

    # Obtem a lista de arquivos SCR do diretório de entrada
    arquivos = [f for f in os.listdir(diretorio) 
               if f.endswith('.scr') and os.path.isfile(os.path.join(diretorio, f))]
    
    # Ordena os arquivos naturalmente
    arquivos = sorted(arquivos, key=natural_sort_key)

    if not arquivos:
        print("Nenhum arquivo .scr encontrado no diretório selecionado.")
        return

    print(f"Processando {len(arquivos)} arquivos...")
    
    for i, nome_arquivo in enumerate(arquivos):
        novo_nome = f"{i + 1}.scr"
        caminho_entrada = os.path.join(diretorio, nome_arquivo)
        caminho_saida = os.path.join(diretorio_saida, novo_nome)
        
        # Se houver próximo arquivo, use o caminho completo para o comando SCRIPT
        if i + 1 < len(arquivos):
            proximo_arquivo = os.path.abspath(os.path.join(diretorio_saida, f"{i + 2}.scr"))
        else:
            proximo_arquivo = ''
        
        editar_final_do_arquivo(caminho_entrada, caminho_saida, proximo_arquivo)
    
    print(f"Processamento concluído! Os arquivos combinados estão em: {diretorio_saida}")

if __name__ == "__main__":
    diretorio_selecionado = selecionar_diretorio()
    processar_arquivos(diretorio_selecionado)
