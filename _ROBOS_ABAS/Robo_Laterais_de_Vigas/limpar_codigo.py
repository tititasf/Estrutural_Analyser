import re
import os

def limpar_codigo(arquivo_entrada, arquivo_saida=None):
    """
    Remove todos os comentários e prints de um arquivo Python
    """
    if arquivo_saida is None:
        nome_base, extensao = os.path.splitext(arquivo_entrada)
        arquivo_saida = f"{nome_base}_limpo{extensao}"
    
    # Ler o conteúdo do arquivo
    with open(arquivo_entrada, 'r', encoding='utf-8') as f:
        conteudo = f.read()
    
    # Obter tamanho original
    tamanho_original = len(conteudo)
    linhas_original = conteudo.count('\n') + 1
    
    
    # Remover comentários de linha única (# ...)
    conteudo = re.sub(r'#.*$', '', conteudo, flags=re.MULTILINE)
    
    # Remover todas as linhas em branco
    conteudo = re.sub(r'\n\s*\n', '\n', conteudo)
    
    # Escrever o conteúdo limpo no arquivo de saída
    with open(arquivo_saida, 'w', encoding='utf-8') as f:
        f.write(conteudo)
    
    # Calcular estatísticas
    tamanho_final = len(conteudo)
    linhas_final = conteudo.count('\n') + 1
    reducao_bytes = tamanho_original - tamanho_final
    reducao_linhas = linhas_original - linhas_final
    
    if tamanho_original > 0:
        percentual_reducao = (reducao_bytes / tamanho_original) * 100
    else:
        percentual_reducao = 0
    
    print(f"Arquivo limpo salvo como: {arquivo_saida}")
    print(f"Tamanho original: {tamanho_original} bytes ({linhas_original} linhas)")
    print(f"Tamanho final: {tamanho_final} bytes ({linhas_final} linhas)")
    print(f"Redução: {reducao_bytes} bytes ({percentual_reducao:.2f}%)")
    print(f"Linhas removidas: {reducao_linhas}")
    
    return arquivo_saida

if __name__ == "__main__":
    arquivo_entrada = "A_B/robo_laterais_viga_limpo2.py"
    arquivo_saida = "A_B/robo_laterais_viga_limpo233.py"
    
    if os.path.exists(arquivo_entrada):
        limpar_codigo(arquivo_entrada, arquivo_saida)
    else:
        print(f"O arquivo {arquivo_entrada} não foi encontrado.") 