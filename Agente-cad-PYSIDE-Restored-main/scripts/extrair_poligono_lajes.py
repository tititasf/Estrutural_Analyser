#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrair_poligono_lajes.py — Extrai coordenadas (poligono) das lajes a partir
dos DXFs ESTRUTURAIS (Fase-2_Triagem/Estruturais_Pavimentos_Limpos/).

Arquitetura B (correta):
  Fonte: desenhos estruturais do projetista (plantas de forma/estrutura)
  NAO usa LJ DXFs de Projetos_Finalizados.

Algoritmo de matching (ordem de prioridade):
  1. PRIMARY   (conf=0.95): label L<n> DENTRO do poligono (ray casting)
  2. SECONDARY (conf=0.80): label dentro do bounding box do poligono
  3. TERTIARY  (conf=0.65): centroide mais proximo (dist < 500)
  4. FALLBACK  (conf=0.30): span texts → retangulo sintetico

Saidas:
  - Fase-3_Interpretacao_Extracao/Lajes/lajes_poligono.json
      Campos novos: coordenadas_absolutas (posicao real no DXF),
                    nivel_texto, nivel_cm (anotacao de nivel encontrada dentro do poligono)

CLI:
  python scripts/extrair_poligono_lajes.py --obra PATH/Obra_TREINO_1
  python scripts/extrair_poligono_lajes.py --obra PATH/Obra_TREINO_1 --pavimento "12 PAV"
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


# ── Padrões de nível ─────────────────────────────────────────────────────────

# Matches: "+3,00"  "-0.05"  "+0.00"  "-2,80"
# Exige sinal explícito (+/-) para diferenciar de textos de dimensão/cota
_NIVEL_RE = re.compile(r'^[+-]\d{1,3}[,\.]\d{1,2}$')


def _parse_nivel_cm(txt: str) -> float | None:
    """
    Converte texto de nivel para cm.
    "+3,00" -> 300.0  |  "3.06" -> 306.0  |  "-0.05" -> -5.0
    Assume metros se abs(valor) < 100, cm se >= 100 e < 10000.
    """
    normalized = txt.replace(',', '.').strip()
    try:
        val = float(normalized)
    except ValueError:
        return None
    # metros → cm
    if abs(val) < 100:
        return round(val * 100, 1)
    # ja em cm (ex: 306.0)
    if abs(val) < 10000:
        return round(val, 1)
    return None


# ── Geometria ─────────────────────────────────────────────────────────────────

def _point_in_polygon(px: float, py: float, pts: list) -> bool:
    """Ray casting algorithm. pts = [(x,y), ...]"""
    n = len(pts)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_bbox(px: float, py: float, pts: list) -> bool:
    """Verifica se ponto esta dentro do bounding box do poligono."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs) <= px <= max(xs) and min(ys) <= py <= max(ys)


def _bbox(pts: list) -> tuple:
    """Retorna (min_x, max_x, min_y, max_y)."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), max(xs), min(ys), max(ys)


def normalize_coords(pts: list) -> list:
    """Normaliza coordenadas para origem (0,0)."""
    if not pts:
        return pts
    min_x = min(p[0] for p in pts)
    min_y = min(p[1] for p in pts)
    return [[round(p[0] - min_x, 1), round(p[1] - min_y, 1)] for p in pts]


def rect_coords(comp: float, larg: float) -> list:
    """Gera coordenadas de retangulo."""
    return [[0.0, 0.0], [comp, 0.0], [comp, larg], [0.0, larg], [0.0, 0.0]]


def rect_coords_abs(ox: float, oy: float, comp: float, larg: float) -> list:
    """Gera coordenadas absolutas de retangulo a partir de origem (ox, oy)."""
    return [[ox, oy], [ox + comp, oy], [ox + comp, oy + larg], [ox, oy + larg], [ox, oy]]


# ── Seleção de DXFs ──────────────────────────────────────────────────────────

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

    # 'PAV' sozinho é muito genérico (matches todos os arquivos de pavimento).
    # Só adicionar se NÃO há número específico E 'PAV' está no nome pedido.
    has_specific_number = bool(nums)
    if not has_specific_number:
        for kw in ['TIPO', 'PADRAO', 'PAV', 'TERREO', 'COBERTURA', 'SUBSOLO', 'SUB', 'FUNDA']:
            if kw in pav_upper:
                keywords.add(kw)
    else:
        # Com número específico, só adicionar keywords não-genéricas
        for kw in ['TIPO', 'TERREO', 'COBERTURA', 'SUBSOLO']:
            if kw in pav_upper:
                keywords.add(kw)

    # 'TIPO' como fallback universal para pavimentos numerados (pavimento padrão)
    if 'PAV' in pav_upper or any(c.isdigit() for c in pav_upper):
        keywords.add('TIPO')

    matched = [f for f in all_dxfs
               if any(kw in f.name.upper() for kw in keywords)]
    if matched:
        print(f"[INFO] Pavimento '{pavimento}': {len(matched)} DXF(s) "
              f"(keywords: {keywords})")
        return matched

    print(f"[INFO] Pavimento '{pavimento}': sem DXF especifico — usando todos ({len(all_dxfs)})")
    return all_dxfs


