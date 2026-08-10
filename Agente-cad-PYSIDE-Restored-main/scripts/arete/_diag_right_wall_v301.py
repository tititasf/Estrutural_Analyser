# -*- coding: utf-8 -*-
"""Dump V/H na zona direita (body_end - 5 .. full) N2 vs N4 V301.A/B."""
from __future__ import annotations

import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import ezdxf

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent))

from arete.geometry_lv_units import pair_units, split_n4_view, unit_label  # noqa: E402
from arete.gerar_lv_n4_fichas import _entry_from_live_recorte  # noqa: E402
from gerar_lv_dxf_stog import (  # noqa: E402
    _degrau_shoulder_y,
    _marco_extension_cm,
    _small_panel_start_x,
    select_canonical_face_units,
)

DB = Path(r"D:\Agente-cad-PYSIDE\project_data.vision")
N4_DIR = Path(
    r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-6_Execucao_CAD\n4"
)


def resolve_n2(item: str) -> Path:
    conn = sqlite3.connect(str(DB))
    row = conn.execute(
        "SELECT recorte_path FROM reverse_eng_recortes "
        "WHERE UPPER(elemento_id)=? AND UPPER(classe)='LV' "
        "ORDER BY id DESC LIMIT 1",
        (item.upper(),),
    ).fetchone()
    conn.close()
    return Path(row[0])


def segs_in_zone(path: Path, x_lo: float, x_hi: float, y_lo: float, y_hi: float, *, layers=None):
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    vs, hs = [], []
    for e in msp:
        if e.dxftype() != "LINE":
            continue
        if layers and e.dxf.layer not in layers:
            continue
        s, t = e.dxf.start, e.dxf.end
        x1, y1, x2, y2 = float(s.x), float(s.y), float(t.x), float(t.y)
        mx, my = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
        if not (x_lo - 1 <= mx <= x_hi + 1 and y_lo - 2 <= my <= y_hi + 2):
            # still allow long V that span zone even if mid outside
            if abs(x1 - x2) < 0.4:
                if not (x_lo - 1 <= x1 <= x_hi + 1):
                    continue
                if max(y1, y2) < y_lo - 2 or min(y1, y2) > y_hi + 2:
                    continue
            elif abs(y1 - y2) < 0.4:
                if not (y_lo - 2 <= y1 <= y_hi + 2):
                    continue
                if max(x1, x2) < x_lo - 1 or min(x1, x2) > x_hi + 1:
                    continue
            else:
                continue
        layer = e.dxf.layer
        if abs(x1 - x2) < 0.4:
            yb, yt = min(y1, y2), max(y1, y2)
            vs.append((round(x1, 2), round(yb, 2), round(yt, 2), round(yt - yb, 2), layer))
        elif abs(y1 - y2) < 0.4:
            xl, xr = min(x1, x2), max(x1, x2)
            hs.append((round(y1, 2), round(xl, 2), round(xr, 2), round(xr - xl, 2), layer))
    vs.sort()
    hs.sort()
    return vs, hs


def n2_bbox_origin(u: dict):
    ox = float(u.get("origin_x") or u.get("x0") or 0)
    oy = float(u.get("origin_y") or u.get("y0") or 0)
    # face_units may store bbox
    if "bbox" in u and u["bbox"]:
        b = u["bbox"]
        if isinstance(b, (list, tuple)) and len(b) >= 4:
            return float(b[0]), float(b[1])
    for k in ("x_min", "xmin", "x"):
        if k in u and u[k] is not None:
            ox = float(u[k])
            break
    for k in ("y_min", "ymin", "y"):
        if k in u and u[k] is not None:
            oy = float(u[k])
            break
    return ox, oy


