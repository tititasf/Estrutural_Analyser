import os
from natsort import natsorted
import re
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import time
import sys

class ProcessadorCoordenadas:
    def __init__(self):
        self.posicao_y = 0  # Posição Y atual
        self.altura_anterior = 0  # Altura do último item processado
        self.larguras_grupo_atual = []  # Lista de larguras dos itens do grupo atual
        
    def extrair_dimensoes_dimlinear(self, linhas):
        """Extrai as dimensões baseadas nos comandos DIMLINEAR horizontais"""
        dimensoes = []
        encontrou_dimlinear = False
        coordenadas_dimlinear = []
        
        for i, linha in enumerate(linhas):
            if '_DIMLINEAR' in linha.upper():
                encontrou_dimlinear = True
                coordenadas = []
                # Procura as próximas coordenadas após o comando DIMLINEAR
                for j in range(i + 1, min(i + 5, len(linhas))):  # Olha as próximas 4 linhas
                    matches = re.finditer(r'(-?\d+\.?\d*),(-?\d+\.?\d*)', linhas[j])
                    for match in matches:
                        x = float(match.group(1))
                        y = float(match.group(2))
                        coordenadas.append((x, y))
                    if len(coordenadas) >= 2:  # Se encontrou pelo menos 2 coordenadas
                        # Verifica se é uma dimensão horizontal (y's próximos)
                        if len(coordenadas) >= 2 and abs(coordenadas[0][1] - coordenadas[1][1]) < 1:
                            largura = abs(coordenadas[0][0] - coordenadas[1][0])
                            dimensoes.append(largura)
                            coordenadas_dimlinear.extend(coordenadas)
                        break
        
        if not dimensoes:
            print("AVISO: Nenhuma dimensão DIMLINEAR horizontal encontrada!")
            return 0, []
            
        # Retorna a maior largura encontrada e todas as coordenadas dos DIMLINEAR
        return round(max(dimensoes), 1), coordenadas_dimlinear

    def extrair_coordenadas(self, linhas):
        """Extrai todas as coordenadas do arquivo SCR"""
        coords = []
        
        # Primeiro extrai a largura baseada nos DIMLINEAR
        largura, coords_dimlinear = self.extrair_dimensoes_dimlinear(linhas)
        
        # Depois extrai todas as coordenadas para calcular altura e posição
        for linha in linhas:
            matches = re.finditer(r'(-?\d+\.?\d*),(-?\d+\.?\d*)', linha)
            for match in matches:
                x = float(match.group(1))
                y = float(match.group(2))
                coords.append((x, y))
        
        if not coords:
            print("AVISO: Nenhuma coordenada encontrada!")
            return [], (0, 0, 0, 0)
        
        # Calcula os limites
        min_x = min(x for x, _ in coords)
        max_x = max(x for x, _ in coords)
        min_y = min(y for _, y in coords)
        max_y = max(y for _, y in coords)
        
        # Usa a altura calculada normalmente, mas a largura vem do DIMLINEAR
        altura = round(max_y - min_y, 1)   # Arredonda para 1 casa decimal
        
        # Se não encontrou nenhum DIMLINEAR, usa a largura tradicional
        if largura == 0:
            largura = round(max_x - min_x, 1)
            print("AVISO: Usando largura baseada nas coordenadas extremas!")
        
        return coords, (largura, altura, min_x, min_y)

    def processar_arquivo(self, caminho_arquivo, primeiro_do_grupo=False):
        """Processa um único arquivo .scr"""
        try:
            with open(caminho_arquivo, 'r', encoding='utf-16') as f:
                linhas = f.readlines()
        except Exception as e:
            print(f"Erro ao ler arquivo {caminho_arquivo}: {e}")
            return 0, 0
        
        # Extrai informações do arquivo
        nome_viga = self.extrair_nome_viga(caminho_arquivo)
        numeracao = self.extrair_numeracao(caminho_arquivo)
        
        # Extrai coordenadas e dimensões
        coords, (largura, altura, min_x, min_y) = self.extrair_coordenadas(linhas)
        
        if not coords:
            return 0, 0
        
        # Calcula a posição X baseada nas larguras anteriores do grupo
        if primeiro_do_grupo:
            self.larguras_grupo_atual = []  # Limpa o histórico de larguras para o novo grupo
            posicao_x = 0  # Primeiro item sempre começa em X = 0
        else:
            # Soma todas as larguras anteriores do grupo
            posicao_x = sum(self.larguras_grupo_atual)
        
        print(f"\nProcessando Viga:")
        print(f"Nome: {nome_viga}")
        print(f"Numeração: {numeracao}")
        print(f"Arquivo: {Path(caminho_arquivo).name}")
        print(f"Altura: {altura:.1f}")
        print(f"Largura: {largura:.1f}")
        print(f"Larguras anteriores: {[f'{x:.1f}' for x in self.larguras_grupo_atual]}")
        print(f"Posição X calculada: {posicao_x:.1f}")
        print(f"Posição Y: {self.posicao_y:.1f}")
        print(f"Posição X original: {min_x:.1f}")
        print("-" * 50)
        
        # Aplica os deslocamentos
        novo_conteudo = []
        deslocamento_x = posicao_x - min_x  # Calcula o deslocamento necessário
        
        for linha in linhas:
            nova_linha = re.sub(
                r'(-?\d+\.?\d*),(-?\d+\.?\d*)',
                lambda m: f"{round(float(m.group(1)) + deslocamento_x, 1):.1f}," +  # Ajusta X
                         f"{round(float(m.group(2)) - min_y + self.posicao_y, 1):.1f}",  # Ajusta Y
                linha
            )
            novo_conteudo.append(nova_linha)
        
        try:
            with open(caminho_arquivo, 'w', encoding='utf-16') as f:
                f.writelines(novo_conteudo)
        except Exception as e:
            print(f"Erro ao salvar arquivo {caminho_arquivo}: {e}")
            return 0, 0
        
        # Adiciona a largura atual ao histórico do grupo
        self.larguras_grupo_atual.append(largura)
        
        return altura, largura
    
    def exibir_log(self, nome_arquivo, largura, altura, alteracao_y_aplicada):
        """Exibe informações de log do processamento"""
        print(f"\nArquivo: {nome_arquivo}")
        print(f"Dimensões do retângulo: Largura = {largura:.1f}, Altura = {altura:.1f}")
        print(f"Alteracao Y aplicada: {alteracao_y_aplicada:.1f}")

    def encontrar_coordenada_nome(self, caminho_arquivo):
        # Busca a coordenada do _TEXT do nome no arquivo SCR
        try:
            with open(caminho_arquivo, 'r', encoding='utf-16') as f:
                linhas = f.readlines()
            for i, linha in enumerate(linhas):
                if '_TEXT' in linha.upper():
                    # Procura coordenada na linha seguinte
                    if i+1 < len(linhas):
                        match = re.search(r'(-?\d+\.?\d*),(-?\d+\.?\d*)', linhas[i+1])
                        if match:
                            x = float(match.group(1))
                            y = float(match.group(2))
                            return x, y
        except Exception as e:
            print(f"Erro ao buscar coordenada do nome: {e}")
        return 0, 0

    def extrair_nome_viga(self, caminho_arquivo):
        # Busca o valor do _TEXT do nome no arquivo SCR
        try:
            with open(caminho_arquivo, 'r', encoding='utf-16') as f:
                linhas = f.readlines()
            for i, linha in enumerate(linhas):
                if '_TEXT' in linha.upper():
                    # O valor do nome está 4 linhas abaixo
                    if i+4 < len(linhas):
                        valor = linhas[i+4].strip()
                        if valor:
                            return valor
        except Exception as e:
            print(f"Erro ao buscar nome da viga: {e}")
        return ''

    def extrair_numeracao(self, caminho_arquivo):
        # Busca o valor da numeracao no início do arquivo SCR
        try:
            with open(caminho_arquivo, 'r', encoding='utf-16') as f:
                for _ in range(5):
                    linha = f.readline()
                    if linha.startswith('; (numeracao:'):
                        valor = linha.split(':',1)[1].replace(')','').strip()
                        return valor
        except Exception as e:
            print(f"Erro ao buscar numeracao: {e}")
        return ''

    def extrair_ajuste(self, caminho_arquivo):
        # Lê o valor do ajuste do próprio arquivo .scr (linha ; Ajuste: n)
        try:
            with open(caminho_arquivo, 'r', encoding='utf-16') as f:
                linhas = f.readlines()
            for linha in reversed(linhas):
                if '; Ajuste:' in linha:
                    try:
                        return float(linha.split(':',1)[1].strip())
                    except Exception:
                        return 0
        except Exception:
            pass
        return 0

    def _agrupar_por_numeracao(self, numeracoes):
        """Agrupa os arquivos por número inteiro e ordena as frações"""
        grupos = {}
        for arquivo, numeracao in numeracoes:
            try:
                if '.' in numeracao:
                    num_inteiro = int(numeracao.split('.')[0])
                    num_fracao = float(numeracao)
                else:
                    num_inteiro = int(numeracao)
                    num_fracao = float(num_inteiro)
                
                if num_inteiro not in grupos:
                    grupos[num_inteiro] = []
                grupos[num_inteiro].append((arquivo, num_fracao))
            except (ValueError, TypeError):
                print(f"Erro ao processar numeração: {numeracao}")
                continue
        
        # Ordena as frações dentro de cada grupo
        for grupo in grupos.values():
            grupo.sort(key=lambda x: x[1])
        
        return grupos

    def processar_grupo(self, grupo_arquivos, pasta):
        """Processa um grupo de arquivos (número inteiro e suas frações)"""
        altura_grupo = 0
        for i, (arquivo, _) in enumerate(grupo_arquivos):
            caminho_completo = os.path.join(pasta, arquivo)
            altura, _ = self.processar_arquivo(caminho_completo, primeiro_do_grupo=(i==0))
            altura_grupo = max(altura_grupo, altura)  # Usa a maior altura do grupo
        return altura_grupo

    def processar_arquivos(self, pasta, numeracoes):
        """Processa todos os arquivos organizando por grupos"""
        grupos = self._agrupar_por_numeracao(numeracoes)
        self.posicao_y = 0
        
        # Processa cada grupo em ordem numérica
        numeros_grupos = sorted(grupos.keys())
        print("\nOrdem de processamento dos grupos:")
        for num in numeros_grupos:
            print(f"Grupo {num}: {[arquivo for arquivo, _ in grupos[num]]}")
        print("\nIniciando processamento detalhado:")
        
        for num_inteiro in numeros_grupos:
            print(f"\nProcessando Grupo {num_inteiro}")
            print("=" * 50)
            
            # Processa o grupo atual e obtém a altura máxima do grupo
            altura_grupo = self.processar_grupo(grupos[num_inteiro], pasta)
            
            # Incrementa Y para o próximo grupo
            if altura_grupo > 0:
                self.posicao_y += altura_grupo + 50  # Espaçamento de 50 entre grupos

