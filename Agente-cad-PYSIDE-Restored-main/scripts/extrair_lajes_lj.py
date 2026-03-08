#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrair_lajes_lj.py — Extrai coordenadas, dimensoes e area de lajes do LJ DXF.

Estrategia 1 (alta precisao): Layer "AUX00" tem codigos como "L11^J94X244"
  - L11 = laje 11
  - J = tipo (J=joist, A=aligeirada, etc)
  - 94 = dimensao 1 em cm
  - 244 = dimensao 2 em cm
  -> area_cm2 = 94 * 244 = 22.936 cm2

Estrategia 2 (media precisao): LWPOLYLINE/LINE entities proximas ao label L{n}
  -> extrair bounding box do poligono da laje

CLI:
  python scripts/extrair_lajes_lj.py \\
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


def parse_aux00_code(txt: str) -> dict | None:
    """
    Parseia codigo AUX00 no formato "L{n}^J{dim1}X{dim2}" ou "L{n}^{tipo}{dim1}X{dim2}".

    Exemplos reais encontrados:
    - "L11^J94X244" -> laje L11, tipo J, dim1=94, dim2=244
    - "L5^A60X150" -> laje L5, tipo A, dim1=60, dim2=150

    Retorna None se nao for um codigo de laje valido.
    """
    # Padrao principal: L{n}^{tipo}{dim1}X{dim2}
    m = re.match(r'L(\d+)\^([A-Za-z])(\d+)X(\d+)', txt.strip(), re.IGNORECASE)
    if m:
        lid = f'L{m.group(1)}'
        tipo = m.group(2).upper()
        dim1 = float(m.group(3))
        dim2 = float(m.group(4))
        return {
            'id': lid,
            'tipo': tipo,
            'dim1': dim1,
            'dim2': dim2,
            'area_cm2': round(dim1 * dim2, 1)
        }

    # Padrao alternativo: L{n} separado do codigo de dimensao
    # Ex: texto "L11" com texto proximo "94X244"
    m2 = re.match(r'L(\d+)$', txt.strip(), re.IGNORECASE)
    if m2:
        return {'id': f'L{m2.group(1)}', 'tipo': None, 'dim1': None, 'dim2': None, 'area_cm2': None}

    # Padrao de dimensao isolado: "94X244"
    m3 = re.match(r'^(\d+)X(\d+)$', txt.strip(), re.IGNORECASE)
    if m3:
        return {
            'id': None,  # sera associado por proximidade
            'tipo': None,
            'dim1': float(m3.group(1)),
            'dim2': float(m3.group(2)),
            'area_cm2': round(float(m3.group(1)) * float(m3.group(2)), 1)
        }

    return None