def main():
    item = "V301"
    n2_path = resolve_n2(item)
    entry = _entry_from_live_recorte(item)
    fus = select_canonical_face_units(entry.get("face_units") or [], item)
    n4a = N4_DIR / f"LV_preview_{item}_VIEW_A.dxf"
    n4b = N4_DIR / f"LV_preview_{item}_VIEW_B.dxf"
    n4_by = {
        "A": split_n4_view(n4a, "A"),
        "B": split_n4_view(n4b, "B"),
    }
    n2_by = {"A": [], "B": []}
    for i, u in enumerate(fus):
        side = str(u.get("side") or "?").upper()
        if side in n2_by:
            u = dict(u)
            u["_idx"] = i
            n2_by[side].append(u)

    print("N2", n2_path)
    layers = ("Painéis", "Paineis")

    for side in ("A", "B"):
        pairs = pair_units(n2_by[side], n4_by[side])
        n4_path = n4a if side == "A" else n4b
        for pr in pairs:
            if pr["status"] != "matched":
                continue
            u2, u4 = pr["n2"], pr["n4"]
            lab = unit_label(u2, u2.get("_idx", 0))
            if "V301" not in str(lab).upper() and "V301" not in str(u4.get("label", "")).upper():
                # still print primary V301-ish
                pass
            panels = u2.get("panels") or []
            widths = [float(p.get("width", 0) or 0) for p in panels]
            h = float(u2.get("h_body") or u2.get("h") or 0)
            x0 = 0.0
            y0 = 0.0
            small = _small_panel_start_x(x0, h, panels)
            body_end_local = float(small) if small is not None else sum(widths)
            full_end_local = sum(widths)
            marco_h = _marco_extension_cm(
                bool(u2.get("marco_laje_sup") or u2.get("marco")),
                float(u2.get("laje_sup") or 0),
            )
            # N4 anchors
            ox4, oy4 = u4["origin"]
            be4 = float(u4.get("body_end_x") or ox4 + body_end_local)
            fe4 = ox4 + full_end_local
            y_top4 = oy4 + float(u4.get("h_body") or h)
            y_marco4 = y_top4 + marco_h

            # N2: need absolute coords from face_unit
            # Prefer bbox from unit if present
            keys = sorted(u2.keys())
            print(f"\n{'='*70}")
            print(f"[{side}] {lab} ↔ {u4.get('label')} score={pr['score']}")
            print(f"  widths={ [round(w,1) for w in widths] }")
            print(f"  h={h:.1f} small_x={small} body_end_local={body_end_local:.1f} full={full_end_local:.1f} marco_h={marco_h:.1f}")
            print(f"  u2 keys sample: {[k for k in keys if any(x in k.lower() for x in ('x','y','orig','bbox','band','marco','laje','panel'))][:40]}")
            print(f"  N4 origin=({ox4:.2f},{oy4:.2f}) body_end={be4:.2f} full~={fe4:.2f} y_top={y_top4:.2f} y_marco={y_marco4:.2f}")

            # Zone: right wall region body_end-15 to full+20, y0 to y_marco+5
            z_lo = be4 - 20
            z_hi = max(fe4, be4) + 25
            y_lo = oy4 - 5
            y_hi = y_marco4 + 10

            vs4, hs4 = segs_in_zone(n4_path, z_lo, z_hi, y_lo, y_hi, layers=layers)
            print(f"\n  --- N4 Painéis V in x=[{z_lo:.1f},{z_hi:.1f}] ---")
            for v in vs4:
                print(f"    V x={v[0]:8.2f} y={v[1]:8.2f}->{v[2]:8.2f} L={v[3]:6.1f}  {v[4]}")
            print(f"  --- N4 Painéis H ---")
            for hseg in hs4:
                print(f"    H y={hseg[0]:8.2f} x={hseg[1]:8.2f}->{hseg[2]:8.2f} L={hseg[3]:6.1f}  {hseg[4]}")

            # N2 zone: need absolute origin of unit in recorte
            # Try common fields
            ox2 = oy2 = None
            for kx, ky in (
                ("origin_x", "origin_y"),
                ("x0", "y0"),
                ("x", "y"),
            ):
                if u2.get(kx) is not None and u2.get(ky) is not None:
                    ox2, oy2 = float(u2[kx]), float(u2[ky])
                    break
            if ox2 is None and u2.get("bbox"):
                b = u2["bbox"]
                ox2, oy2 = float(b[0]), float(b[1])
            if ox2 is None and u2.get("clip"):
                c = u2["clip"]
                if isinstance(c, dict):
                    ox2 = float(c.get("x0", c.get("xmin", 0)))
                    oy2 = float(c.get("y0", c.get("ymin", 0)))

            # dump a few unit fields that look like coords
            print(f"  N2 origin guess: ({ox2}, {oy2})")
            if ox2 is not None:
                be2 = ox2 + body_end_local
                fe2 = ox2 + full_end_local
                y_top2 = oy2 + h
                y_marco2 = y_top2 + marco_h
                z_lo2 = be2 - 20
                z_hi2 = fe2 + 25
                vs2, hs2 = segs_in_zone(
                    n2_path, z_lo2, z_hi2, oy2 - 5, y_marco2 + 10, layers=layers
                )
                print(f"  --- N2 Painéis V in x=[{z_lo2:.1f},{z_hi2:.1f}] ---")
                for v in vs2:
                    print(f"    V x={v[0]:8.2f} y={v[1]:8.2f}->{v[2]:8.2f} L={v[3]:6.1f}  {v[4]}")
                print(f"  --- N2 Painéis H ---")
                for hseg in hs2:
                    print(f"    H y={hseg[0]:8.2f} x={hseg[1]:8.2f}->{hseg[2]:8.2f} L={hseg[3]:6.1f}  {hseg[4]}")

                # relative compare (shift to local)
                def rel_v(vs, ox, oy):
                    return sorted(
                        {
                            (round(x - ox, 1), round(yb - oy, 1), round(yt - oy, 1), round(L, 1))
                            for x, yb, yt, L, _ in vs
                        }
                    )

                def rel_h(hs, ox, oy):
                    return sorted(
                        {
                            (round(y - oy, 1), round(xl - ox, 1), round(xr - ox, 1), round(L, 1))
                            for y, xl, xr, L, _ in hs
                        }
                    )

                rv2, rv4 = rel_v(vs2, ox2, oy2), rel_v(vs4, ox4, oy4)
                rh2, rh4 = rel_h(hs2, ox2, oy2), rel_h(hs4, ox4, oy4)
                print(f"\n  EXTRA V in N4 (local): {[v for v in rv4 if v not in rv2]}")
                print(f"  MISS  V in N4 (local): {[v for v in rv2 if v not in rv4]}")
                print(f"  EXTRA H in N4 (local): {[v for v in rh4 if v not in rh2]}")
                print(f"  MISS  H in N4 (local): {[v for v in rh2 if v not in rh4]}")
            else:
                # fall back: scan whole N2 for similar width pattern — dump rightmost cluster
                print("  (no N2 origin; dumping full N2 right-edge V with L>40)")
                doc = ezdxf.readfile(str(n2_path))
                msp = doc.modelspace()
                all_v = []
                for e in msp:
                    if e.dxftype() != "LINE" or e.dxf.layer not in layers:
                        continue
                    s, t = e.dxf.start, e.dxf.end
                    if abs(s.x - t.x) > 0.4:
                        continue
                    L = abs(s.y - t.y)
                    if L < 40:
                        continue
                    all_v.append((round(float(s.x), 2), round(min(s.y, t.y), 2), round(max(s.y, t.y), 2), round(L, 1)))
                all_v.sort()
                # show last 25
                for v in all_v[-25:]:
                    print(f"    V x={v[0]:8.2f} y={v[1]:8.2f}->{v[2]:8.2f} L={v[3]}")


if __name__ == "__main__":
    main()