def selecionar_diretorio():
    # Se passado argumento na linha de comando, usar ele
    if len(sys.argv) > 1:
        return sys.argv[1]
    root = tk.Tk()
    root.withdraw()  # Esconde a janela principal do tkinter
    diretorio = filedialog.askdirectory(
        title="Selecione a pasta com os arquivos SCR para ordenar coordenadas"
    )
    return diretorio if diretorio else None

def atualizar_comando_combinado(primeiro_arquivo_path):
    """Atualiza o arquivo comando_TESTE_VIGA_TVTV.scr com o caminho do primeiro arquivo"""
    # Caminho fixo para o arquivo comando_TESTE_VIGA_TVTV.scr
    comando_path = "C:/Users/thier/Downloads/Vigas/A_B/Ferramentas/TESTE_VIGA_TVTV.scr"
    
    try:
        # Abre o arquivo em modo de escrita binária para garantir o encoding correto
        with open(comando_path, 'w') as f:
            # Prepara o conteúdo
            conteudo = "_SCRIPT\n"
            caminho_formatado = primeiro_arquivo_path.replace('\\', '/')
            conteudo += f"{caminho_formatado}\n"
            conteudo += ""
            
            # Codifica e salva o conteúdo com BOM
            f.write(conteudo.encode('utf-16-le'))
        
        print(f"\nArquivo comando_FDFD_COMBINADO.scr atualizado com sucesso!")
        print(f"Novo caminho: {caminho_formatado}")
    except Exception as e:
        print(f"Erro ao atualizar comando_FDFD_COMBINADO.scr: {str(e)}")