# ── Extração principal ────────────────────────────────────────────────────────

def extract_polygon_data_from_dxf(dxf_path: Path, ezdxf_mod) -> list:
    """
    Extrai nomes de laje, poligonos e niveis de um DXF estrutural.

    Retorna lista de dicts:
      id, coordenadas (rel), coordenadas_absolutas, comprimento, largura,
      confidence, source, nivel_texto, nivel_cm
    """
    try:
        doc = ezdxf_mod.readfile(str(dxf_path))
    except Exception as ex:
        print(f"  [WARN] Nao foi possivel ler {dxf_path.name}: {ex}")
        return []

    msp = doc.modelspace()

    laje_names = []   # [{id, raw, x, y}]
    polylines = []    # [{pts, cx, cy, w, h, area, min_x, max_x, min_y, max_y}]
    nivel_texts = []  # [{txt, nivel_cm, x, y}]  — candidatos de nivel
    span_texts = []   # [{val, x, y}]             — fallback span

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

            # Nome de laje
            if re.match(r'^L\d+[A-Z]*$', txt, re.IGNORECASE):
                lid = _normalize_laje_id(txt)
                laje_names.append({'id': lid, 'raw': txt, 'x': x, 'y': y})
                continue

            # Texto de nivel (ex: "+3,00", "-0.05", "3.06")
            if _NIVEL_RE.match(txt):
                ncm = _parse_nivel_cm(txt)
                if ncm is not None:
                    nivel_texts.append({'txt': txt, 'nivel_cm': ncm, 'x': x, 'y': y})
                    continue

            # Span text (fallback)
            if '/' not in txt and 'x' not in txt.lower():
                m = re.match(r'^(\d+\.?\d*)$', txt)
                if m:
                    val = float(m.group(1))
                    if 50 <= val <= 5000:
                        span_texts.append({'val': val, 'x': x, 'y': y})

        elif etype == 'LWPOLYLINE':
            try:
                pts = [(float(v[0]), float(v[1])) for v in e.get_points()]
                if len(pts) < 3:
                    continue
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                cx = sum(xs) / len(xs)
                cy = sum(ys) / len(ys)
                w = max(xs) - min(xs)
                h = max(ys) - min(ys)
                area = w * h
                if area < 10000:   # min ~1m²
                    continue
                # Fechar poligono se necessario
                if pts[0] != pts[-1]:
                    pts.append(pts[0])
                polylines.append({
                    'pts': pts,
                    'cx': cx, 'cy': cy,
                    'w': round(w, 1), 'h': round(h, 1),
                    'area': round(area, 1),
                    'min_x': min(xs), 'max_x': max(xs),
                    'min_y': min(ys), 'max_y': max(ys),
                })
            except Exception:
                continue

    # ── Classificar polígonos: contar quantas labels cada um contém ──────────
    # Polígonos com muitas labels são outlines gerais do pavimento (não lajes individuais)
    poly_label_count = [0] * len(polylines)
    for laje in laje_names:
        lx, ly = laje['x'], laje['y']
        for idx, poly in enumerate(polylines):
            if _point_in_polygon(lx, ly, poly['pts']):
                poly_label_count[idx] += 1

    # Polígono é candidato a laje individual se contém <= MAX_LABELS_PER_POLY labels
    MAX_LABELS_PER_POLY = 2
    valid_poly_indices = set(
        idx for idx, cnt in enumerate(poly_label_count)
        if cnt <= MAX_LABELS_PER_POLY
    )

    results = []
    used_polys = set()

    for laje in laje_names:
        lid = laje['id']
        lx, ly = laje['x'], laje['y']

        chosen_poly = None
        chosen_conf = 0.0
        chosen_idx = -1

        # ── PRIMARY: label DENTRO do polígono (apenas polys individuais) ─
        for idx, poly in enumerate(polylines):
            if idx in used_polys:
                continue
            if idx not in valid_poly_indices:
                continue  # poly genérico (contém muitas lajes) — ignorar
            if _point_in_polygon(lx, ly, poly['pts']):
                # Se há vários polígonos que contêm o label, prefer menor área
                if chosen_conf < 0.95 or (chosen_conf == 0.95 and poly['area'] < polylines[chosen_idx]['area']):
                    chosen_poly = poly
                    chosen_conf = 0.95
                    chosen_idx = idx

        # ── SECONDARY: label dentro do bounding box (apenas polys individuais) ─
        if chosen_idx == -1:
            for idx, poly in enumerate(polylines):
                if idx in used_polys:
                    continue
                if idx not in valid_poly_indices:
                    continue
                if _point_in_bbox(lx, ly, poly['pts']):
                    if chosen_conf < 0.80 or (chosen_conf == 0.80 and poly['area'] < polylines[chosen_idx]['area']):
                        chosen_poly = poly
                        chosen_conf = 0.80
                        chosen_idx = idx

        # ── TERTIARY: centroide mais próximo (prefer polys individuais) ──
        if chosen_idx == -1:
            best_dist = float('inf')
            # Primeiro tenta apenas polys individuais
            for idx, poly in enumerate(polylines):
                if idx in used_polys:
                    continue
                if idx not in valid_poly_indices:
                    continue
                d = dist2d(lx, ly, poly['cx'], poly['cy'])
                if d < best_dist:
                    best_dist = d
                    chosen_poly = poly
                    chosen_idx = idx
            # Se não encontrou polys individuais, aceita qualquer poly
            if chosen_idx == -1:
                for idx, poly in enumerate(polylines):
                    if idx in used_polys:
                        continue
                    d = dist2d(lx, ly, poly['cx'], poly['cy'])
                    if d < best_dist:
                        best_dist = d
                        chosen_poly = poly
                        chosen_idx = idx
            if chosen_poly and best_dist < 5000:
                chosen_conf = 0.65 if best_dist < 500 else 0.50 if best_dist < 2000 else 0.35
            else:
                chosen_poly = None
                chosen_idx = -1

        # ── Extrair nível dentro do polígono ─────────────────────────────
        nivel_texto = None
        nivel_cm = None

        if chosen_poly:
            used_polys.add(chosen_idx)
            px_min = chosen_poly['min_x']
            px_max = chosen_poly['max_x']
            py_min = chosen_poly['min_y']
            py_max = chosen_poly['max_y']

            # Todos os textos de nivel dentro do bbox desta laje
            candidates = []
            for nt in nivel_texts:
                if px_min <= nt['x'] <= px_max and py_min <= nt['y'] <= py_max:
                    # Verificar se está dentro do polígono (mais preciso)
                    if _point_in_polygon(nt['x'], nt['y'], chosen_poly['pts']):
                        d = dist2d(lx, ly, nt['x'], nt['y'])
                        candidates.append((d, nt))
                    elif _point_in_bbox(nt['x'], nt['y'], chosen_poly['pts']):
                        d = dist2d(lx, ly, nt['x'], nt['y'])
                        candidates.append((d + 1000, nt))  # penalty para bbox-only

            if candidates:
                candidates.sort(key=lambda x: x[0])
                best_nivel = candidates[0][1]
                nivel_texto = best_nivel['txt']
                nivel_cm = best_nivel['nivel_cm']

            comp = max(chosen_poly['w'], chosen_poly['h'])
            larg = min(chosen_poly['w'], chosen_poly['h'])

            if comp >= 50 and larg >= 50:
                coords_abs = [[round(p[0], 1), round(p[1], 1)] for p in chosen_poly['pts']]
                coords_rel = normalize_coords(chosen_poly['pts'])
                results.append({
                    'id': lid,
                    'coordenadas': coords_rel,
                    'coordenadas_absolutas': coords_abs,
                    'comprimento': comp,
                    'largura': larg,
                    'confidence': chosen_conf,
                    'source': f'structural-lwpoly:{dxf_path.stem}',
                    'dist': round(dist2d(lx, ly, chosen_poly['cx'], chosen_poly['cy']), 1),
                    'nivel_texto': nivel_texto,
                    'nivel_cm': nivel_cm,
                })
                continue

        # ── FALLBACK: span texts → retângulo sintético ────────────────────
        nearby_spans = []
        for s in span_texts:
            d = dist2d(lx, ly, s['x'], s['y'])
            if d < 3000:
                nearby_spans.append((d, s['val']))
        nearby_spans.sort()

        if len(nearby_spans) >= 2:
            vals = sorted([v for _, v in nearby_spans[:4]], reverse=True)
            comp = round(vals[0], 1)
            larg = round(vals[1], 1)
            coords_abs = rect_coords_abs(lx, ly, comp, larg)
            results.append({
                'id': lid,
                'coordenadas': rect_coords(comp, larg),
                'coordenadas_absolutas': coords_abs,
                'comprimento': comp,
                'largura': larg,
                'confidence': 0.40,
                'source': f'structural-span:{dxf_path.stem}',
                'nivel_texto': nivel_texto,
                'nivel_cm': nivel_cm,
            })
        elif len(nearby_spans) == 1:
            val = round(nearby_spans[0][1], 1)
            coords_abs = rect_coords_abs(lx, ly, val, val)
            results.append({
                'id': lid,
                'coordenadas': rect_coords(val, val),
                'coordenadas_absolutas': coords_abs,
                'comprimento': val,
                'largura': val,
                'confidence': 0.25,
                'source': f'structural-span-single:{dxf_path.stem}',
                'nivel_texto': nivel_texto,
                'nivel_cm': nivel_cm,
            })
        else:
            # Nenhuma informacao geometrica — placeholder mínimo
            coords_abs = rect_coords_abs(lx, ly, 100.0, 100.0)
            results.append({
                'id': lid,
                'coordenadas': rect_coords(100.0, 100.0),
                'coordenadas_absolutas': coords_abs,
                'comprimento': 100.0,
                'largura': 100.0,
                'confidence': 0.05,
                'source': f'structural-default:{dxf_path.stem}',
                'nivel_texto': None,
                'nivel_cm': None,
            })

    return results


