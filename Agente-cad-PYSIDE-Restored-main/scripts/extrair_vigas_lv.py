#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrair_vigas_lv.py — Extrai altura_lateral (h) e comprimento de vigas a partir
dos DXFs ESTRUTURAIS (Fase-2_Triagem/Estruturais_Pavimentos_Limpos/).

Arquitetura B (correta):
  Fonte: desenhos estruturais do projetista (plantas de forma/estrutura)
  NAO usa Projetos_Finalizados (esse e apenas para comparacao de fidelidade STOG).

Algoritmo:
  1. Varre DXFs em Fase-2_Triagem/Estruturais_Pavimentos_Limpos/
  2. Para cada DXF extrai TEXT/MTEXT:
       - Nomes de viga: padrao V<num>[sufixo]  ex: V1, V281A, V32
       - Textos de dimensao: padrao <b>/<h> ou <b>x<h>  ex: 20/60, 14x50
       - Textos de vao (span): plain numbers 50..5000 (sem / ou x)
  3. Proximity matching: cada nome de viga -> dimensao + span mais proximos
  4. Normaliza ID: V281A -> V281 (remove sufixo de pavimento TQS)
  5. Agrega resultados de todos os DXFs (maior frequencia vence)
  6. Salva em Fase-3_Interpretacao_Extracao/Vigas/vigas_dim.json

CLI:
  python scripts/extrair_vigas_lv.py --obra PATH/Obra_TREINO_1
  python scripts/extrair_vigas_lv.py --obra PATH/Obra_TREINO_1 --pavimento "12 PAV"
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
    """
    Normaliza ID da viga: remove sufixo de pavimento TQS.
    V281A -> V281
    V32   -> V32
    VA2   -> VA2  (especiais: nao normalizar se tem letra entre V e num)
    """
    m = re.match(r'^(V[A-Z]?\d+)[A-Z]?$', raw.strip())
    if m:
        return m.group(1)
    return raw.strip()


def _parse_dim_text(txt: str):
    """
    Parseia texto de dimensao estrutural.
    Retorna (b_cm, h_cm) ou None.
    Formatos aceitos: '20/60', '14x50', '19X50'
    Range valido: 10-300 cm cada valor.
    """
    m = re.match(r'^(\d+)[/xX](\d+)$', txt.strip())
    if not m:
        return None
    v1, v2 = int(m.group(1)), int(m.group(2))
    if not (10 <= v1 <= 300 and 10 <= v2 <= 300):
        return None
    return (min(v1, v2), max(v1, v2))  # b=menor, h=maior


def _is_span_text(txt: str) -> float | None:
    """
    Verifica se texto e um valor de vao (span) em cm.
    Plain numbers no range 50..5000 (sem / ou x).
    Retorna o valor float ou None.
    """
    txt = txt.strip()
    # Rejeitar se contem / ou x (e dimensao b/h)
    if '/' in txt or 'x' in txt.lower():
        return None
    m = re.match(r'^(\d+\.?\d*)$', txt)
    if not m:
        return None
    val = float(m.group(1))
    if 50 <= val <= 5000:
        return val
    return None


def extract_from_dxf(dxf_path: Path, ezdxf_mod) -> tuple[list, list, list]:
    """
    Extrai nomes de viga, textos de dimensao, e textos de vao de um DXF estrutural.

    Returns:
        names: [{'id': 'V281', 'x': float, 'y': float, 'raw': 'V281A'}, ...]
        dims:  [{'b': int, 'h': int, 'x': float, 'y': float, 'raw': '20/60'}, ...]
        spans: [{'val': float, 'x': float, 'y': float, 'raw': '953'}, ...]
    """
    try:
        doc = ezdxf_mod.readfile(str(dxf_path))
    except Exception as ex:
        print(f"  [WARN] Nao foi possivel ler {dxf_path.name}: {ex}")
        return [], [], []

    msp = doc.modelspace()
    names = []
    dims = []
    spans = []

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

        # Verificar se e nome de viga: V<num>[letras opcionais]
        if re.match(r'^V[A-Z]?\d+[A-Z]*$', txt):
            vid = _normalize_viga_id(txt)
            if vid:
                names.append({'id': vid, 'raw': txt, 'x': x, 'y': y})
            continue

        # Verificar se e texto de dimensao b/h ou bxh
        parsed = _parse_dim_text(txt)
        if parsed:
            b, h = parsed
            dims.append({'b': b, 'h': h, 'raw': txt, 'x': x, 'y': y})
            continue

        # Verificar se e texto de vao (span)
        span_val = _is_span_text(txt)
        if span_val is not None:
            spans.append({'val': span_val, 'raw': txt, 'x': x, 'y': y})

    return names, dims, spans


