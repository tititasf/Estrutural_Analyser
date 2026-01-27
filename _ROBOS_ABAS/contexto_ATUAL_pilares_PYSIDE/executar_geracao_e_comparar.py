#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para executar geração de scripts e comparar com legacy
Acompanha todo o processo de geração e executa comparação detalhada
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional

# Adicionar paths
project_root = Path(__file__).parent.parent.parent
robo_pilares_path = project_root / "_ROBOS_ABAS" / "Robo_Pilares" / "pilares-atualizado-09-25"
sys.path.insert(0, str(robo_pilares_path))
sys.path.insert(0, str(robo_pilares_path / "src"))

from models.pilar_model import PilarModel
from models.pavimento_model import PavimentoModel
from models.obra_model import ObraModel
from services.automation_service import AutomationOrchestratorService

def read_utf16(file_path: Path) -> str:
    """Lê arquivo UTF-16 LE"""
    with open(file_path, 'rb') as f:
        raw = f.read()
    if raw.startswith(b'\xff\xfe'):
        raw = raw[2:]
    return raw.decode('utf-16-le', errors='ignore')

def criar_dados_teste_p1():
    """
    Cria dados de teste baseados no pilar P1 do legacy.
    Valores extraídos do script legacy Ptestelegacy_CIMA.scr
    """
    return PilarModel(
        numero="1",
        nome="P1",
        comprimento=44.0,
        largura=44.0,
        altura=300.0,
        pavimento="P1",
        # Parafusos (valores de exemplo - ajustar conforme necessário)
        par_1_2=0.0,
        par_2_3=0.0,
        par_3_4=0.0,
        par_4_5=0.0,
        par_5_6=0.0,
        par_6_7=0.0,
        par_7_8=0.0,
        par_8_9=0.0,
        # Grades Grupo 1
        grade_1=0.0,
        distancia_1=0.0,
        grade_2=0.0,
        distancia_2=0.0,
        grade_3=0.0,
        # Detalhes Grades Grupo 1
        detalhe_grade1_1=0.0,
        detalhe_grade1_2=0.0,
        detalhe_grade1_3=0.0,
        detalhe_grade1_4=0.0,
        detalhe_grade1_5=0.0,
        detalhe_grade2_1=0.0,
        detalhe_grade2_2=0.0,
        detalhe_grade2_3=0.0,
        detalhe_grade2_4=0.0,
        detalhe_grade2_5=0.0,
        detalhe_grade3_1=0.0,
        detalhe_grade3_2=0.0,
        detalhe_grade3_3=0.0,
        detalhe_grade3_4=0.0,
        detalhe_grade3_5=0.0,
        # Pilar especial
        pilar_especial_ativo=False,
        tipo_pilar_especial="L",
    )