# ── Tabela global de pavimentos ───────────────────────────────────────────────

def _extract_tabela_pavimentos(dxf_path: Path, ezdxf_mod) -> dict:
    """
    Extrai tabela de niveis de pavimentos do DXF.
    Busca pares (label_pav, nivel_texto) proximos no DXF.
    Retorna {nome_pav: nivel_cm}

    Exemplo: {'TIPO': 300.0, 'PAV 1': 300.0, 'PAV 2': 580.0}
    """
    try:
        doc = ezdxf_mod.readfile(str(dxf_path))
    except Exception:
        return {}

    msp = doc.modelspace()
    pav_labels = []   # [{txt, x, y}]
    nivel_values = [] # [{txt, nivel_cm, x, y}]

    _PAV_RE = re.compile(
        r'(PAV(?:IMENTO)?\.?\s*\d*|TIPO|TERREO|COBERTURA|SUBSOLO|ÁTICO|ATICO|FUNDA)',
        re.IGNORECASE
    )

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

        if _PAV_RE.search(txt):
            pav_labels.append({'txt': txt, 'x': x, 'y': y})
            continue

        if _NIVEL_RE.match(txt):
            ncm = _parse_nivel_cm(txt)
            if ncm is not None:
                nivel_values.append({'txt': txt, 'nivel_cm': ncm, 'x': x, 'y': y})

    tabela = {}
    for pav in pav_labels:
        # Encontrar nivel mais proximo do label do pavimento
        if not nivel_values:
            continue
        closest = min(nivel_values, key=lambda n: dist2d(pav['x'], pav['y'], n['x'], n['y']))
        d = dist2d(pav['x'], pav['y'], closest['x'], closest['y'])
        if d < 2000:  # max 20m
            tabela[pav['txt'].strip()] = closest['nivel_cm']

    return tabela


