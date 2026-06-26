#!/usr/bin/env python3
"""
integrar_fichas_pilares.py - Integra todas as fontes Fase 3 em pilares.json completo.

Fontes para pilares:
  - pilares_bh.json:        b, h, confidence, source, dist_d1, dist_d2
  - pilares_assembly.json:  grade_1, grade_2, chapa_total, perfil_metalico,
                             sp_per_face, faces_found, confidence_assembly

Output:
  - Fase-3_Interpretacao_Extracao/Pilares/pilares.json

Equivalente de integrar_fichas_fase3.py para pilares.
Elimina a assimetria onde vigas.json e lajes.json existem
mas pilares.json nao era gerado por um integrador dedicado.

Story: CAD-STOG-PIPELINE
Usage: python scripts/integrar_fichas_pilares.py --obra PATH
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Integrar fichas de pilares Fase 3')
    parser.add_argument('--obra', required=True, help='Path da obra')
    args = parser.parse_args()

    obra = Path(args.obra)
    fase3 = obra / "Fase-3_Interpretacao_Extracao"
    pilares_dir = fase3 / "Pilares"
    pilares_dir.mkdir(parents=True, exist_ok=True)

    bh_path  = pilares_dir / "pilares_bh.json"
    asm_path = pilares_dir / "pilares_assembly.json"
    out_path = pilares_dir / "pilares.json"

    print("=== PILARES ===")

    # ── Carregar pilares_bh.json ───────────────────────────────────────────────
    if not bh_path.exists():
        print(f"  ERRO: pilares_bh.json nao encontrado em {pilares_dir}")
        return 1

    bh_data = json.loads(bh_path.read_text(encoding='utf-8'))
    pids = [k for k in bh_data if not k.startswith('_')]
    print(f"  pilares_bh.json: {len(pids)} pilares")

    # ── Carregar pilares_assembly.json (opcional) ──────────────────────────────
    asm_data = {}
    if asm_path.exists():
        asm_data = json.loads(asm_path.read_text(encoding='utf-8'))
        asm_pids = [k for k in asm_data if not k.startswith('_')]
        print(f"  pilares_assembly.json: {len(asm_pids)} pilares")
    else:
        print(f"  AVISO: pilares_assembly.json nao encontrado — grades ficarao vazias")

    # ── Mesclar ───────────────────────────────────────────────────────────────
    merged = {}
    sem_assembly = []

    for pid in pids:
        bh = bh_data[pid]
        asm = asm_data.get(pid, {})

        if not asm:
            sem_assembly.append(pid)

        b = float(bh.get('b') or 0)
        h = float(bh.get('h') or 0)

        if b <= 0 or h <= 0:
            print(f"  AVISO: Pilar {pid}: dimensoes invalidas (b={b}, h={h}), pulando")
            continue

        merged[pid] = {
            # Dimensoes B/H (de pilares_bh.json)
            "b":          b,
            "h":          h,
            "confidence": float(bh.get('confidence', 0.7)),
            "source":     bh.get('source', 'pilares_bh'),

            # Distancias aux (usadas pelo motor_fase4 para nivelamento)
            "dist_d1":    float(bh.get('dist_d1', 0) or 0),
            "dist_d2":    float(bh.get('dist_d2', 0) or 0),

            # Assembly / grades (de pilares_assembly.json)
            "grade_1":          float(asm.get('grade_1') or 0),
            "grade_2":          float(asm.get('grade_2') or 0),
            "grade_source":     asm.get('grade_source', ''),
            "chapa_total":      int(asm.get('chapa_total', 0) or 0),
            "chapa_vert":       int(asm.get('chapa_vert', 0) or 0),
            "chapa_horiz":      int(asm.get('chapa_horiz', 0) or 0),
            "perfil_metalico":  int(asm.get('perfil_metalico', 0) or 0),
            "sp_total":         int(asm.get('sp_total', 0) or 0),
            "sp_per_face":      asm.get('sp_per_face', {}),
            "faces_found":      asm.get('faces_found', []),
            "confidence_assembly": float(asm.get('confidence', 0.0)),
        }

    merged["_meta"] = {
        "total":        len(merged) - 1,
        "sem_assembly": len(sem_assembly),
        "fontes":       ["pilares_bh.json", "pilares_assembly.json"],
    }

    out_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding='utf-8')

    total = len(merged) - 1
    print(f"  pilares.json atualizado: {total} pilares")
    if sem_assembly:
        print(f"  AVISO: {len(sem_assembly)} pilares sem assembly: {sem_assembly[:5]}")

    for pid, v in sorted([(k, v) for k, v in merged.items() if not k.startswith('_')],
                          key=lambda x: (len(x[0]), x[0])):
        g1 = v['grade_1']; g2 = v['grade_2']
        grades = f"g1={g1}" + (f" g2={g2}" if g2 else "")
        print(f"    {pid}: b={v['b']}cm h={v['h']}cm  {grades}  chapa={v['chapa_total']}  sp={v['sp_total']}")

    print(f"\n=== INTEGRACAO COMPLETA: {total} pilares ===")
    print(f"  Proximo passo: python scripts/motor_fase4.py --obra {args.obra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
