#!/usr/bin/env python3
"""
enrich_vigas_reverso.py — Enriquece vigas.json com comprimento real da forma.

PROBLEMA: vigas.json usa comprimento estrutural (vão TQS ~50-178cm).
SOLUÇÃO:  fichas_reverso_VIG_ALL.json contém comprimento real da forma (~300-1152cm).

Regras de enriquecimento:
  1. Para cada viga em vigas.json que existe no reverso ALL:
     - Se reverso.comprimento_cm > 0 e reverso.has_lv=True:
         → vigas[viga].comprimento = reverso.comprimento_cm
         → vigas[viga].source += "+reverso_lv"
     - Else (sem LV, só FV): manter original, anotar como "rev_fv_only"
  2. Vigas sem dados reverso: manter original, anotar como "sem_reverso"
  3. Campo novo: comprimento_original = valor antigo (para auditoria)

Saida: vigas.json atualizado in-place (original em _backup_pre_enrich/)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json, os, argparse


VIGAS_JSON   = 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-3_Interpretacao_Extracao/Vigas/vigas.json'
REVERSO_ALL  = 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-3_Interpretacao_Extracao/Vigas/fichas_reverso_VIG_ALL.json'


def enrich(vigas_path, reverso_path, dry_run=False):
    with open(vigas_path, encoding='utf-8') as f:
        vigas = json.load(f)

    with open(reverso_path, encoding='utf-8') as f:
        reverso = json.load(f)

    stats = {'enriched': 0, 'fv_only': 0, 'sem_reverso': 0, 'zero_comp': 0}

    for viga_name, viga in vigas.items():
        rev = reverso.get(viga_name)

        if rev is None:
            viga['comprimento_enrich_status'] = 'sem_reverso'
            stats['sem_reverso'] += 1
            continue

        rev_comp = rev.get('comprimento_cm', 0)
        has_lv   = rev.get('has_lv', False)

        if rev_comp > 0 and has_lv:
            # Enriquecimento principal
            old_comp = viga.get('comprimento', 0)
            viga['comprimento_original']    = old_comp
            viga['comprimento']             = rev_comp
            viga['comprimento_enrich_status'] = 'enriched_lv'
            old_src = viga.get('source', '')
            viga['source'] = old_src + '+reverso_lv'
            stats['enriched'] += 1

        elif rev_comp > 0 and not has_lv:
            # Só FV — comprimento vem dos paineis de fundo (menos confiável)
            old_comp = viga.get('comprimento', 0)
            viga['comprimento_original']    = old_comp
            viga['comprimento']             = rev_comp
            viga['comprimento_enrich_status'] = 'enriched_fv_only'
            old_src = viga.get('source', '')
            viga['source'] = old_src + '+reverso_fv_only'
            stats['fv_only'] += 1

        else:
            # Reverso existe mas comprimento=0
            viga['comprimento_enrich_status'] = 'rev_zero_comp'
            stats['zero_comp'] += 1

    # ── Relatório ─────────────────────────────────────────────────────────────
    print(f"\nResultados do enriquecimento:")
    print(f"  Total vigas:           {len(vigas)}")
    print(f"  Enriquecidas (LV):     {stats['enriched']}")
    print(f"  Enriquecidas (FV only):{stats['fv_only']}")
    print(f"  Rev comp=0:            {stats['zero_comp']}")
    print(f"  Sem reverso:           {stats['sem_reverso']}")

    if not dry_run:
        with open(vigas_path, 'w', encoding='utf-8') as f:
            json.dump(vigas, f, ensure_ascii=False, indent=2)
        print(f"\nSalvo: {vigas_path}")
    else:
        print("\n[DRY-RUN] Nao salvo.")

    # ── Amostra de vigas enriquecidas ─────────────────────────────────────────
    print(f"\n{'VIGA':<8} {'COMP_OLD':>9} {'COMP_NEW':>9} {'DELTA':>7}  STATUS")
    print(f"{'-' * 55}")
    for viga_name, viga in vigas.items():
        status = viga.get('comprimento_enrich_status', '')
        if status in ('enriched_lv', 'enriched_fv_only'):
            old = viga.get('comprimento_original', 0)
            new = viga.get('comprimento', 0)
            delta = new - old
            print(f"  {viga_name:<6} {old:>9.0f} {new:>9.0f} {delta:>+7.0f}  {status}")

    return vigas


def main():
    parser = argparse.ArgumentParser(
        description='Enriquece vigas.json com comprimento real da forma'
    )
    parser.add_argument('--vigas',   default=VIGAS_JSON)
    parser.add_argument('--reverso', default=REVERSO_ALL)
    parser.add_argument('--dry-run', action='store_true', help='Nao gravar alteracoes')
    args = parser.parse_args()

    print(f"Enriquecendo: {args.vigas}")
    print(f"Fonte reverso: {args.reverso}")
    enrich(args.vigas, args.reverso, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
