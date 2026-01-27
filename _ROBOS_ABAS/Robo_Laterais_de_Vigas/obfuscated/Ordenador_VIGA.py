import os
import re
import sys
import tkinter as tk
from tkinter import filedialog
from collections import defaultdict

def selecionar_diretorio():
    if len(sys.argv) > 1:
        return sys.argv[1]
    root = tk.Tk()
    root.withdraw()
    diretorio = filedialog.askdirectory(title="Selecione a pasta com os arquivos SCR para ordenar coordenadas")
    return diretorio if diretorio else None

# Função para extrair numeração, largura e altura da linha de cabeçalho
# Exemplo da linha: ; (numeracao: 13.1, largura: 320.97, altura: 44.00)
def extrair_info_linha(linha):
    # Captura tudo até a vírgula na numeração para suportar nomes ou sufixos
    padrao = r"numeracao:\s*([^,]+),\s*largura:\s*([\d\.]+),\s*altura:\s*([\d\.]+)"
    match = re.search(padrao, linha)
    if match:
        numeracao = match.group(1).strip()
        largura = float(match.group(2))
        altura = float(match.group(3))
        return numeracao, largura, altura
    return None, None, None

def natural_sort_key(s):
    """Chave para ordenação natural (1, 2, 10 em vez de 1, 10, 2)."""
    import re
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', str(s))]

def extrair_numero_base(s):
    """Extrai o número base de uma string (fallback)."""
    if not s: return 0
    m = re.search(r'[vV](\d+)', s)
    if m: return int(m.group(1))
    nums = re.findall(r'\d+', s)
    return int(nums[0]) if nums else 0

def extrair_chave_grupo(s):
    """
    Retorna uma tupla chave para agrupamento: (NumeroInt, SufixoNome, Lado).
    Ex: 'V1.Aa' -> (1, '', 'A')
    Ex: 'V12B.Ba' -> (12, 'B', 'B')
    Ex: 'V2.Ba' -> (2, '', 'B')
    """
    if not s: return (0, '', '')
    
    # Regex para capturar componentes: V{Num}{Resto}.{Lado}{Seg}
    # Ex: V12B.Ba -> g1=12, g2=B, g3=B
    padrao = r'^[vV]?(\d+)(.*?)\.([a-zA-Z])'
    match = re.search(padrao, s)
    if match:
        num = int(match.group(1))
        # Remover extensão ou traços extras do grupo 2 e 3 se houver sujeira
        sufixo_viga = match.group(2) 
        lado = match.group(3)        
        return (num, sufixo_viga, lado)
    
    # Fallback
    num_fallback = extrair_numero_base(s)
    return (num_fallback, s, '')

def agrupar_por_nome_viga(lista_infos):
    """Agrupa pelo 'DNA' numérico + Lado da viga."""
    grupos = defaultdict(list)
    for info in lista_infos:
        # Usa o nome do arquivo como fonte primária
        chave = extrair_chave_grupo(info['arquivo'])
        grupos[chave].append(info)
    
    # Ordena itens dentro de cada grupo por NOME DO ARQUIVO
    for k in grupos:
        grupos[k].sort(key=lambda x: natural_sort_key(x['arquivo'])) 
    return grupos

def encontrar_min_xy(linhas):
    min_x = None
    min_y = None
    for linha in linhas:
        for m in re.finditer(r'(-?\d+\.?\d*),(-?\d+\.?\d*)', linha):
            x = float(m.group(1))
            y = float(m.group(2))
            if min_x is None or x < min_x:
                min_x = x
            if min_y is None or y < min_y:
                min_y = y
    return min_x or 0, min_y or 0

def processar_pasta(pasta):
    arquivos = [f for f in os.listdir(pasta) if f.endswith('.scr')]
    lista_infos = []
    for arquivo in arquivos:
        caminho = os.path.join(pasta, arquivo)
        with open(caminho, 'r', encoding='utf-16') as f:
            for linha in f:
                if linha.strip().startswith('; (numeracao:'):
                    numeracao, largura, altura = extrair_info_linha(linha)
                    if numeracao:
                        lista_infos.append({
                            'arquivo': arquivo,
                            'caminho': caminho,
                            'numeracao': numeracao,
                            'largura': largura,
                            'altura': altura
                        })
                    break
    
    grupos = agrupar_por_nome_viga(lista_infos)
    
    # Processamento Reverso (Para V1 ficar no Topo)
    # Entre (2,'','B') e (2,'','A'):
    # Ordem normal: (2,A) < (2,B).
    # Reverso: (2,B) vem antes de (2,A).
    # (2,B) processado primeiro (Y mais baixo).
    # (2,A) processado depois (Y mais alto).
    
    espacamento_y = 150
    desloc_y = 0
    
    # Debug para ver a ordem de desenho
    chaves_ordenadas = sorted(grupos.keys(), reverse=True)
    
    for chave in chaves_ordenadas:
        grupo = grupos[chave]
        desloc_x = 0
        altura_max_grupo = 0
        
        for idx, info in enumerate(grupo):
            with open(info['caminho'], 'r', encoding='utf-16') as f:
                linhas = f.readlines()
            min_x, min_y = encontrar_min_xy(linhas)
            
            desloc_extra_x = 0
            # Se for continuação (ex: Ab), recua 20cm
            if idx > 0:
                desloc_extra_x = -20
            
            print(f"DEBUG_ORDEM: Grupo {chave} | Item: {info['numeracao']} | XF: {(desloc_x + desloc_extra_x):.1f} | YF: {desloc_y:.1f}")
            
            novas_linhas = []
            for linha in linhas:
                def ajusta_coord(m):
                    x = float(m.group(1)) + desloc_x + desloc_extra_x
                    y = float(m.group(2)) + desloc_y
                    return f"{x:.2f},{y:.2f}"
                nova_linha = re.sub(r'(-?\d+\.?\d*),(-?\d+\.?\d*)', ajusta_coord, linha)
                novas_linhas.append(nova_linha)
            
            with open(info['caminho'], 'w', encoding='utf-16') as f:
                f.writelines(novas_linhas)
                
            desloc_x += info['largura'] + 50
            altura_max_grupo = max(altura_max_grupo, info['altura'])
                
        desloc_y += altura_max_grupo + espacamento_y
    print('Processamento concluído!')

def atualizar_comando_combinado(primeiro_arquivo_path):
    comando_path = "C:/Users/rvene/Desktop/Automacao_cad/Vigas/A_B/Ferramentas/TESTE_VIGA_TVTV.scr"
    try:
        with open(comando_path, 'w') as f:
            conteudo = "_SCRIPT\n"
            caminho_formatado = primeiro_arquivo_path.replace('\\', '/')
            conteudo += f"{caminho_formatado}\n"
            conteudo += ""
            f.write(conteudo.encode('utf-16-le'))
        print(f"\nArquivo TESTE_VIGA_TVTV.scr atualizado com sucesso!")
        print(f"Novo caminho: {caminho_formatado}")
    except Exception as e:
        print(f"Erro ao atualizar TESTE_VIGA_TVTV.scr: {str(e)}")

if __name__ == "__main__":
    pasta = selecionar_diretorio()
    if not pasta or not os.path.isdir(pasta):
        print('Pasta inválida!')
    else:
        processar_pasta(pasta)
        arquivos = [f for f in os.listdir(pasta) if f.endswith('.scr')]
        if arquivos:
            primeiro_arquivo = os.path.abspath(os.path.join(pasta, arquivos[0]))
            atualizar_comando_combinado(primeiro_arquivo)
