#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
regenerar_batch.py — Regenera DXFs Fase-5 em todas as obras usando os geradores atualizados.

Executa gerar_dxf_pilares.py, gerar_dxf_vigas.py e gerar_dxf_lajes.py para cada
obra que tenha dados em Fase-4. Necessário após atualizar os geradores com DIMENSION entities.

Uso:
  # Regenerar todas as obras
  python scripts/regenerar_batch.py

  # Obra específica
  python scripts/regenerar_batch.py --obra Obra_TREINO_21

  # Apenas um tipo
  python scripts/regenerar_batch.py --tipo PL

  # Dry-run (mostra o que faria)
  python scripts/regenerar_batch.py --dry-run
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

DATA_DIR = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
SCRIPT_DIR = Path(__file__).parent

GERADORES = {
    "PL": SCRIPT_DIR / "gerar_dxf_pilares.py",
    "LV": SCRIPT_DIR / "gerar_dxf_vigas.py",
    "FV": SCRIPT_DIR / "gerar_dxf_vigas.py",   # mesmo script, vigas LV e FV
    "LJ": SCRIPT_DIR / "gerar_dxf_lajes.py",
}

# Verificações de que a Fase-4 tem dados para cada tipo
FASE4_CHECK = {
    "PL": "JSON_Pilares",
    "LV": "JSON_Vigas_Laterais",
    "FV": "JSON_Vigas_Fundo",
    "LJ": "JSON_Lajes",
}


def pav_representativo(obra_dir: Path) -> str:
    """Retorna o pavimento mais representativo para nomear os DXFs."""
    # Ordem de preferência
    for candidato in ["TIPO", "TIP", "12PAV", "12 PAV", "1PAV", "1 PAV"]:
        if any(candidato.upper() in p.upper() for p in ["TIPO", "TIP", "12PAV"]):
            pass
    # Sem discovery aqui: usar label genérico
    return "TIPO"


def rodar_gerador(tipo: str, obra_dir: Path, pav: str, dry: bool = False) -> bool:
    """Roda o gerador para um tipo numa obra. Retorna True se OK."""
    script = GERADORES.get(tipo)
    if script is None or not script.exists():
        print(f"    [SKIP] Gerador não encontrado para {tipo}")
        return False

    fase4_subdir = obra_dir / "Fase-4_Sincronizacao" / FASE4_CHECK[tipo]
    if not fase4_subdir.exists():
        print(f"    [SKIP] Fase-4 {FASE4_CHECK[tipo]} não existe")
        return False

    cmd = [
        sys.executable, str(script),
        "--obra", str(obra_dir),
        "--pav", pav,
    ]

    if dry:
        print(f"    [DRY] {' '.join(cmd)}")
        return True

    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        elapsed = time.time() - t0
        if result.returncode == 0:
            # Contar DXFs gerados
            if tipo == "PL":
                count = len(list((obra_dir / "Fase-5_Geracao_Scripts" / "DXF_Pilares").glob("*.dxf")))
            elif tipo in ("LV", "FV"):
                count = len(list((obra_dir / "Fase-5_Geracao_Scripts" / "DXF_Vigas").glob("*.dxf")))
            else:
                count = len(list((obra_dir / "Fase-5_Geracao_Scripts" / "DXF_Lajes").glob("*.dxf")))
            print(f"    ✅ {tipo}: {count} DXFs em {elapsed:.1f}s")
            return True
        else:
            print(f"    ❌ {tipo}: exit={result.returncode}")
            # Mostrar últimas linhas de erro
            for line in (result.stderr or result.stdout or "").strip().splitlines()[-3:]:
                print(f"       {line}")
            return False
    except subprocess.TimeoutExpired:
        print(f"    ❌ {tipo}: TIMEOUT (>120s)")
        return False
    except Exception as e:
        print(f"    ❌ {tipo}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Regenerar DXFs Fase-5 em batch")
    parser.add_argument("--obra",    default=None, help="Regenerar só esta obra")
    parser.add_argument("--tipo",    default=None, choices=["PL", "LV", "FV", "LJ"],
                        help="Regenerar só este tipo")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar sem executar")
    parser.add_argument("--data-dir", default=str(DATA_DIR), help="DADOS-OBRAS/")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    tipos = [args.tipo] if args.tipo else ["PL", "LV", "LJ"]  # FV usa mesmo script de LV

    # Obras a processar
    if args.obra:
        obras = [data_dir / args.obra]
    else:
        obras = sorted([
            d for d in data_dir.iterdir()
            if d.is_dir() and d.name.startswith("Obra_TREINO")
        ])

    print(f"\n{'='*70}")
    print(f"  REGENERAR BATCH — {len(obras)} obras | tipos: {tipos}")
    print(f"  {'[DRY-RUN] ' if args.dry_run else ''}Início: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*70}\n")

    resumo = {}
    total_ok = 0
    total_fail = 0

    for obra_dir in obras:
        obra_nome = obra_dir.name
        print(f"\n{obra_nome}")
        print("-" * 50)

        # Verificar se tem Fase-4
        fase4 = obra_dir / "Fase-4_Sincronizacao"
        if not fase4.exists():
            print(f"  [SKIP] Sem Fase-4")
            resumo[obra_nome] = "sem_fase4"
            continue

        # Pav representativo (só para label)
        pav = pav_representativo(obra_dir)

        obra_ok = 0
        obra_fail = 0
        for tipo in tipos:
            ok = rodar_gerador(tipo, obra_dir, pav, dry=args.dry_run)
            if ok:
                obra_ok += 1
                total_ok += 1
            else:
                obra_fail += 1
                total_fail += 1

        resumo[obra_nome] = f"{obra_ok}/{len(tipos)} OK"

    # Resumo final
    print(f"\n{'='*70}")
    print(f"  RESULTADO BATCH")
    print(f"{'='*70}")
    for obra, status in resumo.items():
        icon = "✅" if "sem_fase4" not in status and "0/" not in status else "⛔"
        print(f"  {icon} {obra:<35} {status}")
    print(f"\n  Total OK: {total_ok} | Falhas: {total_fail}")
    print(f"  Fim: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
