#!/usr/bin/env python3
"""
integrar_fichas_completas.py — Integra todos os dados extraídos em fichas completas
para cada robô: Robo_Pilares, Robo_Fundos_de_Vigas, Robo_Laterais_de_Vigas, Robo_Lajes.

Fontes:
  - pilares_bh.json       → ficha_pilar (B, H)
  - vigas_dim.json        → ficha_lateral_viga (comprimento, altura_lateral)
  - garfos_evg.json       → ficha_fundo_viga (garfo_count)
  - lajes_data.json       → ficha_laje (area, paineis)

Story: CAD-5.5
Usage: python scripts/integrar_fichas_completas.py --obra PATH --pavimento "12 PAV"
"""
import argparse, json, sys
from pathlib import Path


def load_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def build_fichas_pilares(pilares_bh: dict, pilares_gt: dict) -> dict:
    """Ficha do Robo_Pilares: combina B/H com ground truth."""
    fichas = {}
    all_pids = set(list(pilares_bh.keys()) + list(pilares_gt.keys()))

    for pid in sorted(all_pids, key=lambda x: (len(x), x)):
        bh = pilares_bh.get(pid, {})
        gt = pilares_gt.get(pid, {})

        # B e H da extração direta
        b = bh.get('b') or gt.get('b')
        h = bh.get('h') or gt.get('h')
        altura = gt.get('altura')  # padrão 280cm se não encontrado
        faces = gt.get('faces_encontradas', [])

        fichas[pid] = {
            'id': pid,
            'b_cm': b,
            'h_cm': h,
            'altura_cm': altura if altura else 280.0,  # default pé-direito
            'faces': sorted(faces) if faces else ['A', 'B', 'C', 'D'],
            'confidence': bh.get('confidence') or gt.get('confidence', 0.0),
            'source_bh': bh.get('source', 'none'),
            'nota': 'B/H via inverse-proximity DXF' if bh.get('b') else 'B/H placeholder',
        }

    return fichas


def build_fichas_laterais(vigas_dim: dict, vigas_gt: dict) -> dict:
    """Ficha do Robo_Laterais_de_Vigas: comprimento + altura lateral."""
    fichas = {}
    all_vids = set(list(vigas_dim.keys()) + list(vigas_gt.keys()))

    for vid in sorted(all_vids, key=lambda x: (len(x), x)):
        dim = vigas_dim.get(vid, {})
        gt = vigas_gt.get(vid, {})

        comprimento = dim.get('comprimento_cm') or gt.get('comprimento')
        altura_lateral = dim.get('altura_lateral_cm') or gt.get('h')
        sides = dim.get('sides') or gt.get('sides_encontrados', ['A', 'B'])

        fichas[vid] = {
            'id': vid,
            'comprimento_cm': comprimento,
            'altura_lateral_cm': altura_lateral,
            'sides': sorted(sides) if sides else ['A', 'B'],
            'confidence': dim.get('confidence') or gt.get('confidence', 0.0),
            'fonte_comprimento': dim.get('comprimento_source', 'none'),
            'nota': 'Extraído do LV DXF via max-COTA proximity' if dim.get('comprimento_cm') else 'Sem dados extraídos',
        }

    return fichas


def build_fichas_fundos(vigas_dim: dict, garfos: dict) -> dict:
    """Ficha do Robo_Fundos_de_Vigas: comprimento + garfos."""
    fichas = {}
    all_vids = set(list(vigas_dim.keys()) + list(garfos.keys()))

    for vid in sorted(all_vids, key=lambda x: (len(x), x)):
        dim = vigas_dim.get(vid, {})
        garf = garfos.get(vid, {})

        comprimento = dim.get('comprimento_cm')
        garfo_count = garf.get('garfo_count', 0)
        garfo_section = garf.get('section', 'tipo')

        fichas[vid] = {
            'id': vid,
            'comprimento_cm': comprimento,
            'garfo_count': garfo_count,
            'garfo_section': garfo_section,
            'tem_garfo': garfo_count > 0,
            'confidence': max(
                dim.get('confidence', 0.0),
                garf.get('confidence', 0.0)
            ),
            'nota': f'Garfo: {garfo_count}x ({garfo_section})' if garfo_count > 0 else 'Sem garfo EVG',
        }

    return fichas


def build_fichas_lajes(lajes_data: dict) -> dict:
    """Ficha do Robo_Lajes: área, painéis, coordenadas."""
    fichas = {}

    for lid, data in sorted(lajes_data.items(), key=lambda x: (len(x[0]), x[0])):
        n_paineis = data.get('n_paineis', 0)
        area_paineis = data.get('area_total_paineis_cm2')
        dims = data.get('dims_paineis_unicas', []) or data.get('dims_paineis', [])
        pos_label = data.get('pos_label')

        # Bounding box estimado a partir de posições dos painéis
        pos_paineis = data.get('pos_paineis', [])
        bbox = None
        if pos_paineis:
            xs = [p[0] for p in pos_paineis]
            ys = [p[1] for p in pos_paineis]
            bbox = {
                'min_x': round(min(xs), 1),
                'max_x': round(max(xs), 1),
                'min_y': round(min(ys), 1),
                'max_y': round(max(ys), 1),
                'span_x': round(max(xs) - min(xs), 1),
                'span_y': round(max(ys) - min(ys), 1),
            }

        fichas[lid] = {
            'id': lid,
            'n_paineis': n_paineis,
            'area_total_paineis_cm2': area_paineis,
            'dims_paineis': dims[:5],  # Top 5 unique panel sizes
            'bbox_dxf': bbox,  # Bounding box em unidades DXF (para referência)
            'pos_label_dxf': [round(x, 1) for x in pos_label] if pos_label else None,
            'source': data.get('source', 'aux00-panels'),
            'confidence': data.get('confidence', 0.5),
            'nota': f'{n_paineis} painéis AUX00 encontrados' if n_paineis > 0 else 'Label only',
        }

    return fichas


