#!/usr/bin/env python3
"""
atualizar_bh_com_stog.py - Atualiza pilares_bh.json com dados STOG (ground truth).

Faz merge: para cada pilar, se STOG conf >= MIN_CONF substitui B/H.
Salva backup do antigo e regenera DXFs.

Usage: python scripts/atualizar_bh_com_stog.py --obra PATH
"""
import argparse, json, shutil, subprocess, sys
from pathlib import Path

MIN_CONF_STOG = 0.60  # confianca minima para usar valor STOG


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--obra", required=True)
    args = parser.parse_args()

    obra = Path(args.obra)
    bh_path   = obra / "Fase-3_Interpretacao_Extracao" / "Pilares" / "pilares_bh.json"
    stog_path = obra / "Fase-3_Interpretacao_Extracao" / "Pilares" / "pilares_bh_stog.json"

    if not stog_path.exists():
        print("ERRO: pilares_bh_stog.json nao encontrado. Execute extrair_secoes_stog_pl.py primeiro.")
        sys.exit(1)

    # Carrega dados atuais e STOG
    bh_old  = json.loads(bh_path.read_text(encoding='utf-8'))
    stog    = json.loads(stog_path.read_text(encoding='utf-8'))
    stog.pop('_meta', None)

    # Backup
    backup = bh_path.with_suffix('.json.backup')
    shutil.copy2(bh_path, backup)
    print(f"Backup salvo: {backup.name}")

    n_updated = 0
    n_kept    = 0
    updates   = []

    for pid, stog_data in stog.items():
        conf = stog_data.get('confidence', 0.0)
        if conf < MIN_CONF_STOG:
            n_kept += 1
            continue

        B_new = stog_data['b']
        H_new = stog_data['h']

        if pid in bh_old:
            B_old = bh_old[pid].get('b', 0)
            H_old = bh_old[pid].get('h', 0)

            if abs(B_new - B_old) > 1 or abs(H_new - H_old) > 1:
                updates.append(f"  {pid}: B {B_old}->{B_new}  H {H_old}->{H_new}  [{stog_data['source']}]")

            # Atualiza preservando outros campos
            bh_old[pid] = {
                **bh_old[pid],
                'b': B_new,
                'h': H_new,
                'source': f"stog-{stog_data['source']}",
                'confidence': conf,
            }
        else:
            # Pilar novo (nao existia no bh_old)
            bh_old[pid] = {
                'b': B_new,
                'h': H_new,
                'source': f"stog-{stog_data['source']}",
                'confidence': conf,
            }
            updates.append(f"  {pid}: NOVO B={B_new} H={H_new}")

        n_updated += 1

    # Salva bh atualizado
    bh_path.write_text(json.dumps(bh_old, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f"\nPilares atualizados com STOG (conf>={MIN_CONF_STOG}): {n_updated}")
    print(f"Pilares mantidos (conf baixa): {n_kept}")

    if updates:
        print("\nMudancas B/H:")
        for u in updates:
            print(u)

    print(f"\nSalvo: {bh_path.name}")
    print("PROXIMO: Regenerar DXFs com novos B/H:")
    print(f"  python scripts/motor_fase4.py --obra {args.obra} --pavimento '12 PAV' --nivel-chegada 0 --nivel-saida 280")
    print(f"  python scripts/gerar_dxf_pilares.py --obra {args.obra}")
    print(f"  python scripts/comparar_bh_stog_vs_gerado.py --obra {args.obra}")


if __name__ == "__main__":
    main()
