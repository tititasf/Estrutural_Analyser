#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrair_lajes_lj.py — Extrai dados de lajes a partir dos DXFs ESTRUTURAIS
(Fase-2_Triagem/Estruturais_Pavimentos_Limpos/).

Arquitetura B (correta):
  Fonte: desenhos estruturais do projetista (plantas de forma/estrutura)
  NAO usa LJ DXFs de Projetos_Finalizados.

Algoritmo:
  1. Varre DXFs em Fase-2_Triagem/Estruturais_Pavimentos_Limpos/
  2. Para cada DXF extrai TEXT/MTEXT:
       - Nomes de laje: padrao L<num>[sufixo]
  3. Para cada laje, busca nearest LWPOLYLINE -> bounding box -> dimensoes
  4. Fallback: busca textos de span (plain numbers 50..5000) proximos
  5. Agrega resultados por frequencia
  6. Salva em Fase-3_Interpretacao_Extracao/Lajes/lajes_data.json

CLI:
  python scripts/extrair_lajes_lj.py --obra PATH/Obra_TREINO_1
  python scripts/extrair_lajes_lj.py --obra PATH/Obra_TREINO_1 --pavimento "12 PAV"
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


def _normalize_laje_id(raw: str) -> str:
    """Normaliza ID: L11A -> L11."""
    m = re.match(r'^(L\d+)[A-Z]?$', raw.strip(), re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return raw.strip().upper()


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


def extract_laje_data_from_dxf(dxf_path: Path, ezdxf_mod) -> list:
    """
    Extrai nomes de laje e tenta associar a LWPOLYLINE ou spans proximos.

    Returns list of:
        {'id': 'L11', 'comprimento': float|None, 'largura': float|None,
         'area': float|None, 'confidence': float, 'source': str, 'method': str}
    """
    try:
        doc = ezdxf_mod.readfile(str(dxf_path))
    except Exception as ex:
        print(f"  [WARN] Nao foi possivel ler {dxf_path.name}: {ex}")
        return []

    msp = doc.modelspace()

    # Collect laje name labels
    laje_names = []
    # Collect LWPOLYLINE centroids and bboxes
    polylines = []
    # Collect span texts (plain numbers)
    span_texts = []

    for e in msp:
        etype = e.dxftype()

        if etype in ('TEXT', 'MTEXT'):
            try:
                txt = e.plain_text().strip() if etype == 'MTEXT' else e.dxf.text.strip()
                pos = e.dxf.insert
                x, y = float(pos.x), float(pos.y)
            except Exception:
                continue
            if not txt:
                continue

            # Laje name
            if re.match(r'^L\d+[A-Z]*$', txt, re.IGNORECASE):
                lid = _normalize_laje_id(txt)
                laje_names.append({'id': lid, 'raw': txt, 'x': x, 'y': y})
                continue

            # Span text (plain number 50..5000)
            if '/' not in txt and 'x' not in txt.lower():
                m = re.match(r'^(\d+\.?\d*)$', txt)
                if m:
                    val = float(m.group(1))
                    if 50 <= val <= 5000:
                        span_texts.append({'val': val, 'x': x, 'y': y})

        elif etype == 'LWPOLYLINE':
            try:
                pts = [(v[0], v[1]) for v in e.get_points()]
                if len(pts) < 3:
                    continue
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                cx = sum(xs) / len(xs)
                cy = sum(ys) / len(ys)
                w = max(xs) - min(xs)
                h = max(ys) - min(ys)
                # Filter: area must be reasonable for a laje (>= 1m2 = 10000 cm2)
                area = w * h
                if area < 10000:
                    continue
                polylines.append({
                    'cx': cx, 'cy': cy,
                    'w': round(w, 1), 'h': round(h, 1),
                    'area': round(area, 1),
                })
            except Exception:
                continue

    results = []

    for laje in laje_names:
        lid = laje['id']
        lx, ly = laje['x'], laje['y']

        # Try to find nearest LWPOLYLINE
        best_poly = None
        best_poly_dist = float('inf')
        for poly in polylines:
            d = dist2d(lx, ly, poly['cx'], poly['cy'])
            if d < best_poly_dist:
                best_poly_dist = d
                best_poly = poly

        if best_poly and best_poly_dist < 5000:
            comp = max(best_poly['w'], best_poly['h'])
            larg = min(best_poly['w'], best_poly['h'])
            if comp >= 50 and larg >= 50:
                conf = 0.80 if best_poly_dist < 500 else 0.65 if best_poly_dist < 2000 else 0.50
                results.append({
                    'id': lid,
                    'comprimento': comp,
                    'largura': larg,
                    'area': round(comp * larg, 1),
                    'confidence': conf,
                    'source': dxf_path.stem,
                    'method': 'lwpolyline-bbox',
                    'dist': round(best_poly_dist, 1),
                })
                continue

        # Fallback: use nearby span texts for dimensions
        nearby_spans = []
        for s in span_texts:
            d = dist2d(lx, ly, s['x'], s['y'])
            if d < 3000:
                nearby_spans.append((d, s['val']))
        nearby_spans.sort()

        if len(nearby_spans) >= 2:
            vals = sorted([v for _, v in nearby_spans[:4]], reverse=True)
            comp = vals[0]
            larg = vals[1]
            results.append({
                'id': lid,
                'comprimento': round(comp, 1),
                'largura': round(larg, 1),
                'area': round(comp * larg, 1),
                'confidence': 0.45,
                'source': dxf_path.stem,
                'method': 'span-proximity',
                'dist': round(nearby_spans[0][0], 1),
            })
        elif len(nearby_spans) == 1:
            val = nearby_spans[0][1]
            results.append({
                'id': lid,
                'comprimento': round(val, 1),
                'largura': round(val, 1),
                'area': round(val * val, 1),
                'confidence': 0.30,
                'source': dxf_path.stem,
                'method': 'span-single',
                'dist': round(nearby_spans[0][0], 1),
            })
        else:
            results.append({
                'id': lid,
                'comprimento': None,
                'largura': None,
                'area': None,
                'confidence': 0.15,
                'source': dxf_path.stem,
                'method': 'name-only',
                'dist': None,
            })

    return results


def run(obra_path: str, pavimento: str = None) -> None:
    ezdxf = _load_ezdxf()
    obra = Path(obra_path)

    struct_dir = obra / "Fase-2_Triagem" / "Estruturais_Pavimentos_Limpos"
    out_dir = obra / "Fase-3_Interpretacao_Extracao" / "Lajes"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not struct_dir.exists():
        print(f"[ERROR] Diretorio estrutural nao encontrado: {struct_dir}")
        sys.exit(1)

    dxf_files = _select_structural_dxfs(struct_dir, pavimento)
    if not dxf_files:
        print(f"[ERROR] Nenhum DXF encontrado em {struct_dir}")
        sys.exit(1)

    print(f"[INFO] === extrair_lajes_lj.py | {obra.name} ===")
    print(f"[INFO] Fonte: {struct_dir}")
    print(f"[INFO] DXFs selecionados: {len(dxf_files)}")

    # Aggregate: {lid: [results from each dxf]}
    all_results: dict[str, list] = {}

    for dxf_path in dxf_files:
        print(f"\n[INFO] Processando: {dxf_path.name}")
        entries = extract_laje_data_from_dxf(dxf_path, ezdxf)
        print(f"  Lajes encontradas: {len(entries)}")

        for entry in entries:
            lid = entry['id']
            if lid not in all_results:
                all_results[lid] = []
            all_results[lid].append(entry)

    if not all_results:
        print(f"\n[WARN] Nenhuma laje encontrada nos DXFs estruturais — "
              f"output vazio (normal para obras sem labels L<n> nos estruturais)")
        # Write empty result
        empty = {"_meta": {
            "total": 0,
            "obra": obra.name,
            "pavimento": pavimento or "todos",
            "extraido_em": datetime.now().strftime("%Y-%m-%d"),
            "nota": "Nenhuma laje encontrada nos DXFs estruturais",
        }}
        out_path = out_dir / "lajes_data.json"
        out_path.write_text(json.dumps(empty, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"[INFO] Salvo (vazio): {out_path}")
        return

    # For each laje, pick best result (highest confidence)
    fichas: dict = {}

    def _lsort(x):
        m = re.match(r'^L(\d+)([A-Za-z]?)$', x, re.IGNORECASE)
        return (int(m.group(1)), m.group(2)) if m else (0, x)

    for lid in sorted(all_results.keys(), key=_lsort):
        entries = all_results[lid]
        # Pick entry with highest confidence
        best = max(entries, key=lambda e: e['confidence'])

        comp = best.get('comprimento')
        larg = best.get('largura')
        area = best.get('area')

        fichas[lid] = {
            'n_paineis': 1,
            'area_total_paineis_cm2': area,
            'comprimento_cm': comp,
            'largura_cm': larg,
            'confidence': round(best['confidence'], 2),
            'source': f"structural-{best['method']}:{best['source']}",
        }

    # Meta
    fichas['_meta'] = {
        'total': len([k for k in fichas if not k.startswith('_')]),
        'obra': obra.name,
        'pavimento': pavimento or 'todos',
        'extraido_em': datetime.now().strftime('%Y-%m-%d'),
        'algoritmo': 'structural-text-proximity',
        'fonte': str(struct_dir),
        'dxfs_processados': len(dxf_files),
        'com_dimensoes': sum(1 for k, v in fichas.items()
                             if not k.startswith('_') and v.get('comprimento_cm') is not None),
    }

    out_path = out_dir / "lajes_data.json"
    out_path.write_text(json.dumps(fichas, indent=2, ensure_ascii=False), encoding='utf-8')

    meta = fichas['_meta']
    print(f"\n[RESULTADO] Extracao de Lajes (Estrutural)")
    print(f"  Total lajes:        {meta['total']}")
    print(f"  Com dimensoes:      {meta['com_dimensoes']}")
    print(f"  Output: {out_path}")

    # Sample
    print(f"\n[AMOSTRA] Primeiras lajes:")
    count = 0
    for lid in sorted([k for k in fichas if not k.startswith('_')], key=_lsort):
        v = fichas[lid]
        c = v.get('comprimento_cm', '-')
        l = v.get('largura_cm', '-')
        a = v.get('area_total_paineis_cm2', '-')
        print(f"  {lid}: {c}x{l}cm | area={a}cm2 | conf={v.get('confidence',0):.0%} | {v.get('source','')}")
        count += 1
        if count >= 8:
            break


def main():
    parser = argparse.ArgumentParser(
        description='Extrai dados de lajes dos DXFs estruturais (Fase-2)'
    )
    parser.add_argument('--obra', required=True, help='Path para o diretorio da obra')
    parser.add_argument('--pavimento', default=None,
                        help='Pavimento (opcional)')
    args = parser.parse_args()
    run(args.obra, args.pavimento)


if __name__ == '__main__':
    main()