def match_names_to_dims(names: list, dims: list) -> list:
    """
    Para cada viga, encontra a dimensao mais proxima.
    """
    if not names or not dims:
        return []

    results = []
    for v in names:
        best = min(dims, key=lambda d: dist2d(v['x'], v['y'], d['x'], d['y']))
        d = dist2d(v['x'], v['y'], best['x'], best['y'])
        results.append({
            'id': v['id'],
            'raw_id': v['raw'],
            'b': best['b'],
            'h': best['h'],
            'dist': round(d, 1),
            'raw_dim': best['raw'],
        })
    return results


def match_names_to_spans(names: list, spans: list) -> dict:
    """
    Para cada viga, encontra o span (vao) mais proximo.
    Returns: {vid: {'val': float, 'dist': float}}
    """
    if not names or not spans:
        return {}

    result = {}
    for v in names:
        best = min(spans, key=lambda s: dist2d(v['x'], v['y'], s['x'], s['y']))
        d = dist2d(v['x'], v['y'], best['x'], best['y'])
        vid = v['id']
        if vid not in result or d < result[vid]['dist']:
            result[vid] = {'val': best['val'], 'dist': round(d, 1)}
    return result


def confidence_from_dist(d: float) -> float:
    """Confidence baseada na distancia nome-dimensao."""
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
    """
    Seleciona DXFs estruturais mais relevantes para o pavimento alvo.
    (Same logic as extrair_bh_pilares.py)
    """
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


