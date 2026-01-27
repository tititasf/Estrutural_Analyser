#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Comparação Detalhada: Legacy vs Atual
Compara scripts .scr linha por linha identificando TODAS as diferenças
"""

import difflib
import os
import sys
from pathlib import Path
from typing import List, Tuple, Dict
import codecs

def read_script_file(file_path: str) -> Tuple[List[str], bytes]:
    """
    Lê arquivo .scr tentando diferentes encodings
    Retorna: (linhas, bytes_originais)
    """
    encodings = ['utf-16-le', 'utf-16', 'utf-8-sig', 'utf-8', 'latin-1']
    
    # Primeiro, ler como bytes para análise
    with open(file_path, 'rb') as f:
        raw_bytes = f.read()
    
    # Tentar cada encoding
    for encoding in encodings:
        try:
            # Remover BOM se presente
            bom_removed = raw_bytes
            if encoding.startswith('utf-16'):
                # UTF-16 LE BOM: FF FE
                # UTF-16 BE BOM: FE FF
                if raw_bytes.startswith(b'\xff\xfe'):
                    bom_removed = raw_bytes[2:]
                elif raw_bytes.startswith(b'\xfe\xff'):
                    bom_removed = raw_bytes[2:]
            elif encoding == 'utf-8-sig':
                if raw_bytes.startswith(b'\xef\xbb\xbf'):
                    bom_removed = raw_bytes[3:]
            
            # Decodificar
            content = bom_removed.decode(encoding, errors='strict')
            lines = content.splitlines(keepends=True)
            
            print(f"[INFO] Arquivo {file_path} lido com encoding: {encoding}")
            print(f"[INFO] Tamanho original: {len(raw_bytes)} bytes, linhas: {len(lines)}")
            if len(raw_bytes) > 0:
                print(f"[INFO] Primeiros bytes (hex): {raw_bytes[:10].hex()}")
            
            return lines, raw_bytes
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    raise ValueError(f"Não foi possível decodificar {file_path} com nenhum encoding testado")

def normalize_line(line: str) -> str:
    """Normaliza linha para comparação (remove espaços extras, mas preserva estrutura)"""
    # Não normalizar muito - queremos detectar diferenças de espaçamento
    return line

def compare_scripts(legacy_path: str, atual_path: str) -> Dict:
    """
    Compara dois scripts e retorna relatório detalhado
    """
    print(f"\n{'='*80}")
    print(f"COMPARANDO SCRIPTS")
    print(f"{'='*80}")
    print(f"Legacy: {legacy_path}")
    print(f"Atual:  {atual_path}")
    print(f"{'='*80}\n")
    
    # Ler arquivos
    try:
        legacy_lines, legacy_bytes = read_script_file(legacy_path)
        atual_lines, atual_bytes = read_script_file(atual_path)
    except Exception as e:
        return {
            'error': str(e),
            'legacy_path': legacy_path,
            'atual_path': atual_path
        }
    
    # Comparação byte-a-byte
    byte_identical = legacy_bytes == atual_bytes
    byte_diff_size = abs(len(legacy_bytes) - len(atual_bytes))
    
    # Comparação linha por linha
    diff = list(difflib.unified_diff(
        legacy_lines,
        atual_lines,
        fromfile=f'LEGACY ({legacy_path})',
        tofile=f'ATUAL ({atual_path})',
        lineterm='',
        n=0  # Contexto 0 = mostrar apenas diferenças
    ))
    
    # Análise detalhada
    differences = []
    legacy_idx = 0
    atual_idx = 0
    
    # Usar SequenceMatcher para análise mais precisa
    matcher = difflib.SequenceMatcher(None, legacy_lines, atual_lines)
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            # Linhas iguais - avançar índices
            legacy_idx = i2
            atual_idx = j2
        elif tag == 'replace':
            # Linhas substituídas
            for i in range(i1, i2):
                if i < len(legacy_lines):
                    legacy_line = legacy_lines[i].rstrip('\n\r')
                    atual_line = atual_lines[j1 + (i - i1)].rstrip('\n\r') if (j1 + (i - i1)) < len(atual_lines) else "[LINHA AUSENTE]"
                    differences.append({
                        'type': 'replace',
                        'legacy_line_num': i + 1,
                        'atual_line_num': j1 + (i - i1) + 1 if (j1 + (i - i1)) < len(atual_lines) else None,
                        'legacy_content': legacy_line,
                        'atual_content': atual_line,
                        'analysis': analyze_line_difference(legacy_line, atual_line)
                    })
            legacy_idx = i2
            atual_idx = j2
        elif tag == 'delete':
            # Linhas deletadas no atual
            for i in range(i1, i2):
                if i < len(legacy_lines):
                    differences.append({
                        'type': 'delete',
                        'legacy_line_num': i + 1,
                        'atual_line_num': None,
                        'legacy_content': legacy_lines[i].rstrip('\n\r'),
                        'atual_content': '[LINHA AUSENTE]',
                        'analysis': 'Linha presente no legacy mas ausente no atual'
                    })
            legacy_idx = i2
        elif tag == 'insert':
            # Linhas inseridas no atual
            for j in range(j1, j2):
                if j < len(atual_lines):
                    differences.append({
                        'type': 'insert',
                        'legacy_line_num': None,
                        'atual_line_num': j + 1,
                        'legacy_content': '[LINHA AUSENTE]',
                        'atual_content': atual_lines[j].rstrip('\n\r'),
                        'analysis': 'Linha presente no atual mas ausente no legacy'
                    })
            atual_idx = j2
    
    # Estatísticas
    total_legacy_lines = len(legacy_lines)
    total_atual_lines = len(atual_lines)
    total_differences = len(differences)
    
    return {
        'legacy_path': legacy_path,
        'atual_path': atual_path,
        'byte_identical': byte_identical,
        'byte_diff_size': byte_diff_size,
        'legacy_size_bytes': len(legacy_bytes),
        'atual_size_bytes': len(atual_bytes),
        'total_legacy_lines': total_legacy_lines,
        'total_atual_lines': total_atual_lines,
        'total_differences': total_differences,
        'differences': differences,
        'unified_diff': diff
    }

def analyze_line_difference(legacy_line: str, atual_line: str) -> str:
    """Analisa diferença entre duas linhas e retorna descrição"""
    legacy_stripped = legacy_line.strip()
    atual_stripped = atual_line.strip()
    
    # Comandos diferentes
    if legacy_stripped.startswith('_LAYER') and atual_stripped.startswith('LAYER'):
        return "LAYER sem underscore no atual (deveria ser _LAYER)"
    if legacy_stripped.startswith('LAYER') and atual_stripped.startswith('_LAYER'):
        return "LAYER com underscore no atual (deveria ser LAYER)"
    
    # Espaçamento diferente
    if legacy_stripped == atual_stripped and legacy_line != atual_line:
        legacy_spaces = len(legacy_line) - len(legacy_line.lstrip())
        atual_spaces = len(atual_line) - len(atual_line.lstrip())
        if legacy_spaces != atual_spaces:
            return f"Espaçamento inicial diferente: legacy={legacy_spaces}, atual={atual_spaces}"
        
        legacy_trailing = len(legacy_line) - len(legacy_line.rstrip())
        atual_trailing = len(atual_line) - len(atual_line.rstrip())
        if legacy_trailing != atual_trailing:
            return f"Espaçamento final diferente: legacy={legacy_trailing}, atual={atual_trailing}"
    
    # Valores numéricos diferentes
    import re
    legacy_nums = re.findall(r'-?\d+\.?\d*', legacy_line)
    atual_nums = re.findall(r'-?\d+\.?\d*', atual_line)
    if legacy_nums != atual_nums:
        return f"Valores numéricos diferentes: legacy={legacy_nums}, atual={atual_nums}"
    
    # Comandos diferentes
    legacy_cmd = legacy_stripped.split()[0] if legacy_stripped else ""
    atual_cmd = atual_stripped.split()[0] if atual_stripped else ""
    if legacy_cmd != atual_cmd:
        return f"Comando diferente: legacy='{legacy_cmd}', atual='{atual_cmd}'"
    
    return "Diferença não categorizada"

def generate_report(comparison_result: Dict, output_path: str):
    """Gera relatório markdown detalhado"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Relatório de Comparação: Legacy vs Atual\n\n")
        f.write(f"**Data:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Legacy:** `{comparison_result['legacy_path']}`\n\n")
        f.write(f"**Atual:** `{comparison_result['atual_path']}`\n\n")
        
        f.write("## Resumo\n\n")
        f.write(f"- **Idênticos byte-a-byte:** {'SIM' if comparison_result['byte_identical'] else 'NÃO'}\n")
        f.write(f"- **Tamanho Legacy:** {comparison_result['legacy_size_bytes']} bytes\n")
        f.write(f"- **Tamanho Atual:** {comparison_result['atual_size_bytes']} bytes\n")
        f.write(f"- **Diferença de tamanho:** {comparison_result['byte_diff_size']} bytes\n")
        f.write(f"- **Total de linhas Legacy:** {comparison_result['total_legacy_lines']}\n")
        f.write(f"- **Total de linhas Atual:** {comparison_result['total_atual_lines']}\n")
        f.write(f"- **Total de diferenças:** {comparison_result['total_differences']}\n\n")
        
        if comparison_result['total_differences'] == 0:
            f.write("## ✅ Scripts são idênticos!\n\n")
        else:
            f.write("## Diferenças Detalhadas\n\n")
            
            # Agrupar por tipo
            by_type = {}
            for diff in comparison_result['differences']:
                diff_type = diff['type']
                if diff_type not in by_type:
                    by_type[diff_type] = []
                by_type[diff_type].append(diff)
            
            for diff_type, diffs in by_type.items():
                f.write(f"### {diff_type.upper()} ({len(diffs)} ocorrências)\n\n")
                for i, diff in enumerate(diffs[:50], 1):  # Limitar a 50 por tipo
                    f.write(f"#### Diferença #{i}\n\n")
                    f.write(f"- **Linha Legacy:** {diff['legacy_line_num']}\n")
                    f.write(f"- **Linha Atual:** {diff['atual_line_num']}\n")
                    f.write(f"- **Análise:** {diff['analysis']}\n\n")
                    f.write("```\n")
                    f.write(f"LEGACY: {repr(diff['legacy_content'])}\n")
                    f.write(f"ATUAL:  {repr(diff['atual_content'])}\n")
                    f.write("```\n\n")
                
                if len(diffs) > 50:
                    f.write(f"\n*... e mais {len(diffs) - 50} diferenças deste tipo*\n\n")
            
            # Unified diff completo
            f.write("## Unified Diff Completo\n\n")
            f.write("```diff\n")
            for line in comparison_result['unified_diff'][:1000]:  # Limitar tamanho
                f.write(line)
            f.write("\n```\n")
    
    print(f"\n[SUCCESS] Relatório salvo em: {output_path}")

