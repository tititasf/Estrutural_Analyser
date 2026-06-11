#!/usr/bin/env python3
"""
converter_dwg_dxf_autocad.py
============================
Converte DWG → DXF R2018 ASCII usando AutoCAD COM (win32com).

Uso:
    python scripts/converter_dwg_dxf_autocad.py --obra D:/DADOS-OBRAS/Obra_TREINO_20
    python scripts/converter_dwg_dxf_autocad.py --input D:/path/to/file.dwg [--output D:/path/out.dxf]

Requer: AutoCAD instalado + pip install pywin32
"""
import argparse
import sys
import time
from pathlib import Path


def _acad_convert(dwg_path: Path, dxf_path: Path, acad=None) -> bool:
    """Converte um DWG para DXF via AutoCAD COM."""
    import win32com.client

    owned = False
    if acad is None:
        try:
            acad = win32com.client.GetActiveObject("AutoCAD.Application")
        except Exception:
            acad = win32com.client.Dispatch("AutoCAD.Application")
            owned = True

    try:
        acad.Visible = False
        doc = acad.Documents.Open(str(dwg_path))
        time.sleep(0.5)  # aguarda o documento carregar

        # Exportar como DXF R2018 ASCII
        # SaveAs: 1=DXF, 61=R2018 DXF
        # Version codes AutoCAD: acVersion2018 = 23
        doc.SaveAs(str(dxf_path), 1)  # 1 = acSaveAsDXF
        doc.Close(False)
        return True
    except Exception as e:
        print(f"  [ERRO] {dwg_path.name}: {e}", file=sys.stderr)
        try:
            doc.Close(False)
        except Exception:
            pass
        return False
    finally:
        if owned:
            try:
                acad.Quit()
            except Exception:
                pass


def convert_folder(folder: Path, force: bool = False) -> dict:
    """Converte todos DWGs sem DXF correspondente em uma pasta."""
    import win32com.client

    dwgs = sorted(folder.glob("*.dwg"))
    if not dwgs:
        print(f"[INFO] Nenhum DWG encontrado em {folder}")
        return {}

    # Abrir AutoCAD uma vez para todos os arquivos
    try:
        acad = win32com.client.GetActiveObject("AutoCAD.Application")
        print("[INFO] Reutilizando AutoCAD aberto")
    except Exception:
        acad = win32com.client.Dispatch("AutoCAD.Application")
        print("[INFO] AutoCAD iniciado")

    acad.Visible = False

    results = {}
    for dwg in dwgs:
        # Nome padrão do DXF gerado
        dxf = dwg.with_name(dwg.stem + "_R2018_ASCII_ODA.dxf")
        if dxf.exists() and not force:
            print(f"  [SKIP] {dwg.name} (DXF já existe)")
            results[dwg.name] = "SKIP"
            continue

        print(f"  [CONV] {dwg.name} → {dxf.name} ...", end=" ", flush=True)
        ok = _acad_convert(dwg, dxf, acad=acad)
        if ok:
            print("OK")
            results[dwg.name] = "OK"
        else:
            results[dwg.name] = "ERRO"

    try:
        acad.Quit()
    except Exception:
        pass

    return results


def convert_single(dwg_path: Path, dxf_path: Path) -> bool:
    print(f"Convertendo {dwg_path.name} → {dxf_path.name} ...")
    ok = _acad_convert(dwg_path, dxf_path)
    if ok:
        print("OK")
    else:
        print("ERRO")
    return ok


def main():
    ap = argparse.ArgumentParser(description="Converte DWG → DXF via AutoCAD COM")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--obra", type=Path, help="Pasta obra (converte Fase-1/.../Projetos_Finalizados)")
    grp.add_argument("--input", type=Path, help="Arquivo DWG único")
    ap.add_argument("--output", type=Path, help="Arquivo DXF de saída (para --input)")
    ap.add_argument("--folder", type=Path, help="Pasta com DWGs (para converter pasta específica)")
    ap.add_argument("--force", action="store_true", help="Recriar DXF mesmo se já existir")
    args = ap.parse_args()

    if args.input:
        if not args.input.exists():
            print(f"[ERRO] DWG não encontrado: {args.input}", file=sys.stderr)
            sys.exit(1)
        out = args.output or args.input.with_name(args.input.stem + "_R2018_ASCII_ODA.dxf")
        ok = convert_single(args.input, out)
        sys.exit(0 if ok else 1)

    # --obra ou --folder
    if args.obra:
        folder = args.obra / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    else:
        folder = args.folder

    if not folder.exists():
        print(f"[ERRO] Pasta não encontrada: {folder}", file=sys.stderr)
        sys.exit(1)

    print(f"Convertendo DWGs em: {folder}")
    results = convert_folder(folder, force=args.force)

    ok = sum(1 for v in results.values() if v == "OK")
    skip = sum(1 for v in results.values() if v == "SKIP")
    erros = sum(1 for v in results.values() if v == "ERRO")
    print(f"\nResultado: {ok} convertidos, {skip} pulados, {erros} erros")
    sys.exit(0 if erros == 0 else 1)


if __name__ == "__main__":
    main()
