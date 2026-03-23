#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_batch.py — Processa TODAS as obras/pavimentos completos em batch.

Le dxf_discovery.json e executa pipeline_e2e.py para cada
obra/pavimento que tenha PL + LV + LJ disponíveis.

CLI:
  # Processar todas as obras/pavimentos completos
  python scripts/pipeline_batch.py --data-dir DADOS-OBRAS

  # Apenas uma obra específica (todos os pavimentos completos)
  python scripts/pipeline_batch.py --data-dir DADOS-OBRAS --obra Obra_TREINO_21

  # Dry-run (mostra o que faria)
  python scripts/pipeline_batch.py --data-dir DADOS-OBRAS --dry-run

  # Forcar reprocessamento
  python scripts/pipeline_batch.py --data-dir DADOS-OBRAS --force

  # Limitar N obras (debug)
  python scripts/pipeline_batch.py --data-dir DADOS-OBRAS --limit 3
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def run_pipeline_e2e(obra_path: str, pavimento: str,
                     dry_run: bool = False, force: bool = False) -> dict:
    """Executa pipeline_e2e.py para uma obra/pavimento. Retorna resultado."""
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "pipeline_e2e.py"),
        "--obra", obra_path,
        "--pavimento", pavimento,
    ]
    if dry_run:
        cmd.append("--dry-run")
    if force:
        cmd.append("--force")

    t0 = time.time()
    try:
        result = subprocess.run(cmd, capture_output=False, check=False)
        elapsed = time.time() - t0
        return {
            "returncode": result.returncode,
            "elapsed": round(elapsed, 1),
            "status": {0: "APROVADO", 1: "PARCIAL"}.get(result.returncode, "REPROVADO"),
        }
    except Exception as ex:
        return {"returncode": -1, "elapsed": 0, "status": "ERRO", "error": str(ex)}


def load_discovery(data_dir: Path) -> dict:
    """Carrega dxf_discovery.json."""
    disc_path = data_dir / "dxf_discovery.json"
    if not disc_path.exists():
        print(f"[ERROR] dxf_discovery.json nao encontrado em {data_dir}")
        print(f"        Execute: python scripts/descobrir_obras.py --data-dir {data_dir}")
        sys.exit(1)
    with open(disc_path, encoding='utf-8') as f:
        return json.load(f)


def coletar_targets(discovery: dict, obra_filtro: str = None) -> list:
    """
    Retorna lista de (obra_path, pavimento) para pavimentos completos (PL+LV+LJ).
    """
    targets = []
    for obra_nome, pav_map in discovery.items():
        if obra_filtro and obra_nome != obra_filtro:
            continue
        for pav, tipos in pav_map.items():
            pl = tipos.get("PL")
            lv = tipos.get("LV")
            lj = tipos.get("LJ")
            if pl and lv and lj:
                # Inferir obra_path a partir do path do DXF PL
                obra_path = str(Path(pl).parent.parent.parent)
                targets.append((obra_nome, pav, obra_path))
    return sorted(targets, key=lambda t: (t[0], t[1]))


def run_batch(data_dir: str, obra_filtro: str = None,
              dry_run: bool = False, force: bool = False,
              limit: int = 0) -> dict:
    data_path = Path(data_dir).resolve()
    discovery = load_discovery(data_path)
    targets = coletar_targets(discovery, obra_filtro)

    if limit > 0:
        targets = targets[:limit]

    print(f"\n{'='*65}")
    print(f"PIPELINE BATCH | {len(targets)} pavimentos completos")
    if obra_filtro:
        print(f"  Filtro obra: {obra_filtro}")
    if dry_run:
        print(f"  Modo: DRY-RUN")
    print(f"{'='*65}\n")

    resultados = []
    aprovados = parciais = reprovados = erros = 0
    t_batch = time.time()

    for i, (obra_nome, pavimento, obra_path) in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] {obra_nome} | {pavimento}")
        print(f"  Path: {obra_path}")

        res = run_pipeline_e2e(obra_path, pavimento, dry_run, force)
        res.update({"obra": obra_nome, "pavimento": pavimento})
        resultados.append(res)

        s = res["status"]
        if s == "APROVADO":
            aprovados += 1
        elif s == "PARCIAL":
            parciais += 1
        elif s == "ERRO":
            erros += 1
        else:
            reprovados += 1

        print(f"  -> {s} ({res['elapsed']}s)")

    elapsed_total = time.time() - t_batch

    print(f"\n{'='*65}")
    print(f"BATCH CONCLUIDO em {elapsed_total:.0f}s")
    print(f"  Aprovados:   {aprovados}")
    print(f"  Parciais:    {parciais}")
    print(f"  Reprovados:  {reprovados}")
    print(f"  Erros:       {erros}")
    print(f"  Total:       {len(targets)}")
    print(f"{'='*65}\n")

    # Salvar relatório batch
    report = {
        "timestamp": datetime.now().isoformat(),
        "total": len(targets),
        "aprovados": aprovados,
        "parciais": parciais,
        "reprovados": reprovados,
        "erros": erros,
        "elapsed_s": round(elapsed_total, 1),
        "resultados": resultados,
    }
    report_path = data_path / "batch_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  Relatorio: {report_path}")

    return report


def main():
    parser = argparse.ArgumentParser(
        description='Processa TODAS as obras/pavimentos completos em batch'
    )
    parser.add_argument('--data-dir', required=True,
                        help='Diretório raiz das obras (onde está dxf_discovery.json)')
    parser.add_argument('--obra', default=None,
                        help='Filtrar apenas esta obra (ex: Obra_TREINO_21)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Mostrar o que faria sem executar')
    parser.add_argument('--force', action='store_true',
                        help='Reprocessar mesmo se outputs existem')
    parser.add_argument('--limit', type=int, default=0,
                        help='Limitar a N obras (0 = sem limite)')
    parser.add_argument('--list', action='store_true',
                        help='Apenas listar targets sem executar')
    args = parser.parse_args()

    if args.list:
        data_path = Path(args.data_dir).resolve()
        discovery = load_discovery(data_path)
        targets = coletar_targets(discovery, args.obra)
        print(f"\nTargets completos (PL+LV+LJ): {len(targets)}")
        for obra, pav, path in targets:
            print(f"  {obra} | {pav}")
        return

    report = run_batch(
        args.data_dir,
        obra_filtro=args.obra,
        dry_run=args.dry_run,
        force=args.force,
        limit=args.limit,
    )

    total = report["total"]
    aprovados = report["aprovados"]
    if aprovados == total:
        sys.exit(0)
    elif aprovados > 0:
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == '__main__':
    main()
