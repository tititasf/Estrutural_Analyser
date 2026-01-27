#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para analisar scripts CIMA e extrair informações detalhadas sobre parafusos e grades.
Compara scripts gerados com scripts legacy para identificar diferenças.
"""

import os
import re
import sys
from pathlib import Path

def ler_script_utf16(caminho):
    """Lê um script .scr que está em UTF-16"""
    try:
        with open(caminho, 'r', encoding='utf-16-le') as f:
            return f.read()
    except:
        try:
            with open(caminho, 'r', encoding='utf-16') as f:
                return f.read()
        except:
            return None

def extrair_parafusos(script):
    """Extrai informações sobre parafusos do script"""
    parafusos = []
    
    # Padrão para -INSERT com PAR.CIM ou PAR.BAI
    padrao_insert = r'-INSERT\s+PAR\.(CIM|BAI|ESQ|DIR|_CIMA|_BAIXO)\s+([-\d.]+),([-\d.]+)'
    matches = re.finditer(padrao_insert, script, re.IGNORECASE | re.MULTILINE)
    
    for match in matches:
        tipo = match.group(1)
        x = float(match.group(2))
        y = float(match.group(3))
        parafusos.append({
            'tipo': tipo,
            'x': x,
            'y': y,
            'linha': script[:match.start()].count('\n') + 1
        })
    
    return parafusos

def extrair_grades(script):
    """Extrai informações sobre grades (PLINE) do script"""
    grades = []
    
    # Padrão para _PLINE que forma retângulos (grades)
    # Procurar por sequências de _PLINE com 4 pontos que formam retângulo
    padrao_pline = r'_PLINE\s+([-\d.]+),([-\d.]+)\s+([-\d.]+),([-\d.]+)\s+([-\d.]+),([-\d.]+)\s+([-\d.]+),([-\d.]+)\s+C'
    matches = re.finditer(padrao_pline, script, re.IGNORECASE | re.MULTILINE)
    
    for match in matches:
        x1, y1 = float(match.group(1)), float(match.group(2))
        x2, y2 = float(match.group(3)), float(match.group(4))
        x3, y3 = float(match.group(5)), float(match.group(6))
        x4, y4 = float(match.group(7)), float(match.group(8))
        
        # Calcular largura e altura
        largura = abs(x2 - x1) if abs(x2 - x1) > abs(x3 - x1) else abs(x3 - x1)
        altura = abs(y2 - y1) if abs(y2 - y1) > abs(y3 - y1) else abs(y3 - y1)
        
        # Verificar se parece uma grade (altura pequena, largura maior)
        if altura < 5 and largura > 10:
            grades.append({
                'x1': x1, 'y1': y1,
                'x2': x2, 'y2': y2,
                'x3': x3, 'y3': y3,
                'x4': x4, 'y4': y4,
                'largura': largura,
                'altura': altura,
                'x_inicio': min(x1, x2, x3, x4),
                'x_fim': max(x1, x2, x3, x4),
                'y_pos': (y1 + y2 + y3 + y4) / 4,
                'linha': script[:match.start()].count('\n') + 1
            })
    
    return grades

def analisar_script(caminho):
    """Analisa um script e retorna informações estruturadas"""
    script = ler_script_utf16(caminho)
    if not script:
        return None
    
    parafusos = extrair_parafusos(script)
    grades = extrair_grades(script)
    
    return {
        'caminho': caminho,
        'parafusos': parafusos,
        'grades': grades,
        'total_parafusos': len(parafusos),
        'total_grades': len(grades)
    }

def comparar_scripts(novo_caminho, legacy_caminho=None):
    """Compara dois scripts e mostra diferenças"""
    print("=" * 80)
    print("ANÁLISE DE SCRIPTS CIMA - PARAFUSOS E GRADES")
    print("=" * 80)
    
    novo = analisar_script(novo_caminho)
    if not novo:
        print(f"[ERRO] Erro ao ler script novo: {novo_caminho}")
        return
    
    print(f"\n[SCRIPT NOVO]: {novo_caminho}")
    print(f"   Total de parafusos: {novo['total_parafusos']}")
    print(f"   Total de grades: {novo['total_grades']}")
    
    print("\n[PARAFUSOS]:")
    if novo['parafusos']:
        for i, p in enumerate(novo['parafusos'], 1):
            print(f"   {i}. {p['tipo']:10s} @ ({p['x']:8.1f}, {p['y']:8.1f}) - linha {p['linha']}")
    else:
        print("   Nenhum parafuso encontrado!")
    
    print("\n[GRADES]:")
    if novo['grades']:
        for i, g in enumerate(novo['grades'], 1):
            print(f"   {i}. Largura: {g['largura']:6.1f}cm, Altura: {g['altura']:4.1f}cm")
            print(f"      Posição: X={g['x_inicio']:6.1f} a {g['x_fim']:6.1f}, Y={g['y_pos']:6.1f}")
    else:
        print("   Nenhuma grade encontrada!")
    
    if legacy_caminho:
        legacy = analisar_script(legacy_caminho)
        if legacy:
            print(f"\n[SCRIPT LEGACY]: {legacy_caminho}")
            print(f"   Total de parafusos: {legacy['total_parafusos']}")
            print(f"   Total de grades: {legacy['total_grades']}")
            
            print("\n[COMPARACAO]:")
            print(f"   Parafusos: Novo={novo['total_parafusos']}, Legacy={legacy['total_parafusos']}, Diferença={novo['total_parafusos'] - legacy['total_parafusos']}")
            print(f"   Grades: Novo={novo['total_grades']}, Legacy={legacy['total_grades']}, Diferença={novo['total_grades'] - legacy['total_grades']}")
            
            # Comparar posições de parafusos
            if len(novo['parafusos']) == len(legacy['parafusos']):
                print("\n   Posições de Parafusos (X):")
                for i, (n, l) in enumerate(zip(novo['parafusos'], legacy['parafusos']), 1):
                    diff_x = abs(n['x'] - l['x'])
                    diff_y = abs(n['y'] - l['y'])
                    status = "OK" if diff_x < 0.1 and diff_y < 0.1 else "DIFERENTE"
                    print(f"   {status} Parafuso {i}: Novo X={n['x']:8.1f}, Legacy X={l['x']:8.1f}, Diff={diff_x:6.2f}cm")
            else:
                print(f"\n   [AVISO] Quantidade diferente de parafusos!")
                print(f"      Novo: {[p['x'] for p in novo['parafusos']]}")
                print(f"      Legacy: {[p['x'] for p in legacy['parafusos']]}")
            
            # Comparar grades
            if len(novo['grades']) == len(legacy['grades']):
                print("\n   Grades (Largura):")
                for i, (n, l) in enumerate(zip(novo['grades'], legacy['grades']), 1):
                    diff_largura = abs(n['largura'] - l['largura'])
                    diff_x = abs(n['x_inicio'] - l['x_inicio'])
                    status = "OK" if diff_largura < 0.1 and diff_x < 0.1 else "DIFERENTE"
                    print(f"   {status} Grade {i}: Novo L={n['largura']:6.1f}cm X={n['x_inicio']:6.1f}, Legacy L={l['largura']:6.1f}cm X={l['x_inicio']:6.1f}")
            else:
                print(f"\n   [AVISO] Quantidade diferente de grades!")
                print(f"      Novo: {[g['largura'] for g in novo['grades']]}")
                print(f"      Legacy: {[g['largura'] for g in legacy['grades']]}")

if __name__ == "__main__":
    # Caminho do script gerado
    novo_script = r"c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\_ROBOS_ABAS\Robo_Pilares\pilares-atualizado-09-25\SCRIPTS_ROBOS\Subsolo_CIMA\P1_CIMA.scr"
    
    # Se fornecido, comparar com legacy
    legacy_script = sys.argv[1] if len(sys.argv) > 1 else None
    
    comparar_scripts(novo_script, legacy_script)