def executar_geracao_completa():
    """
    Executa geração completa de scripts (CIMA, ABCD, GRADES) e acompanha o processo.
    """
    print("\n" + "=" * 100)
    print("EXECUÇÃO: Geração Completa de Scripts")
    print("=" * 100)
    
    # Criar service
    service = AutomationOrchestratorService(str(project_root))
    print(f"[EXEC] Service criado: {service}")
    print(f"[EXEC] Scripts dir: {service.scripts_dir}")
    
    # Criar dados de teste
    pilar = criar_dados_teste_p1()
    obra = ObraModel(nome="Teste", scripts_dir=str(project_root / "SCRIPTS_ROBOS"))
    pavimento = PavimentoModel(nome="P1", pilares=[pilar])
    
    print(f"\n[EXEC] Dados de teste criados:")
    print(f"  Obra: {obra.nome}")
    print(f"  Pavimento: {pavimento.nome}")
    print(f"  Pilar: {pilar.nome} (comp={pilar.comprimento}, larg={pilar.largura}, alt={pilar.altura})")
    
    # Executar geração completa
    print(f"\n[EXEC] Iniciando geração completa (CIMA + ABCD + GRADES)...")
    start_time = time.time()
    
    try:
        result = service.generate_full_paviment_orchestration(pavimento, obra)
        elapsed = time.time() - start_time
        
        print(f"\n[EXEC] ✅ Geração concluída em {elapsed:.2f}s")
        print(f"[EXEC] Resultado: {result}")
        
        return True, pavimento.nome
        
    except Exception as e:
        print(f"\n[EXEC] ❌ Erro na geração: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def verificar_scripts_gerados(pavimento_nome: str):
    """
    Verifica quais scripts foram gerados e seus tamanhos.
    """
    print("\n" + "=" * 100)
    print("VERIFICAÇÃO: Scripts Gerados")
    print("=" * 100)
    
    scripts_dir = project_root / "SCRIPTS_ROBOS"
    pav_safe = pavimento_nome.replace(" ", "_").replace("-", "_")
    
    tipos = ["CIMA", "ABCD", "GRADES"]
    scripts_encontrados = {}
    
    for tipo in tipos:
        tipo_dir = scripts_dir / f"{pav_safe}_{tipo}"
        combinados_dir = tipo_dir / "Combinados"
        
        print(f"\n[{tipo}] Verificando: {tipo_dir}")
        
        if tipo_dir.exists():
            # Listar todos os .scr
            scr_files = list(tipo_dir.glob("*.scr"))
            print(f"  Scripts individuais: {len(scr_files)}")
            for scr in scr_files[:5]:  # Primeiros 5
                size = scr.stat().st_size
                print(f"    - {scr.name}: {size} bytes")
            
            # Verificar combinados
            if combinados_dir.exists():
                combinados = list(combinados_dir.glob("*.scr"))
                print(f"  Scripts combinados: {len(combinados)}")
                for comb in combinados:
                    size = comb.stat().st_size
                    content = read_utf16(comb)
                    lines = len(content.splitlines())
                    scripts_encontrados[tipo] = {
                        'path': comb,
                        'size': size,
                        'lines': lines,
                        'content': content
                    }
                    print(f"    - {comb.name}: {size} bytes, {lines} linhas")
        else:
            print(f"  ⚠️ Diretório não existe")
    
    return scripts_encontrados

def comparar_com_legacy(scripts_gerados: dict):
    """
    Compara scripts gerados com scripts legacy de referência.
    """
    print("\n" + "=" * 100)
    print("COMPARAÇÃO: Scripts Gerados vs Legacy")
    print("=" * 100)
    
    legacy_dir = project_root / "_ROBOS_ABAS" / "contexto_legacy_pilares"
    
    comparacoes = {
        'CIMA': {
            'legacy': legacy_dir / "Ptestelegacy_CIMA.scr",
            'atual': scripts_gerados.get('CIMA', {}).get('path')
        },
        'ABCD': {
            'legacy': legacy_dir / "Ptestelegacy_ABCD.scr",
            'atual': scripts_gerados.get('ABCD', {}).get('path')
        }
    }
    
    for tipo, paths in comparacoes.items():
        print(f"\n[{tipo}] Comparação:")
        
        legacy_path = paths['legacy']
        atual_path = paths['atual']
        
        if not legacy_path.exists():
            print(f"  ⚠️ Script legacy não encontrado: {legacy_path}")
            continue
        
        if not atual_path or not atual_path.exists():
            print(f"  ⚠️ Script atual não encontrado")
            continue
        
        try:
            # Ler arquivos
            legacy_content = read_utf16(legacy_path)
            atual_content = read_utf16(atual_path)
            
            # Estatísticas
            legacy_lines = len(legacy_content.splitlines())
            atual_lines = len(atual_content.splitlines())
            legacy_size = len(legacy_content.encode('utf-16-le'))
            atual_size = len(atual_content.encode('utf-16-le'))
            
            print(f"  Legacy: {legacy_lines} linhas, {legacy_size} bytes")
            print(f"  Atual:  {atual_lines} linhas, {atual_size} bytes")
            print(f"  Diferença: {atual_lines - legacy_lines} linhas, {atual_size - legacy_size} bytes")
            
            # Contar comandos
            legacy_layers = legacy_content.count('_LAYER')
            atual_layers = atual_content.count('_LAYER')
            legacy_inserts = legacy_content.count('-INSERT')
            atual_inserts = atual_content.count('-INSERT')
            legacy_dimlinear = legacy_content.count('_DIMLINEAR')
            atual_dimlinear = atual_content.count('_DIMLINEAR')
            
            print(f"\n  Comandos:")
            print(f"    LAYER:    Legacy={legacy_layers:3d}, Atual={atual_layers:3d}, Diff={atual_layers - legacy_layers:+d}")
            print(f"    INSERT:   Legacy={legacy_inserts:3d}, Atual={atual_inserts:3d}, Diff={atual_inserts - legacy_inserts:+d}")
            print(f"    DIMLINEAR: Legacy={legacy_dimlinear:3d}, Atual={atual_dimlinear:3d}, Diff={atual_dimlinear - legacy_dimlinear:+d}")
            
            # Verificar se são idênticos
            if legacy_content == atual_content:
                print(f"\n  ✅ Scripts são IDÊNTICOS byte-a-byte!")
            else:
                print(f"\n  ⚠️ Scripts são DIFERENTES")
                print(f"  Use compare_scripts.py para análise detalhada")
                
        except Exception as e:
            print(f"  ❌ Erro ao comparar: {e}")
            import traceback
            traceback.print_exc()

def executar_comparacao_detalhada():
    """
    Executa comparação detalhada usando o script compare_scripts.py
    """
    print("\n" + "=" * 100)
    print("COMPARAÇÃO DETALHADA: Executando compare_scripts.py")
    print("=" * 100)
    
    compare_script = project_root / "_ROBOS_ABAS" / "ATUAL_PYSIDE" / "compare_scripts.py"
    
    if not compare_script.exists():
        print(f"  ⚠️ Script de comparação não encontrado: {compare_script}")
        return
    
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(compare_script)],
            cwd=str(compare_script.parent),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
    except Exception as e:
        print(f"  ❌ Erro ao executar comparação: {e}")

def main():
    """
    Função principal: executa geração completa e comparação.
    """
    print("\n" + "=" * 100)
    print("EXECUÇÃO COMPLETA: Geração e Comparação de Scripts")
    print("=" * 100)
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project root: {project_root}")
    
    # 1. Executar geração
    success, pavimento_nome = executar_geracao_completa()
    
    if not success:
        print("\n[ERRO] Falha na geração. Abortando comparação.")
        return
    
    # 2. Verificar scripts gerados
    scripts_gerados = verificar_scripts_gerados(pavimento_nome)
    
    if not scripts_gerados:
        print("\n[AVISO] Nenhum script foi gerado.")
        return
    
    # 3. Comparar com legacy
    comparar_com_legacy(scripts_gerados)
    
    # 4. Executar comparação detalhada
    executar_comparacao_detalhada()
    
    print("\n" + "=" * 100)
    print("EXECUÇÃO COMPLETA FINALIZADA")
    print("=" * 100)
    print("\nPróximos passos:")
    print("1. Verificar logs de debug para identificar diferenças")
    print("2. Analisar relatórios em _ROBOS_ABAS/ATUAL_PYSIDE/diferencas_*.md")
    print("3. Ajustar dados de entrada se necessário")
    print("4. Re-executar para validar correções")

if __name__ == '__main__':
    main()