def tem_obstaculo_no_arquivo(caminho_arquivo):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-16') as f:
            conteudo = f.read()
        # Critério: se encontrar a palavra 'OBSTACULO' no arquivo
        return 'OBSTACULO' in conteudo.upper()
    except Exception:
        return True  # Por segurança, assume obstáculo se não conseguir ler

def tem_viga_continuacao_no_arquivo(caminho_arquivo):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-16') as f:
            conteudo = f.read()
        # Critério: se encontrar a palavra 'VIGA CONTINUACAO' no arquivo
        return 'VIGA CONTINUACAO' in conteudo.upper()
    except Exception:
        return False  # Por segurança, assume que não é continuação se não conseguir ler

def main():
    # Solicita ao usuário que selecione a pasta
    pasta = selecionar_diretorio()
    
    if not pasta:
        print("Nenhum diretório selecionado. Operação cancelada.")
        return
    
    # Verifica se existem arquivos .scr na pasta
    arquivos = [f for f in os.listdir(pasta) if f.endswith('.scr') and f != 'comando_FDFD_COMBINADO.scr']
    if not arquivos:
        messagebox.showwarning(
            "Aviso",
            "Nenhum arquivo .scr encontrado no diretório selecionado."
        )
        return
    
    print(f"Pasta selecionada: {pasta}")
    print(f"Encontrados {len(arquivos)} arquivos .scr")
    print("\nIniciando processamento...")
    
    processador = ProcessadorCoordenadas()
    
    # Coleta numerações de todos os arquivos
    numeracoes = []
    for arquivo in arquivos:
        caminho_completo = os.path.join(pasta, arquivo)
        numeracao = processador.extrair_numeracao(caminho_completo)
        if numeracao:  # Só inclui se tiver numeração
            numeracoes.append((arquivo, numeracao))
    
    if not numeracoes:
        messagebox.showwarning(
            "Aviso",
            "Nenhum arquivo com numeração válida encontrado."
        )
        return
    
    # Processa os arquivos usando o novo sistema de grupos
    processador.processar_arquivos(pasta, numeracoes)
    
    # Atualiza o arquivo comando_FDFD_COMBINADO.scr com o caminho do primeiro arquivo
    if arquivos:
        primeiro_arquivo = os.path.abspath(os.path.join(pasta, arquivos[0]))
        atualizar_comando_combinado(primeiro_arquivo)
    
    print("\nProcessamento concluído!")
    messagebox.showinfo(
        "Concluído",
        f"Processamento finalizado!\n{len(arquivos)} arquivos foram processados."
    )

if __name__ == "__main__":
    main()