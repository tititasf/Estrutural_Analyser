"""
Script de Comparação Direta: Parafusos e Grades entre Scripts Gerados e Legacy

Extrai e compara valores de parafusos e grades de dois scripts CIMA.
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json

# Configurar encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def ler_script(script_path: str) -> Optional[str]:
    """Lê script com detecção de encoding"""
    encodings = ['utf-16', 'utf-8', 'latin-1']
    
    for enc in encodings:
        try:
            with open(script_path, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    print(f"[ERRO] Não foi possível ler {script_path}")
    return None


def extrair_parafusos(conteudo: str) -> List[Dict]:
    """
    Extrai parafusos do script.
    Procura por comandos INSERT com blocos PAR.CIM e PAR.BAI
    Retorna: Lista de dicionários com informações dos parafusos
    """
    if not conteudo:
        return []
    
    parafusos = []
    
    # Padrão mais flexível para INSERT de parafusos
    # Formato pode ser:
    # -INSERT\nPAR.CIM\nx,y\n1\n0\n;
    # ou
    # -INSERT PAR.CIM x,y 1 0 ;
    patterns = [
        r'-INSERT\s+PAR\.(CIM|BAI)\s+([-\d.]+)\s*,\s*([-\d.]+)',
        r'-INSERT\s+PAR\.(CIM|BAI)\s+([-\d.]+)\s+([-\d.]+)',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, conteudo, re.IGNORECASE | re.MULTILINE)
        
        for match in matches:
            tipo = match.group(1)
            x = float(match.group(2))
            y = float(match.group(3))
            
            # Calcular distância acumulada (assumindo que começam em x_inicial)
            # Para parafusos CIM, a posição X indica a distância acumulada
            parafusos.append({
                'tipo': tipo,
                'x': x,
                'y': y,
                'posicao': len(parafusos) + 1
            })
    
    return parafusos


def extrair_grades(conteudo: str) -> List[Dict]:
    """
    Extrai informações sobre grades do script.
    Procura por PLINE que formam retângulos de grade
    """
    if not conteudo:
        return []
    
    grades = []
    
    # Padrão para PLINE (retângulos de grade)
    # Formato: _PLINE\nx1,y1\nx2,y2\nx3,y3\nx4,y4\nC
    # ou: _PLINE x1,y1 x2,y2 x3,y3 x4,y4 C
    pline_patterns = [
        r'_PLINE\s+([-\d.]+)\s*,\s*([-\d.]+)\s+([-\d.]+)\s*,\s*([-\d.]+)\s+([-\d.]+)\s*,\s*([-\d.]+)\s+([-\d.]+)\s*,\s*([-\d.]+)\s+C',
        r'_PLINE\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+C',
    ]
    
    for pattern in pline_patterns:
        matches = re.finditer(pattern, conteudo, re.IGNORECASE | re.MULTILINE)
        
        for match in matches:
            x1, y1 = float(match.group(1)), float(match.group(2))
            x2, y2 = float(match.group(3)), float(match.group(4))
            x3, y3 = float(match.group(5)), float(match.group(6))
            x4, y4 = float(match.group(7)), float(match.group(8))
            
            # Calcular dimensões
            largura = abs(x2 - x1)
            altura = abs(y3 - y1)
            
            # Filtrar retângulos pequenos (parafusos, etc) e grandes demais (paineis)
            # Grades geralmente têm largura entre 50-150 e altura similar
            if 50 <= largura <= 150 and 10 <= altura <= 50:
                grades.append({
                    'posicao': (x1, y1),
                    'largura': round(largura, 1),
                    'altura': round(altura, 1),
                    'vertices': [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]
                })
    
    return grades


def calcular_distancias_parafusos(parafusos: List[Dict]) -> List[float]:
    """
    Calcula distâncias entre parafusos consecutivos.
    Assume que parafusos estão ordenados por posição X.
    """
    if len(parafusos) < 2:
        return []
    
    # Ordenar por X
    parafusos_ordenados = sorted(parafusos, key=lambda p: p['x'])
    
    distancias = []
    for i in range(len(parafusos_ordenados) - 1):
        distancia = parafusos_ordenados[i + 1]['x'] - parafusos_ordenados[i]['x']
        distancias.append(round(distancia, 1))
    
    return distancias


def comparar_scripts(script_novo: str, script_legacy: str) -> Dict:
    """
    Compara dois scripts e retorna diferenças em parafusos e grades
    """
    conteudo_novo = ler_script(script_novo)
    conteudo_legacy = ler_script(script_legacy)
    
    if not conteudo_novo or not conteudo_legacy:
        return {'erro': 'Não foi possível ler um ou ambos os scripts'}
    
    parafusos_novo = extrair_parafusos(conteudo_novo)
    parafusos_legacy = extrair_parafusos(conteudo_legacy)
    
    grades_novo = extrair_grades(conteudo_novo)
    grades_legacy = extrair_grades(conteudo_legacy)
    
    # Calcular distâncias entre parafusos
    distancias_novo = calcular_distancias_parafusos(parafusos_novo)
    distancias_legacy = calcular_distancias_parafusos(parafusos_legacy)
    
    comparacao = {
        'parafusos': {
            'novo': {
                'total': len(parafusos_novo),
                'posicoes': [p['x'] for p in sorted(parafusos_novo, key=lambda x: x['x'])],
                'distancias': distancias_novo,
                'detalhes': parafusos_novo
            },
            'legacy': {
                'total': len(parafusos_legacy),
                'posicoes': [p['x'] for p in sorted(parafusos_legacy, key=lambda x: x['x'])],
                'distancias': distancias_legacy,
                'detalhes': parafusos_legacy
            },
            'diferencas': {
                'quantidade': len(parafusos_novo) - len(parafusos_legacy),
                'posicoes_diferentes': [],
                'distancias_diferentes': []
            }
        },
        'grades': {
            'novo': {
                'total': len(grades_novo),
                'larguras': sorted([g['largura'] for g in grades_novo]),
                'detalhes': grades_novo
            },
            'legacy': {
                'total': len(grades_legacy),
                'larguras': sorted([g['largura'] for g in grades_legacy]),
                'detalhes': grades_legacy
            },
            'diferencas': {
                'quantidade': len(grades_novo) - len(grades_legacy),
                'larguras_diferentes': []
            }
        }
    }
    
    # Comparar distâncias de parafusos
    min_len = min(len(distancias_novo), len(distancias_legacy))
    for i in range(min_len):
        if abs(distancias_novo[i] - distancias_legacy[i]) > 0.1:  # Tolerância de 0.1
            comparacao['parafusos']['diferencas']['distancias_diferentes'].append({
                'indice': i,
                'novo': distancias_novo[i],
                'legacy': distancias_legacy[i],
                'diferenca': distancias_novo[i] - distancias_legacy[i]
            })
    
    # Comparar larguras de grades
    larguras_novo_set = set(comparacao['grades']['novo']['larguras'])
    larguras_legacy_set = set(comparacao['grades']['legacy']['larguras'])
    comparacao['grades']['diferencas']['larguras_diferentes'] = {
        'apenas_novo': sorted(larguras_novo_set - larguras_legacy_set),
        'apenas_legacy': sorted(larguras_legacy_set - larguras_novo_set),
        'comuns': sorted(larguras_novo_set & larguras_legacy_set)
    }
    
    return comparacao


def imprimir_comparacao(comparacao: Dict):
    """Imprime comparação formatada"""
    print("\n" + "="*70)
    print("COMPARAÇÃO DE SCRIPTS: PARAFUSOS E GRADES")
    print("="*70)
    
    # Parafusos
    print("\n📌 PARAFUSOS:")
    print(f"  Novo: {comparacao['parafusos']['novo']['total']} parafusos")
    print(f"  Legacy: {comparacao['parafusos']['legacy']['total']} parafusos")
    print(f"  Diferença: {comparacao['parafusos']['diferencas']['quantidade']}")
    
    if comparacao['parafusos']['novo']['distancias']:
        print(f"\n  Distâncias NOVO: {comparacao['parafusos']['novo']['distancias']}")
    if comparacao['parafusos']['legacy']['distancias']:
        print(f"  Distâncias LEGACY: {comparacao['parafusos']['legacy']['distancias']}")
    
    if comparacao['parafusos']['diferencas']['distancias_diferentes']:
        print("\n  ⚠️  DISTÂNCIAS DIFERENTES:")
        for diff in comparacao['parafusos']['diferencas']['distancias_diferentes']:
            print(f"    Índice {diff['indice']}: NOVO={diff['novo']}, LEGACY={diff['legacy']}, DIF={diff['diferenca']:.1f}")
    else:
        print("\n  ✅ Distâncias idênticas")
    
    # Grades
    print("\n📐 GRADES:")
    print(f"  Novo: {comparacao['grades']['novo']['total']} grades")
    print(f"  Legacy: {comparacao['grades']['legacy']['total']} grades")
    print(f"  Diferença: {comparacao['grades']['diferencas']['quantidade']}")
    
    if comparacao['grades']['novo']['larguras']:
        print(f"\n  Larguras NOVO: {comparacao['grades']['novo']['larguras']}")
    if comparacao['grades']['legacy']['larguras']:
        print(f"  Larguras LEGACY: {comparacao['grades']['legacy']['larguras']}")
    
    difs = comparacao['grades']['diferencas']['larguras_diferentes']
    if difs['apenas_novo'] or difs['apenas_legacy']:
        print("\n  ⚠️  LARGURAS DIFERENTES:")
        if difs['apenas_novo']:
            print(f"    Apenas NOVO: {difs['apenas_novo']}")
        if difs['apenas_legacy']:
            print(f"    Apenas LEGACY: {difs['apenas_legacy']}")
    else:
        print("\n  ✅ Larguras idênticas")
    
    print("\n" + "="*70)


def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Compara dois scripts CIMA para identificar diferenças em parafusos e grades'
    )
    parser.add_argument('script_novo', help='Caminho do script novo (gerado)')
    parser.add_argument('script_legacy', help='Caminho do script legacy (referência)')
    parser.add_argument('--json', help='Salvar resultado em JSON (opcional)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.script_novo):
        print(f"[ERRO] Script novo não encontrado: {args.script_novo}")
        return
    
    if not os.path.exists(args.script_legacy):
        print(f"[ERRO] Script legacy não encontrado: {args.script_legacy}")
        return
    
    comparacao = comparar_scripts(args.script_novo, args.script_legacy)
    
    if 'erro' in comparacao:
        print(f"[ERRO] {comparacao['erro']}")
        return
    
    imprimir_comparacao(comparacao)
    
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(comparacao, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Resultado salvo em: {args.json}")


if __name__ == '__main__':
    main()
