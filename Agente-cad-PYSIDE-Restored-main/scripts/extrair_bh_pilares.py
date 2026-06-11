#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrair_bh_pilares.py — Extrai dimensoes B e H de pilares a partir dos
DXFs ESTRUTURAIS (Fase-2_Triagem/Estruturais_Pavimentos_Limpos/).

Arquitetura B (correta):
  Fonte: desenhos estruturais do projetista (plantas de forma/estrutura)
  NAO usa Projetos_Finalizados (esse e apenas para comparacao de fidelidade STOG).

Algoritmo:
  1. Varre TODOS os DXFs em Fase-2_Triagem/Estruturais_Pavimentos_Limpos/
  2. Para cada DXF extrai TEXT/MTEXT:
       - Nomes de pilar: padrao P<num>[sufixo]  ex: P1, P7B, P11A
       - Textos de dimensao: padrao <b>/<h> ou <b>x<h>  ex: 20/60, 19x50
  3. Proximity matching: cada nome de pilar -> dimensao mais proxima
  4. Normaliza ID: P7B -> P7 (remove sufixo de pavimento TQS)
  5. Agrega resultados de todos os DXFs (maior confianca vence)
  6. Salva em Fase-3_Interpretacao_Extracao/Pilares/pilares_bh.json

Suporta tres convencoes de layer (auto-detectado):
  - MTH-  : MTH-TIT1-PILAR (nomes) + MTH-DIM-PILAR (dims) — TQS padrao
  - ES-   : ES-PILAR-NOME (nomes e dims intercalados)
  - numerico: layers numericos (ex: 4=nomes, 3=dims)
  - fallback: scan de todos os layers

CLI:
  python scripts/extrair_bh_pilares.py --obra PATH/Obra_TREINO_3
  python scripts/extrair_bh_pilares.py --obra PATH/Obra_TREINO_1 [--pavimento ignorado]
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


# ==============================================================================
# SPRINT 2 — Geometria de pilar: bbox + ângulo de LWPOLYLINE
# ==============================================================================

def _rect_from_lwpoly(pts: list) -> dict | None:
    """
    Tenta interpretar uma LWPOLYLINE como retângulo.
    Aceita 4 ou 5 pontos (5 = fechado: último == primeiro).
    Retorna {'cx', 'cy', 'w', 'h', 'angle'} ou None.
    angle = ângulo em graus do eixo longo em relação ao eixo X [0..180).
    """
    if len(pts) not in (4, 5):
        return None
    # Desconsiderar ponto de fechamento se igual ao primeiro
    uniq = pts[:4] if (len(pts) == 5 and
                       abs(pts[4][0] - pts[0][0]) < 0.1 and
                       abs(pts[4][1] - pts[0][1]) < 0.1) else pts
    if len(uniq) != 4:
        return None

    xs = [p[0] for p in uniq]
    ys = [p[1] for p in uniq]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    if w < 1 or h < 1:
        return None  # degenerado

    cx = (max(xs) + min(xs)) / 2
    cy = (max(ys) + min(ys)) / 2

    # Ângulo do eixo longo: 0° = horizontal (w>h), 90° = vertical (h>w)
    angle = 0.0 if w >= h else 90.0
    # Refinamento: usar vetor entre vértices adjacentes para detectar rotação real
    # (para retângulos axiais, angle 0/90 é exato; para rotacionados, aproximar)
    try:
        dx = uniq[1][0] - uniq[0][0]
        dy = uniq[1][1] - uniq[0][1]
        edge_len = math.sqrt(dx * dx + dy * dy)
        if edge_len > 1:
            raw_angle = math.degrees(math.atan2(abs(dy), abs(dx)))
            # Normalizar ao eixo longo
            angle = raw_angle if edge_len >= (w + h) / 2 else (90 - raw_angle)
    except Exception:
        pass

    return {'cx': round(cx, 2), 'cy': round(cy, 2),
            'geo_w': round(min(w, h), 1), 'geo_h': round(max(w, h), 1),
            'angle': round(angle, 1)}


