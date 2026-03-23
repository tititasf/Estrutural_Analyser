#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
consolidar_dxf_pilares.py — Consolida DXFs individuais de pilares em um
único DXF coletivo (PL_gerado.dxf) posicionando cada pilar nas coordenadas
absolutas do STOG original.

Requer:
  - Fase-5_Geracao_Scripts/DXF_Pilares/P*.dxf (gerados por gerar_dxf_pilares.py)
  - Fase-3_Interpretacao_Extracao/ancoras_pilares.json (gerado por extrair_ancoras_dxf.py)

Saída:
  - Fase-6_Execucao_CAD/PL_gerado.dxf

CLI:
  python scripts/consolidar_dxf_pilares.py --obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV"
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import ezdxf
    from ezdxf.math import Vec2, Vec3
except ImportError:
    print("[ERROR] ezdxf não encontrado. Instale: pip install ezdxf")
    sys.exit(1)


def transferir_entidades(src_msp, dst_doc, dst_msp, offset_x: float, offset_y: float,
                         escala: float = 1.0) -> int:
    """
    Copia todas as entidades do modelo fonte para o destino, aplicando translação.
    Retorna número de entidades copiadas.
    """
    from ezdxf import colors
    import copy

    count = 0
    for entity in src_msp:
        tipo = entity.dxftype()

        if tipo == 'LWPOLYLINE':
            pts = list(entity.get_points('xyb'))
            new_pts = [(x + offset_x, y + offset_y, b) for x, y, b in pts]
            new_e = dst_msp.add_lwpolyline(new_pts, close=entity.closed)
            new_e.dxf.layer = entity.dxf.layer
            if hasattr(entity.dxf, 'color') and entity.dxf.color:
                new_e.dxf.color = entity.dxf.color
            count += 1

        elif tipo == 'LINE':
            start = entity.dxf.start
            end = entity.dxf.end
            new_e = dst_msp.add_line(
                (start.x + offset_x, start.y + offset_y),
                (end.x + offset_x, end.y + offset_y)
            )
            new_e.dxf.layer = entity.dxf.layer
            count += 1

        elif tipo == 'TEXT':
            try:
                ins = entity.dxf.insert
                txt = entity.dxf.text or ''
                new_e = dst_msp.add_text(
                    txt,
                    dxfattribs={
                        'insert': (ins.x + offset_x, ins.y + offset_y),
                        'height': entity.dxf.height if hasattr(entity.dxf, 'height') else 1.0,
                        'layer': entity.dxf.layer,
                    }
                )
                count += 1
            except Exception:
                pass

        elif tipo == 'MTEXT':
            try:
                ins = entity.dxf.insert
                try:
                    raw_txt = entity.plain_text()
                except AttributeError:
                    raw_txt = getattr(entity.dxf, 'text', '') or ''
                char_h = entity.dxf.char_height if hasattr(entity.dxf, 'char_height') else 1.0
                new_e = dst_msp.add_mtext(
                    raw_txt,
                    dxfattribs={
                        'insert': (ins.x + offset_x, ins.y + offset_y),
                        'char_height': char_h,
                        'layer': entity.dxf.layer,
                    }
                )
                count += 1
            except Exception:
                pass

        elif tipo == 'INSERT':
            # Block insert — copiar com offset
            try:
                ins = entity.dxf.insert
                new_e = dst_msp.add_blockref(
                    entity.dxf.name,
                    (ins.x + offset_x, ins.y + offset_y)
                )
                new_e.dxf.layer = entity.dxf.layer
                count += 1
            except Exception:
                pass

        elif tipo == 'DIMENSION':
            # Dimensions são complexas — skip por ora
            pass

        elif tipo == 'HATCH':
            # Hatch — skip por ora
            pass

        # outros tipos: skip silencioso

    return count


