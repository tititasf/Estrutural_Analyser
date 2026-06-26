#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrair_largura_vigas_fv.py — Extrai largura (B = min(b,h)) das vigas a partir
dos DXFs ESTRUTURAIS (Fase-2_Triagem/Estruturais_Pavimentos_Limpos/).

Arquitetura B (correta):
  Fonte: desenhos estruturais do projetista (plantas de forma/estrutura)
  NAO usa FV DXFs de Projetos_Finalizados.

Algoritmo:
  1. Varre DXFs em Fase-2_Triagem/Estruturais_Pavimentos_Limpos/
  2. Para cada DXF extrai TEXT/MTEXT:
       - Nomes de viga: padrao V<num>[sufixo]
       - Textos de dimensao: padrao <b>/<h> ou <b>x<h>
  3. Proximity matching: cada nome -> dimensao mais proxima
  4. largura_cm = min(val1, val2)  (b = menor valor)
  5. Agrega por frequencia
  6. Salva em Fase-3_Interpretacao_Extracao/Vigas/vigas_largura.json

CLI:
  python scripts/extrair_largura_vigas_fv.py --obra PATH/Obra_TREINO_1
  python scripts/extrair_largura_vigas_fv.py --obra PATH/Obra_TREINO_1 --pavimento "12 PAV"