# ── Main run ─────────────────────────────────────────────────────────────────

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

    print(f"[INFO] === extrair_poligono_lajes.py | {obra.name} ===")
    print(f"[INFO] Fonte: {struct_dir}")
    print(f"[INFO] DXFs selecionados: {len(dxf_files)}")

    # Extrair tabela de pavimentos de todos os DXFs
    tabela_pav: dict = {}
    for dxf_path in dxf_files:
        tp = _extract_tabela_pavimentos(dxf_path, ezdxf)
        tabela_pav.update(tp)

    if tabela_pav:
        print(f"[INFO] Tabela pavimentos: {len(tabela_pav)} entradas")

    # {lid: [results from each dxf]}
    all_results: dict[str, list] = {}

    for dxf_path in dxf_files:
        print(f"\n[INFO] Processando: {dxf_path.name}")
        entries = extract_polygon_data_from_dxf(dxf_path, ezdxf)
        print(f"  Lajes encontradas: {len(entries)}")

        for entry in entries:
            lid = entry['id']
            if lid not in all_results:
                all_results[lid] = []
            all_results[lid].append(entry)

    if not all_results:
        print(f"\n[WARN] Nenhuma laje encontrada — output vazio")
        empty = {"_meta": {"total": 0, "tabela_pavimentos": tabela_pav}}
        out_path = out_dir / "lajes_poligono.json"
        out_path.write_text(json.dumps(empty, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"[INFO] Salvo (vazio): {out_path}")
        return

    # Para cada laje, escolher o melhor resultado (maior confiança, menor area em empate)
    result: dict = {}

    def _lsort(x):
        m = re.match(r'^L(\d+)([A-Za-z]?)$', x, re.IGNORECASE)
        return (int(m.group(1)), m.group(2)) if m else (0, x)

    for lid in sorted(all_results.keys(), key=_lsort):
        entries = all_results[lid]
        best = max(entries, key=lambda e: (e['confidence'], -(e.get('comprimento', 9999) * e.get('largura', 9999))))

        # Nivel: usar o do melhor result; se None → procurar em outros candidatos
        nivel_txt = best.get('nivel_texto')
        nivel_cm_val = best.get('nivel_cm')
        if nivel_txt is None:
            for e in entries:
                if e.get('nivel_texto') is not None:
                    nivel_txt = e['nivel_texto']
                    nivel_cm_val = e['nivel_cm']
                    break

        result[lid] = {
            'id': lid,
            'coordenadas': best['coordenadas'],
            'coordenadas_absolutas': best.get('coordenadas_absolutas', best['coordenadas']),
            'comprimento': best['comprimento'],
            'largura': best['largura'],
            'confidence': round(best['confidence'], 2),
            'source': best['source'],
            'nivel_texto': nivel_txt,
            'nivel_cm': nivel_cm_val,
        }

    # Meta
    result['_meta'] = {
        'total': len(result) - 1,
        'tabela_pavimentos': tabela_pav,
        'obra': obra.name,
        'extraido_em': datetime.now().strftime('%Y-%m-%d'),
        'algoritmo': 'point-in-polygon+bbox+centroid',
    }

    out_path = out_dir / "lajes_poligono.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')

    # ── Relatório ─────────────────────────────────────────────────────────
    conf_counts = {'>=0.80': 0, '>=0.50': 0, '<0.50': 0}
    nivel_count = 0
    src_counts = {}

    for k, v in result.items():
        if k == '_meta':
            continue
        c = v['confidence']
        if c >= 0.80:
            conf_counts['>=0.80'] += 1
        elif c >= 0.50:
            conf_counts['>=0.50'] += 1
        else:
            conf_counts['<0.50'] += 1
        if v.get('nivel_cm') is not None:
            nivel_count += 1
        s = v.get('source', '?').split(':')[0]
        src_counts[s] = src_counts.get(s, 0) + 1

    total = len(result) - 1
    print(f"\n=== RESULTADO ===")
    print(f"  Total lajes:        {total}")
    print(f"  Conf >= 0.80:       {conf_counts['>=0.80']}  ({conf_counts['>=0.80']/max(total,1)*100:.0f}%)")
    print(f"  Conf >= 0.50:       {conf_counts['>=0.50']}")
    print(f"  Conf <  0.50:       {conf_counts['<0.50']}")
    print(f"  Com nivel extraido: {nivel_count}")
    for s, c in sorted(src_counts.items()):
        print(f"  [{s}]: {c}")
    print(f"  Output: {out_path}")

    if tabela_pav:
        print(f"\n  Tabela pavimentos ({len(tabela_pav)} entradas):")
        for k, v in list(tabela_pav.items())[:8]:
            print(f"    {k}: {v:+.0f} cm")

    print(f"\n{'Laje':<8} {'Comp':<8} {'Larg':<8} {'Conf':<6} {'Nivel':<12} {'Fonte'}")
    print("-" * 70)
    count = 0
    for lid in sorted(result.keys(), key=_lsort):
        if lid == '_meta':
            continue
        v = result[lid]
        niv = f"{v['nivel_cm']:+.0f}cm" if v.get('nivel_cm') is not None else '—'
        print(f"{lid:<8} {str(v['comprimento']):<8} {str(v['largura']):<8} "
              f"{v['confidence']:<6.2f} {niv:<12} {v['source']}")
        count += 1
        if count >= 20:
            print(f"  ... ({total - 20} mais)")
            break


def main():
    parser = argparse.ArgumentParser(
        description='Extrai poligono das lajes dos DXFs estruturais (Fase-2)'
    )
    parser.add_argument('--obra', required=True, help='Path para o diretorio da obra')
    parser.add_argument('--pavimento', default=None,
                        help='Pavimento alvo (opcional)')
    args = parser.parse_args()
    run(args.obra, args.pavimento)


if __name__ == '__main__':
    main()