def consolidar_pilares(obra_path: str, pavimento: str) -> None:
    obra = Path(obra_path)

    # Paths
    dxf_pilares_dir = obra / "Fase-5_Geracao_Scripts" / "DXF_Pilares"
    ancoras_path = obra / "Fase-3_Interpretacao_Extracao" / "ancoras_pilares.json"
    fase6_dir = obra / "Fase-6_Execucao_CAD"
    fase6_dir.mkdir(parents=True, exist_ok=True)
    out_path = fase6_dir / "PL_gerado.dxf"

    print(f"[INFO] === consolidar_dxf_pilares.py | {obra.name} | {pavimento} ===")

    # Validar entradas
    if not dxf_pilares_dir.exists():
        print(f"[ERROR] DXF_Pilares/ não encontrado: {dxf_pilares_dir}")
        print(f"        Execute: python scripts/gerar_dxf_pilares.py --obra {obra_path}")
        sys.exit(1)

    if not ancoras_path.exists():
        print(f"[ERROR] ancoras_pilares.json não encontrado: {ancoras_path}")
        print(f"        Execute: python scripts/extrair_ancoras_dxf.py --obra {obra_path}")
        sys.exit(1)

    with open(ancoras_path, encoding='utf-8') as f:
        ancoras = json.load(f)

    # Criar DXF coletivo
    dst_doc = ezdxf.new('R2010')
    dst_msp = dst_doc.modelspace()

    # Adicionar layers do pilar ao documento destino
    for layer_name in ['Paineis', 'Texto Seção', 'Cota Seção (2x)', 'HACHURA', '0']:
        if layer_name not in dst_doc.layers:
            dst_doc.layers.add(layer_name)

    # Processar cada pilar
    dxf_files = sorted(dxf_pilares_dir.glob("P*.dxf"),
                        key=lambda p: int(p.stem[1:]) if p.stem[1:].isdigit() else 999)

    ok_count = 0
    sem_ancora = []
    erros = []

    for dxf_file in dxf_files:
        pid = dxf_file.stem  # "P1", "P9", etc.

        if pid not in ancoras:
            sem_ancora.append(pid)
            continue

        ancora = ancoras[pid]
        offset_x = ancora[0]
        offset_y = ancora[1]

        try:
            src_doc = ezdxf.readfile(str(dxf_file))
            src_msp = src_doc.modelspace()

            # Calcular bbox do DXF individual para centralizar no anchor
            # (o pilar individual está em coords locais próximas de 0,0)
            # Encontrar centróide do pilar individual
            pts_x, pts_y = [], []
            for e in src_msp:
                if e.dxftype() == 'LWPOLYLINE':
                    for pt in e.get_points('xy'):
                        pts_x.append(pt[0])
                        pts_y.append(pt[1])
            if pts_x:
                local_cx = (min(pts_x) + max(pts_x)) / 2
                local_cy = (min(pts_y) + max(pts_y)) / 2
                # Ajuste para centralizar o pilar na âncora
                final_offset_x = offset_x - local_cx
                final_offset_y = offset_y - local_cy
            else:
                final_offset_x = offset_x
                final_offset_y = offset_y

            n = transferir_entidades(src_msp, dst_doc, dst_msp, final_offset_x, final_offset_y)
            ok_count += 1
            print(f"  {pid}: ancora=({offset_x:.0f},{offset_y:.0f}) offset=({final_offset_x:.0f},{final_offset_y:.0f}) [{n} ents]")

        except Exception as ex:
            erros.append(f"{pid}: {ex}")
            print(f"  [ERRO] {pid}: {ex}")

    # Salvar
    dst_doc.saveas(str(out_path))

    # Relatório
    print(f"\n[RESULTADO]")
    print(f"  Pilares consolidados: {ok_count}/{len(dxf_files)}")
    if sem_ancora:
        print(f"  Sem ancora: {sem_ancora}")
    if erros:
        print(f"  Erros: {erros}")
    print(f"  Output: {out_path}")

    # Validação básica: abrir o DXF gerado e contar entidades
    try:
        check_doc = ezdxf.readfile(str(out_path))
        check_msp = check_doc.modelspace()
        total_ents = sum(1 for _ in check_msp)
        print(f"  Validação: {total_ents} entidades no PL_gerado.dxf")
    except Exception as ex:
        print(f"  [WARN] Erro na validação: {ex}")

    # Salvar relatório JSON
    report = {
        "pilares_consolidados": ok_count,
        "total_dxf_files": len(dxf_files),
        "sem_ancora": sem_ancora,
        "erros": erros,
        "output": str(out_path),
        "aprovado": ok_count >= int(len(dxf_files) * 0.95),
    }
    report_path = fase6_dir / "consolidacao_pilares.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  Relatório: {report_path}")


def main():
    parser = argparse.ArgumentParser(description='Consolida DXF individuais de pilares em PL_gerado.dxf')
    parser.add_argument('--obra', required=True, help='Path da obra')
    parser.add_argument('--pavimento', default='12 PAV', help='Pavimento (default: "12 PAV")')
    args = parser.parse_args()

    consolidar_pilares(args.obra, args.pavimento)


if __name__ == '__main__':
    main()
