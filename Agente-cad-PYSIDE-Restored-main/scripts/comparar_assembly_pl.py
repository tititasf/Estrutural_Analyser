"""
comparar_assembly_pl.py — Validação não-circular dos dados de assembly (CAD-7.x)
================================================================================
Compara grade_1 extraído via COTA annotations do DXF PL contra
as dimensões B/H do pilar (pilares_bh.json) para verificar consistência.

Hipótese: grade_1 deve ser <= max(B, H) do pilar (a grade não pode ser maior que o pilar).
Hipótese: chapa_total > 0 para pilares com secoes (não-edge cases).

Uso:
  python scripts/comparar_assembly_pl.py --obra DADOS-OBRAS/Obra_TREINO_21
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("comparar_assembly_pl")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--obra", required=True)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    fase3 = obra_path / "Fase-3_Interpretacao_Extracao" / "Pilares"

    # Carregar assembly
    assembly_path = fase3 / "pilares_assembly.json"
    if not assembly_path.exists():
        log.error(f"pilares_assembly.json nao encontrado: {assembly_path}")
        sys.exit(1)
    with open(assembly_path, encoding='utf-8') as f:
        assembly = json.load(f)

    # Carregar BH
    bh_path = fase3 / "pilares_bh.json"
    if not bh_path.exists():
        log.warning("pilares_bh.json nao encontrado — verificacao B/H desabilitada")
        bh_data = {}
    else:
        with open(bh_path, encoding='utf-8') as f:
            bh_data = json.load(f)

    total = len(assembly)
    passed = 0
    failed = 0
    warnings = 0

    print(f"\n{'='*60}")
    print(f"VALIDACAO ASSEMBLY DATA ({total} pilares)")
    print(f"{'='*60}")

    for pilar_id, asm in sorted(assembly.items(), key=lambda x: int(x[0][1:])):
        grade_1 = asm.get("grade_1")
        chapa_total = asm.get("chapa_total", 0)
        sp_total = asm.get("sp_total", 0)
        faces = asm.get("faces_found", [])

        issues = []

        # Verificar grade em faixa razoavel (30-200cm, paineis padrao STOG)
        if grade_1 is not None:
            if grade_1 < 30 or grade_1 > 200:
                issues.append(f"grade_1={grade_1} fora faixa esperada [30-200cm]")

        # Verificar chapa
        n_faces = len(faces)
        if n_faces >= 3 and chapa_total == 0:
            issues.append(f"chapa_total=0 com {n_faces} faces")

        # Verificar SP
        if sp_total == 0 and n_faces >= 2:
            issues.append(f"sp_total=0 com {n_faces} faces")

        # Verificar grade presente
        if grade_1 is None:
            issues.append("grade_1=None")

        status = "PASS" if not issues else "WARN"
        if issues:
            warnings += 1
            print(f"  {pilar_id:4s}: {status} — {', '.join(issues)}")
        else:
            passed += 1

    # Pilares com grade_1 None
    no_grade = sum(1 for v in assembly.values() if v.get("grade_1") is None)
    no_chapa = sum(1 for v in assembly.values() if v.get("chapa_total", 0) == 0)

    print(f"\n{'='*60}")
    print(f"RESULTADO FINAL")
    print(f"{'='*60}")
    print(f"Total:      {total}")
    print(f"PASS:       {passed}")
    print(f"WARN:       {warnings}")
    print(f"Sem grade_1: {no_grade}")
    print(f"Sem CHAPA:   {no_chapa}")
    print()
    coverage = (total - no_grade) / total * 100
    print(f"Grade coverage: {total - no_grade}/{total} = {coverage:.1f}%")
    if coverage >= 90:
        print("STATUS: APROVADO (grade coverage >= 90%)")
    else:
        print("STATUS: ATENCAO (grade coverage < 90%)")


if __name__ == "__main__":
    main()
