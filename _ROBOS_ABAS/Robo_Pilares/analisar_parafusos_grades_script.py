#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para analisar parafusos e grades em scripts CIMA gerados.
Compara comandos -INSERT (parafusos) e _PLINE (grades) extraídos do script.
"""

import re
import sys
import os

def extrair_parafusos(script_content):
    """Extrai todos os comandos -INSERT de parafusos do script"""
    parafusos = []
    # Padrão para -INSERT de parafusos (PAR.CIM, PAR.BAI, PAR_CIMA, PAR_BAIXO)
    pattern = r'-INSERT\s+(PAR\.(?:CIM|BAI)|PAR_(?:CIMA|BAIXO))\s+([-\d.]+),([-\d.]+)\s+1\s+0'
    matches = re.finditer(pattern, script_content, re.MULTILINE | re.IGNORECASE)
    
    for match in matches:
        block_name = match.group(1)
        x = float(match.group(2))
        y = float(match.group(3))
        parafusos.append({
            'block': block_name,
            'x': x,
            'y': y,
            'line': script_content[:match.start()].count('\n') + 1
        })
    
    return parafusos

def extrair_grades(script_content):
    """Extrai todos os comandos _PLINE de grades (GRAVATA layer) do script"""
    grades = []
    # Procurar por _PLINE seguido de coordenadas (retângulo de grade)
    # Grades geralmente têm coordenadas próximas e altura de 2.4cm
    pattern = r'_PLINE\s+([-\d.]+),([-\d.]+)\s+([-\d.]+),([-\d.]+)\s+([-\d.]+),([-\d.]+)\s+([-\d.]+),([-\d.]+)\s+C'
    matches = re.finditer(pattern, script_content, re.MULTILINE)
    
    for match in matches:
        coords = [float(match.group(i)) for i in range(1, 9)]
        # Calcular dimensões do retângulo
        x_coords = [coords[0], coords[2], coords[4], coords[6]]
        y_coords = [coords[1], coords[3], coords[5], coords[7]]
        
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        
        width = abs(x_max - x_min)
        height = abs(y_max - y_min)
        
        # Filtrar apenas grades (altura ~2.4cm e largura > 0)
        if 2.0 <= height <= 3.0 and width > 10:
            grades.append({
                'x_min': x_min,
                'x_max': x_max,
                'y_min': y_min,
                'y_max': y_max,
                'width': width,
                'height': height,
                'coords': coords,
                'line': script_content[:match.start()].count('\n') + 1
            })
    
    return grades

def analisar_script(script_path):
    """Analisa um script CIMA e retorna informações sobre parafusos e grades"""
    try:
        # Tentar ler como UTF-16 (encoding comum para scripts AutoCAD)
        with open(script_path, 'r', encoding='utf-16') as f:
            content = f.read()
    except:
        try:
            # Fallback para UTF-8
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"Erro ao ler {script_path}: {e}")
            return None
    
    parafusos = extrair_parafusos(content)
    grades = extrair_grades(content)
    
    return {
        'parafusos': parafusos,
        'grades': grades,
        'total_parafusos': len(parafusos),
        'total_grades': len(grades)
    }

def comparar_scripts(script_novo, script_legacy=None):
    """Compara dois scripts e mostra diferenças"""
    print("="*80)
    print(f"ANÁLISE DE SCRIPT: {os.path.basename(script_novo)}")
    print("="*80)
    
    resultado_novo = analisar_script(script_novo)
    if not resultado_novo:
        print(f"❌ Erro ao analisar script novo: {script_novo}")
        return
    
    print(f"\n📊 PARAFUSOS ENCONTRADOS: {resultado_novo['total_parafusos']}")
    print("-"*80)
    for i, par in enumerate(resultado_novo['parafusos'], 1):
        print(f"  {i}. {par['block']:15s} @ ({par['x']:8.1f}, {par['y']:8.1f}) [linha {par['line']}]")
    
    print(f"\n📊 GRADES ENCONTRADAS: {resultado_novo['total_grades']}")
    print("-"*80)
    for i, grade in enumerate(resultado_novo['grades'], 1):
        print(f"  {i}. Largura: {grade['width']:6.1f}cm, Altura: {grade['height']:4.1f}cm")
        print(f"     Posição: X=[{grade['x_min']:6.1f}, {grade['x_max']:6.1f}], Y=[{grade['y_min']:6.1f}, {grade['y_max']:6.1f}]")
        print(f"     [linha {grade['line']}]")
    
    if script_legacy and os.path.exists(script_legacy):
        print("\n" + "="*80)
        print(f"COMPARAÇÃO COM LEGACY: {os.path.basename(script_legacy)}")
        print("="*80)
        
        resultado_legacy = analisar_script(script_legacy)
        if not resultado_legacy:
            print(f"❌ Erro ao analisar script legacy: {script_legacy}")
            return
        
        # Comparar parafusos
        print(f"\n🔍 COMPARAÇÃO DE PARAFUSOS:")
        print(f"  Novo: {resultado_novo['total_parafusos']} parafusos")
        print(f"  Legacy: {resultado_legacy['total_parafusos']} parafusos")
        
        if resultado_novo['total_parafusos'] != resultado_legacy['total_parafusos']:
            print(f"  ⚠️ DIFERENÇA: Quantidade diferente!")
        
        # Comparar coordenadas dos parafusos
        min_len = min(len(resultado_novo['parafusos']), len(resultado_legacy['parafusos']))
        for i in range(min_len):
            p_novo = resultado_novo['parafusos'][i]
            p_legacy = resultado_legacy['parafusos'][i]
            diff_x = abs(p_novo['x'] - p_legacy['x'])
            diff_y = abs(p_novo['y'] - p_legacy['y'])
            if diff_x > 0.1 or diff_y > 0.1:
                print(f"  ⚠️ Parafuso {i+1}: Diferença X={diff_x:.2f}cm, Y={diff_y:.2f}cm")
                print(f"     Novo: ({p_novo['x']:.1f}, {p_novo['y']:.1f})")
                print(f"     Legacy: ({p_legacy['x']:.1f}, {p_legacy['y']:.1f})")
        
        # Comparar grades
        print(f"\n🔍 COMPARAÇÃO DE GRADES:")
        print(f"  Novo: {resultado_novo['total_grades']} grades")
        print(f"  Legacy: {resultado_legacy['total_grades']} grades")
        
        if resultado_novo['total_grades'] != resultado_legacy['total_grades']:
            print(f"  ⚠️ DIFERENÇA: Quantidade diferente!")
        
        # Comparar dimensões das grades
        min_len = min(len(resultado_novo['grades']), len(resultado_legacy['grades']))
        for i in range(min_len):
            g_novo = resultado_novo['grades'][i]
            g_legacy = resultado_legacy['grades'][i]
            diff_width = abs(g_novo['width'] - g_legacy['width'])
            diff_x_min = abs(g_novo['x_min'] - g_legacy['x_min'])
            if diff_width > 0.1 or diff_x_min > 0.1:
                print(f"  ⚠️ Grade {i+1}: Diferença Largura={diff_width:.2f}cm, X_min={diff_x_min:.2f}cm")
                print(f"     Novo: Largura={g_novo['width']:.1f}cm, X_min={g_novo['x_min']:.1f}cm")
                print(f"     Legacy: Largura={g_legacy['width']:.1f}cm, X_min={g_legacy['x_min']:.1f}cm")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python analisar_parafusos_grades_script.py <script_novo.scr> [script_legacy.scr]")
        sys.exit(1)
    
    script_novo = sys.argv[1]
    script_legacy = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(script_novo):
        print(f"❌ Script não encontrado: {script_novo}")
        sys.exit(1)
    
    comparar_scripts(script_novo, script_legacy)
