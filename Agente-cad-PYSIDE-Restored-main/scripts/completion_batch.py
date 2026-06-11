#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
completion_batch.py — Roda tipos faltando para obras com JSON parcial.

Uso:
  python scripts/completion_batch.py
  python scripts/completion_batch.py --dry-run
  python scripts/completion_batch.py --obras TREINO_11,TREINO_21
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "validar_visual_dxf.py"
VALIDATION_DIR = Path("D:/Agente-cad-PYSIDE/validacao_visual")
DADOS_DIR = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
TODOS_TIPOS = ["PL", "LV", "FV", "LJ"]

# Obras que precisam de pav customizado (discovery escolheu pav errado)
PAV_OVERRIDE = {
    "Obra_TREINO_15": "LO - 6PV",
}


def carregar_discovery() -> dict:
    disc_path = DADOS_DIR / "dxf_discovery.json"
    return json.loads(disc_path.read_text(encoding="utf-8"))


def encontrar_pav_json(obra_dir: Path):
    """Retorna (pav_name_real, json_path) para o pav com JSON existente."""
    for pav_dir in obra_dir.iterdir():
        if pav_dir.is_dir():
            j = pav_dir / "validation_visual.json"
            if j.exists():
                # Converte underscores de volta para espaços no pav name
                pav_real = pav_dir.name.replace("_", " ").replace("  ", " ")
                return pav_real, j
    return None, None


def pav_dir_to_name(pav_dir_name: str) -> str:
    """Converte nome de diretório (underscores) para nome real do pav."""
    return pav_dir_name.replace("_", " ")


def main():
    parser = argparse.ArgumentParser(description="Completion batch — tipos faltando")
    parser.add_argument("--dry-run", action="store_true", help="Só mostra o que faria")
    parser.add_argument("--obras", default=None, help="Subset: TREINO_11,TREINO_21")
    parser.add_argument("--force-all", action="store_true", help="Re-rodar mesmo obras completas")
    args = parser.parse_args()

    discovery = carregar_discovery()

    # Determinar obras a processar
    if args.obras:
        obra_names = [f"Obra_{o.strip()}" if not o.startswith("Obra_") else o.strip()
                      for o in args.obras.split(",")]
    else:
        obra_names = sorted(VALIDATION_DIR.glob("Obra_TREINO_*"))
        obra_names = [o.name for o in obra_names if o.is_dir()]

    print(f"[COMPLETION] Verificando {len(obra_names)} obras...\n")

    runs_needed = []

    for obra_nome in obra_names:
        obra_val_dir = VALIDATION_DIR / obra_nome

        # Verificar se existe JSON
        if not obra_val_dir.exists():
            print(f"  {obra_nome}: sem pasta em validacao_visual — skipping")
            continue

        # Encontrar JSON existente
        pav_real = None
        json_path = None
        tipos_existentes = []

        for pav_d in obra_val_dir.iterdir():
            if pav_d.is_dir():
                j = pav_d / "validation_visual.json"
                if j.exists():
                    try:
                        data = json.loads(j.read_text(encoding="utf-8"))
                        tipos_ex = data.get("tipos_validados", [])
                        if len(tipos_ex) > len(tipos_existentes):
                            tipos_existentes = tipos_ex
                            json_path = j
                            # Converte nome do dir de volta para pav real
                            # (substitui underscores, mas mantém hífens)
                            pav_real = pav_d.name.replace("_", " ")
                    except Exception:
                        pass

        if not json_path:
            # Verificar se há PAV_OVERRIDE para criar do zero
            if obra_nome in PAV_OVERRIDE:
                pav_to_use = PAV_OVERRIDE[obra_nome]
                print(f"  {obra_nome}: sem JSON válido — agendando com pav override '{pav_to_use}'")
                runs_needed.append((obra_nome, pav_to_use, TODOS_TIPOS))
            else:
                print(f"  {obra_nome}: sem JSON válido — skipping (batch não terminou?)")
            continue

        tipos_faltando = [t for t in TODOS_TIPOS if t not in tipos_existentes]
        score = None
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            score = data.get("score_pavimento")
        except Exception:
            pass

        if not tipos_faltando and not args.force_all:
            print(f"  {obra_nome}/{pav_real}: COMPLETO (score={score}, tipos={'+'.join(tipos_existentes)})")
            continue

        if args.force_all and not tipos_faltando:
            tipos_faltando = TODOS_TIPOS

        print(f"  {obra_nome}/{pav_real}: faltando {tipos_faltando} (tem {tipos_existentes}, score={score})")

        # PAV override se necessário
        pav_to_use = PAV_OVERRIDE.get(obra_nome, pav_real)
        if pav_to_use != pav_real:
            print(f"    -> PAV override: '{pav_real}' -> '{pav_to_use}'")

        runs_needed.append((obra_nome, pav_to_use, tipos_faltando))

    print(f"\n[COMPLETION] {len(runs_needed)} runs necessários.\n")

    if args.dry_run:
        for obra, pav, tipos in runs_needed:
            tipo_args = " ".join(f"--tipo {t}" for t in tipos)
            print(f"  python validar_visual_dxf.py --obra {obra} --pav \"{pav}\" {tipo_args}")
        return

    # Executar runs
    for i, (obra, pav, tipos) in enumerate(runs_needed, 1):
        print(f"\n[{i}/{len(runs_needed)}] {obra}/{pav} -> {tipos}")
        cmd = [sys.executable, str(SCRIPT), "--obra", obra, "--pav", pav]
        for t in tipos:
            cmd += ["--tipo", t]

        result = subprocess.run(cmd, capture_output=False)
        if result.returncode != 0:
            print(f"  ERRO (exit {result.returncode}) — continuando...")

    print("\n[COMPLETION] Concluído.")


if __name__ == "__main__":
    main()