def main():
    """Função principal"""
    base_dir = Path(__file__).parent
    
    # Arquivos para comparar
    comparisons = [
        {
            'legacy': base_dir.parent / 'contexto_legacy_pilares' / 'Ptestelegacy_CIMA.scr',
            'atual': base_dir / 'P1_CIMA.scr',
            'output': base_dir / 'diferencas_CIMA.md'
        },
        {
            'legacy': base_dir.parent / 'contexto_legacy_pilares' / 'Ptestelegacy_ABCD.scr',
            'atual': base_dir / 'P1_ABCD.scr',
            'output': base_dir / 'diferencas_ABCD.md'
        }
    ]
    
    all_results = []
    
    for comp in comparisons:
        legacy_path = str(comp['legacy'])
        atual_path = str(comp['atual'])
        output_path = str(comp['output'])
        
        if not os.path.exists(legacy_path):
            print(f"[WARNING] Arquivo legacy não encontrado: {legacy_path}")
            continue
        if not os.path.exists(atual_path):
            print(f"[WARNING] Arquivo atual não encontrado: {atual_path}")
            continue
        
        print(f"\n{'='*80}")
        print(f"Processando: {Path(legacy_path).name} vs {Path(atual_path).name}")
        print(f"{'='*80}")
        
        result = compare_scripts(legacy_path, atual_path)
        
        if 'error' in result:
            print(f"[ERROR] {result['error']}")
            continue
        
        generate_report(result, output_path)
        all_results.append(result)
        
        # Resumo rápido
        print(f"\n[RESUMO]")
        print(f"  Idênticos byte-a-byte: {'SIM' if result['byte_identical'] else 'NÃO'}")
        print(f"  Diferenças encontradas: {result['total_differences']}")
    
    # Relatório consolidado
    if all_results:
        consolidated_path = base_dir / 'diferencas_consolidado.md'
        with open(consolidated_path, 'w', encoding='utf-8') as f:
            f.write("# Relatório Consolidado de Comparação\n\n")
            f.write(f"**Data:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for result in all_results:
                f.write(f"## {Path(result['legacy_path']).name}\n\n")
                f.write(f"- Idênticos: {'SIM' if result['byte_identical'] else 'NÃO'}\n")
                f.write(f"- Diferenças: {result['total_differences']}\n")
                f.write(f"- Tamanho Legacy: {result['legacy_size_bytes']} bytes\n")
                f.write(f"- Tamanho Atual: {result['atual_size_bytes']} bytes\n\n")
        
        print(f"\n[SUCCESS] Relatório consolidado salvo em: {consolidated_path}")

if __name__ == '__main__':
    main()
