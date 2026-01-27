#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Análise rápida de diferenças específicas"""

import sys
from pathlib import Path

def read_utf16(file_path):
    """Lê arquivo UTF-16 LE"""
    with open(file_path, 'rb') as f:
        raw = f.read()
    # Remover BOM se presente
    if raw.startswith(b'\xff\xfe'):
        raw = raw[2:]
    return raw.decode('utf-16-le', errors='ignore')

legacy_path = Path(__file__).parent.parent / 'contexto_legacy_pilares' / 'Ptestelegacy_CIMA.scr'
atual_path = Path(__file__).parent / 'P1_CIMA.scr'

legacy = read_utf16(str(legacy_path))
atual = read_utf16(str(atual_path))

# Analisar comandos LAYER
print("=" * 80)
print("ANÁLISE DE COMANDOS LAYER")
print("=" * 80)

legacy_layers = [(i+1, l.strip()) for i, l in enumerate(legacy.split('\n')) if 'LAYER' in l.upper() and l.strip()]
atual_layers = [(i+1, l.strip()) for i, l in enumerate(atual.split('\n')) if 'LAYER' in l.upper() and l.strip()]

print(f"\nLEGACY: {len(legacy_layers)} comandos LAYER encontrados")
for i, (line_num, cmd) in enumerate(legacy_layers[:15], 1):
    print(f"  {i:2d}. Linha {line_num:4d}: {cmd}")

print(f"\nATUAL: {len(atual_layers)} comandos LAYER encontrados")
for i, (line_num, cmd) in enumerate(atual_layers[:15], 1):
    print(f"  {i:2d}. Linha {line_num:4d}: {cmd}")

# Verificar se usa _LAYER ou LAYER
legacy_underscore = sum(1 for _, cmd in legacy_layers if cmd.startswith('_LAYER'))
legacy_no_underscore = sum(1 for _, cmd in legacy_layers if cmd.startswith('LAYER') and not cmd.startswith('_LAYER'))

atual_underscore = sum(1 for _, cmd in atual_layers if cmd.startswith('_LAYER'))
atual_no_underscore = sum(1 for _, cmd in atual_layers if cmd.startswith('LAYER') and not cmd.startswith('_LAYER'))

print(f"\nLEGACY: _LAYER={legacy_underscore}, LAYER={legacy_no_underscore}")
print(f"ATUAL:  _LAYER={atual_underscore}, LAYER={atual_no_underscore}")

# Analisar comandos -INSERT
print("\n" + "=" * 80)
print("ANÁLISE DE COMANDOS -INSERT")
print("=" * 80)

legacy_inserts = [(i+1, l.strip()) for i, l in enumerate(legacy.split('\n')) if '-INSERT' in l.upper() and l.strip()]
atual_inserts = [(i+1, l.strip()) for i, l in enumerate(atual.split('\n')) if '-INSERT' in l.upper() and l.strip()]

print(f"\nLEGACY: {len(legacy_inserts)} comandos -INSERT")
for i, (line_num, cmd) in enumerate(legacy_inserts[:10], 1):
    print(f"  {i:2d}. Linha {line_num:4d}: {cmd}")

print(f"\nATUAL: {len(atual_inserts)} comandos -INSERT")
for i, (line_num, cmd) in enumerate(atual_inserts[:10], 1):
    print(f"  {i:2d}. Linha {line_num:4d}: {cmd}")
