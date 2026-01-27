#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script rápido para verificar se os scripts foram gerados e fazer comparação básica
"""

import os
from pathlib import Path

def read_utf16(file_path: Path) -> str:
    """Lê arquivo UTF-16 LE"""
    with open(file_path, 'rb') as f:
        raw = f.read()
    if raw.startswith(b'\xff\xfe'):
        raw = raw[2:]
    return raw.decode('utf-16-le', errors='ignore')

def main():
    project_root = Path(__file__).parent.parent.parent
    
    # Verificar scripts gerados
    scripts_dir = project_root / "SCRIPTS_ROBOS"
    legacy_dir = project_root / "_ROBOS_ABAS" / "contexto_legacy_pilares"
    
    print("\n" + "=" * 100)
    print("VERIFICAÇÃO RÁPIDA: Scripts Gerados")
    print("=" * 100)
    
    # Procurar por diretórios de pavimento (estrutura: Subsolo_CIMA, Subsolo_ABCD, Subsolo_GRADES)
    pavimentos_cima = [d for d in scripts_dir.iterdir() if d.is_dir() and d.name.endswith("_CIMA")]
    pavimentos_abcd = [d for d in scripts_dir.iterdir() if d.is_dir() and d.name.endswith("_ABCD")]
    pavimentos_grades = [d for d in scripts_dir.iterdir() if d.is_dir() and d.name.endswith("_GRADES")]
    
    # Extrair nome base do pavimento (ex: "Subsolo" de "Subsolo_CIMA")
    pavimento_base = None
    if pavimentos_cima:
        pavimento_base = pavimentos_cima[0].name.replace("_CIMA", "")
    elif pavimentos_abcd:
        pavimento_base = pavimentos_abcd[0].name.replace("_ABCD", "")
    elif pavimentos_grades:
        pavimento_base = pavimentos_grades[0].name.replace("_GRADES", "")
    
    if not pavimento_base:
        print("[AVISO] Nenhum diretorio de pavimento encontrado em SCRIPTS_ROBOS")
        print(f"   Diretorios encontrados: {[d.name for d in scripts_dir.iterdir() if d.is_dir()][:10]}")
        return
    
    print(f"\n[OK] Pavimento base encontrado: {pavimento_base}")
    
    # Verificar scripts legacy
    legacy_files = {
        'CIMA': legacy_dir / "Ptestelegacy_CIMA.scr",
        'ABCD': legacy_dir / "Ptestelegacy_ABCD.scr",
        'A': legacy_dir / "Ptestelegacy.A.scr",
        'B': legacy_dir / "Ptestelegacy.B.scr"
    }
    
    # Verificar scripts gerados
    print("\n[INFO] Verificando scripts gerados:")
    for tipo, legacy_path in legacy_files.items():
        print(f"\n[{tipo}]")
        
        if not legacy_path.exists():
            print(f"  [AVISO] Legacy nao encontrado: {legacy_path.name}")
            continue
        
        # Procurar script gerado
        if tipo == 'CIMA':
            atual_dir = scripts_dir / f"{pavimento_base}_CIMA" / "Combinados"
            atual_files = list(atual_dir.glob("*.scr")) if atual_dir.exists() else []
        elif tipo == 'ABCD':
            atual_dir = scripts_dir / f"{pavimento_base}_ABCD" / "Combinados"
            atual_files = list(atual_dir.glob("*.scr")) if atual_dir.exists() else []
        else:  # A ou B
            atual_dir = scripts_dir / f"{pavimento_base}_GRADES"
            sufixo = f".{tipo}.scr"
            pattern = f"*{sufixo}"
            atual_files = list(atual_dir.glob(pattern)) if atual_dir.exists() else []
            if not atual_files:
                combinados = atual_dir / "Combinados"
                if combinados.exists():
                    atual_files = list(combinados.glob(pattern))
        
        if not atual_files:
            print(f"  [AVISO] Script gerado nao encontrado em: {atual_dir}")
            continue
        
        atual_path = atual_files[0]
        print(f"  [OK] Legacy: {legacy_path.name}")
        print(f"  [OK] Gerado: {atual_path.name}")
        
        # Comparação básica
        try:
            legacy_content = read_utf16(legacy_path)
            atual_content = read_utf16(atual_path)
            
            legacy_lines = len(legacy_content.splitlines())
            atual_lines = len(atual_content.splitlines())
            
            print(f"  [INFO] Legacy: {legacy_lines} linhas")
            print(f"  [INFO] Gerado: {atual_lines} linhas")
            print(f"  [INFO] Diferenca: {atual_lines - legacy_lines:+d} linhas")
            
            if legacy_content == atual_content:
                print(f"  [OK] IDENTICO byte-a-byte!")
            else:
                print(f"  [AVISO] DIFERENTE")
                
                # Contar comandos principais
                legacy_layers = legacy_content.count('_LAYER')
                atual_layers = atual_content.count('_LAYER')
                legacy_inserts = legacy_content.count('-INSERT')
                atual_inserts = atual_content.count('-INSERT')
                
                print(f"     LAYER: Legacy={legacy_layers}, Gerado={atual_layers}")
                print(f"     INSERT: Legacy={legacy_inserts}, Gerado={atual_inserts}")
                
        except Exception as e:
            print(f"  [ERRO] Erro ao comparar: {e}")

if __name__ == '__main__':
    main()