def update_vigas_ground_truth(vigas_gt_path: Path, vigas_dim: dict):
    """Atualiza vigas_ground_truth.json com dados extraídos do LV DXF."""
    gt = load_json(vigas_gt_path)
    updated = 0

    for vid, dim in vigas_dim.items():
        if vid in gt:
            if gt[vid].get('comprimento') is None and dim.get('comprimento_cm'):
                gt[vid]['comprimento'] = dim['comprimento_cm']
                gt[vid]['comprimento_source'] = 'lv-dxf-proximity'
                updated += 1
            if gt[vid].get('h') is None and dim.get('altura_lateral_cm'):
                gt[vid]['h'] = dim['altura_lateral_cm']
                gt[vid]['h_source'] = 'lv-dxf-cota-secao'
                updated += 1

    with open(vigas_gt_path, 'w', encoding='utf-8') as f:
        json.dump(gt, f, indent=2, ensure_ascii=False)

    return updated


def main():
    parser = argparse.ArgumentParser(description='Integrar fichas completas de todos os elementos')
    parser.add_argument('--obra', required=True, help='Path da obra')
    parser.add_argument('--pavimento', default='12 PAV')
    parser.add_argument('--output-dir', default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    fase3 = obra_path / 'Fase-3_Interpretacao_Extracao'

    # Carregar fontes
    pilares_bh = load_json(fase3 / 'Pilares' / 'pilares_bh.json')
    pilares_gt = load_json(fase3 / 'Pilares' / 'pilares_ground_truth.json')
    vigas_dim = load_json(fase3 / 'Vigas' / 'vigas_dim.json')
    vigas_gt = load_json(fase3 / 'Vigas' / 'vigas_ground_truth.json')
    garfos = load_json(fase3 / 'Garfos' / 'garfos_evg.json')
    lajes_data = load_json(fase3 / 'Lajes' / 'lajes_data.json')

    print(f"Carregado: {len(pilares_bh)} pilares_bh | {len(vigas_dim)} vigas_dim | "
          f"{len(garfos)} garfos | {len(lajes_data)} lajes")

    # Atualizar vigas_ground_truth com dados LV
    vigas_gt_path = fase3 / 'Vigas' / 'vigas_ground_truth.json'
    n_updated = update_vigas_ground_truth(vigas_gt_path, vigas_dim)
    print(f"vigas_ground_truth.json: {n_updated} campos atualizados")

    # Build fichas
    fichas_pilares = build_fichas_pilares(pilares_bh, pilares_gt)
    fichas_laterais = build_fichas_laterais(vigas_dim, vigas_gt)
    fichas_fundos = build_fichas_fundos(vigas_dim, garfos)
    fichas_lajes = build_fichas_lajes(lajes_data)

    # Output dir
    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        out_dir = fase3 / 'Fichas_Completas'
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save all fichas
    all_fichas = {
        'fichas_pilares': fichas_pilares,
        'fichas_laterais_vigas': fichas_laterais,
        'fichas_fundos_vigas': fichas_fundos,
        'fichas_lajes': fichas_lajes,
        'meta': {
            'pavimento': args.pavimento,
            'n_pilares': len(fichas_pilares),
            'n_vigas_lateral': len(fichas_laterais),
            'n_vigas_fundo': len(fichas_fundos),
            'n_lajes': len(fichas_lajes),
        }
    }

    out_path = out_dir / 'fichas_completas.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_fichas, f, indent=2, ensure_ascii=False)

    # Save individual fichas
    for fname, data in [
        ('ficha_pilares.json', fichas_pilares),
        ('ficha_laterais_vigas.json', fichas_laterais),
        ('ficha_fundos_vigas.json', fichas_fundos),
        ('ficha_lajes.json', fichas_lajes),
    ]:
        with open(out_dir / fname, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # Resumo
    print(f"\n=== FICHAS COMPLETAS ===")
    print(f"  Pilares: {len(fichas_pilares)} (b/h extraídos: {sum(1 for v in fichas_pilares.values() if v['b_cm'])})")
    print(f"  Laterais vigas: {len(fichas_laterais)} (comprimento: {sum(1 for v in fichas_laterais.values() if v['comprimento_cm'])})")
    print(f"  Fundos vigas: {len(fichas_fundos)} (com garfo: {sum(1 for v in fichas_fundos.values() if v['tem_garfo'])})")
    print(f"  Lajes: {len(fichas_lajes)} (com paineis: {sum(1 for v in fichas_lajes.values() if v['n_paineis'] > 0)})")
    print(f"\n  Output: {out_dir}/")

    print(f"\n=== SAMPLE — Pilar P1 ===")
    print(json.dumps(fichas_pilares.get('P1', {}), indent=2, ensure_ascii=False))

    print(f"\n=== SAMPLE — Viga V22 (lateral) ===")
    print(json.dumps(fichas_laterais.get('V22', {}), indent=2, ensure_ascii=False))

    print(f"\n=== SAMPLE — Viga V12 (fundo + garfo) ===")
    print(json.dumps(fichas_fundos.get('V12', {}), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
