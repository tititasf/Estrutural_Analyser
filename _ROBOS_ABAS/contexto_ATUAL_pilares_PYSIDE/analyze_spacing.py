#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Análise de espaçamentos e formatação"""

from pathlib import Path

def read_utf16(file_path):
    """Lê arquivo UTF-16 LE"""
    with open(file_path, 'rb') as f:
        raw = f.read()
    if raw.startswith(b'\xff\xfe'):
        raw = raw[2:]
    return raw.decode('utf-16-le', errors='ignore')

legacy_path = Path(__file__).parent.parent / 'contexto_legacy_pilares' / 'Ptestelegacy_CIMA.scr'
atual_path = Path(__file__).parent / 'P1_CIMA.scr'

legacy = read_utf16(str(legacy_path))
atual = read_utf16(str(atual_path))

legacy_lines = legacy.split('\n')
atual_lines = atual.split('\n')

print("=" * 100)
print("COMPARAÇÃO LINHA POR LINHA (Primeiras 50 linhas)")
print("=" * 100)

for i in range(min(50, len(legacy_lines), len(atual_lines))):
    leg = legacy_lines[i].rstrip('\r')
    atu = atual_lines[i].rstrip('\r') if i < len(atual_lines) else "[AUSENTE]"
    
    # Mostrar diferenças de espaçamento
    leg_repr = repr(leg)
    atu_repr = repr(atu)
    
    if leg != atu:
        print(f"L{i+1:3d} | DIFERENTE")
        print(f"     | LEGACY: {leg_repr}")
        print(f"     | ATUAL:  {atu_repr}")
        
        # Análise de espaçamento
        if leg.strip() == atu.strip():
            leg_spaces_start = len(leg) - len(leg.lstrip())
            atu_spaces_start = len(atu) - len(atu.lstrip()) if atu != "[AUSENTE]" else 0
            leg_spaces_end = len(leg) - len(leg.rstrip())
            atu_spaces_end = len(atu) - len(atu.rstrip()) if atu != "[AUSENTE]" else 0
            
            if leg_spaces_start != atu_spaces_start or leg_spaces_end != atu_spaces_end:
                print(f"     | ESPAÇAMENTO: inicio L={leg_spaces_start} A={atu_spaces_start}, fim L={leg_spaces_end} A={atu_spaces_end}")
    else:
        if i < 10:  # Mostrar primeiras 10 iguais
            print(f"L{i+1:3d} | IGUAL: {leg_repr[:80]}")

print("\n" + "=" * 100)
print("ANÁLISE DE ESPAÇAMENTOS APÓS COMANDOS")
print("=" * 100)

# Analisar padrões de espaçamento após comandos específicos
commands_to_check = ['_LAYER', 'S ', '-INSERT', '_PLINE', '_DIMLINEAR']

for cmd in commands_to_check:
    print(f"\nComando: {cmd}")
    legacy_matches = [(i+1, l) for i, l in enumerate(legacy_lines) if cmd in l]
    atual_matches = [(i+1, l) for i, l in enumerate(atual_lines) if cmd in l]
    
    print(f"  Legacy: {len(legacy_matches)} ocorrências")
    print(f"  Atual:  {len(atual_matches)} ocorrências")
    
    # Comparar primeiras 3 ocorrências
    for i in range(min(3, len(legacy_matches), len(atual_matches))):
        leg_line_num, leg_line = legacy_matches[i]
        atu_line_num, atu_line = atual_matches[i] if i < len(atual_matches) else (None, "[AUSENTE]")
        
        print(f"    Ocorrência {i+1}:")
        print(f"      Legacy L{leg_line_num}: {repr(leg_line)}")
        if atu_line != "[AUSENTE]":
            print(f"      Atual  L{atu_line_num}: {repr(atu_line)}")
            if leg_line != atu_line:
                print(f"      ⚠️ DIFERENTE")
        else:
            print(f"      Atual:  [AUSENTE]")
