#!/usr/bin/env python3
"""
run_scr_autocad.py — Executa SCR no AutoCAD via COM automation
===============================================================
Usa win32com para conectar ao AutoCAD, executar um .scr script e salvar como DXF.

Requisitos:
  - AutoCAD aberto e visível
  - pip install pywin32

Uso:
  python scripts/run_scr_autocad.py --scr path/to/script.scr --output path/output.dxf
  python scripts/run_scr_autocad.py --scr-dir path/to/SCRIPTS_ROBOS/P1_CIMA/ --output path/output.dxf
"""
import sys, time, argparse
from pathlib import Path

try:
    import win32com.client
except ImportError:
    print("pip install pywin32")
    sys.exit(1)


def connect_autocad(max_retries=3):
    """Conecta ao AutoCAD via COM."""
    for i in range(max_retries):
        try:
            acad = win32com.client.Dispatch('AutoCAD.Application')
            acad.Visible = True
            print(f"AutoCAD {acad.Version} conectado ({acad.Documents.Count} docs)")
            return acad
        except Exception as e:
            print(f"Tentativa {i+1}: {e}")
            time.sleep(3)
    return None


def run_scr(acad, scr_path, output_dxf, wait_time=20):
    """Executa SCR num novo documento e salva como DXF."""
    scr_path = str(Path(scr_path).resolve()).replace('/', '\\')
    output_dxf = str(Path(output_dxf).resolve()).replace('/', '\\')

    print(f"SCR: {scr_path}")
    print(f"Output: {output_dxf}")

    # Criar novo documento
    doc = acad.Documents.Add()
    time.sleep(2)
    print(f"Doc criado: {doc.Name}")

    # Enviar SCRIPT command
    try:
        doc.SendCommand(f'(command "_SCRIPT" "{scr_path}") \n')
        print(f"Script enviado — aguardando {wait_time}s...")
        time.sleep(wait_time)
    except Exception as e:
        print(f"SendCommand error: {e}")
        # Retry
        time.sleep(5)
        doc.SendCommand(f'_SCRIPT\n{scr_path}\n')
        time.sleep(wait_time)

    # Zoom extents
    try:
        doc.SendCommand('_ZOOM\nE\n')
        time.sleep(2)
    except Exception:
        pass

    # Save as DXF (acSaveDXF = 1)
    try:
        doc.SaveAs(output_dxf, 1)  # 1 = R2018 DXF
        print(f"SALVO: {output_dxf}")
        return True
    except Exception as e:
        print(f"SaveAs error: {e}")
        # Try LISP approach
        try:
            doc.SendCommand(f'(command "_SAVEAS" "DXF" "" "{output_dxf}") \n')
            time.sleep(5)
            if Path(output_dxf).exists():
                print(f"SALVO (via LISP): {output_dxf}")
                return True
        except Exception as e2:
            print(f"LISP SaveAs error: {e2}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scr', help='Path to SCR script')
    parser.add_argument('--scr-dir', help='Directory with SCR scripts (runs all)')
    parser.add_argument('--output', required=True, help='Output DXF path')
    parser.add_argument('--wait', type=int, default=20, help='Wait time after script (seconds)')
    args = parser.parse_args()

    acad = connect_autocad()
    if not acad:
        print("ERRO: AutoCAD nao encontrado")
        sys.exit(1)

    if args.scr:
        run_scr(acad, args.scr, args.output, args.wait)
    elif args.scr_dir:
        scr_dir = Path(args.scr_dir)
        scrs = sorted(scr_dir.glob('*.scr'))
        if not scrs:
            print(f"Nenhum .scr em {scr_dir}")
            sys.exit(1)
        # Run first SCR and save
        for scr in scrs:
            print(f"\n--- {scr.name} ---")
            run_scr(acad, scr, args.output, args.wait)
            break  # Only first for now


if __name__ == '__main__':
    main()
