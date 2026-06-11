#!/usr/bin/env python3
"""
gerar_ground_truth_batch.py — Executa todos os 50 SCR de cada tipo no AutoCAD via COM
=======================================================================================
Gera DXF ground truth para cada cenário:
  CIMA: 50 SCR → 50 DXF em GROUND_TRUTH/CIMA/
  ABCD: 50 SCR → 50 DXF em GROUND_TRUTH/ABCD/
  GRADES: 50 SCR → 50 DXF em GROUND_TRUTH/GRADES/
  LV:   48 SCR → 48 DXF em GROUND_TRUTH/LV/
  VC:   50 SCR → 50 DXF em GROUND_TRUTH/VC/

Requer: AutoCAD 2021 aberto + MOLDE_PILARES ATUALIZADO2.dwg carregado ou acessível
        pip install pywin32

Uso:
  python scripts/gerar_ground_truth_batch.py --tipo CIMA
  python scripts/gerar_ground_truth_batch.py --tipo ALL --max 10
  python scripts/gerar_ground_truth_batch.py --tipo CIMA --start 0 --max 5
"""
import sys, io, time, os, argparse, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPTS_ROBOS = ROOT / '_ROBOS_ABAS' / 'Robo_Pilares' / 'pilares-atualizado-09-25' / 'SCRIPTS_ROBOS'
SCRIPTS_LV = ROOT / '_ROBOS_ABAS' / 'Robo_Laterais_de_Vigas' / 'SCRIPTS'
GROUND_TRUTH_DIR = ROOT / 'GROUND_TRUTH'

MOLDE_PL = ROOT / '_ROBOS_ABAS' / 'Robo_Pilares' / 'pilares-atualizado-09-25' / 'templates' / 'MOLDE_PILARES ATUALIZADO2.dwg'

# Mapeamento tipo → diretório SCR
SCR_DIRS = {
    'CIMA':   SCRIPTS_ROBOS / 'CENARIOS_CIMA',
    'ABCD':   SCRIPTS_ROBOS / 'CENARIOS_ABCD',
    'GRADES': SCRIPTS_ROBOS / 'CENARIOS_GRADES',
    'LV':     SCRIPTS_LV / 'CENARIOS_LV',
    'VC':     SCRIPTS_LV / 'CENARIOS_VC_HEADLESS',
}


def connect_acad():
    """Conecta ao AutoCAD aberto via COM."""
    try:
        import win32com.client
        acad = win32com.client.Dispatch("AutoCAD.Application")
        acad.Visible = True
        print(f"  AutoCAD conectado: {acad.Name}")
        return acad
    except Exception as e:
        print(f"  ERRO AutoCAD COM: {e}")
        print("  Certifique-se que o AutoCAD está aberto com MOLDE_PILARES ATUALIZADO2.dwg")
        return None


def run_scr_autocad(acad, scr_path, output_dxf, molde_path=MOLDE_PL, wait=18):
    """Abre MOLDE, executa SCR, salva DXF, fecha."""
    scr_abs = str(Path(scr_path).resolve())
    dxf_abs = str(Path(output_dxf).resolve())
    molde_abs = str(molde_path.resolve())

    try:
        # Abre MOLDE como base (readonly=False)
        doc = acad.Documents.Open(molde_abs, False)
        time.sleep(3)

        # Desativa fileDialogs
        doc.SendCommand("FILEDIA\n0\n")
        time.sleep(0.5)

        # Executa o SCR
        doc.SendCommand(f"_SCRIPT\n{scr_abs}\n")
        time.sleep(wait)

        # Zoom extents para ver tudo
        doc.SendCommand("_ZOOM\nE\n")
        time.sleep(2)

        # Salva como DXF R2010
        doc.SendCommand(f"_SAVEAS\nDXF\n\n{dxf_abs}\n\n")
        time.sleep(5)

        doc.SendCommand("FILEDIA\n1\n")
        time.sleep(0.5)

        # Fecha sem salvar alterações
        doc.Close(False)
        time.sleep(2)

        if os.path.exists(dxf_abs):
            sz = os.path.getsize(dxf_abs)
            return sz
        return 0

    except Exception as e:
        print(f"    ERR: {e}")
        try:
            acad.ActiveDocument.Close(False)
        except:
            pass
        return 0


def batch_tipo(tipo, start=0, max_count=999, dry_run=False):
    """Executa batch para um tipo de SCR."""
    scr_dir = SCR_DIRS.get(tipo)
    if not scr_dir or not scr_dir.exists():
        print(f"  Diretório não encontrado: {scr_dir}")
        return []

    out_dir = GROUND_TRUTH_DIR / tipo
    out_dir.mkdir(parents=True, exist_ok=True)

    # Lista SCR
    pattern = '*.scr'
    scrs = sorted(scr_dir.glob(pattern))[start:start + max_count]
    print(f"\n[{tipo}] {len(scrs)} SCR em {scr_dir.name} → {out_dir.name}")

    if dry_run:
        for s in scrs[:5]:
            print(f"  DRY: {s.name}")
        return []

    acad = connect_acad()
    if acad is None:
        return []

    results = []
    for i, scr in enumerate(scrs):
        out_dxf = out_dir / scr.with_suffix('.dxf').name
        if out_dxf.exists() and out_dxf.stat().st_size > 10_000:
            print(f"  [{i+1}/{len(scrs)}] {scr.name} → SKIP (já existe)")
            results.append({'scr': scr.name, 'dxf': out_dxf.name, 'size': out_dxf.stat().st_size, 'status': 'SKIP'})
            continue

        print(f"  [{i+1}/{len(scrs)}] {scr.name}...", end=' ', flush=True)
        sz = run_scr_autocad(acad, scr, out_dxf)

        if sz > 5_000:
            status = 'OK'
            print(f"OK ({sz//1024}KB)")
        else:
            status = 'FAIL'
            print(f"FAIL ({sz}B)")

        results.append({'scr': scr.name, 'dxf': out_dxf.name, 'size': sz, 'status': status})

    ok = sum(1 for r in results if r['status'] == 'OK')
    skip = sum(1 for r in results if r['status'] == 'SKIP')
    fail = sum(1 for r in results if r['status'] == 'FAIL')
    print(f"\n  {tipo}: OK={ok} SKIP={skip} FAIL={fail} / {len(results)}")

    # Salva resumo
    resumo_path = out_dir / f'ground_truth_{tipo.lower()}_resumo.json'
    with open(resumo_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tipo', choices=['CIMA', 'ABCD', 'GRADES', 'LV', 'VC', 'ALL'], default='ALL')
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--max', type=int, default=999)
    parser.add_argument('--dry-run', action='store_true', help='Listar sem executar')
    args = parser.parse_args()

    print(f"=== GROUND TRUTH BATCH === DRY={'YES' if args.dry_run else 'NO'}")
    print(f"Output: {GROUND_TRUTH_DIR}")
    print(f"MOLDE: {MOLDE_PL}")

    tipos = ['CIMA', 'ABCD', 'GRADES', 'LV', 'VC'] if args.tipo == 'ALL' else [args.tipo]

    all_results = {}
    for tipo in tipos:
        r = batch_tipo(tipo, args.start, args.max, args.dry_run)
        all_results[tipo] = r

    if not args.dry_run:
        # Resumo geral
        print("\n=== RESUMO FINAL ===")
        for tipo, results in all_results.items():
            if results:
                ok = sum(1 for r in results if r['status'] in ('OK', 'SKIP'))
                print(f"  {tipo}: {ok}/{len(results)} disponíveis")


if __name__ == '__main__':
    main()
