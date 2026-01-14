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

            print(f"DEBUG_COMBINADOR: Lido {os.path.basename(arquivo_entrada)} - {len(linhas)} linhas.")
            if any("; === INICIO SECAO DE CORTE ===" in line for line in linhas):
                print(f"DEBUG_COMBINADOR: [SUCESSO] Seção de Corte ENCONTRADA em {os.path.basename(arquivo_entrada)}")
            else:
                print(f"DEBUG_COMBINADOR: [INFO] Sem Seção de Corte em {os.path.basename(arquivo_entrada)}")
            if len(linhas) < 10:
                print(f"AVISO: Arquivo muito curto ou vazio: {arquivo_entrada}")
            break
        except PermissionError as e:
            print(f"[Tentativa {tentativa}/100] ERRO de acesso ao ler {arquivo_entrada}: {e}")
            time.sleep(0.1)
    else:
        print(f"[FALHA] Não foi possível acessar {arquivo_entrada} após 100 tentativas!")
        return
    # Processamento igual
    ultimas_linhas = linhas[-8:] if len(linhas) >= 8 else linhas
    novas_linhas = linhas[:-len(ultimas_linhas)] if len(linhas) >= 8 else []
    
    # Remove apenas se for realmente lixo de final de script (ex: trocas de layer automáticas do CAD)
    while ultimas_linhas and (ultimas_linhas[-1].strip() in ["", ";", "-LAYER", "S Painéis", "S NOMENCLATURA"]):
        # Se a linha anterior for um INSERT (coordenadas), precisamos dos enters vazios.
        # Procuramos o comando _INSERT subindo nas linhas.
        is_insert_group = False
        for check_idx in range(len(ultimas_linhas)-1, max(-1, len(ultimas_linhas)-5), -1):
             if "_INSERT" in ultimas_linhas[check_idx]:
                 is_insert_group = True
                 break
        
        if is_insert_group:
            # Se for um grupo de INSERT, paramos de limpar para não tirar os Enters de confirmação
            break
        ultimas_linhas.pop()
    
    novas_linhas.extend(ultimas_linhas)
    
    content = "".join(novas_linhas)
    
    # --- TRATAMENTO FINAL INSERT (User Request: Estabilidade AutoCAD) ---
    # Garante que todo comando _INSERT tenha exatamente 2 espaços em branco após a coordenada
    import re
    # 1. (_INSERT\n)
    # 2. ([^\n]+\n)
    # 3. ([\d\.\,-]+\n)
    # 4. (\s*\n)* - Consome apenas linhas vazias ou com espaços após a coordenada
    content = re.sub(r'(_INSERT\n)([^\n]+\n)([\d\.\,-]+\n)(\s*\n)*', r'\1\2\3\n\n;\n', content)
    
    # Escrita com retentativa
    for tentativa in range(1, 101):
        try:
            with open(arquivo_saida, 'w', encoding='utf-16-le') as file:
                file.write(content)
                if proximo_arquivo:
                    # Se o conteúdo não termina em newline, adiciona
                    if content and not content.endswith("\n"):
                        file.write("\n")
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
    
    # Separa arquivos normais de arquivos de Visao Corte (VC-*)
    arquivos_vigas = [f for f in arquivos if not f.startswith("VC-")]
    arquivos_vc = [f for f in arquivos if f.startswith("VC-")]

    # Ordena os arquivos naturalmente
    arquivos_vigas = sorted(arquivos_vigas, key=natural_sort_key)
    arquivos_vc = sorted(arquivos_vc, key=natural_sort_key)
    
    # Lista final: Vigas primeiro, depois VC
    arquivos = arquivos_vigas + arquivos_vc

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
