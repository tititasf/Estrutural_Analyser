"""
Diagnóstico de visões de corte — PAV 13.
Lê DB, imprime fichas de cada cut_view_geom, identifica WRN e duplicatas.
"""
from __future__ import annotations
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")


def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    proj_id = '4869be2b-f17c-410b-a9c8-98a887ec1c95'
    cur.execute("SELECT name FROM projects WHERE id=?", (proj_id,))
    row = cur.fetchone()
    if not row:
        print("Projeto não encontrado"); return
    proj_name = row[0]
    print(f"Projeto: {proj_name} ({proj_id})")

    cur.execute(
        "SELECT name, links_json FROM slabs WHERE project_id=? ORDER BY name",
        (proj_id,)
    )
    slab_rows = cur.fetchall()
    slabs = []
    for name, lj in slab_rows:
        links = json.loads(lj) if lj else {}
        slabs.append({'name': name, 'links': links})
    print(f"\nPAV 13 — {len(slabs)} lajes\n")

    total = 0
    wrn_list = []
    pos_seen: dict[tuple, list] = {}  # centroid → list of (slab_name, entry_info)

    for slab in slabs:
        sname = slab.get('name') or '?'
        links = slab.get('links') or {}
        cut_links = links.get('laje_visao_corte') or {}
        if not isinstance(cut_links, dict):
            continue
        geom_list = cut_links.get('cut_view_geom') or []

        for cut in geom_list:
            if not isinstance(cut, dict):
                continue
            pts = cut.get('points') or []
            n_pts = len(pts)
            ext = cut.get('extended_by_companion', False)
            ficha = cut.get('ficha') or {}
            bh = ficha.get('beam_height') or '—'
            sv = ficha.get('scale_v') or '1.0'
            own_h = ficha.get('own_slab_height') or '—'
            own_dt = ficha.get('own_dist_top') or '—'
            own_df = ficha.get('own_dist_bottom') or '—'
            neigh_h = ficha.get('neigh_slab_height') or '—'
            neigh_dt = ficha.get('neighbor_dist_top') or '—'
            neigh_df = ficha.get('neighbor_dist_bottom') or '—'
            direc = ficha.get('direction') or '—'
            sa = ficha.get('side_a_laje_name') or '—'
            sb = ficha.get('side_b_laje_name') or '—'
            total += 1

            # centroid
            try:
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                cx = round((min(xs) + max(xs)) / 2.0)
                cy = round((min(ys) + max(ys)) / 2.0)
                cpos = (cx, cy)
            except Exception:
                cpos = None

            # Detect WRN: inconsistência h+dt+df ≠ bh
            status = 'OK'
            try:
                bh_f = float(bh)
                oh_f = float(own_h)
                odt_f = float(own_dt)
                odf_f = float(own_df)
                own_sum = oh_f + odt_f + odf_f
                if abs(own_sum - bh_f) > 2.0:
                    status = 'WRN-own'
                try:
                    nh_f = float(neigh_h)
                    ndt_f = float(neigh_dt)
                    ndf_f = float(neigh_df)
                    neigh_sum = nh_f + ndt_f + ndf_f
                    if abs(neigh_sum - bh_f) > 2.0:
                        status = 'WRN-neigh' if status == 'OK' else 'WRN-both'
                except Exception:
                    pass
            except Exception:
                status = 'skip'

            label = f"{sname}/{direc} sA={sa} sB={sb} bh={bh} sv={sv} pts={n_pts} ext={ext}"
            own_str = f"own(h={own_h},dt={own_dt},df={own_df})"
            neigh_str = f"neigh(h={neigh_h},dt={neigh_dt},df={neigh_df})"

            if status != 'OK':
                wrn_list.append(f"[{status}] {label}")
                wrn_list.append(f"         {own_str} {neigh_str}")

            if cpos:
                pos_seen.setdefault(cpos, []).append(f"{sname}/{direc}(pts={n_pts})")

    print(f"Total entries: {total}")

    # Duplicatas por centroide
    dups = {pos: entries for pos, entries in pos_seen.items() if len(entries) > 1}
    print(f"Posições únicas: {len(pos_seen)} — com duplicata: {len(dups)}\n")
    if dups:
        print("=== DUPLICATAS ===")
        for pos, entries in sorted(dups.items()):
            print(f"  {pos}: {entries}")

    print(f"\n=== WRN ({len(wrn_list)//2 if wrn_list else 0}) ===")
    for line in wrn_list:
        print(line)

    con.close()


if __name__ == '__main__':
    main()
