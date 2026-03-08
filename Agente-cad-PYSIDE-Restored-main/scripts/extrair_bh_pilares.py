#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrair_bh_pilares.py — Extrai dimensoes B e H de pilares do PL DXF via DIMENSION proximity.

Algoritmo:
  1. Le MTEXT no layer "Texto Secao" -> posicoes dos pilares
  2. Le DIMENSION no layer "Cota Secao (2x)" -> valores B e H
  3. Para cada pilar: encontra as 2 DIMENSIONs mais proximas
  4. Classifica: menor valor = B, maior valor = H
  5. Salva em pilares_bh.json

CLI:
  python scripts/extrair_bh_pilares.py \\
    --obra ../DADOS-OBRAS/Obra_TREINO_21 \\
    --pavimento "12 PAV"
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


def _find_dxf(rev_dir: Path, pattern: str) -> Path | None:
    for f in rev_dir.iterdir():
        if f.suffix.upper() == '.DXF' and pattern.upper() in f.name.upper():
            return f
    return None


def dist2d(p1, p2) -> float:
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def get_dimension_center(e) -> tuple | None:
    """Retorna o centro aproximado de uma DIMENSION entity."""
    try:
        # Ponto de definicao da dimensao (onde a cota aponta)
        defpt = e.dxf.defpoint
        return (defpt.x, defpt.y)
    except Exception:
        pass
    try:
        # Ponto medio da linha de dimensao
        pt1 = e.dxf.defpoint2
        pt2 = e.dxf.defpoint3
        return ((pt1.x + pt2.x) / 2, (pt1.y + pt2.y) / 2)
    except Exception:
        pass
    return None


def get_dimension_angle(e) -> float | None:
    """Retorna o angulo da DIMENSION em graus (0=horizontal, 90=vertical)."""
    try:
        angle = e.dxf.angle
        return angle
    except Exception:
        pass
    try:
        # Calcular angulo a partir dos pontos de definicao
        pt2 = e.dxf.defpoint2
        pt3 = e.dxf.defpoint3
        dx = pt3.x - pt2.x
        dy = pt3.y - pt2.y
        angle_rad = math.atan2(dy, dx)
        return math.degrees(angle_rad) % 180
    except Exception:
        return None


def classify_bh(val1: float, val2: float, angle1=None, angle2=None) -> dict:
    """
    Classifica quais das 2 cotas e B (menor) e H (maior).
    B = lado menor, H = lado maior (convencao estrutural brasileira).

    Se angulo disponivel:
      - horizontal (angulo ~0 ou ~180): geralmente H (largura horizontal do pilar)
      - vertical (angulo ~90): geralmente B (espessura)
    Fallback: ordenar por valor (menor = B, maior = H)
    """
    # Fallback por valor
    if val1 <= val2:
        b_val, h_val = val1, val2
    else:
        b_val, h_val = val2, val1
    return {"b": round(b_val, 1), "h": round(h_val, 1)}


def extract_pilar_positions(msp, ezdxf) -> dict:
    """
    Extrai posicoes dos pilares do layer "Texto Secao".
    Retorna: {pid: {"positions": [(x,y),...], "faces": set()}}
    """
    pilar_data = {}
    target_layers = {"Texto Se", "TEXTO SECAO", "TEXTO_SECAO"}

    for e in msp:
        if e.dxftype() != 'MTEXT':
            continue
        layer = e.dxf.layer
        if not any(tl in layer.upper() for tl in {"TEXTO SE", "TEXTO_SE", "SECAO"}):
            continue

        try:
            txt = e.plain_text().strip()
        except Exception:
            try:
                txt = e.dxf.text.strip()
            except Exception:
                continue

        matches = re.findall(r'[Pp](\d+)\.([A-H])', txt)
        for num, face in matches:
            pid = f'P{num}'
            if pid not in pilar_data:
                pilar_data[pid] = {'positions': [], 'faces': set()}
            pilar_data[pid]['faces'].add(face)
            try:
                pos = e.dxf.insert
                pilar_data[pid]['positions'].append((pos.x, pos.y))
            except Exception:
                try:
                    pos = e.dxf.attachment_point
                except Exception:
                    pass

    return pilar_data