DEFAULT_SPAN = 300.0  # comprimento default quando nao encontrado


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

    print(f"[INFO] === extrair_vigas_lv.py | {obra.name} ===")
    print(f"[INFO] Fonte: {struct_dir}")
    print(f"[INFO] DXFs selecionados: {len(dxf_files)}")

    # Frequency tables for dimensions and spans
    # {vid: {(b,h): {'count': int, 'dist_sum': float, 'sources': [str]}}}
    freq_dim: dict[str, dict] = {}
    # {vid: {span_val: {'count': int, 'dist_sum': float}}}
    freq_span: dict[str, dict] = {}
    # LV-B3: posições de labels por viga (para centróide cx/cy)
    positions_table: dict[str, list] = {}

    for dxf_path in dxf_files:
        print(f"\n[INFO] Processando: {dxf_path.name}")
        names, dims, spans = extract_from_dxf(dxf_path, ezdxf)
        print(f"  Nomes V: {len(names)}  |  Dims b/h: {len(dims)}  |  Spans: {len(spans)}")

        if not names:
            print(f"  [SKIP] Sem nomes de viga neste DXF")
            continue

        # Coletar posições de labels (para cx/cy — LV-B3)
        for n in names:
            positions_table.setdefault(n['id'], []).append([n['x'], n['y']])

        # Match dims
        if dims:
            matches = match_names_to_dims(names, dims)
            print(f"  Matches dim: {len(matches)}")
            for m in matches:
                vid = m['id']
                bh_key = (float(m['b']), float(m['h']))
                if vid not in freq_dim:
                    freq_dim[vid] = {}
                if bh_key not in freq_dim[vid]:
                    freq_dim[vid][bh_key] = {'count': 0, 'dist_sum': 0.0, 'sources': []}
                freq_dim[vid][bh_key]['count'] += 1
                freq_dim[vid][bh_key]['dist_sum'] += m['dist']
                freq_dim[vid][bh_key]['sources'].append(dxf_path.stem)

        # Match spans
        if spans:
            span_matches = match_names_to_spans(names, spans)
            for vid, sm in span_matches.items():
                sv = round(sm['val'], 1)
                if vid not in freq_span:
                    freq_span[vid] = {}
                if sv not in freq_span[vid]:
                    freq_span[vid][sv] = {'count': 0, 'dist_sum': 0.0}
                freq_span[vid][sv]['count'] += 1
                freq_span[vid][sv]['dist_sum'] += sm['dist']

    if not freq_dim:
        print("\n[ERROR] Nenhuma viga extraida de nenhum DXF estrutural")
        sys.exit(1)

    # Aggregate: for each viga pick most frequent (b,h) and most frequent span
    result: dict = {}
    all_vids = sorted(set(freq_dim.keys()) | set(freq_span.keys()),
                      key=lambda x: (len(x), x))

    for vid in all_vids:
        # Dimension (b/h)
        b, h, dim_conf = None, None, 0.0
        if vid in freq_dim:
            bh_map = freq_dim[vid]
            best_bh = max(bh_map.items(),
                          key=lambda kv: (kv[1]['count'], -kv[1]['dist_sum'] / kv[1]['count']))
            bh_key, stats = best_bh
            b, h = bh_key
            avg_dist = stats['dist_sum'] / stats['count']
            dim_conf = confidence_from_dist(avg_dist)

        # Span (comprimento)
        comp, comp_conf, comp_source = None, None, None
        if vid in freq_span:
            sp_map = freq_span[vid]
            best_sp = max(sp_map.items(),
                          key=lambda kv: (kv[1]['count'], -kv[1]['dist_sum'] / kv[1]['count']))
            span_val, sp_stats = best_sp
            comp = span_val
            sp_avg_dist = sp_stats['dist_sum'] / sp_stats['count']
            comp_conf = confidence_from_dist(sp_avg_dist) * 0.9  # slightly lower for spans
            comp_source = 'structural-span-proximity'

        if comp is None:
            comp = DEFAULT_SPAN
            comp_conf = 0.10
            comp_source = 'default'

        altura = h if h else None  # h = max(b,h) = altura_lateral

        confs = [c for c in [dim_conf, comp_conf] if c and c > 0]
        overall_conf = round(sum(confs) / len(confs), 2) if confs else 0.0

        # LV-B3: centróide do label (posição aproximada da viga no plano)
        pts = positions_table.get(vid, [])
        vx = round(sum(p[0] for p in pts) / len(pts), 2) if pts else None
        vy = round(sum(p[1] for p in pts) / len(pts), 2) if pts else None

        result[vid] = {
            'id': vid,
            'sides': ['A', 'B'],
            'altura_lateral_cm': altura,
            'altura_conf': round(dim_conf, 2) if dim_conf else None,
            'comprimento_cm': comp,
            'comprimento_conf': round(comp_conf, 2) if comp_conf else None,
            'comprimento_source': comp_source,
            'confidence': overall_conf,
            # LV-B3: centróide do label em coordenadas DXF (cm) — para pillar_left/right
            'cx': vx,
            'cy': vy,
        }

    print(f"\n[INFO] Vigas unicas: {len(result)}")

    # Add meta
    result["_meta"] = {
        "total": len([k for k in result if not k.startswith('_')]),
        "obra": obra.name,
        "pavimento": pavimento or "todos",
        "extraido_em": datetime.now().strftime("%Y-%m-%d"),
        "algoritmo": "structural-text-proximity",
        "fonte": str(struct_dir),
        "dxfs_processados": len(dxf_files),
    }

    out_path = out_dir / "vigas_dim.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')

    # Summary
    total = len([k for k in result if not k.startswith('_')])
    com_alt = sum(1 for k, v in result.items()
                  if not k.startswith('_') and v.get('altura_lateral_cm') is not None)
    com_comp = sum(1 for k, v in result.items()
                   if not k.startswith('_') and v.get('comprimento_cm') is not None)
    com_ambos = sum(1 for k, v in result.items()
                    if not k.startswith('_') and v.get('altura_lateral_cm') and v.get('comprimento_cm'))
    avg_conf = (sum(v.get('confidence', 0) for k, v in result.items() if not k.startswith('_'))
                / total if total else 0)

    print(f"\n=== RESULTADO ===")
    print(f"  Total vigas: {total}")
    print(f"  Com altura_lateral: {com_alt}/{total}")
    print(f"  Com comprimento: {com_comp}/{total}")
    print(f"  Com ambos: {com_ambos}/{total}")
    print(f"  Confianca media: {avg_conf:.0%}")
    print(f"  Output: {out_path}")
    print()
    print(f"{'Viga':<8} {'Alt(cm)':<10} {'Comp(cm)':<12} {'Conf':<8} {'Sides'}")
    print("-" * 55)
    count = 0
    for vid in sorted([k for k in result if not k.startswith('_')], key=lambda x: (len(x), x)):
        v = result[vid]
        alt = f"{v['altura_lateral_cm']:.0f}" if v['altura_lateral_cm'] else "None"
        comp = f"{v['comprimento_cm']:.0f}" if v['comprimento_cm'] else "None"
        conf = f"{v['confidence']:.0%}" if v['confidence'] else "0%"
        sides = '+'.join(v['sides'])
        print(f"{vid:<8} {alt:<10} {comp:<12} {conf:<8} {sides}")
        count += 1
        if count >= 15:
            print(f"  ... ({total - 15} mais)")
            break


def main():
    parser = argparse.ArgumentParser(
        description='Extrai dimensoes de vigas dos DXFs estruturais (Fase-2)'
    )
    parser.add_argument('--obra', required=True, help='Path da obra')
    parser.add_argument('--pavimento', default=None,
                        help='Pavimento (opcional — processados todos por padrao)')
    args = parser.parse_args()
    run(args.obra, args.pavimento)


if __name__ == '__main__':
    main()