def extract_pilar_geometry(dxf_path: Path, ezdxf_mod,
                           known_dims: dict | None = None) -> dict:
    """
    Sprint 2: Extrai geometria precisa de pilares (bbox + ângulo) de LWPOLYLINE.

    Estratégia de layer detection (em ordem de prioridade):
    1. Layers nomeados contendo 'PIL' ou 'PILAR' (TQS: MTH-PIL-*, ES: ES-PIL-*)
    2. Layer '7' (convenção numérica observada em TREINO_1/PAVIMENTO-TIPO)
    3. Scan de TODAS as layers: filtra por bbox compatível com pilar (10-300cm²)

    known_dims: {pid: {'b': float, 'h': float, 'cx': float, 'cy': float}}
                Se fornecido, melhora o match por proximidade + dimensão.

    Retorna {pid: {'cx_geo', 'cy_geo', 'geo_w', 'geo_h', 'angle'}} — somente
    pilares que tiveram match geométrico confirmado.
    """
    try:
        doc = ezdxf_mod.readfile(str(dxf_path))
        msp = doc.modelspace()
    except Exception:
        return {}

    # Candidatos: todas as LWPOLYLINEs que parecem retângulos de pilar
    candidates = []
    for e in msp:
        if e.dxftype() != 'LWPOLYLINE':
            continue
        pts = list(e.get_points())
        rect = _rect_from_lwpoly(pts)
        if rect is None:
            continue
        # Filtrar por tamanho de pilar (b: 10-300cm, h: 10-400cm)
        if not (10 <= rect['geo_w'] <= 300 and 10 <= rect['geo_h'] <= 400):
            continue
        candidates.append(rect)

    if not candidates:
        return {}

    if not known_dims:
        return {}

    # Associar cada pilar ao retângulo mais próximo + dimensionalmente compatível
    result = {}
    for pid, info in known_dims.items():
        b = float(info.get('b') or 0)
        h_val = float(info.get('h') or 0)
        px = float(info.get('cx') or 0)
        py = float(info.get('cy') or 0)
        if b <= 0 or h_val <= 0 or (px == 0 and py == 0):
            continue

        b_lo, b_hi = min(b, h_val) * 0.85, min(b, h_val) * 1.15
        h_lo, h_hi = max(b, h_val) * 0.85, max(b, h_val) * 1.15

        best, best_dist = None, float('inf')
        for c in candidates:
            # Tolerância dimensional ±15%
            if not (b_lo <= c['geo_w'] <= b_hi and h_lo <= c['geo_h'] <= h_hi):
                continue
            d = dist2d(px, py, c['cx'], c['cy'])
            if d < best_dist:
                best, best_dist = c, d

        # Aceitar se centróide geométrico está a menos de 200 unidades DXF
        if best is not None and best_dist < 200:
            result[pid] = {
                'cx_geo': best['cx'], 'cy_geo': best['cy'],
                'geo_w': best['geo_w'], 'geo_h': best['geo_h'],
                'angle': best['angle'],
                'geo_dist_to_label': round(best_dist, 1),
            }

    return result


def _normalize_pilar_id(raw: str) -> str:
    """
    Normaliza ID do pilar: remove sufixo de pavimento TQS.
    P7B  -> P7
    P11A -> P11
    P1   -> P1
    PE1  -> PE1  (especiais: nao normalizar se tem letra entre P e num)
    """
    m = re.match(r'^(P[A-Z]?\d+)[A-Z]?$', raw.strip())
    if m:
        return m.group(1)
    return raw.strip()


def _parse_dim_text(txt: str):
    """
    Parseia texto de dimensao estrutural.
    Retorna (b_cm, h_cm) ou None.
    Formatos aceitos: '20/60', '19x50', '19X50', '60/24'
    Range valido: 10-300 cm cada valor.
    """
    m = re.match(r'^(\d+)[/xX](\d+)$', txt.strip())
    if not m:
        return None
    v1, v2 = int(m.group(1)), int(m.group(2))
    if not (10 <= v1 <= 300 and 10 <= v2 <= 300):
        return None
    return (min(v1, v2), max(v1, v2))  # b=menor, h=maior