def dist2d(p1, p2) -> float:
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def extract_laje_labels_with_dims(msp) -> dict:
    """
    Extrai labels de lajes do LJ DXF.

    Formato real descoberto no DXF:
    - Layer "4" (TEXT): labels simples "L{n}" com posicao no plano
    - Layer "AUX00" (TEXT/MTEXT): entradas multiline formato:
        "L{n}\\n{dim1}X{dim2}\\n[notas]"
      Onde dim1 e dim2 sao dimensoes de UM PAINEL individual de forma (chapa).
      A mesma laje tem MULTIPLOS paineis (multiplas entradas AUX00).

    Estrategia:
    1. Coletar labels simples L{n} do layer "4" -> posicoes dos labels no plano
    2. Coletar todos os paineis AUX00 por laje -> agregar posicoes e dimensoes
    3. Para cada laje: calcular bounding box dos paineis como area aproximada
    """
    # Labels simples (layer "4")
    labels_pos = {}  # lid -> lista de posicoes
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        layer = e.dxf.layer
        if layer not in ('4', '3', '2'):  # layers com labels de laje
            continue
        try:
            if e.dxftype() == 'MTEXT':
                txt = e.plain_text().strip()
            else:
                txt = e.dxf.text.strip()
        except Exception:
            continue

        m = re.match(r'^L(\d+)$', txt, re.IGNORECASE)
        if m:
            lid = f'L{m.group(1)}'
            try:
                pos = (e.dxf.insert.x, e.dxf.insert.y)
            except Exception:
                continue
            if lid not in labels_pos:
                labels_pos[lid] = []
            labels_pos[lid].append(pos)

    # Paineis AUX00 (formato multiline L{n}\n{dim1}X{dim2})
    paineis_por_laje = {}  # lid -> lista de {dim1, dim2, area, pos}
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        layer = e.dxf.layer
        if 'AUX' not in layer.upper() and layer not in ('AUX00',):
            continue
        try:
            if e.dxftype() == 'MTEXT':
                raw = e.plain_text()
            else:
                raw = e.dxf.text
            # Normalizar line breaks do DXF (pode ser \n, \r\n, ou \\P em MTEXT)
            txt = raw.replace('\\P', '\n').replace('\r\n', '\n').strip()
        except Exception:
            continue

        try:
            pos = (e.dxf.insert.x, e.dxf.insert.y)
        except Exception:
            pos = None

        lines = [l.strip() for l in txt.split('\n') if l.strip()]
        if len(lines) < 2:
            continue

        # Primeira linha: L{n}
        m_lid = re.match(r'^L(\d+)$', lines[0], re.IGNORECASE)
        if not m_lid:
            continue
        lid = f'L{m_lid.group(1)}'

        # Segunda linha: {dim1}X{dim2} (ou {dim1}x{dim2})
        m_dim = re.match(r'^(\d+\.?\d*)x(\d+\.?\d*)$', lines[1], re.IGNORECASE)
        if not m_dim:
            continue
        dim1 = float(m_dim.group(1))
        dim2 = float(m_dim.group(2))

        if lid not in paineis_por_laje:
            paineis_por_laje[lid] = []
        paineis_por_laje[lid].append({
            'dim1': dim1,
            'dim2': dim2,
            'area_cm2': round(dim1 * dim2, 1),
            'pos': pos,
            'nota': lines[2] if len(lines) > 2 else None
        })

    # Consolidar: juntar labels_pos + paineis_por_laje
    todas_lajes = set(labels_pos.keys()) | set(paineis_por_laje.keys())
    result = {}

    for lid in sorted(todas_lajes, key=lambda x: int(x[1:])):
        pos_label = labels_pos.get(lid, [None])[0]
        paineis = paineis_por_laje.get(lid, [])

        if paineis:
            # Calcular area total somando paineis
            area_total = round(sum(p['area_cm2'] for p in paineis), 1)
            # Dimensao maxima de painel (maior painel indica escala da laje)
            max_d1 = max(p['dim1'] for p in paineis)
            max_d2 = max(p['dim2'] for p in paineis)
            # Dimensoes unicas encontradas
            dims_unicas = sorted(set(f"{p['dim1']}x{p['dim2']}" for p in paineis))
            # Posicoes dos paineis para bounding box
            pos_paineis = [p['pos'] for p in paineis if p['pos']]

            result[lid] = {
                'id': lid,
                'n_paineis': len(paineis),
                'area_total_paineis_cm2': area_total,
                'maior_painel_dim1': max_d1,
                'maior_painel_dim2': max_d2,
                'dims_paineis_unicas': dims_unicas[:5],  # primeiras 5
                'pos_label': pos_label,
                'pos_paineis': pos_paineis,
                'source': 'aux00-panels'
            }
        elif pos_label:
            result[lid] = {
                'id': lid,
                'n_paineis': 0,
                'area_total_paineis_cm2': None,
                'maior_painel_dim1': None,
                'maior_painel_dim2': None,
                'dims_paineis_unicas': [],
                'pos_label': pos_label,
                'pos_paineis': [],
                'source': 'label-only'
            }

    print(f"[DEBUG] Labels encontrados: {sorted(labels_pos.keys())}")
    print(f"[DEBUG] Lajes com paineis AUX00: {sorted(paineis_por_laje.keys())}")

    return result


def extract_polylines_for_laje(msp, laje_pos: tuple, max_dist: float = 800.0) -> list:
    """
    Extrai LWPOLYLINE/LINE entities proximas ao label da laje.
    Retorna lista de pontos do contorno.
    """
    if laje_pos is None:
        return []

    polylines = []
    for e in msp:
        if e.dxftype() == 'LWPOLYLINE':
            try:
                pts = [(v[0], v[1]) for v in e.get_points()]
                if not pts:
                    continue
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                d = dist2d(laje_pos, (cx, cy))
                if d <= max_dist:
                    polylines.append({
                        'type': 'LWPOLYLINE',
                        'points': pts,
                        'center': (round(cx, 1), round(cy, 1)),
                        'dist': round(d, 1)
                    })
            except Exception:
                continue

    return sorted(polylines, key=lambda x: x['dist'])


