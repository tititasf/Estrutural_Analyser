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
    padrao = r"numeracao:\s*([^,]+),\s*largura:\s*([\d\.]+),\s*altura:\s*([\d\.]+)(?:,\s*continuacao:\s*([^)]+))?"
    match = re.search(padrao, linha)
    if match:
        numeracao = match.group(1).strip()
        largura = float(match.group(2))
        altura = float(match.group(3))
        continuacao = match.group(4).strip() if match.group(4) else ""
        return numeracao, largura, altura, continuacao
    return None, None, None, None

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
    # Ex: V12B.Ba -> g1=12, g2=B, g3=B, g4=a
    padrao = r'^[vV]?(\d+)(.*?)\.([a-zA-Z])([a-zA-Z])?'
    match = re.search(padrao, s)
    if match:
        num = int(match.group(1))
        # Remover extensão ou traços extras do grupo 2 e 3 se houver sujeira
        sufixo_viga = match.group(2) 
        lado = match.group(3)        
        segmento = match.group(4) or ""
        return (num, sufixo_viga, lado, segmento)
    
    # Fallback
    num_fallback = extrair_numero_base(s)
    return (num_fallback, s, '')

def agrupar_por_nome_viga(lista_infos):
    """Agrupa pelo 'DNA' numérico + Lado da viga."""
    grupos = defaultdict(list)
    for info in lista_infos:
        # Usa os 3 primeiros elementos (Número, Sufixo, Lado) para agrupar
        # O 4º elemento (Segmento) serve apenas para regras internas do loop
        componentes = extrair_chave_grupo(info['arquivo'])
        chave = componentes[:3]
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
                    numeracao, largura, altura, continuacao = extrair_info_linha(linha)
                    if numeracao:
                        lista_infos.append({
                            'arquivo': arquivo,
                            'caminho': caminho,
                            'numeracao': numeracao,
                            'largura': largura,
                            'altura': altura,
                            'continuacao': continuacao
                        })
                    break
    
    # Separação Vigas vs VCs
    lista_vigas = [i for i in lista_infos if not i['arquivo'].startswith('VC-')]
    lista_vc = [i for i in lista_infos if i['arquivo'].startswith('VC-')]
    
    grupos = agrupar_por_nome_viga(lista_vigas)
    
    # Processamento Reverso (Para V1 ficar no Topo)
    # Entre (2,'','B') e (2,'','A'):
    # Ordem normal: (2,A) < (2,B).
    # Reverso: (2,B) vem antes de (2,A).
    # (2,B) processado primeiro (Y mais baixo).
    # (2,A) processado depois (Y mais alto).
    
    espacamento_y = 200 # Diminuído em 100 (era 300) conforme solicitado
    desloc_y = 0
    
    # Debug para ver a ordem de desenho
    # Reverso para que V1 tenha Y maior e fique no TOPO (já que Y cresce para cima)
    chaves_ordenadas = sorted(grupos.keys(), reverse=True)
    
    # Rastrear limites globais das vigas para posicionar o VC perto
    global_min_x = float('inf')
    global_min_y = float('inf')

    for chave in chaves_ordenadas:
        grupo = grupos[chave]
        desloc_x = 0
        altura_max_grupo = 0
        
        for idx, info in enumerate(grupo):
            with open(info['caminho'], 'r', encoding='utf-16') as f:
                linhas = f.readlines()
            min_x, min_y = encontrar_min_xy(linhas)
            
            # Atualizar limites globais (considerando o deslocamento que SERÁ aplicado? 
            # O script soma desloc_x nas coordenadas originais.
            # Então a posição final será x_orig + desloc_x.
            # Min X final será min_x_original + 0 (para o primeiro grupo/item).
            # Vamos pegar o menor x_original encontrado como referência base.
            if min_x < global_min_x: global_min_x = min_x
            if min_y < global_min_y: global_min_y = min_y
            
            desloc_extra_x = 0
            # Se for continuação (ex: Ab)
            # Logica de deslocamento REMOVIDA para resetar posicionamento original
            if idx > 0:
                # Removido o deslocamento extra de 10 para aproximar os segmentos conforme solicitado
                desloc_extra_x = 0
            
            print(f"DEBUG_ORDEM: Grupo {chave} | Item: {info['numeracao']} | Cont: {info.get('continuacao','')} | XF: {(desloc_x + desloc_extra_x):.1f} | YF: {desloc_y:.1f}")
            
            novas_linhas = []
            for linha in linhas:
                def ajusta_coord(m):
                    # Normaliza (subtrai min) e aplica deslocamento
                    x = float(m.group(1)) - min_x + desloc_x + desloc_extra_x
                    y = float(m.group(2)) - min_y + desloc_y
                    return f"{x:.2f},{y:.2f}"
                nova_linha = re.sub(r'(-?\d+\.?\d*),(-?\d+\.?\d*)', ajusta_coord, linha)
                novas_linhas.append(nova_linha)
            
            with open(info['caminho'], 'w', encoding='utf-16') as f:
                f.writelines(novas_linhas)
                
            # Verificar se é obstáculo para adicionar espaçamento extra PARA O PROXIMO ITEM
            continuacao = str(info.get('continuacao', '')).lower()
            espaco_obstaculo = 0
            if 'obstaculo' in continuacao or 'vigacontinuacao' in continuacao:
                espaco_obstaculo = 30.0
            
            desloc_x += info['largura'] + 0 + espaco_obstaculo
            altura_max_grupo = max(altura_max_grupo, info['altura'])
                
        desloc_y += altura_max_grupo + espacamento_y
    
    # ----------------------------------------------------
    # PROCESSAMENTO DE VISÃO DE CORTE (VC)
    # Posicionar todas numa coluna à esquerda das vigas
    # Usando o global_min_x encontrado para ficar RELATIVO
    # ----------------------------------------------------
    if lista_vc:
        print("DEBUG_ORDEM: Processando Visões de Corte...")
        
        # Se não achou nada (nenhuma viga), usa 0
        if global_min_x == float('inf'): global_min_x = 0
        if global_min_y == float('inf'): global_min_y = 0
        
        # Posiciona VC à esquerda e abaixo das vigas (ajuste refinado: +2000 em X da posição anterior)
        x_vc_coluna = global_min_x - 700
        
        # Alinha Y inicial com o Y inicial das vigas (global_min_y) menos 13000
        y_vc_atual = global_min_y - 13000
        
        # Ordenar VCs por nome (VC-1, VC-2...) em REVERSO
        # Para que o VC-1 fique no TOPO (Y maior)
        lista_vc.sort(key=lambda x: natural_sort_key(x['arquivo']), reverse=True)
        
        for info in lista_vc:
            with open(info['caminho'], 'r', encoding='utf-16') as f:
                linhas = f.readlines()
            
            # Normalizar para 0,0 (find min) ou assumir que o gerador ja fez em 0,0?
            # O gerador fez self._gerar_secao_corte(dA, dB, 0, 0)
            # Então assumimos que min_x pode ser 0 ou próximo.
            # Mas vamos forçar o deslocamento absoluto para x_vc_coluna
            
            # Encontrar bounding box atual
            min_x, min_y = encontrar_min_xy(linhas)
            
            # offset para mover do que está (min_x) para o alvo (x_vc_coluna)
            offset_x = x_vc_coluna - min_x
            offset_y = y_vc_atual - min_y
            
            print(f"DEBUG_ORDEM: VC {info['arquivo']} | XF: {x_vc_coluna:.1f} | YF: {y_vc_atual:.1f}")
            
            novas_linhas = []
            for linha in linhas:
                def ajusta_coord(m):
                    x = float(m.group(1)) + offset_x
                    y = float(m.group(2)) + offset_y
                    return f"{x:.2f},{y:.2f}"
                nova_linha = re.sub(r'(-?\d+\.?\d*),(-?\d+\.?\d*)', ajusta_coord, linha)
                novas_linhas.append(nova_linha)

            with open(info['caminho'], 'w', encoding='utf-16') as f:
                f.writelines(novas_linhas)
            
            y_vc_atual += info['altura'] + 450 # Aumentado em 50 (era 400) conforme solicitado

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
