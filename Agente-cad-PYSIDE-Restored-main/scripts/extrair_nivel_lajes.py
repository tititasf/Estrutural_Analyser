#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrair_nivel_lajes.py — Extrai mapa granular de nível por laje.

Premissa:
  Cada laje tem seu próprio nível que pode diferir do nível geral do pavimento.
  Desníveis, mezaninos, rampas, coberturas parciais: cada L<n> tem nivel_cm individual.

Fontes (em ordem de prioridade):
  1. INDIVIDUAL: texto +/-N,NN DENTRO do polígono da laje (no DXF estrutural)
  2. TABELA_PAV: nível do pavimento ao qual a laje pertence (tabela geral no DXF)
  3. NENHUM: nivel_cm = None (não foi possível determinar)

Dependências:
  - Fase-3_Interpretacao_Extracao/Lajes/lajes_poligono.json (com coordenadas_absolutas)
  - Fase-2_Triagem/Estruturais_Pavimentos_Limpos/ (DXFs estruturais)

Saída:
  - Fase-3_Interpretacao_Extracao/Lajes/lajes_nivel.json
    Formato: {
      "L1": {"nivel_cm": -3.0, "nivel_texto": "-0.03", "origem": "individual"},
      "L2": {"nivel_cm": 300.0, "nivel_texto": "+3.00", "origem": "tabela_pav"},
      "_meta": {...}
    }

CLI:
  python scripts/extrair_nivel_lajes.py --obra PATH/Obra_TREINO_1
  python scripts/extrair_nivel_lajes.py --obra PATH/Obra_TREINO_1 --pavimento "12 PAV"
