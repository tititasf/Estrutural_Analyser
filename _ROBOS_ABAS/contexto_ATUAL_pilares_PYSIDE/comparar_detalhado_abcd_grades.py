#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comparação detalhada entre scripts ABCD e GRADES legacy vs gerados
Identifica TODAS as diferenças linha por linha
"""

import difflib
from pathlib import Path

def read_utf16(file_path: Path) -> str:
    """Lê arquivo UTF-16 LE"""
    with open(file_path, 'rb') as f:
        raw = f.read()
    if raw.startswith(b'\xff\xfe'):
        raw = raw[2:]
    return raw.decode('utf-16-le', errors='ignore')

def normalize_lines(content: str) -> list[str]:
    """Normaliza linhas removendo espaços extras mas mantendo estrutura"""
    lines = content.splitlines()
    return [line.rstrip() for line in lines]

def comparar_scripts_detalhado(legacy_path: Path, gerado_path: Path, tipo: str):
    """Compara dois scripts linha por linha e identifica diferenças"""
    print(f"\n{'='*100}")
    print(f"COMPARAÇÃO DETALHADA: {tipo}")
    print(f"{'='*100}")
    
    if not legacy_path.exists():
        print(f"[ERRO] Legacy não encontrado: {legacy_path}")
        return
    
    if not gerado_path.exists():
        print(f"[ERRO] Gerado não encontrado: {gerado_path}")
        return
    
    legacy_content = read_utf16(legacy_path)
    gerado_content = read_utf16(gerado_path)
    
    legacy_lines = normalize_lines(legacy_content)
    gerado_lines = normalize_lines(gerado_content)
    
    print(f"\n[INFO] Legacy: {len(legacy_lines)} linhas")
    print(f"[INFO] Gerado: {len(gerado_lines)} linhas")
    print(f"[INFO] Diferença: {len(gerado_lines) - len(legacy_lines):+d} linhas")
    
    # Usar difflib para comparação detalhada
    diff = list(difflib.unified_diff(
        legacy_lines, 
        gerado_lines,
        fromfile=f"LEGACY ({legacy_path.name})",
        tofile=f"GERADO ({gerado_path.name})",
        lineterm='',
        n=0  # Sem contexto
    ))
    
    if not diff:
        print(f"\n[OK] Scripts são IDÊNTICOS!")
        return
    
    print(f"\n[AVISO] Scripts são DIFERENTES - {len(diff)} diferenças encontradas")
    
    # Analisar diferenças
    diferencas_por_tipo = {
        'PLINE': 0,
        'INSERT': 0,
        'DIMLINEAR': 0,
        'TEXT': 0,
        'LAYER': 0,
        'ZOOM': 0,
        'outros': 0
    }
    
    linhas_diferentes = []
    for i, line in enumerate(diff):
        if line.startswith('---') or line.startswith('+++') or line.startswith('@@'):
            continue
        
        if line.startswith('-') or line.startswith('+'):
            linhas_diferentes.append((i, line))
            
            # Categorizar diferença
            line_stripped = line[1:].strip()
            if '_PLINE' in line_stripped or 'PLINE' in line_stripped:
                diferencas_por_tipo['PLINE'] += 1
            elif '-INSERT' in line_stripped or 'INSERT' in line_stripped:
                diferencas_por_tipo['INSERT'] += 1
            elif '_DIMLINEAR' in line_stripped or 'DIMLINEAR' in line_stripped:
                diferencas_por_tipo['DIMLINEAR'] += 1
            elif '_TEXT' in line_stripped or 'TEXT' in line_stripped:
                diferencas_por_tipo['TEXT'] += 1
            elif '_LAYER' in line_stripped or 'LAYER' in line_stripped:
                diferencas_por_tipo['LAYER'] += 1
            elif '_ZOOM' in line_stripped or 'ZOOM' in line_stripped:
                diferencas_por_tipo['ZOOM'] += 1
            else:
                diferencas_por_tipo['outros'] += 1
    
    print(f"\n[ANÁLISE] Diferenças por tipo:")
    for tipo_diff, count in diferencas_por_tipo.items():
        if count > 0:
            print(f"  {tipo_diff}: {count}")
    
    # Mostrar primeiras 50 diferenças
    print(f"\n[PRIMEIRAS 50 DIFERENÇAS]:")
    for i, (idx, line) in enumerate(linhas_diferentes[:50]):
        print(f"  {i+1:3d}. {line[:100]}")
    
    if len(linhas_diferentes) > 50:
        print(f"  ... e mais {len(linhas_diferentes) - 50} diferenças")
    
    # Análise específica para ABCD
    if tipo == 'ABCD':
        print(f"\n[ANÁLISE ESPECÍFICA ABCD]:")
        
        # Contar PLINEs
        legacy_plines = legacy_content.count('_PLINE')
        gerado_plines = gerado_content.count('_PLINE')
        print(f"  PLINEs: Legacy={legacy_plines}, Gerado={gerado_plines}, Diff={gerado_plines - legacy_plines:+d}")
        
        # Contar INSERTs
        legacy_inserts = legacy_content.count('-INSERT')
        gerado_inserts = gerado_content.count('-INSERT')
        print(f"  INSERTs: Legacy={legacy_inserts}, Gerado={gerado_inserts}, Diff={gerado_inserts - legacy_inserts:+d}")
        
        # Verificar texto de nível
        if 'NÍVEL DE CHEGADA: 3,00' in legacy_content:
            print(f"  [OK] Legacy tem 'NÍVEL DE CHEGADA: 3,00'")
        if 'NÍVEL DE CHEGADA: INDEFINIDO' in gerado_content:
            print(f"  [ERRO] Gerado tem 'NÍVEL DE CHEGADA: INDEFINIDO' (deveria ser 3,00)")
        
        # Verificar PD
        if 'PD: 3,00' in legacy_content:
            print(f"  [OK] Legacy tem 'PD: 3,00'")
        if 'PD: 0,00' in gerado_content:
            print(f"  [ERRO] Gerado tem 'PD: 0,00' (deveria ser 3,00)")
    
    # Análise específica para GRADES
    elif tipo.startswith('GRADES'):
        print(f"\n[ANÁLISE ESPECÍFICA GRADES]:")
        
        # Verificar sarrafos verticais (devem ter altura ~282.2)
        import re
        pattern_vertical = r'_LINE\s+([-\d.]+),([-\d.]+)\s+([-\d.]+),([-\d.]+)'
        legacy_verticals = re.findall(pattern_vertical, legacy_content)
        gerado_verticals = re.findall(pattern_vertical, gerado_content)
        
        # Verificar alturas dos sarrafos verticais
        legacy_alturas = []
        for match in legacy_verticals:
            y1, y2 = float(match[1]), float(match[3])
            altura = abs(y2 - y1)
            if altura > 100:  # Sarrafo vertical
                legacy_alturas.append(altura)
        
        gerado_alturas = []
        for match in gerado_verticals:
            y1, y2 = float(match[1]), float(match[3])
            altura = abs(y2 - y1)
            if altura > 100:  # Sarrafo vertical
                gerado_alturas.append(altura)
        
        print(f"  Sarrafos verticais: Legacy={len(legacy_alturas)}, Gerado={len(gerado_alturas)}")
        if legacy_alturas:
            print(f"  Altura média legacy: {sum(legacy_alturas)/len(legacy_alturas):.1f}")
        if gerado_alturas:
            print(f"  Altura média gerado: {sum(gerado_alturas)/len(gerado_alturas):.1f}")
    
    return diff

def main():
    project_root = Path(__file__).parent.parent.parent
    
    legacy_dir = project_root / "_ROBOS_ABAS" / "contexto_legacy_pilares"
    gerado_dir = project_root / "_ROBOS_ABAS" / "Robo_Pilares" / "pilares-atualizado-09-25" / "SCRIPTS_ROBOS"
    
    # Comparar ABCD
    legacy_abcd = legacy_dir / "Ptestelegacy_ABCD.scr"
    gerado_abcd = gerado_dir / "Subsolo_ABCD" / "Ptestelegacy_ABCD.scr"
    
    if gerado_abcd.exists():
        comparar_scripts_detalhado(legacy_abcd, gerado_abcd, "ABCD")
    else:
        print(f"[AVISO] Script ABCD gerado não encontrado: {gerado_abcd}")
    
    # Comparar GRADES A
    legacy_grades_a = legacy_dir / "Ptestelegacy.A.scr"
    gerado_grades_a = gerado_dir / "Subsolo_GRADES" / "Ptestelegacy.A.scr"
    
    if gerado_grades_a.exists():
        comparar_scripts_detalhado(legacy_grades_a, gerado_grades_a, "GRADES_A")
    else:
        print(f"[AVISO] Script GRADES A gerado não encontrado: {gerado_grades_a}")
    
    # Comparar GRADES B
    legacy_grades_b = legacy_dir / "Ptestelegacy.B.scr"
    gerado_grades_b = gerado_dir / "Subsolo_GRADES" / "Ptestelegacy.B.scr"
    
    if gerado_grades_b.exists():
        comparar_scripts_detalhado(legacy_grades_b, gerado_grades_b, "GRADES_B")
    else:
        print(f"[AVISO] Script GRADES B gerado não encontrado: {gerado_grades_b}")

if __name__ == '__main__':
    main()
