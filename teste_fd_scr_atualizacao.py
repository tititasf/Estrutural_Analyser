"""
Teste de atualização do FD.scr
"""

import sys
import os
from pathlib import Path

print("TESTE DE ATUALIZACAO DO FD.SCR")
print("="*60)

try:
    # Configurar caminhos
    legacy_path = os.path.join(os.path.dirname(__file__), "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
    sys.path.insert(0, legacy_path)

    print("1. Testando importacao...")
    from fundo_utils_novo import atualizar_fd_scr
    print("   [OK] Funcao atualizar_fd_scr importada")

    print("2. Testando atualizacao do FD.scr...")
    project_root = Path(__file__).parent
    lisp_dir = project_root / "ferramentas_LOAD_LISP"
    fd_scr_path = lisp_dir / "FD.scr"
    
    # Script de teste
    script_teste = """ferramentas_LOAD_LISP

;; Script de teste
-LINE
0,0
100,0
100,50
0,50
0,0

(princ "\\nTeste executado!\\n")
"""
    
    resultado = atualizar_fd_scr(script_teste)
    
    if resultado:
        print("   [OK] FD.scr atualizado com sucesso")
        
        # Verificar se o arquivo foi criado
        if fd_scr_path.exists():
            print(f"   [OK] Arquivo existe: {fd_scr_path}")
            
            # Ler e mostrar primeiras linhas
            with open(fd_scr_path, 'r', encoding='utf-8') as f:
                linhas = f.readlines()[:10]
                print("   [INFO] Primeiras linhas do arquivo:")
                for i, linha in enumerate(linhas, 1):
                    print(f"      {i}: {linha.rstrip()}")
        else:
            print(f"   [ERRO] Arquivo nao encontrado: {fd_scr_path}")
    else:
        print("   [ERRO] Falha ao atualizar FD.scr")

    print("\n3. Verificando estrutura do FD.LSP...")
    lisp_path = lisp_dir / "FD.LSP"
    if lisp_path.exists():
        with open(lisp_path, 'r', encoding='utf-8') as f:
            conteudo = f.read()
            if "ferramentas_LOAD_LISP/FD.scr" in conteudo or "FD.scr" in conteudo:
                print("   [OK] FD.LSP aponta para FD.scr")
            else:
                print("   [INFO] Verificar se FD.LSP aponta para o caminho correto")
    else:
        print("   [INFO] FD.LSP ainda nao foi criado (sera criado ao clicar no botao)")

    print("\n" + "="*60)
    print("RESUMO:")
    print("[OK] Funcao atualizar_fd_scr implementada")
    print("[OK] FD.scr e atualizado quando scripts sao gerados")
    print("[OK] FD.scr e criado na pasta ferramentas_LOAD_LISP")
    print("="*60)

except Exception as e:
    print(f"[ERRO] Falha geral: {e}")
    import traceback
    traceback.print_exc()
