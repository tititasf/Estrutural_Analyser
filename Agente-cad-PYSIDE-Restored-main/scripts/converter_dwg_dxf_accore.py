#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
converter_dwg_dxf_accore.py — Converte DWG → DXF usando accoreconsole + DXFOUT.

Estratégia descoberta após testes exaustivos:
  - accoreconsole NÃO suporta -SAVEAS (comando inexistente)
  - DXFOUT como comando direto no SCR (não via LISP command) FUNCIONA
  - Prompt sequence: DXFOUT → filename → precision (16) → QUIT Y

Uso:
  python scripts/converter_dwg_dxf_accore.py --obra DADOS-OBRAS/Obra_TREINO_20
  python scripts/converter_dwg_dxf_accore.py --dwg "path/to/file.dwg" --out "path/to/out.dxf"
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ACCORE = Path(r"C:\Program Files\Autodesk\AutoCAD 2021\accoreconsole.exe")
TMP_DIR = Path(r"C:\Temp\dwg_convert_tmp")
TMP_DWG = TMP_DIR / "input.dwg"
TMP_DXF = TMP_DIR / "output.dxf"


def convert_dwg_to_dxf(dwg_src: Path, dxf_dst: Path, timeout: int = 90) -> bool:
    """Convert single DWG to DXF. Returns True if successful."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # Copy DWG to ASCII path (accoreconsole fails with accented chars)
    print(f"  Copiando: {dwg_src.name}")
    try:
        shutil.copy2(dwg_src, TMP_DWG)
    except Exception as e:
        print(f"  ERRO cópia: {e}")
        return False

    # Remove old output if exists
    if TMP_DXF.exists():
        TMP_DXF.unlink()

    # SCR script: DXFOUT → absolute path → precision → QUIT
    dxf_posix = TMP_DXF.as_posix()
    scr = f"DXFOUT\n{dxf_posix}\n16\nQUIT\nY\n"
    scr_path = TMP_DIR / "convert.scr"
    scr_path.write_text(scr, encoding="ascii")

    # Run accoreconsole
    t0 = time.time()
    proc = subprocess.Popen(
        [str(ACCORE), "/i", str(TMP_DWG), "/s", str(scr_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    try:
        proc.communicate(timeout=timeout)
        elapsed = time.time() - t0
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        print(f"  TIMEOUT após {timeout}s")
        return False

    # Check result
    if TMP_DXF.exists() and TMP_DXF.stat().st_size > 10000:
        dxf_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TMP_DXF, dxf_dst)
        size_mb = dxf_dst.stat().st_size / 1024 / 1024
        print(f"  OK: {dxf_dst.name} ({size_mb:.1f}MB, {elapsed:.1f}s)")
        return True
    else:
        size = TMP_DXF.stat().st_size if TMP_DXF.exists() else 0
        print(f"  FALHOU: DXF não criado ou vazio ({size}B, {elapsed:.1f}s)")
        return False


def convert_obra(obra_path: Path) -> dict:
    """Convert all LV/FV/LJ DWGs in an obra that don't have DXF yet."""
    if not ACCORE.exists():
        print(f"ERRO: accoreconsole não encontrado: {ACCORE}")
        return {}

    fase1 = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    if not fase1.exists():
        print(f"ERRO: pasta não encontrada: {fase1}")
        return {}

    # Find DWGs that need conversion (LV, FV, LJ — not PL)
    dwgs = list(fase1.glob("*.dwg")) + list(fase1.glob("*.DWG"))
    tipos_alvo = {"LV", "FV", "LJ"}
    results = {}

    for dwg in sorted(dwgs):
        # Check if it's LV/FV/LJ type
        name_upper = dwg.stem.upper()
        tipo = None
        for t in tipos_alvo:
            if f"-{t}-" in name_upper or f" {t} " in name_upper or name_upper.endswith(f"-{t}"):
                tipo = t
                break
        if not tipo:
            continue

        # Check if DXF already exists
        dxf_name = dwg.stem + "_R2018_ASCII_ODA.dxf"
        dxf_path = fase1 / dxf_name
        if dxf_path.exists() and dxf_path.stat().st_size > 10000:
            print(f"  [SKIP] {dxf_name} (já existe)")
            results[dwg.name] = "SKIP"
            continue

        print(f"\n[{tipo}] {dwg.name}")
        ok = convert_dwg_to_dxf(dwg, dxf_path)
        results[dwg.name] = "OK" if ok else "FALHOU"

    return results


def main():
    parser = argparse.ArgumentParser(description="Converter DWG → DXF via accoreconsole")
    parser.add_argument("--obra", help="Pasta da obra (ex: DADOS-OBRAS/Obra_TREINO_20)")
    parser.add_argument("--dwg", help="Arquivo DWG específico")
    parser.add_argument("--out", help="Arquivo DXF de saída (com --dwg)")
    parser.add_argument("--force", action="store_true", help="Reconverter mesmo se DXF existe")
    args = parser.parse_args()

    if not ACCORE.exists():
        print(f"ERRO: accoreconsole não encontrado em {ACCORE}")
        sys.exit(1)

    if args.dwg:
        dwg = Path(args.dwg)
        dxf = Path(args.out) if args.out else dwg.parent / (dwg.stem + "_R2018_ASCII_ODA.dxf")
        ok = convert_dwg_to_dxf(dwg, dxf)
        sys.exit(0 if ok else 1)

    if args.obra:
        obra = Path(args.obra)
        if not obra.is_absolute():
            # Tentar relativo ao diretório do script
            script_dir = Path(__file__).parent.parent
            obra = script_dir / args.obra
        if not obra.exists():
            print(f"ERRO: obra não encontrada: {obra}")
            sys.exit(1)
        results = convert_obra(obra)
        ok_count = sum(1 for v in results.values() if v == "OK")
        skip_count = sum(1 for v in results.values() if v == "SKIP")
        fail_count = sum(1 for v in results.values() if v == "FALHOU")
        print(f"\nResumo: {ok_count} OK, {skip_count} já existiam, {fail_count} falharam")
        sys.exit(0 if fail_count == 0 else 1)

    parser.print_help()


if __name__ == "__main__":
    main()