def extract_from_dxf(dxf_path: Path, ezdxf_mod) -> tuple[list, list]:
    """
    Extrai nomes de pilar e textos de dimensao de um DXF estrutural.

    Returns:
        names: [{'id': 'P7', 'x': float, 'y': float, 'raw': 'P7B'}, ...]
        dims:  [{'b': int, 'h': int, 'x': float, 'y': float, 'raw': '20/60'}, ...]
    """
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

        # Verificar se e nome de pilar: P<num>[letras opcionais]
        if re.match(r'^P[A-Z]?\d+[A-Z]*$', txt):
            pid = _normalize_pilar_id(txt)
            if pid:
                names.append({'id': pid, 'raw': txt, 'x': x, 'y': y})
            continue

        # Verificar se e texto de dimensao b/h ou bxh
        parsed = _parse_dim_text(txt)
        if parsed:
            b, h = parsed
            dims.append({'b': b, 'h': h, 'raw': txt, 'x': x, 'y': y})

    return names, dims


def match_names_to_dims(names: list, dims: list) -> list:
    """
    Para cada pilar, encontra a dimensao mais proxima.

    Returns:
        [{'id': 'P7', 'b': 20, 'h': 60, 'dist': 194.2, 'raw_dim': '20/60'}, ...]
    """
    if not names or not dims:
        return []

    results = []
    for p in names:
        best = min(dims, key=lambda d: dist2d(p['x'], p['y'], d['x'], d['y']))
        d = dist2d(p['x'], p['y'], best['x'], best['y'])
        results.append({
            'id': p['id'],
            'raw_id': p['raw'],
            'b': best['b'],
            'h': best['h'],
            'dist': round(d, 1),
            'raw_dim': best['raw'],
        })

    return results


def confidence_from_dist(d: float) -> float:
    """Confidence baseada na distancia pilar-dimensao."""
    if d < 50:
        return 0.95   # dimensao colada no nome (ES-PILAR-NOME style)
    elif d < 200:
        return 0.90   # proximidade boa
    elif d < 500:
        return 0.80   # razoavel
    elif d < 1200:
        return 0.70
    else:
        return 0.55


def _select_structural_dxfs(struct_dir: Path, pavimento: str | None) -> list:
    """
    Seleciona DXFs estruturais mais relevantes para o pavimento alvo.

    Se pavimento especificado, prefere DXFs cujo nome contem keywords do pavimento.
    Keywords derivadas: "TIPO" -> ["TIPO", "PADRAO", "STANDARD"]
                        "12 PAV" -> ["12", "PAV", "TIPO"]
                        "SUBSOLO" -> ["SUB", "SUBSOLO", "B1"]
    Fallback: todos os DXFs.
    """
    all_dxfs = sorted(struct_dir.glob("*.dxf")) + sorted(struct_dir.glob("*.DXF"))
    # Dedup (Windows case-insensitive)
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

    # Derivar keywords a partir do pavimento
    keywords = set()
    # Numeros no pavimento (ex: "12 PAV" -> "12")
    nums = re.findall(r'\d+', pav_upper)
    keywords.update(nums)
    # Palavras-chave estruturais
    for kw in ['TIPO', 'PADRAO', 'PAV', 'TERREO', 'COBERTURA', 'SUBSOLO', 'SUB', 'FUNDA']:
        if kw in pav_upper:
            keywords.add(kw)
    # TIPO como fallback universal (representa o pavimento padrao)
    if 'PAV' in pav_upper or any(c.isdigit() for c in pav_upper):
        keywords.add('TIPO')

    # Filtrar DXFs que contem alguma keyword
    matched = [f for f in all_dxfs
               if any(kw in f.name.upper() for kw in keywords)]

    if matched:
        print(f"[INFO] Pavimento '{pavimento}': {len(matched)} DXF(s) selecionado(s) "
              f"(keywords: {keywords})")
        return matched

    # Sem match: usar todos
    print(f"[INFO] Pavimento '{pavimento}': sem DXF especifico — usando todos ({len(all_dxfs)})")
    return all_dxfs