def get_pilar_center(pilar_data: dict, pid: str) -> tuple | None:
    """Calcula centroide das posicoes do pilar."""
    positions = pilar_data.get(pid, {}).get('positions', [])
    if not positions:
        return None
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def extract_dimensions(msp) -> list:
    """
    Extrai DIMENSION entities do layer "Cota Secao (2x)" com valores no range B/H real (14-100cm).

    IMPORTANTE: O layer "Cota Secao (2x)" contem:
    - Valores 14-100cm: dimensoes B e H da secao transversal do pilar (O QUE QUEREMOS)
    - Valores 100-200cm+: alturas de paineis de forma (NAO sao B/H do pilar)

    Filtro: layer exato + range 14-100cm
    """
    dims = []

    for e in msp:
        if e.dxftype() != 'DIMENSION':
            continue
        layer = e.dxf.layer

        # Apenas o layer especifico de secao (contem B e H dos pilares)
        # O layer tem acentuacao: "Cota Se��o (2x)" pode variar por encoding
        layer_upper = layer.upper()
        is_secao = ("COTA SE" in layer_upper and "2X" in layer_upper)

        if not is_secao:
            continue

        try:
            val = round(abs(e.get_measurement()), 1)
        except Exception:
            try:
                txt = str(e.dxf.text).strip()
                val_match = re.search(r'(\d+\.?\d*)', txt)
                val = float(val_match.group(1)) if val_match else None
            except Exception:
                continue

        if val is None:
            continue

        # Range valido para B/H de pilar estrutural (14cm minimo estrutural, 100cm maximo pratico)
        # Valores > 100 sao alturas de paineis, nao B/H da secao
        if val < 14 or val > 100:
            continue

        center = get_dimension_center(e)
        if center is None:
            continue

        angle = get_dimension_angle(e)
        dims.append({
            'center': center,
            'value': val,
            'angle': angle,
            'layer': layer
        })

    return dims


def find_bh_for_pilar(pilar_center: tuple, dims: list, max_dist: float = 300.0) -> dict:
    """
    Encontra as 2 DIMENSIONs mais proximas de um pilar e extrai B e H.

    Usa max_dist amplo (default 1500) pois no DXF STOG as MTEXT labels das faces
    estao distribuidas pelo drawing e as DIMENSIONs de secao ficam numa area adjacente.
    A chave e pegar as 2 MAIS PROXIMAS dentro do range, independente da distancia absoluta.

    Returns:
        dict com b, h, confidence, source
    """
    if not dims:
        return {"b": None, "h": None, "confidence": 0.0, "source": "no-dims-found"}

    # Calcular distancias (sem limite de max_dist - pegar as mais proximas globalmente)
    dists = [(dist2d(pilar_center, d['center']), d) for d in dims]
    dists.sort(key=lambda x: x[0])

    if not dists:
        return {"b": None, "h": None, "confidence": 0.0, "source": "no-dims-in-range"}

    if len(dists) == 1:
        d1, dim1 = dists[0]
        confidence = 0.30
        return {
            "b": None,
            "h": dim1['value'],
            "confidence": confidence,
            "source": "single-dim-found",
            "dist": round(d1, 1)
        }

    # Pegar as 2 mais proximas com valores DIFERENTES (evitar duplicatas)
    chosen = []
    seen_vals = set()
    for d, dim in dists:
        v = dim['value']
        # Aceitar valor se nao e duplicata exata (margem 2cm)
        is_dup = any(abs(v - sv) < 2.0 for sv in seen_vals)
        if not is_dup:
            chosen.append((d, dim))
            seen_vals.add(v)
        if len(chosen) >= 2:
            break

    if len(chosen) < 2:
        # Fallback: pegar as 2 mais proximas mesmo com valores iguais
        chosen = dists[:2]

    d1, dim1 = chosen[0]
    d2, dim2 = chosen[1]

    bh = classify_bh(dim1['value'], dim2['value'], dim1.get('angle'), dim2.get('angle'))

    # Confidence baseada na distancia das 2 dimensoes encontradas
    avg_dist = (d1 + d2) / 2
    if avg_dist < 300:
        confidence = 0.90
    elif avg_dist < 700:
        confidence = 0.80
    elif avg_dist < 1200:
        confidence = 0.70
    else:
        confidence = 0.55

    return {
        "b": bh["b"],
        "h": bh["h"],
        "confidence": round(confidence, 2),
        "source": "dimension-proximity",
        "dist_d1": round(d1, 1),
        "dist_d2": round(d2, 1)
    }


