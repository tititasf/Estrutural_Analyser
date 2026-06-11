#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrair_ancoras_dxf.py — Extrai coordenadas absolutas (ancoras) de cada
elemento (P{n}, V{n}, L{n}) nos DXFs ESTRUTURAIS.

Arquitetura B (correta):
  Fonte: Fase-2_Triagem/Estruturais_Pavimentos_Limpos/
  NAO usa Projetos_Finalizados (STOG output).

Algoritmo:
  1. Varre DXFs em Fase-2_Triagem/Estruturais_Pavimentos_Limpos/
  2. Para cada DXF extrai TEXT/MTEXT com nomes P{n}, V{n}, L{n}
  3. Calcula centroide de cada cluster de labels por elemento
  4. Normaliza IDs (P7B -> P7, V281A -> V281, L11A -> L11)
  5. Agrega resultados de todos os DXFs (centroide global)
  6. Salva em Fase-3_Interpretacao_Extracao/ancoras_{tipo}.json

CLI:
  python scripts/extrair_ancoras_dxf.py --obra PATH/Obra_TREINO_1
  python scripts/extrair_ancoras_dxf.py --obra PATH/Obra_TREINO_1 --pavimento "12 PAV"
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def _load_ezdxf():
    try:
        import ezdxf
        return ezdxf
    except ImportError:
        print("[ERROR] ezdxf nao instalado: pip install ezdxf")
        sys.exit(1)


def _normalize_id(raw: str, prefix: str) -> str:
    """Normaliza ID: P7B -> P7, V281A -> V281, L11A -> L11."""
    pat = rf'^({prefix}[A-Z]?\d+)[A-Z]?$'
    m = re.match(pat, raw.strip())
    if m:
        return m.group(1)
    return raw.strip()


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


def centroid(pts: list) -> list:
    """Calcula centroide de lista de pontos (x, y)."""
    n = len(pts)
    return [round(sum(p[0] for p in pts) / n, 2),
            round(sum(p[1] for p in pts) / n, 2)]


def extract_anchors_from_dxf(dxf_path: Path, ezdxf_mod) -> tuple[dict, dict, dict]:
    """
    Extrai posicoes de todos os labels P{n}, V{n}, L{n} de um DXF estrutural.

    Returns:
        pilares: {pid: [(x,y), ...]}, vigas: {vid: [(x,y), ...]}, lajes: {lid: [(x,y), ...]}
    """
    try:
        doc = ezdxf_mod.readfile(str(dxf_path))
    except Exception as ex:
        print(f"  [WARN] Nao foi possivel ler {dxf_path.name}: {ex}")
        return {}, {}, {}

    msp = doc.modelspace()
    pilares = defaultdict(list)
    vigas = defaultdict(list)
    lajes = defaultdict(list)

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

        # Pilar: P{n}[A-Z]*
        if re.match(r'^P[A-Z]?\d+[A-Z]*$', txt):
            pid = _normalize_id(txt, 'P')
            pilares[pid].append((x, y))
            continue

        # Viga: V{n}[A-Z]* (but not dimension texts like V20/60)
        if re.match(r'^V[A-Z]?\d+[A-Z]*$', txt) and '/' not in txt and 'x' not in txt.lower():
            vid = _normalize_id(txt, 'V')
            vigas[vid].append((x, y))
            continue

        # Laje: L{n}[A-Z]*
        if re.match(r'^L\d+[A-Z]*$', txt, re.IGNORECASE):
            lid = _normalize_id(txt, 'L')
            lajes[lid].append((x, y))

    return dict(pilares), dict(vigas), dict(lajes)


def run(obra_path: str, pavimento: str = None) -> None:
    ezdxf = _load_ezdxf()
    obra = Path(obra_path)

    struct_dir = obra / "Fase-2_Triagem" / "Estruturais_Pavimentos_Limpos"
    fase3 = obra / "Fase-3_Interpretacao_Extracao"
    fase3.mkdir(parents=True, exist_ok=True)

    if not struct_dir.exists():
        print(f"[ERROR] Diretorio estrutural nao encontrado: {struct_dir}")
        sys.exit(1)

    dxf_files = _select_structural_dxfs(struct_dir, pavimento)
    if not dxf_files:
        print(f"[ERROR] Nenhum DXF encontrado em {struct_dir}")
        sys.exit(1)

    print(f"[INFO] === extrair_ancoras_dxf.py | {obra.name} ===")
    print(f"[INFO] Fonte: {struct_dir}")
    print(f"[INFO] DXFs selecionados: {len(dxf_files)}")

    # Aggregate across all DXFs
    all_pilares = defaultdict(list)
    all_vigas = defaultdict(list)
    all_lajes = defaultdict(list)

    for dxf_path in dxf_files:
        print(f"\n[INFO] Processando: {dxf_path.name}")
        pilares, vigas, lajes = extract_anchors_from_dxf(dxf_path, ezdxf)
        print(f"  P: {len(pilares)}  V: {len(vigas)}  L: {len(lajes)}")

        for pid, pts in pilares.items():
            all_pilares[pid].extend(pts)
        for vid, pts in vigas.items():
            all_vigas[vid].extend(pts)
        for lid, pts in lajes.items():
            all_lajes[lid].extend(pts)

    # Compute centroids
    ancoras_pilares = {}
    for pid in sorted(all_pilares.keys(), key=lambda x: (len(x), x)):
        ancoras_pilares[pid] = centroid(all_pilares[pid])

    ancoras_vigas = {}
    for vid in sorted(all_vigas.keys(), key=lambda x: (len(x), x)):
        ancoras_vigas[vid] = centroid(all_vigas[vid])

    ancoras_lajes = {}
    for lid in sorted(all_lajes.keys(), key=lambda x: (len(x), x)):
        ancoras_lajes[lid] = centroid(all_lajes[lid])

    # Save
    out_p = fase3 / "ancoras_pilares.json"
    out_p.write_text(json.dumps(ancoras_pilares, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\n[INFO] Salvo: {out_p} ({len(ancoras_pilares)} pilares)")

    out_v = fase3 / "ancoras_vigas.json"
    out_v.write_text(json.dumps(ancoras_vigas, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"[INFO] Salvo: {out_v} ({len(ancoras_vigas)} vigas)")

    out_l = fase3 / "ancoras_lajes.json"
    out_l.write_text(json.dumps(ancoras_lajes, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"[INFO] Salvo: {out_l} ({len(ancoras_lajes)} lajes)")

    # Summary
    print(f"\n[RESULTADO]")
    print(f"  Pilares: {len(ancoras_pilares)} ancoras")
    print(f"  Vigas:   {len(ancoras_vigas)} ancoras")
    print(f"  Lajes:   {len(ancoras_lajes)} ancoras")

    cobertura_ok = (
        len(ancoras_pilares) >= 5 and
        len(ancoras_vigas) >= 5
    )
    print(f"\n  STATUS: {'OK' if cobertura_ok else 'PARCIAL (cobertura baixa)'}")


def main():
    parser = argparse.ArgumentParser(
        description='Extrai ancoras de elementos dos DXFs estruturais (Fase-2)'
    )
    parser.add_argument('--obra', required=True, help='Path da obra')
    parser.add_argument('--pavimento', default=None,
                        help='Pavimento (opcional)')
    args = parser.parse_args()
    run(args.obra, args.pavimento)


if __name__ == '__main__':
    main()