"""

import argparse
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path


# ── Padrões de nível ──────────────────────────────────────────────────────────

# Exige sinal explícito: "+3,00"  "-0.05"  "+0.00"  "-2,80"
_NIVEL_STRICT_RE = re.compile(r'^[+-]\d{1,3}[,\.]\d{1,2}$')

# Relaxado: permite sem sinal, para tabela de pavimentos "3.06", "852.49"
_NIVEL_RELAX_RE = re.compile(r'^[+-]?\d{1,4}[,\.]\d{1,3}$')

# Pavimento labels
_PAV_RE = re.compile(
    r'(PAV(?:IMENTO)?\.?\s*\d*|TIPO|TERREO|COBERTURA|SUBSOLO|ÁTICO|ATICO)',
    re.IGNORECASE
)


def _load_ezdxf():
    try:
        import ezdxf
        return ezdxf
    except ImportError:
        print("[ERROR] ezdxf nao instalado: pip install ezdxf")
        sys.exit(1)


def dist2d(ax, ay, bx, by) -> float:
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def _parse_nivel_cm(txt: str) -> float | None:
    """
    Converte texto de nível para cm.
    "+3,00" → 300.0  |  "-0.05" → -5.0  |  "852.49" → 85249.0 (inválido → None)
    Intervalo válido: -5000..+20000 cm (cobertura 200m em prédio alto)
    """
    normalized = txt.replace(',', '.').strip()
    try:
        val = float(normalized)
    except ValueError:
        return None
    # metros → cm: abs(val) < 100  →  ex: +3.00 = 300cm
    if abs(val) < 100:
        cm = round(val * 100, 1)
    # já em cm: 100 ≤ abs(val) < 10000
    elif abs(val) < 10000:
        cm = round(val, 1)
    else:
        return None
    # Filtro de sanidade: -5000cm a +20000cm
    if not (-5000 <= cm <= 20000):
        return None
    return cm


def _point_in_polygon(px: float, py: float, pts: list) -> bool:
    """Ray casting algorithm."""
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
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs) <= px <= max(xs) and min(ys) <= py <= max(ys)


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

    has_specific_number = bool(nums)
    if not has_specific_number:
        for kw in ['TIPO', 'PADRAO', 'PAV', 'TERREO', 'COBERTURA', 'SUBSOLO', 'SUB', 'FUNDA']:
            if kw in pav_upper:
                keywords.add(kw)
    else:
        for kw in ['TIPO', 'TERREO', 'COBERTURA', 'SUBSOLO']:
            if kw in pav_upper:
                keywords.add(kw)

    if 'PAV' in pav_upper or any(c.isdigit() for c in pav_upper):
        keywords.add('TIPO')

    matched = [f for f in all_dxfs if any(kw in f.name.upper() for kw in keywords)]
    if matched:
        return matched
    return all_dxfs


# ── Extração de textos de nível de um DXF ────────────────────────────────────

def _extract_nivel_texts_from_dxf(dxf_path: Path, ezdxf_mod) -> tuple[list, list]:
    """
    Extrai textos de nível de um DXF estrutural.

    Returns:
        nivel_texts:  [{txt, nivel_cm, x, y}]   — textos com sinal explícito (nível individual)
        tabela_pav:   [{pav_label, nivel_cm, x, y}]  — associações pavimento→nível
    """
    try:
        doc = ezdxf_mod.readfile(str(dxf_path))
    except Exception as ex:
        print(f"  [WARN] Nao foi possivel ler {dxf_path.name}: {ex}")
        return [], []

    msp = doc.modelspace()

    nivel_individual = []  # textos com sinal (candidatos de nível individual)
    nivel_relaxado = []    # todos os textos numéricos (para tabela_pav)
    pav_labels = []        # labels de pavimento

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

        # Nível com sinal explícito → candidato de nível individual de laje
        if _NIVEL_STRICT_RE.match(txt):
            ncm = _parse_nivel_cm(txt)
            if ncm is not None:
                nivel_individual.append({'txt': txt, 'nivel_cm': ncm, 'x': x, 'y': y})

        # Nível sem sinal → candidato para tabela de pavimentos
        elif _NIVEL_RELAX_RE.match(txt) and not _NIVEL_STRICT_RE.match(txt):
            ncm = _parse_nivel_cm(txt)
            if ncm is not None:
                nivel_relaxado.append({'txt': txt, 'nivel_cm': ncm, 'x': x, 'y': y})

        # Label de pavimento
        elif _PAV_RE.search(txt):
            pav_labels.append({'txt': txt, 'x': x, 'y': y})

    # Montar tabela pavimento→nível:
    # Para cada label de pavimento, encontrar o nível mais próximo
    all_nivel = nivel_individual + nivel_relaxado
    tabela_pav = []
    for pav in pav_labels:
        if not all_nivel:
            continue
        closest = min(all_nivel, key=lambda n: dist2d(pav['x'], pav['y'], n['x'], n['y']))
        d = dist2d(pav['x'], pav['y'], closest['x'], closest['y'])
        if d < 2000:  # max 20m (em unidades DXF)
            tabela_pav.append({
                'pav': pav['txt'].strip(),
                'nivel_cm': closest['nivel_cm'],
                'nivel_txt': closest['txt'],
                'dist': round(d, 1),
                'x': pav['x'], 'y': pav['y'],
            })

    return nivel_individual, tabela_pav


# ── Associação nível → lajes via polígonos ────────────────────────────────────

def _assign_nivels_to_lajes(
    lajes_poligono: dict,
    nivel_individual: list,
    tabela_pav: list,
) -> dict:
    """
    Associa nível individual para cada laje.

    Algoritmo:
      PRIMARY  (orig="individual"): texto de nível DENTRO do polígono da laje
      SECONDARY (orig="individual_near"): texto de nível no bbox da laje
      TERTIARY  (orig="tabela_pav"): nível do pavimento mais próximo da laje
      NONE: nivel_cm = None

    Returns:
        {lid: {"nivel_cm": float|None, "nivel_texto": str|None, "origem": str}}
    """
    resultado = {}

    # Tabela de pavimentos consolidada: dict {pav_key: nivel_cm}
    # Em caso de duplicata, usar a de menor distância (mais confiável)
    tabela_dict: dict[str, dict] = {}
    for t in tabela_pav:
        k = t['pav']
        if k not in tabela_dict or t['dist'] < tabela_dict[k]['dist']:
            tabela_dict[k] = t

    for lid, data in lajes_poligono.items():
        if lid.startswith('_'):
            continue

        coords_abs = data.get('coordenadas_absolutas')
        coords_rel = data.get('coordenadas', [])
        nivel_cm = None
        nivel_texto = None
        origem = 'nenhum'

        if coords_abs and len(coords_abs) >= 3:
            pts = [(p[0], p[1]) for p in coords_abs]
            min_x = min(p[0] for p in pts)
            max_x = max(p[0] for p in pts)
            min_y = min(p[1] for p in pts)
            max_y = max(p[1] for p in pts)

            # PRIMARY: textos de nível individual DENTRO do polígono
            candidates = []
            for nt in nivel_individual:
                if min_x <= nt['x'] <= max_x and min_y <= nt['y'] <= max_y:
                    in_poly = _point_in_polygon(nt['x'], nt['y'], pts)
                    in_bbox = _point_in_bbox(nt['x'], nt['y'], pts)
                    if in_poly or in_bbox:
                        # Calcular distância ao centro da laje para desempate
                        cx = (min_x + max_x) / 2
                        cy = (min_y + max_y) / 2
                        d = dist2d(nt['x'], nt['y'], cx, cy)
                        penalty = 0 if in_poly else 500  # bbox-only tem penalidade
                        candidates.append((d + penalty, nt, in_poly))

            if candidates:
                candidates.sort(key=lambda x: x[0])
                best_d, best_nt, in_poly = candidates[0]
                nivel_cm = best_nt['nivel_cm']
                nivel_texto = best_nt['txt']
                origem = 'individual' if in_poly else 'individual_near'

        # TERTIARY: tabela de pavimentos
        # Usa o nível do pavimento mais próximo do centroide da laje
        if nivel_cm is None and tabela_dict:
            # Coordenadas do centroide da laje
            if coords_abs and len(coords_abs) >= 3:
                pts = [(p[0], p[1]) for p in coords_abs]
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                # Encontrar entrada de tabela mais próxima
                closest = min(tabela_dict.values(),
                              key=lambda t: dist2d(cx, cy, t['x'], t['y']))
                nivel_cm = closest['nivel_cm']
                nivel_texto = closest['nivel_txt']
                origem = 'tabela_pav'
            elif tabela_dict:
                # Sem coords absolutas: usar primeiro da tabela
                first = next(iter(tabela_dict.values()))
                nivel_cm = first['nivel_cm']
                nivel_texto = first['nivel_txt']
                origem = 'tabela_pav_fallback'

        resultado[lid] = {
            'nivel_cm': nivel_cm,
            'nivel_texto': nivel_texto,
            'origem': origem,
        }

    return resultado


# ── Main run ──────────────────────────────────────────────────────────────────

def run(obra_path: str, pavimento: str = None) -> None:
    ezdxf = _load_ezdxf()
    obra = Path(obra_path)

    struct_dir = obra / "Fase-2_Triagem" / "Estruturais_Pavimentos_Limpos"
    out_dir = obra / "Fase-3_Interpretacao_Extracao" / "Lajes"
    poly_path = out_dir / "lajes_poligono.json"

    print(f"[INFO] === extrair_nivel_lajes.py | {obra.name} ===")

    if not struct_dir.exists():
        print(f"[ERROR] Diretorio estrutural nao encontrado: {struct_dir}")
        sys.exit(1)

    if not poly_path.exists():
        print(f"[ERROR] lajes_poligono.json nao encontrado: {poly_path}")
        print(f"[INFO]  Execute primeiro: python scripts/extrair_poligono_lajes.py --obra {obra_path}")
        sys.exit(1)

    with open(poly_path, encoding='utf-8') as f:
        lajes_poligono = json.load(f)

    n_lajes = sum(1 for k in lajes_poligono if not k.startswith('_'))
    print(f"[INFO] Lajes no poligono: {n_lajes}")

    dxf_files = _select_structural_dxfs(struct_dir, pavimento)
    print(f"[INFO] DXFs selecionados: {len(dxf_files)}")

    # Acumular textos de nível de todos os DXFs
    all_nivel_individual = []
    all_tabela_pav = []

    for dxf_path in dxf_files:
        print(f"\n[INFO] Processando: {dxf_path.name}")
        ind, tabela = _extract_nivel_texts_from_dxf(dxf_path, ezdxf)
        print(f"  Niveis individuais: {len(ind)}  |  Tabela pav: {len(tabela)}")
        all_nivel_individual.extend(ind)
        all_tabela_pav.extend(tabela)

    print(f"\n[INFO] Total nivel individual: {len(all_nivel_individual)}")
    print(f"[INFO] Total tabela pav: {len(all_tabela_pav)}")

    # Associar níveis às lajes
    resultado = _assign_nivels_to_lajes(lajes_poligono, all_nivel_individual, all_tabela_pav)

    # Estatísticas
    n_individual = sum(1 for v in resultado.values() if v['origem'] in ('individual', 'individual_near'))
    n_tabela = sum(1 for v in resultado.values() if 'tabela' in v['origem'])
    n_nenhum = sum(1 for v in resultado.values() if v['origem'] == 'nenhum')
    n_total = len(resultado)

    # Output
    out = {}

    def _lsort(x):
        m = re.match(r'^L(\d+)([A-Za-z]?)$', x, re.IGNORECASE)
        return (int(m.group(1)), m.group(2)) if m else (0, x)

    for lid in sorted(resultado.keys(), key=_lsort):
        out[lid] = resultado[lid]

    out['_meta'] = {
        'total': n_total,
        'individual': n_individual,
        'tabela_pav': n_tabela,
        'sem_nivel': n_nenhum,
        'obra': obra.name,
        'pavimento': pavimento or 'todos',
        'extraido_em': datetime.now().strftime('%Y-%m-%d'),
        'algoritmo': 'point-in-polygon + tabela-pavimentos',
    }

    out_path = out_dir / "lajes_nivel.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f"\n=== RESULTADO ===")
    print(f"  Total lajes:         {n_total}")
    print(f"  Individual:          {n_individual}  ({n_individual/max(n_total,1)*100:.0f}%)")
    print(f"  Tabela pavimento:    {n_tabela}  ({n_tabela/max(n_total,1)*100:.0f}%)")
    print(f"  Sem nivel:           {n_nenhum}")
    print(f"  Output:              {out_path}")

    if all_tabela_pav:
        seen = set()
        print(f"\n  Tabela pavimentos:")
        for t in all_tabela_pav:
            k = t['pav']
            if k not in seen:
                seen.add(k)
                print(f"    {k:40s} {t['nivel_cm']:+.0f} cm")

    print(f"\n{'Laje':<8} {'Nivel':<12} {'Origem'}")
    print("-" * 45)
    count = 0
    for lid in sorted(out.keys(), key=_lsort):
        if lid == '_meta':
            continue
        v = out[lid]
        niv = f"{v['nivel_cm']:+.0f}cm" if v.get('nivel_cm') is not None else '—'
        print(f"{lid:<8} {niv:<12} {v['origem']}")
        count += 1
        if count >= 20:
            print(f"  ... ({n_total - 20} mais)")
            break


def main():
    parser = argparse.ArgumentParser(
        description='Extrai mapa granular de nivel por laje dos DXFs estruturais'
    )
    parser.add_argument('--obra', required=True, help='Path para o diretorio da obra')
    parser.add_argument('--pavimento', default=None,
                        help='Pavimento alvo (opcional)')
    args = parser.parse_args()
    run(args.obra, args.pavimento)


if __name__ == '__main__':
    main()
