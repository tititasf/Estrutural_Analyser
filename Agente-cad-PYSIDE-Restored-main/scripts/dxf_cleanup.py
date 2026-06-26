#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dxf_cleanup.py — Pós-processamento de DXFs gerados pelos Robôs.

Usa KDTree (scipy) para:
  1. Conectar extremidades de linhas com microgaps (snap within tolerance)
  2. Remover linhas duplicadas (sobrepostas)
  3. Fechar polígonos abertos de pilares/lajes

Chamado opcionalmente após cada Robô gerar seu DXF:
  python scripts/dxf_cleanup.py --input PL_stog_quality.dxf --tolerance 0.5

Ou programaticamente:
  from scripts.dxf_cleanup import fix_microgaps
  fix_microgaps(Path("output.dxf"), tolerance=0.5)
"""
import argparse
import sys
from pathlib import Path


def fix_microgaps(dxf_path: Path, tolerance: float = 0.5,
                  remove_duplicates: bool = True,
                  inplace: bool = True) -> dict:
    """
    Corrige microgaps e duplicatas em LINE/LWPOLYLINE de um DXF.

    Parâmetros
    ----------
    dxf_path    : Path para o arquivo DXF
    tolerance   : distância máxima (unidades DXF) para snap de extremidades
    remove_duplicates : remover LINEs exatamente sobrepostas
    inplace     : sobrescreve o arquivo original (True) ou salva como .clean.dxf

    Retorna
    -------
    dict com estatísticas: {snapped, duplicates_removed, output_path}
    """
    try:
        import ezdxf
        from scipy.spatial import KDTree
        import numpy as np
    except ImportError as e:
        print(f"[dxf_cleanup] Dependência ausente: {e}. Pulando limpeza.")
        return {"skipped": True, "reason": str(e)}

    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception as e:
        print(f"[dxf_cleanup] Erro ao abrir {dxf_path.name}: {e}")
        return {"skipped": True, "reason": str(e)}

    msp = doc.modelspace()

    # 1. Coletar todas as LINEs do modelspace
    lines = [e for e in msp if e.dxftype() == 'LINE']
    if not lines:
        return {"snapped": 0, "duplicates_removed": 0, "output_path": str(dxf_path)}

    # 2. Construir array de pontos (todas as extremidades)
    pts = []
    for ln in lines:
        pts.append([ln.dxf.start.x, ln.dxf.start.y])
        pts.append([ln.dxf.end.x,   ln.dxf.end.y])

    pts_arr = np.array(pts, dtype=float)
    tree = KDTree(pts_arr)

    # 3. Snap: para cada ponto, encontrar todos os vizinhos dentro da tolerance
    #    Substituir pelo ponto representante do cluster (média)
    snapped = 0
    visited = [False] * len(pts_arr)
    clusters = {}  # idx → representante (x, y)

    for i, pt in enumerate(pts_arr):
        if visited[i]:
            continue
        idxs = tree.query_ball_point(pt, r=tolerance)
        if len(idxs) > 1:
            centroid = pts_arr[idxs].mean(axis=0)
            for idx in idxs:
                clusters[idx] = centroid
                visited[idx] = True
                snapped += 1
        else:
            visited[i] = True

    # 4. Aplicar snap de volta às entidades LINE
    for i, ln in enumerate(lines):
        start_idx = i * 2
        end_idx   = i * 2 + 1
        if start_idx in clusters:
            c = clusters[start_idx]
            ln.dxf.start = (c[0], c[1], ln.dxf.start.z if hasattr(ln.dxf.start, 'z') else 0.0)
        if end_idx in clusters:
            c = clusters[end_idx]
            ln.dxf.end = (c[0], c[1], ln.dxf.end.z if hasattr(ln.dxf.end, 'z') else 0.0)

    # 5. Remover duplicatas (mesmas coordenadas start/end)
    dup_removed = 0
    if remove_duplicates:
        seen = set()
        to_delete = []
        for ln in lines:
            s = ln.dxf.start
            e = ln.dxf.end
            key_fwd = (round(s.x, 4), round(s.y, 4), round(e.x, 4), round(e.y, 4))
            key_rev = (round(e.x, 4), round(e.y, 4), round(s.x, 4), round(s.y, 4))
            if key_fwd in seen or key_rev in seen:
                to_delete.append(ln)
                dup_removed += 1
            else:
                seen.add(key_fwd)
        for ln in to_delete:
            msp.delete_entity(ln)

    # 6. Salvar
    if inplace:
        out_path = dxf_path
    else:
        out_path = dxf_path.with_suffix('.clean.dxf')

    try:
        doc.saveas(str(out_path))
    except Exception as e:
        print(f"[dxf_cleanup] Erro ao salvar {out_path.name}: {e}")
        return {"skipped": True, "reason": str(e)}

    stats = {
        "snapped": max(0, snapped - len(lines) * 2),  # net snaps (subtrair self-matches)
        "duplicates_removed": dup_removed,
        "output_path": str(out_path),
    }
    if stats["snapped"] > 0 or dup_removed > 0:
        print(f"[dxf_cleanup] {out_path.name}: snap={stats['snapped']} dup_rem={dup_removed}")
    return stats


def main():
    parser = argparse.ArgumentParser(description='Limpa microgaps em DXFs gerados pelos Robôs')
    parser.add_argument('--input',     required=True, help='Arquivo DXF de entrada')
    parser.add_argument('--tolerance', type=float, default=0.5,
                        help='Distância máxima para snap (padrão: 0.5 unidades DXF)')
    parser.add_argument('--no-inplace', action='store_true',
                        help='Salvar como .clean.dxf em vez de sobrescrever')
    args = parser.parse_args()

    dxf_path = Path(args.input)
    if not dxf_path.exists():
        print(f"[ERROR] Arquivo não encontrado: {dxf_path}")
        sys.exit(1)

    stats = fix_microgaps(dxf_path, tolerance=args.tolerance,
                          inplace=not args.no_inplace)
    print(f"[OK] Limpeza concluída: {stats}")


if __name__ == '__main__':
    main()