"""

import argparse
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path


def _load_ezdxf():
    try:
        import ezdxf
        return ezdxf
    except ImportError:
        print("[ERROR] ezdxf nao instalado: pip install ezdxf")
        sys.exit(1)


def dist2d(ax, ay, bx, by) -> float:
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def _normalize_viga_id(raw: str) -> str:
    """Normaliza ID: V281A -> V281."""
    m = re.match(r'^(V[A-Z]?\d+)[A-Z]?$', raw.strip())
    if m:
        return m.group(1)
    return raw.strip()


def _parse_dim_text(txt: str):
    """Parseia 20/60 -> (min, max). Range 10-300."""
    m = re.match(r'^(\d+)[/xX](\d+)$', txt.strip())
    if not m:
        return None
    v1, v2 = int(m.group(1)), int(m.group(2))
    if not (10 <= v1 <= 300 and 10 <= v2 <= 300):
        return None
    return (min(v1, v2), max(v1, v2))


def extract_from_dxf(dxf_path: Path, ezdxf_mod) -> tuple[list, list]:
    """Extrai nomes de viga e textos de dimensao."""
    try:
        doc = ezdxf_mod.readfile(str(dxf_path))
    except Exception as ex:
        print(f"  [WARN] Nao foi possivel ler {dxf_path.name}: {ex}")
        return [], []

    msp = doc.modelspace()
    names = []
    dims = []

    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = e.plain_text().strip() if e.dxftype() == 'MTEXT' else e.dxf.text.strip()
            pos = e.dxf.insert
            x, y = float(pos.x), float(pos.y)
        except Exception:
            continue

        if not txt:
            continue

        if re.match(r'^V[A-Z]?\d+[A-Z]*$', txt):
            vid = _normalize_viga_id(txt)
            if vid:
                names.append({'id': vid, 'raw': txt, 'x': x, 'y': y})
            continue

        parsed = _parse_dim_text(txt)
        if parsed:
            b, h = parsed
            dims.append({'b': b, 'h': h, 'raw': txt, 'x': x, 'y': y})

    return names, dims


def match_names_to_dims(names: list, dims: list) -> list:
    """Para cada viga, encontra a dimensao mais proxima."""
    if not names or not dims:
        return []
    results = []
    for v in names:
        best = min(dims, key=lambda d: dist2d(v['x'], v['y'], d['x'], d['y']))
        d = dist2d(v['x'], v['y'], best['x'], best['y'])
        results.append({
            'id': v['id'],
            'b': best['b'],
            'h': best['h'],
            'dist': round(d, 1),
        })
    return results


def confidence_from_dist(d: float) -> float:
    if d < 50:
        return 0.95
    elif d < 200:
        return 0.90
    elif d < 500:
        return 0.80
    elif d < 1200:
        return 0.70
    else:
        return 0.55


def _select_structural_dxfs(struct_dir: Path, pavimento: str | None) -> list:
    """Seleciona DXFs estruturais para o pavimento alvo."""
    all_dxfs = sorted(struct_dir.glob("*.dxf")) + sorted(struct_dir.glob("*.DXF"))
    seen_stems = set()
    all_dxfs_dedup = []
    for f in all_dxfs:
        key = f.name.upper()
        if key not in seen_stems:
            seen_stems.add(key)
            all_dxfs_dedup.append(f)
    all_dxfs = all_dxfs_dedup

    if not pavimento:
        return all_dxfs

    pav_upper = pavimento.upper()
    keywords = set()
    nums = re.findall(r'\d+', pav_upper)
    keywords.update(nums)
    for kw in ['TIPO', 'PADRAO', 'PAV', 'TERREO', 'COBERTURA', 'SUBSOLO', 'SUB', 'FUNDA']:
        if kw in pav_upper:
            keywords.add(kw)
    if 'PAV' in pav_upper or any(c.isdigit() for c in pav_upper):
        keywords.add('TIPO')

    matched = [f for f in all_dxfs
               if any(kw in f.name.upper() for kw in keywords)]

    if matched:
        print(f"[INFO] Pavimento '{pavimento}': {len(matched)} DXF(s) selecionado(s) "
              f"(keywords: {keywords})")
        return matched

    print(f"[INFO] Pavimento '{pavimento}': sem DXF especifico — usando todos ({len(all_dxfs)})")
    return all_dxfs


DEFAULT_B = 15.0  # Largura padrao se nao encontrar


def run(obra_path: str, pavimento: str = None) -> None:
    ezdxf = _load_ezdxf()
    obra = Path(obra_path)

    struct_dir = obra / "Fase-2_Triagem" / "Estruturais_Pavimentos_Limpos"
    out_dir = obra / "Fase-3_Interpretacao_Extracao" / "Vigas"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not struct_dir.exists():
        print(f"[ERROR] Diretorio estrutural nao encontrado: {struct_dir}")
        sys.exit(1)

    dxf_files = _select_structural_dxfs(struct_dir, pavimento)
    if not dxf_files:
        print(f"[ERROR] Nenhum DXF encontrado em {struct_dir}")
        sys.exit(1)

    print(f"[INFO] === extrair_largura_vigas_fv.py | {obra.name} ===")
    print(f"[INFO] Fonte: {struct_dir}")
    print(f"[INFO] DXFs selecionados: {len(dxf_files)}")

    # {vid: {b_val: {'count': int, 'dist_sum': float, 'sources': [str]}}}
    freq_table: dict[str, dict] = {}

    for dxf_path in dxf_files:
        print(f"\n[INFO] Processando: {dxf_path.name}")
        names, dims = extract_from_dxf(dxf_path, ezdxf)
        print(f"  Nomes V: {len(names)}  |  Dims: {len(dims)}")

        if not names:
            print(f"  [SKIP] Sem nomes de viga neste DXF")
            continue
        if not dims:
            print(f"  [SKIP] Sem textos de dimensao neste DXF")
            continue

        matches = match_names_to_dims(names, dims)
        print(f"  Matches: {len(matches)}")

        for m in matches:
            vid = m['id']
            b_val = float(m['b'])  # b = min(val1, val2) = largura
            if vid not in freq_table:
                freq_table[vid] = {}
            if b_val not in freq_table[vid]:
                freq_table[vid][b_val] = {'count': 0, 'dist_sum': 0.0, 'sources': []}
            freq_table[vid][b_val]['count'] += 1
            freq_table[vid][b_val]['dist_sum'] += m['dist']
            freq_table[vid][b_val]['sources'].append(dxf_path.stem)

    # Build result
    result: dict = {}

    # Get all vids (from freq_table + optionally from vigas_dim.json for completeness)
    all_vids = set(freq_table.keys())
    vigas_dim_path = out_dir / "vigas_dim.json"
    if vigas_dim_path.exists():
        try:
            vigas_dim = json.loads(vigas_dim_path.read_text(encoding='utf-8'))
            all_vids |= {k for k in vigas_dim.keys() if not k.startswith('_')}
        except Exception:
            pass

    for vid in sorted(all_vids, key=lambda x: (len(x), x)):
        if vid in freq_table:
            b_map = freq_table[vid]
            best_b = max(b_map.items(),
                         key=lambda kv: (kv[1]['count'], -kv[1]['dist_sum'] / kv[1]['count']))
            b_val, stats = best_b
            avg_dist = stats['dist_sum'] / stats['count']
            conf = confidence_from_dist(avg_dist)
            sources = list(dict.fromkeys(stats['sources']))
            result[vid] = {
                'id': vid,
                'largura_cm': b_val,
                'confidence': round(conf, 2),
                'source': f"structural-freq({stats['count']}x):{sources[0]}",
            }
        else:
            result[vid] = {
                'id': vid,
                'largura_cm': DEFAULT_B,
                'confidence': 0.10,
                'source': 'default',
                'note': f'Sem dados estruturais — default {DEFAULT_B}cm',
            }

    print(f"\n[INFO] Vigas com largura: {len(result)}")

    out_path = out_dir / "vigas_largura.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')

    # Summary
    extraidos = sum(1 for v in result.values() if 'structural' in v.get('source', ''))
    defaults = sum(1 for v in result.values() if v['source'] == 'default')

    print(f"\n=== RESULTADO ===")
    print(f"  Total vigas: {len(result)}")
    print(f"  Extraido por proximidade: {extraidos}/{len(result)}")
    print(f"  Default ({DEFAULT_B}cm): {defaults}")
    print(f"  Output: {out_path}")

    print(f"\n{'Viga':<8} {'B (cm)':<10} {'Conf':<8} {'Fonte'}")
    print("-" * 50)
    count = 0
    for vid in sorted([k for k in result if not k.startswith('_')], key=lambda x: (len(x), x)):
        v = result[vid]
        print(f"{vid:<8} {v['largura_cm']:<10} {v['confidence']:<8.2f} {v['source']}")
        count += 1
        if count >= 15:
            print(f"  ... ({len(result) - 15} mais)")
            break


def main():
    parser = argparse.ArgumentParser(
        description='Extrai largura B das vigas dos DXFs estruturais (Fase-2)'
    )
    parser.add_argument('--obra', required=True, help='Path da obra')
    parser.add_argument('--pavimento', default=None,
                        help='Pavimento (opcional)')
    args = parser.parse_args()
    run(args.obra, args.pavimento)


if __name__ == '__main__':
    main()
