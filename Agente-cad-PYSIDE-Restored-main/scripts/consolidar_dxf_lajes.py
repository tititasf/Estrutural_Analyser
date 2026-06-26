#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
consolidar_dxf_lajes.py — Consolida DXFs individuais de lajes em LJ_gerado.dxf.

Requer:
  - Fase-5_Geracao_Scripts/DXF_Lajes/L*.dxf
  - Fase-3_Interpretacao_Extracao/ancoras_lajes.json

Saída:
  - Fase-6_Execucao_CAD/LJ_gerado.dxf

CLI:
  python scripts/consolidar_dxf_lajes.py --obra DADOS-OBRAS/Obra_TREINO_21
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("[ERROR] ezdxf não encontrado. Instale: pip install ezdxf")
    sys.exit(1)


def transferir_com_offset(src_msp, dst_msp, offset_x: float, offset_y: float) -> int:
    count = 0
    for entity in src_msp:
        tipo = entity.dxftype()
        try:
            if tipo == 'LWPOLYLINE':
                pts = list(entity.get_points('xyb'))
                new_pts = [(x + offset_x, y + offset_y, b) for x, y, b in pts]
                e = dst_msp.add_lwpolyline(new_pts, close=entity.closed)
                e.dxf.layer = entity.dxf.layer
                count += 1
            elif tipo == 'LINE':
                s, en = entity.dxf.start, entity.dxf.end
                e = dst_msp.add_line(
                    (s.x + offset_x, s.y + offset_y),
                    (en.x + offset_x, en.y + offset_y)
                )
                e.dxf.layer = entity.dxf.layer
                count += 1
            elif tipo == 'TEXT':
                ins = entity.dxf.insert
                e = dst_msp.add_text(
                    entity.dxf.text or '',
                    dxfattribs={
                        'insert': (ins.x + offset_x, ins.y + offset_y),
                        'height': entity.dxf.height if hasattr(entity.dxf, 'height') else 1.0,
                        'layer': entity.dxf.layer,
                    }
                )
                count += 1
            elif tipo == 'MTEXT':
                ins = entity.dxf.insert
                try:
                    txt = entity.plain_text()
                except AttributeError:
                    txt = getattr(entity.dxf, 'text', '') or ''
                char_h = entity.dxf.char_height if hasattr(entity.dxf, 'char_height') else 1.0
                e = dst_msp.add_mtext(txt, dxfattribs={
                    'insert': (ins.x + offset_x, ins.y + offset_y),
                    'char_height': char_h,
                    'layer': entity.dxf.layer,
                })
                count += 1
        except Exception:
            pass
    return count


def consolidar_lajes(obra_path: str) -> None:
    obra = Path(obra_path)
    dxf_lajes_dir = obra / "Fase-5_Geracao_Scripts" / "DXF_Lajes"
    ancoras_path = obra / "Fase-3_Interpretacao_Extracao" / "ancoras_lajes.json"
    fase6_dir = obra / "Fase-6_Execucao_CAD"
    fase6_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] === consolidar_dxf_lajes.py | {obra.name} ===")

    if not dxf_lajes_dir.exists():
        print(f"[ERROR] DXF_Lajes/ não encontrado: {dxf_lajes_dir}")
        sys.exit(1)

    if not ancoras_path.exists():
        print(f"[ERROR] ancoras_lajes.json não encontrado: {ancoras_path}")
        sys.exit(1)

    with open(ancoras_path, encoding='utf-8') as f:
        ancoras = json.load(f)

    dst_doc = ezdxf.new('R2010')
    dst_msp = dst_doc.modelspace()

    dxf_files = sorted(dxf_lajes_dir.glob("L*.dxf"),
                        key=lambda p: int(''.join(filter(str.isdigit, p.stem)) or '999'))

    ok_count = 0
    sem_ancora = []
    y_fallback = 0.0
    SPACING = 1000.0

    for dxf_file in dxf_files:
        lid = dxf_file.stem.upper()  # "L1", "L7", etc.

        if lid in ancoras:
            anc = ancoras[lid]
            ox, oy = anc[0], anc[1]
        else:
            sem_ancora.append(lid)
            ox, oy = 0, y_fallback
            y_fallback -= SPACING

        try:
            src_doc = ezdxf.readfile(str(dxf_file))

            # Calcular centróide local da laje para centralização
            pts_x, pts_y = [], []
            for e in src_doc.modelspace():
                if e.dxftype() == 'LWPOLYLINE':
                    for pt in e.get_points('xy'):
                        pts_x.append(pt[0])
                        pts_y.append(pt[1])
            if pts_x:
                cx = (min(pts_x) + max(pts_x)) / 2
                cy = (min(pts_y) + max(pts_y)) / 2
                final_ox = ox - cx
                final_oy = oy - cy
            else:
                final_ox, final_oy = ox, oy

            n = transferir_com_offset(src_doc.modelspace(), dst_msp, final_ox, final_oy)
            ok_count += 1
            print(f"  {lid}: ancora=({ox:.0f},{oy:.0f}) [{n} ents]")

        except Exception as ex:
            print(f"  [ERRO] {dxf_file.name}: {ex}")

    out_path = fase6_dir / "LJ_gerado.dxf"
    dst_doc.saveas(str(out_path))

    try:
        check = ezdxf.readfile(str(out_path))
        total = sum(1 for _ in check.modelspace())
    except:
        total = 0

    print(f"\n[RESULTADO]")
    print(f"  Lajes consolidadas: {ok_count}/{len(dxf_files)}")
    if sem_ancora:
        print(f"  Sem ancora: {sem_ancora}")
    print(f"  LJ_gerado.dxf: {total} entidades")
    print(f"  Output: {out_path}")

    report = {
        "lajes_consolidadas": ok_count,
        "total_dxf": len(dxf_files),
        "sem_ancora": sem_ancora,
        "output": str(out_path),
        "aprovado": ok_count >= int(len(dxf_files) * 0.90),
    }
    with open(fase6_dir / "consolidacao_lajes.json", 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', required=True)
    parser.add_argument('--pavimento', default='12 PAV')
    args = parser.parse_args()
    consolidar_lajes(args.obra)


if __name__ == '__main__':
    main()