def build_fichas(labels_data: dict, msp, pavimento: str) -> dict:
    """
    Constroi fichas de lajes compativel com Robo_Lajes.
    Os dados AUX00 sao PAINEIS (chapas de forma), nao as coordenadas da laje.
    A ficha reflete o que o Robo_Lajes pode usar: area total, dimensoes paineis, contagem.
    """
    fichas = {}

    for lid in sorted(labels_data.keys(), key=lambda x: int(x[1:])):
        info = labels_data[lid]
        pos_label = info.get('pos_label')
        pos_paineis = info.get('pos_paineis', [])
        n_paineis = info.get('n_paineis', 0)
        area_total = info.get('area_total_paineis_cm2')

        # Extrair contorno de LWPOLYLINE proximas ao label
        polylines = []
        ref_pos = pos_label
        if ref_pos is None and pos_paineis:
            # Usar centroide dos paineis como referencia
            xs = [p[0] for p in pos_paineis]
            ys = [p[1] for p in pos_paineis]
            ref_pos = (sum(xs) / len(xs), sum(ys) / len(ys))

        if ref_pos:
            polylines = extract_polylines_for_laje(msp, ref_pos, max_dist=1200.0)

        coordenadas = []
        if polylines:
            best = polylines[0]
            if len(best['points']) >= 3:
                coordenadas = [[round(p[0], 1), round(p[1], 1)] for p in best['points']]

        # Area do poligono (se encontrado)
        area_poligono = None
        if coordenadas and len(coordenadas) >= 3:
            n = len(coordenadas)
            area = 0.0
            for i in range(n):
                j = (i + 1) % n
                area += coordenadas[i][0] * coordenadas[j][1]
                area -= coordenadas[j][0] * coordenadas[i][1]
            area_poligono = round(abs(area) / 2.0, 1)

        # Confidence
        source = info.get('source', 'unknown')
        if source == 'aux00-panels' and n_paineis >= 3:
            confidence = 0.85
        elif source == 'aux00-panels':
            confidence = 0.75
        elif coordenadas:
            confidence = 0.60
        else:
            confidence = 0.30

        fichas[lid] = {
            'n_paineis': n_paineis,
            'area_total_paineis_cm2': area_total,
            'area_poligono_cm2': area_poligono,
            'coordenadas': coordenadas,
            'maior_painel': {
                'dim1': info.get('maior_painel_dim1'),
                'dim2': info.get('maior_painel_dim2'),
            },
            'dims_paineis': info.get('dims_paineis_unicas', []),
            'pos_label': [round(x, 1) for x in pos_label] if pos_label else None,
            'confidence': round(confidence, 2),
            'source': source,
            'nota': f'{n_paineis} paineis AUX00 encontrados' if n_paineis > 0 else 'Sem dados de paineis'
        }

    if fichas:
        fichas['_meta'] = {
            'total': len(fichas),
            'pavimento': pavimento,
            'extraido_em': datetime.now().strftime('%Y-%m-%d'),
            'com_paineis': sum(1 for k, v in fichas.items()
                               if not k.startswith('_') and isinstance(v, dict) and v.get('n_paineis', 0) > 0),
            'com_coordenadas': sum(1 for k, v in fichas.items()
                                   if not k.startswith('_') and isinstance(v, dict) and len(v.get('coordenadas', [])) >= 3),
            'nota': 'AUX00 contem paineis individuais de forma, nao coordenadas estruturais da laje'
        }

    return fichas