def run(obra_path: str, pavimento: str = None) -> None:
    ezdxf = _load_ezdxf()
    obra = Path(obra_path)

    # Fonte: desenhos estruturais (arquitetura B correta)
    struct_dir = obra / "Fase-2_Triagem" / "Estruturais_Pavimentos_Limpos"
    out_dir = obra / "Fase-3_Interpretacao_Extracao" / "Pilares"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not struct_dir.exists():
        print(f"[ERROR] Diretorio estrutural nao encontrado: {struct_dir}")
        sys.exit(1)

    dxf_files = _select_structural_dxfs(struct_dir, pavimento)
    if not dxf_files:
        print(f"[ERROR] Nenhum DXF encontrado em {struct_dir}")
        sys.exit(1)

    print(f"[INFO] === extrair_bh_pilares.py | {obra.name} ===")
    print(f"[INFO] Fonte: {struct_dir}")
    print(f"[INFO] DXFs selecionados: {len(dxf_files)}")

    # Acumular resultados de todos os DXFs com frequencia de cada (b,h)
    # {pid: {(b,h): {'count': int, 'dist_sum': float, 'sources': [str]}}}
    freq_table: dict[str, dict] = {}
    # Posições de labels por pilar (para centróide cx/cy — usado em B2/LV-B3)
    positions_table: dict[str, list] = {}

    for dxf_path in dxf_files:
        print(f"\n[INFO] Processando: {dxf_path.name}")
        names, dims = extract_from_dxf(dxf_path, ezdxf)
        print(f"  Nomes encontrados: {len(names)}  |  Dims encontradas: {len(dims)}")

        if not names:
            print(f"  [SKIP] Sem nomes de pilar neste DXF")
            continue

        # Coletar posições de labels (para cx/cy) independentemente dos dims
        for n in names:
            pid = n['id']
            positions_table.setdefault(pid, []).append([n['x'], n['y']])

        if not dims:
            print(f"  [SKIP] Sem textos de dimensao neste DXF")
            continue

        matches = match_names_to_dims(names, dims)
        print(f"  Matches: {len(matches)}")

        for m in matches:
            pid = m['id']
            bh_key = (float(m['b']), float(m['h']))
            if pid not in freq_table:
                freq_table[pid] = {}
            if bh_key not in freq_table[pid]:
                freq_table[pid][bh_key] = {'count': 0, 'dist_sum': 0.0, 'sources': []}
            freq_table[pid][bh_key]['count'] += 1
            freq_table[pid][bh_key]['dist_sum'] += m['dist']
            freq_table[pid][bh_key]['sources'].append(dxf_path.stem)

    if not freq_table:
        print("\n[ERROR] Nenhum pilar extraido de nenhum DXF estrutural")
        sys.exit(1)

    # Agregar por FREQUENCIA: para cada pilar, escolher (b,h) mais frequente
    # Desempate: menor distancia media (match mais proximo)
    aggregated: dict[str, dict] = {}
    for pid, bh_map in freq_table.items():
        best_bh = max(bh_map.items(),
                      key=lambda kv: (kv[1]['count'], -kv[1]['dist_sum'] / kv[1]['count']))
        bh_key, stats = best_bh
        b, h = bh_key
        avg_dist = stats['dist_sum'] / stats['count']
        conf = confidence_from_dist(avg_dist)
        sources = list(dict.fromkeys(stats['sources']))  # unique, preserving order
        aggregated[pid] = {
            'b':          b,
            'h':          h,
            'confidence': conf,
            'source':     f"structural-freq({stats['count']}x):{sources[0]}",
            'dist_d1':    round(avg_dist, 1),
            'dist_d2':    round(avg_dist, 1),
            'freq':       stats['count'],
        }

    print(f"\n[INFO] Pilares unicos: {len(aggregated)}")

    # Montar resultado final
    result: dict = {}
    pilares_ordenados = sorted(aggregated.keys(), key=lambda x: (len(x), x))
    extraidos = 0
    parciais = 0

    # Calcular centróides cx/cy por pilar (média das posições dos labels)
    centroids: dict[str, tuple] = {}
    for pid, pts in positions_table.items():
        cx = round(sum(p[0] for p in pts) / len(pts), 2)
        cy = round(sum(p[1] for p in pts) / len(pts), 2)
        centroids[pid] = (cx, cy)

    # Sprint 2: Extrair geometria precisa (LWPOLYLINE bbox + ângulo) por DXF
    # known_dims: usa dados já aggregated + centroids calculados acima
    known_for_geo = {
        pid: {'b': aggregated[pid]['b'], 'h': aggregated[pid]['h'],
              'cx': centroids.get(pid, (0, 0))[0],
              'cy': centroids.get(pid, (0, 0))[1]}
        for pid in aggregated
    }
    geo_data: dict[str, dict] = {}
    for dxf_path in dxf_files:
        geo = extract_pilar_geometry(dxf_path, ezdxf, known_for_geo)
        for pid, ginfo in geo.items():
            if pid not in geo_data:  # primeiro match wins (maior confiança DXF)
                geo_data[pid] = ginfo
    n_geo = len(geo_data)
    print(f"\n[Sprint2] Geometria LWPOLYLINE: {n_geo}/{len(aggregated)} pilares com bbox preciso")

    for pid in pilares_ordenados:
        data = aggregated[pid]
        b, h = data['b'], data['h']
        cx, cy = centroids.get(pid, (None, None))

        geo = geo_data.get(pid, {})
        if b > 0 and h > 0:
            result[pid] = {
                'b':          b,
                'h':          h,
                'confidence': round(data['confidence'], 2),
                'source':     data['source'],
                'dist_d1':    data['dist_d1'],
                'dist_d2':    data['dist_d2'],
                'cx':         cx,
                'cy':         cy,
                # Sprint 2: geometria precisa (None se LWPOLYLINE não encontrada)
                'cx_geo':     geo.get('cx_geo'),
                'cy_geo':     geo.get('cy_geo'),
                'angle':      geo.get('angle'),
                'geo_w':      geo.get('geo_w'),
                'geo_h':      geo.get('geo_h'),
            }
            extraidos += 1
        else:
            result[pid] = {
                'b':          None,
                'h':          h if h > 0 else None,
                'confidence': 0.0,
                'source':     data['source'],
                'cx':         cx,
                'cy':         cy,
                'cx_geo':     geo.get('cx_geo'),
                'cy_geo':     geo.get('cy_geo'),
                'angle':      geo.get('angle'),
                'geo_w':      geo.get('geo_w'),
                'geo_h':      geo.get('geo_h'),
            }
            parciais += 1

    total = len(result)
    cobertura = (extraidos / total * 100) if total > 0 else 0

    result["_meta"] = {
        "total":                   total,
        "extraidos_bh_completo":   extraidos,
        "extraidos_parcial":       parciais,
        "sem_dados":               0,
        "cobertura_pct":           round(cobertura, 1),
        "obra":                    obra.name,
        "pavimento":               pavimento or "todos",
        "extraido_em":             datetime.now().strftime("%Y-%m-%d"),
        "algoritmo":               "structural-text-proximity",
        "fonte":                   str(struct_dir),
        "dxfs_processados":        len(dxf_files),
    }

    out_path = out_dir / "pilares_bh.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f"\n[RESULTADO] Extracao B/H de Pilares (Estrutural)")
    print(f"  Total pilares:      {total}")
    print(f"  B+H completos:      {extraidos} ({cobertura:.1f}%)")
    print(f"  Apenas parcial:     {parciais}")
    print(f"\n[INFO] Salvo em: {out_path}")

    # Amostra
    print(f"\n[AMOSTRA] Primeiros pilares extraidos:")
    count = 0
    for pid in pilares_ordenados[:10]:
        r = result.get(pid, {})
        if r.get("b") is not None:
            print(f"  {pid}: B={r['b']}cm, H={r['h']}cm, conf={r['confidence']:.0%}, "
                  f"dist={r.get('dist_d1', 0):.0f}, src={r['source']}")
            count += 1
            if count >= 8:
                break


def main():
    parser = argparse.ArgumentParser(
        description='Extrai dimensoes B/H de pilares dos DXFs estruturais (Fase-2)'
    )
    parser.add_argument('--obra', required=True,
                        help='Path para o diretorio da obra')
    parser.add_argument('--pavimento', default=None,
                        help='Pavimento (opcional — processados todos por padrao)')
    args = parser.parse_args()
    run(args.obra, args.pavimento)


if __name__ == '__main__':
    main()