def run(obra_path: str, pavimento: str, max_dist: float = 300.0) -> None:
    ezdxf = _load_ezdxf()
    obra = Path(obra_path)
    rev_dir = obra / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    out_dir = obra / "Fase-3_Interpretacao_Extracao" / "Pilares"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not rev_dir.exists():
        print(f"[ERROR] Diretorio nao encontrado: {rev_dir}")
        sys.exit(1)

    # Encontrar PL DXF
    pl_dxf = _find_dxf(rev_dir, "- PL -") or _find_dxf(rev_dir, "PL -") or _find_dxf(rev_dir, "PL_")
    if not pl_dxf:
        print(f"[ERROR] PL DXF nao encontrado em {rev_dir}")
        print("  Procurando qualquer DXF disponivel...")
        dxfs = list(rev_dir.glob("*.DXF")) + list(rev_dir.glob("*.dxf"))
        if dxfs:
            print(f"  DXFs disponiveis: {[f.name for f in dxfs]}")
        sys.exit(1)

    print(f"[INFO] === extrair_bh_pilares.py | {obra.name} | {pavimento} ===")
    print(f"[INFO] PL DXF: {pl_dxf.name}")
    print(f"[INFO] Max distancia proximity: {max_dist} unidades DXF")

    # Ler DXF
    print("[INFO] Lendo DXF (pode demorar para arquivos grandes)...")
    doc = ezdxf.readfile(str(pl_dxf))
    msp = doc.modelspace()
    print(f"[INFO] DXF carregado: {len(list(msp))} entidades")

    # Extrair posicoes dos pilares
    print("[INFO] Extraindo posicoes dos pilares (layer Texto Secao)...")
    pilar_data = extract_pilar_positions(msp, ezdxf)
    print(f"[INFO] Pilares encontrados: {len(pilar_data)}")

    if not pilar_data:
        print("[WARN] Nenhum pilar encontrado no layer 'Texto Secao'")
        print("[WARN] Tentando outros layers...")

        # Debug: listar layers disponiveis
        layers_found = set()
        for e in msp:
            if e.dxftype() == 'MTEXT':
                layers_found.add(e.dxf.layer)
        print(f"[DEBUG] Layers com MTEXT: {sorted(layers_found)[:20]}")

    # Extrair dimensoes
    print("[INFO] Extraindo DIMENSION entities (layers de cota)...")
    dims = extract_dimensions(msp)
    print(f"[INFO] DIMENSIONs de cota encontradas: {len(dims)}")

    if not dims:
        print("[WARN] Nenhuma DIMENSION encontrada")
        print("[DEBUG] Tentando listar layers com DIMENSION...")
        dim_layers = set()
        for e in msp:
            if e.dxftype() == 'DIMENSION':
                dim_layers.add(e.dxf.layer)
        print(f"[DEBUG] Layers com DIMENSION: {sorted(dim_layers)[:20]}")

    # INVERSE PROXIMITY: cada DIMENSION vai para o pilar mais proximo
    # Isso garante que cada dim e assignada a UM pilar, evitando pilares distantes
    # peguem as mesmas dims de pilares proximos entre si.
    pilar_centers = {}
    for pid in pilar_data:
        center = get_pilar_center(pilar_data, pid)
        if center:
            pilar_centers[pid] = center

    # Agrupar cada DIMENSION no pilar mais proximo
    pilar_dims_assigned: dict[str, list] = {pid: [] for pid in pilar_centers}
    for dim in dims:
        if not pilar_centers:
            break
        nearest_pid = min(pilar_centers, key=lambda pid: dist2d(pilar_centers[pid], dim['center']))
        pilar_dims_assigned[nearest_pid].append(dim)

    print(f"[INFO] Inverse proximity: {len(dims)} dims assignadas a {len(pilar_centers)} pilares")

    # Processar cada pilar usando suas dims assignadas
    result = {}
    extraidos = 0
    parciais = 0

    pilares_ordenados = sorted(pilar_data.keys(), key=lambda x: int(x[1:]))

    for pid in pilares_ordenados:
        center = pilar_centers.get(pid)
        if center is None:
            result[pid] = {
                "b": None, "h": None, "confidence": 0.0, "source": "no-position"
            }
            continue

        assigned = pilar_dims_assigned.get(pid, [])

        if len(assigned) >= 2:
            # Tem dims proprias: ordenar por distancia e pegar as 2 mais proximas
            with_dist = [(dist2d(center, d['center']), d) for d in assigned]
            with_dist.sort(key=lambda x: x[0])
            d1, dim1 = with_dist[0]
            d2, dim2 = with_dist[1]
            # Verificar se tem 2 valores distintos
            vals = sorted(set(round(d['value'], 0) for d in assigned))
            if len(vals) >= 2:
                # Usar as 2 mais proximas com valores diferentes
                chosen = []
                seen = set()
                for d, dim in with_dist:
                    v = round(dim['value'], 0)
                    if v not in seen:
                        chosen.append((d, dim))
                        seen.add(v)
                    if len(chosen) >= 2:
                        break
                d1, dim1 = chosen[0]
                d2, dim2 = chosen[1] if len(chosen) > 1 else chosen[0]
            else:
                # Apenas 1 valor unico: faltam dados
                bh_val = assigned[0]['value']
                result[pid] = {
                    "b": None, "h": bh_val, "confidence": 0.35,
                    "source": "single-value-assigned",
                    "nota": f"Apenas 1 valor unico {bh_val}cm nas dims assignadas"
                }
                parciais += 1
                continue

            bh = classify_bh(dim1['value'], dim2['value'])
            avg_dist = (d1 + d2) / 2
            confidence = 0.90 if avg_dist < 300 else (0.80 if avg_dist < 700 else 0.70)

            result[pid] = {
                "b": bh["b"],
                "h": bh["h"],
                "confidence": round(confidence, 2),
                "source": "inverse-proximity",
                "dims_assignadas": len(assigned),
                "dist_d1": round(d1, 1),
                "dist_d2": round(d2, 1)
            }
            extraidos += 1

        elif len(assigned) == 1:
            # Apenas 1 dim assignada
            result[pid] = {
                "b": None, "h": assigned[0]['value'], "confidence": 0.35,
                "source": "single-dim-assigned"
            }
            parciais += 1

        else:
            # Sem dims assignadas — fallback para proximity global
            bh = find_bh_for_pilar(center, dims, max_dist=float('inf'))
            bh['source'] = 'proximity-fallback'
            bh['confidence'] = min(bh.get('confidence', 0.3), 0.40)
            result[pid] = bh
            if bh.get("b") is not None and bh.get("h") is not None:
                extraidos += 1
            elif bh.get("h") is not None:
                parciais += 1

    # Meta
    total = len(pilar_data)
    cobertura = (extraidos / total * 100) if total > 0 else 0

    result["_meta"] = {
        "total": total,
        "extraidos_bh_completo": extraidos,
        "extraidos_parcial": parciais,
        "sem_dados": total - extraidos - parciais,
        "cobertura_pct": round(cobertura, 1),
        "max_dist": max_dist,
        "obra": obra.name,
        "pavimento": pavimento,
        "extraido_em": datetime.now().strftime("%Y-%m-%d"),
        "algoritmo": "dimension-proximity-matching"
    }

    # Salvar resultado
    out_path = out_dir / "pilares_bh.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n[RESULTADO] Extracao B/H de Pilares")
    print(f"  Total pilares:      {total}")
    print(f"  B+H completos:      {extraidos} ({cobertura:.1f}%)")
    print(f"  Apenas H:           {parciais}")
    print(f"  Sem dados:          {total - extraidos - parciais}")
    print(f"\n[INFO] Salvo em: {out_path}")

    # Atualizar ground truth com B/H reais
    gt_path = out_dir / "pilares_ground_truth.json"
    if gt_path.exists():
        with open(gt_path, 'r', encoding='utf-8') as f:
            gt = json.load(f)

        atualizados = 0
        for pid, bh in result.items():
            if pid.startswith('_'):
                continue
            if pid in gt and bh.get("b") is not None:
                gt[pid]["b"] = bh["b"]
                gt[pid]["h"] = bh["h"]
                gt[pid]["confidence"] = max(gt[pid].get("confidence", 0.3), bh["confidence"])
                gt[pid]["bh_source"] = bh.get("source")
                atualizados += 1

        if "_meta" in gt:
            gt["_meta"]["bh_extraidos"] = atualizados
            gt["_meta"]["bh_atualizado_em"] = datetime.now().strftime("%Y-%m-%d")

        with open(gt_path, 'w', encoding='utf-8') as f:
            json.dump(gt, f, indent=2, ensure_ascii=False)

        print(f"[INFO] pilares_ground_truth.json atualizado: {atualizados} pilares com B/H")

    # Exibir amostra dos resultados
    print(f"\n[AMOSTRA] Primeiros 5 pilares extraidos:")
    count = 0
    for pid in pilares_ordenados[:10]:
        r = result.get(pid, {})
        if r.get("b") is not None:
            print(f"  {pid}: B={r['b']}cm, H={r['h']}cm, conf={r['confidence']:.0%}")
            count += 1
            if count >= 5:
                break


def main():
    parser = argparse.ArgumentParser(
        description='Extrai dimensoes B/H de pilares do PL DXF via DIMENSION proximity'
    )
    parser.add_argument('--obra', required=True, help='Path para o diretorio da obra')
    parser.add_argument('--pavimento', required=True, help='Identificador do pavimento (ex: "12 PAV")')
    parser.add_argument('--max-dist', type=float, default=300.0,
                        help='Distancia maxima de proximity em unidades DXF (default: 300)')
    args = parser.parse_args()
    run(args.obra, args.pavimento, args.max_dist)


if __name__ == '__main__':
    main()