def run(obra_path: str, pavimento: str) -> None:
    ezdxf = _load_ezdxf()
    obra = Path(obra_path)
    rev_dir = obra / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    out_dir = obra / "Fase-3_Interpretacao_Extracao" / "Lajes"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not rev_dir.exists():
        print(f"[ERROR] Diretorio nao encontrado: {rev_dir}")
        sys.exit(1)

    lj_dxf = _find_dxf(rev_dir, "- LJ -") or _find_dxf(rev_dir, "LJ -") or _find_dxf(rev_dir, "LJ_")
    if not lj_dxf:
        print(f"[ERROR] LJ DXF nao encontrado em {rev_dir}")
        dxfs = list(rev_dir.glob("*.DXF")) + list(rev_dir.glob("*.dxf"))
        if dxfs:
            print(f"  DXFs disponiveis: {[f.name for f in dxfs]}")
        sys.exit(1)

    print(f"[INFO] === extrair_lajes_lj.py | {obra.name} | {pavimento} ===")
    print(f"[INFO] LJ DXF: {lj_dxf.name}")

    print("[INFO] Lendo DXF...")
    doc = ezdxf.readfile(str(lj_dxf))
    msp = doc.modelspace()
    print(f"[INFO] {len(list(msp))} entidades")

    print("[INFO] Extraindo labels e codigos de lajes...")
    labels_data = extract_laje_labels_with_dims(msp)
    print(f"[INFO] Lajes encontradas: {len(labels_data)}")

    if not labels_data:
        print("[WARN] Nenhuma laje encontrada. Debug layers...")
        layers_text = set()
        for e in msp:
            if e.dxftype() in ('TEXT', 'MTEXT'):
                try:
                    txt = e.plain_text() if e.dxftype() == 'MTEXT' else e.dxf.text
                    if re.search(r'L\d+', txt):
                        layers_text.add(e.dxf.layer)
                except Exception:
                    pass
        print(f"  Layers com L{{n}} labels: {sorted(layers_text)}")
        return

    print("[INFO] Construindo fichas com coordenadas...")
    fichas = build_fichas(labels_data, msp, pavimento)

    # Salvar
    out_path = out_dir / "lajes_data.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(fichas, f, indent=2, ensure_ascii=False)

    meta = fichas.get('_meta', {})
    print(f"\n[RESULTADO] Extracao de Lajes")
    print(f"  Total lajes:        {meta.get('total', 0)}")
    print(f"  Com dimensoes:      {meta.get('com_dimensoes', 0)}")
    print(f"  Com coordenadas:    {meta.get('com_coordenadas', 0)}")
    print(f"\n[INFO] Salvo em: {out_path}")

    # Atualizar ground truth
    gt_path = out_dir / "lajes_ground_truth.json"
    if gt_path.exists():
        with open(gt_path, 'r', encoding='utf-8') as f:
            gt = json.load(f)

        atualizados = 0
        for lid, data in fichas.items():
            if lid.startswith('_'):
                continue
            if lid in gt and isinstance(data, dict):
                if data.get('comprimento'):
                    gt[lid]['comprimento'] = data['comprimento']
                    gt[lid]['largura'] = data['largura']
                    gt[lid]['area_cm2'] = data['area_cm2']
                    gt[lid]['confidence'] = max(gt[lid].get('confidence', 0.25), data['confidence'])
                    atualizados += 1
                if data.get('coordenadas'):
                    gt[lid]['coordenadas'] = data['coordenadas']

        with open(gt_path, 'w', encoding='utf-8') as f:
            json.dump(gt, f, indent=2, ensure_ascii=False)
        print(f"[INFO] lajes_ground_truth.json atualizado: {atualizados} lajes com dimensoes")

    # Amostra
    print(f"\n[AMOSTRA] Primeiras lajes:")
    count = 0
    for lid in sorted([k for k in fichas if not k.startswith('_')], key=lambda x: int(x[1:])):
        v = fichas[lid]
        if not isinstance(v, dict):
            continue
        c = v.get('comprimento')
        l = v.get('largura')
        a = v.get('area_cm2')
        coords = len(v.get('coordenadas', []))
        print(f"  {lid}: {c}x{l}cm | area={a}cm2 | coords={coords}pts | conf={v.get('confidence',0):.0%}")
        count += 1
        if count >= 8:
            break


def main():
    parser = argparse.ArgumentParser(description='Extrai dados de lajes do LJ DXF')
    parser.add_argument('--obra', required=True, help='Path para o diretorio da obra')
    parser.add_argument('--pavimento', required=True, help='Identificador do pavimento')
    args = parser.parse_args()
    run(args.obra, args.pavimento)


if __name__ == '__main__':
    main()
