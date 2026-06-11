#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
consolidar_dxf_vigas.py — Consolida DXFs individuais de vigas em
LV_gerado.dxf (laterais) e FV_gerado.dxf (fundos).

Requer:
  - Fase-5_Geracao_Scripts/DXF_Vigas/V*.dxf
  - Fase-3_Interpretacao_Extracao/ancoras_vigas.json

Saída:
  - Fase-6_Execucao_CAD/LV_gerado.dxf
  - Fase-6_Execucao_CAD/FV_gerado.dxf

CLI:
  python scripts/consolidar_dxf_vigas.py --obra DADOS-OBRAS/Obra_TREINO_21
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


def _setup_dimstyle_cota_vig(doc):
    """Garante que o dimstyle COTA_VIG existe no documento destino."""
    if "COTA_VIG" not in doc.dimstyles:
        ds = doc.dimstyles.new("COTA_VIG")
        ds.dxf.dimtxt  = 7.0
        ds.dxf.dimasz  = 3.5
        ds.dxf.dimscale = 1.0
        ds.dxf.dimexo  = 2.0
        ds.dxf.dimexe  = 2.0
        ds.dxf.dimgap  = 1.5
        ds.dxf.dimdec  = 1
        ds.dxf.dimrnd  = 0
        ds.dxf.dimclrd = 3
        ds.dxf.dimclre = 3
        ds.dxf.dimclrt = 3


def transferir_com_offset(src_msp, dst_msp, offset_x: float, offset_y: float) -> int:
    """Copia entidades com translação. Retorna count copiados."""
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
            elif tipo == 'DIMENSION':
                # Recria dimensão linear com pontos transladados
                # dimtype & 0x0F: 0=horizontal, 1=vertical, 2=angular, 3=diâmetro, 4=raio
                dimtype = getattr(entity.dxf, 'dimtype', 0) & 0x0F
                if dimtype not in (0, 1):
                    continue  # só dimensões lineares (horizontal/vertical)
                dp  = entity.dxf.defpoint   # ponto da linha de cota
                dp2 = entity.dxf.defpoint2  # origem extensão 1
                dp3 = entity.dxf.defpoint3  # origem extensão 2
                layer = getattr(entity.dxf, 'layer', 'COTA')
                angle = 90 if dimtype == 1 else 0
                d = dst_msp.add_linear_dim(
                    base=(dp.x  + offset_x, dp.y  + offset_y),
                    p1  =(dp2.x + offset_x, dp2.y + offset_y),
                    p2  =(dp3.x + offset_x, dp3.y + offset_y),
                    angle=angle,
                    dimstyle="COTA_VIG",
                    dxfattribs={"layer": layer},
                )
                d.render()
                count += 1
        except Exception:
            pass
    return count


def consolidar_vigas(obra_path: str, pavimento: str) -> None:
    obra = Path(obra_path)
    dxf_vigas_dir = obra / "Fase-5_Geracao_Scripts" / "DXF_Vigas"
    ancoras_path = obra / "Fase-3_Interpretacao_Extracao" / "ancoras_vigas.json"
    fase6_dir = obra / "Fase-6_Execucao_CAD"
    fase6_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] === consolidar_dxf_vigas.py | {obra.name} ===")

    if not dxf_vigas_dir.exists():
        print(f"[ERROR] DXF_Vigas/ não encontrado: {dxf_vigas_dir}")
        sys.exit(1)

    if not ancoras_path.exists():
        print(f"[ERROR] ancoras_vigas.json não encontrado: {ancoras_path}")
        sys.exit(1)

    with open(ancoras_path, encoding='utf-8') as f:
        ancoras = json.load(f)

    # ── DXF LV (laterais A + B) ────────────────────────────────
    lv_doc = ezdxf.new('R2010')
    lv_msp = lv_doc.modelspace()
    _setup_dimstyle_cota_vig(lv_doc)
    lv_doc.layers.new("COTA").color = 3

    # ── DXF FV (fundos) ────────────────────────────────────────
    fv_doc = ezdxf.new('R2010')
    fv_msp = fv_doc.modelspace()
    _setup_dimstyle_cota_vig(fv_doc)
    fv_doc.layers.new("COTA").color = 3

    # Os DXFs de vigas são V{n}.dxf — um DXF por viga com todas as vistas
    dxf_files = sorted(dxf_vigas_dir.glob("V*.dxf"),
                        key=lambda p: int(''.join(filter(str.isdigit, p.stem)) or '999'))

    ok_lv = 0
    sem_ancora = []
    y_fallback = 0.0
    SPACING = 600.0

    for dxf_file in dxf_files:
        vid = dxf_file.stem.upper()  # "V1", "V2", etc.

        # Obter âncora — suporta formato dict {'A': [x,y]} (legado) e list [x,y] (novo)
        if vid in ancoras:
            raw_anc = ancoras[vid]
            if isinstance(raw_anc, list):
                ox, oy = raw_anc[0], raw_anc[1]
            elif isinstance(raw_anc, dict):
                anc = raw_anc.get('A') or raw_anc.get('B') or next(iter(raw_anc.values()), None)
                if anc:
                    ox, oy = anc[0], anc[1]
                else:
                    ox, oy = 0, y_fallback
                    y_fallback -= SPACING
            else:
                ox, oy = 0, y_fallback
                y_fallback -= SPACING
        else:
            sem_ancora.append(vid)
            ox, oy = 0, y_fallback
            y_fallback -= SPACING

        try:
            src_doc = ezdxf.readfile(str(dxf_file))
            src_msp = src_doc.modelspace()

            # Calcular centróide local
            pts_x, pts_y = [], []
            for e in src_msp:
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

            n = transferir_com_offset(src_msp, lv_msp, final_ox, final_oy)
            # Copiar também para FV (mesmas entidades — view combinada)
            transferir_com_offset(src_doc.modelspace(), fv_msp, final_ox, final_oy - 2000)
            ok_lv += 1
            print(f"  {vid}: ancora=({ox:.0f},{oy:.0f}) [{n} ents]")

        except Exception as ex:
            print(f"  [ERRO] {dxf_file.name}: {ex}")

    # Salvar
    lv_path = fase6_dir / "LV_gerado.dxf"
    fv_path = fase6_dir / "FV_gerado.dxf"
    lv_doc.saveas(str(lv_path))
    fv_doc.saveas(str(fv_path))

    def count_ents(path):
        try:
            doc = ezdxf.readfile(str(path))
            return sum(1 for _ in doc.modelspace())
        except:
            return 0

    print(f"\n[RESULTADO]")
    print(f"  LV_gerado.dxf: {ok_lv} vigas ({count_ents(lv_path)} entidades)")
    print(f"  FV_gerado.dxf: {ok_lv} vigas offset ({count_ents(fv_path)} entidades)")
    if sem_ancora:
        print(f"  Sem ancora: {sem_ancora}")

    ok_fv = ok_lv
    report = {
        "lv_consolidados": ok_lv, "fv_consolidados": ok_fv,
        "sem_ancora": sem_ancora,
        "lv_output": str(lv_path), "fv_output": str(fv_path),
        "aprovado": ok_lv >= 25,
    }
    with open(fase6_dir / "consolidacao_vigas.json", 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', required=True)
    parser.add_argument('--pavimento', default='12 PAV')
    args = parser.parse_args()
    consolidar_vigas(args.obra, args.pavimento)


if __name__ == '__main__':
    main()
