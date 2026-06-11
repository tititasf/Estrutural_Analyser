#!/usr/bin/env python3
"""
regen_fase4_panels.py — Regenera panels[] dos JSON individuais de vigas (Fase4)
usando o comprimento enriquecido de vigas.json.

Problema anterior: V*_A.json, V*_B.json e V*_fundo.json tinham panels com largura
= vao estrutural TQS (50-178cm) em vez do comprimento real da forma (200-1009cm).

Fix: recalcular panels com auto_dividir_paineis(comprimento, MAX=244cm) identico
ao motor_fase4.py, preservando todos os outros campos (holes, pillars, sarrafos).

Arquivos atualizados:
  - JSON_Vigas_Laterais/V{n}_A.json
  - JSON_Vigas_Laterais/V{n}_B.json
  - JSON_Vigas_Fundo/V{n}_fundo.json
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json, math, os, glob, re, argparse
from pathlib import Path


MAX_PAINEL_LARGURA = 244.0  # cm — igual ao motor_fase4.py


def auto_dividir_paineis(comprimento: float, max_largura: float = MAX_PAINEL_LARGURA):
    """Divide comprimento em paineis <= max_largura (logica identica ao motor_fase4.py)."""
    if comprimento <= 0:
        return []
    n_paineis = math.ceil(comprimento / max_largura)
    largura_uniforme = round(comprimento / n_paineis, 1)
    return [largura_uniforme] * n_paineis


def make_panels(larguras, height):
    """Cria lista de panels com height1=height2=height."""
    h = float(height) if height else 0.0
    return [
        {"width": w, "height1": h, "height2": h, "grade_h1": "0", "grade_h2": "0"}
        for w in larguras
    ]


def update_json_file(path: Path, new_panels: list, dry_run: bool = False) -> bool:
    """Atualiza panels[] de um JSON individual. Retorna True se alterado."""
    if not path.exists():
        return False
    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    old_panels = data.get('panels', [])
    if not new_panels:
        return False  # nao apagar panels sem motivo

    # Verificar se muda
    old_widths = [p.get('width', 0) for p in old_panels]
    new_widths  = [p.get('width', 0) for p in new_panels]
    if old_widths == new_widths:
        return False  # sem alteracao

    data['panels'] = new_panels

    # Marcar regeneracao no _sa_meta
    if '_sa_meta' in data:
        data['_sa_meta']['panels_regenerated'] = True
        data['_sa_meta']['panels_regen_source'] = 'regen_fase4_panels.py (comprimento enriquecido LV)'

    if not dry_run:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    return True


def main():
    parser = argparse.ArgumentParser(description='Regenera panels[] dos JSON Fase4 com comprimento real da forma')
    parser.add_argument('--vigas-json',
                        default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-3_Interpretacao_Extracao/Vigas/vigas.json',
                        help='vigas.json enriquecido')
    parser.add_argument('--lv-dir',
                        default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-4_Sincronizacao/JSON_Vigas_Laterais',
                        help='Pasta JSON_Vigas_Laterais')
    parser.add_argument('--fv-dir',
                        default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-4_Sincronizacao/JSON_Vigas_Fundo',
                        help='Pasta JSON_Vigas_Fundo')
    parser.add_argument('--dry-run', action='store_true', help='Simular sem escrever')
    parser.add_argument('--only-enriched', action='store_true',
                        help='Atualizar apenas vigas com comprimento_enrich_status definido (default: todas)')
    args = parser.parse_args()

    lv_dir = Path(args.lv_dir)
    fv_dir = Path(args.fv_dir)

    # ── Carregar vigas.json ───────────────────────────────────────────────────
    with open(args.vigas_json, encoding='utf-8') as f:
        vigas = json.load(f)
    print(f"vigas.json: {len(vigas)} vigas")

    stats = {
        'lv_updated': 0, 'lv_skipped': 0, 'lv_missing': 0,
        'fv_updated': 0, 'fv_skipped': 0, 'fv_missing': 0,
        'comp_zero': 0,
    }

    print(f"\n{'VIG':<8} {'COMP':>7} {'N_PAIN':>7} {'LARGURA':>8}  STATUS")
    print('=' * 55)

    def sort_key(kv):
        m = re.search(r'\d+', kv[0])
        return int(m.group()) if m else 99999

    for vid, viga in sorted(vigas.items(), key=sort_key):
        if not isinstance(viga, dict):
            continue
        comp   = float(viga.get('comprimento', 0) or 0)
        h      = float(viga.get('h', 0) or 0)
        status = viga.get('comprimento_enrich_status', '')
        sides  = viga.get('sides', ['A', 'B'])

        if args.only_enriched and not status:
            continue

        if comp <= 0:
            stats['comp_zero'] += 1
            print(f"  {vid:<6} {'---':>7}  comp=0, pulando")
            continue

        larguras   = auto_dividir_paineis(comp)
        new_panels = make_panels(larguras, h)
        n          = len(larguras)
        w          = larguras[0] if larguras else 0

        row_status = []

        # LV (lateral): A e B
        for side in sides:
            lv_path = lv_dir / f"{vid}_{side}.json"
            changed = update_json_file(lv_path, new_panels, dry_run=args.dry_run)
            if changed:
                stats['lv_updated'] += 1
                row_status.append(f"LV_{side}✓")
            elif lv_path.exists():
                stats['lv_skipped'] += 1
                row_status.append(f"LV_{side}=")
            else:
                stats['lv_missing'] += 1
                row_status.append(f"LV_{side}?")

        # FV (fundo)
        fv_path = fv_dir / f"{vid}_fundo.json"
        changed = update_json_file(fv_path, new_panels, dry_run=args.dry_run)
        if changed:
            stats['fv_updated'] += 1
            row_status.append("FV✓")
        elif fv_path.exists():
            stats['fv_skipped'] += 1
            row_status.append("FV=")
        else:
            stats['fv_missing'] += 1
            row_status.append("FV?")

        print(f"  {vid:<6} {comp:>7.1f} {n:>7}  {w:>7.1f}   {' '.join(row_status)}")

    # ── Sumario ───────────────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"LV atualizados: {stats['lv_updated']}  sem-alteracao: {stats['lv_skipped']}  nao-encontrados: {stats['lv_missing']}")
    print(f"FV atualizados: {stats['fv_updated']}  sem-alteracao: {stats['fv_skipped']}  nao-encontrados: {stats['fv_missing']}")
    print(f"Comp=0 pulados: {stats['comp_zero']}")
    if args.dry_run:
        print("\n[DRY RUN] Nenhum arquivo foi alterado.")
    else:
        total = stats['lv_updated'] + stats['fv_updated']
        print(f"\nTotal arquivos atualizados: {total}")


if __name__ == '__main__':
    main()
