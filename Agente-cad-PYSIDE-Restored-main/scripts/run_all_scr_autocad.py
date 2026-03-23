#!/usr/bin/env python3
"""
run_all_scr_autocad.py — Executa SCR scripts no AutoCAD via COM automation
==========================================================================
Frente 1: SCR → AutoCAD = 100% fidelidade.

Requer:
  - AutoCAD 2021 aberto
  - pip install pywin32

Uso:
  python scripts/run_all_scr_autocad.py --obra DADOS-OBRAS/Obra_TREINO_1 --tipo PL
  python scripts/run_all_scr_autocad.py --scr path/to/script.scr
"""
import sys, io, time, os, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

try:
    import win32com.client
except ImportError:
    print("pip install pywin32")
    sys.exit(1)

# Template DWG with layers/blocks/dimstyles
MOLDE_PL = Path("D:/Agente-cad-PYSIDE/_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/templates/MOLDE_PILARES ATUALIZADO2.dwg")


def connect():
    """Conecta ao AutoCAD via COM."""
    acad = win32com.client.Dispatch("AutoCAD.Application")
    acad.Visible = True
    return acad


def run_scr_on_molde(acad, scr_path, output_dxf, molde=MOLDE_PL, wait=15):
    """Abre MOLDE, executa SCR, salva DXF."""
    scr_path = str(Path(scr_path).resolve())
    output_dxf = str(Path(output_dxf).resolve())

    # Abrir MOLDE (com layers e blocks)
    doc = acad.Documents.Open(str(molde), False)
    time.sleep(3)

    # FILEDIA off
    doc.SendCommand("FILEDIA\n0\n")
    time.sleep(1)

    # Executar SCR
    doc.SendCommand(f"_SCRIPT\n{scr_path}\n")
    time.sleep(wait)

    # Zoom + Save
    doc.SendCommand("_ZOOM\nE\n")
    time.sleep(2)
    doc.SendCommand(f"_SAVEAS\nDXF\n\n{output_dxf}\n\n")
    time.sleep(5)
    doc.SendCommand("FILEDIA\n1\n")

    # Fechar sem salvar
    try:
        doc.Close(False)
    except:
        pass
    time.sleep(2)

    if os.path.exists(output_dxf):
        sz = os.path.getsize(output_dxf) // 1024
        return sz
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', help='Path da obra')
    parser.add_argument('--tipo', choices=['PL', 'LJ', 'LV', 'FV'], default='PL')
    parser.add_argument('--scr', help='SCR individual')
    parser.add_argument('--max', type=int, default=999)
    args = parser.parse_args()

    acad = connect()
    print(f"AutoCAD conectado: {acad.Name}")

    if args.scr:
        scr = Path(args.scr)
        out = scr.with_suffix('.dxf')
        sz = run_scr_on_molde(acad, scr, out)
        print(f"{'OK' if sz else 'FAIL'}: {out.name} ({sz}KB)")
        return

    if not args.obra:
        print("Use --obra ou --scr")
        return

    obra = Path(args.obra)
    scr_dir = obra / 'Fase-6_Execucao_CAD' / f'SCR_Pilares'
    out_dir = obra / 'Fase-6_Execucao_CAD' / 'DXF_via_AutoCAD'
    out_dir.mkdir(parents=True, exist_ok=True)

    scrs = sorted(scr_dir.glob('*.scr'))[:args.max]
    print(f"Executando {len(scrs)} SCR scripts via AutoCAD...")

    for i, scr in enumerate(scrs):
        out = out_dir / scr.with_suffix('.dxf').name
        print(f"  [{i+1}/{len(scrs)}] {scr.name}...", end=" ", flush=True)
        sz = run_scr_on_molde(acad, scr, out)
        print(f"{'OK' if sz else 'FAIL'} ({sz}KB)")

    print(f"\nDXFs salvos em: {out_dir}")


if __name__ == '__main__':
    main()
