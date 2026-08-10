# -*- coding: utf-8 -*-
"""Inventário geométrico de fidelidade — coordenadas de CADA linha e cota.

Objetivo: base para reprodução 100% (N4 deve poder ser reconstruído a partir
do ledger N2 `must_reproduce`, não só “parecer igual”).

Schema (por entidade):
  - id estável
  - layer / family
  - tipo (LINE | LWPOLYLINE_SEG | COTA_TEXT | COTA_DIMENSION | HATCH_BBOX | TEXT)
  - abs {x1,y1,x2,y2} ou pts[] / insert / defpoints
  - rel  (cm relativos à origem do corpo da face)
  - orient, length_cm, measurement_cm, content
  - role / flags (must_reproduce | context_neighbor | void_junk | tick)

Uso:
  py -3 scripts/arete/inventario_geometria_fidelidade.py \\
      --n2 path/LV_V301_motor_....dxf \\
      --n4 path/n4/LV_preview_V301_VIEW_A.dxf \\
      --face A \\
      --origin-n2 5479.891,8154.0 \\
      --h-body 109 --widths 244,28.7,21.8,111,19,21.2 \\
      --out scripts/arete/relatorios/g2v/v301_reproducao

Sem --n4: só ledger N2.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import ezdxf

TOL_MATCH = 1.0
TOL_NEAR = 2.5
COTA_LAYERS = {"COTA", "Cotas", "Cota Seção (2x)", "Painéis", "Paineis"}


def _r(v, n=4):
    try:
        return round(float(v), n)
    except Exception:
        return v


def _norm_line(x1, y1, x2, y2, tol=0.05):
    if abs(x1 - x2) < tol:
        ya, yb = (y1, y2) if y1 <= y2 else (y2, y1)
        return _r(x1, 4), _r(ya, 4), _r(x1, 4), _r(yb, 4), "V"
    if abs(y1 - y2) < tol:
        xa, xb = (x1, x2) if x1 <= x2 else (x2, x1)
        return _r(xa, 4), _r(y1, 4), _r(xb, 4), _r(y1, 4), "H"
    if (x1, y1) <= (x2, y2):
        return _r(x1, 4), _r(y1, 4), _r(x2, 4), _r(y2, 4), "D"
    return _r(x2, 4), _r(y2, 4), _r(x1, 4), _r(y1, 4), "D"


def _len(x1, y1, x2, y2):
    return _r(math.hypot(x2 - x1, y2 - y1), 4)


def _family(layer: str) -> str:
    u = (layer or "").upper()
    if u.startswith("SARR"):
        return "SARR"
    if "PAIN" in u:
        return "Painéis"
    if "COTA" in u:
        return "Cota"
    if "REAPROV" in u or "HACH" in u or "CONCRETO" in u:
        return "Material"
    if "NOMEN" in u or "TEXTO" in u or layer in {"5", "Texto Seção"}:
        return "Texto"
    return layer or "?"


def _parse_num(text: str):
    if not text:
        return None
    t = str(text).strip().replace(",", ".")
    t = re.sub(r"\\[A-Za-z][^;]*;", "", t)
    t = t.replace("{", "").replace("}", "")
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if not m:
        return None
    try:
        return _r(float(m.group(0)), 4)
    except Exception:
        return None


def _flags_line(rel, fam, h_body, total_w):
    x1, y1, x2, y2 = rel
    flags = []
    o = "V" if abs(x1 - x2) < 0.05 else ("H" if abs(y1 - y2) < 0.05 else "D")
    L = _len(x1, y1, x2, y2)
    mx = 0.5 * (x1 + x2)
    my = 0.5 * (y1 + y2)

    if max(y1, y2) < -1.0:
        flags.append("void_junk")
    # verticals that plunge deep below body (dim witnesses mis-layered as Painéis)
    if o == "V" and min(y1, y2) < -20.0:
        flags.append("void_junk")
        flags.append("dim_geometry")
    # stubs acima do marco (ticks de cota). Nao marcar V7 residual do marco
    # (N2 B: 7 cm em y~117-124 = h_body+14..+21) — sao silhueta, nao tick.
    if o == "V" and min(y1, y2) >= h_body + 14.0:
        is_marco_v7 = 5.0 <= float(L) <= 8.5 and max(y1, y2) <= h_body + 28.0
        if not is_marco_v7:
            flags.append("tick")
            flags.append("dim_geometry")
    if mx < -5.0 or mx > total_w + 15.0:
        flags.append("context_neighbor")
    if o == "D" and L < 6.0:
        flags.append("tick")
    if fam == "Cota" and o != "D" and L > 6:
        # linha de cota / witness em layer COTA — não silhueta Painéis
        flags.append("dim_geometry")
    if (
        fam in ("Painéis", "SARR")
        and "void_junk" not in flags
        and "tick" not in flags
        and "context_neighbor" not in flags
    ):
        flags.append("must_reproduce")
    if not flags:
        flags.append("review")
    return flags, o, L, [_r(mx, 3), _r(my, 3)]


def _flags_cota(val, pos, total_w, h_body):
    flags = []
    if pos is None:
        flags.append("no_pos")
        return flags
    x, y = pos
    # laterais N4 usam offset L1=25 / L2=50 + texto (~8 no dimstyle PAINEL,
    # confirmado por medida real: text_mid_rel=-58 num L2=-50) — -55 cortava
    # a propria cota "must_reproduce" da unidade, marcando como vizinha uma
    # cota que e dela mesma (ver UNIT.B#10/V301.B#4, cota 124).
    if x < -65.0 or x > total_w + 65.0:
        flags.append("context_neighbor")
    else:
        flags.append("must_reproduce")
    if y < -1.0:
        flags.append("below_body")
    if y > h_body + 5:
        flags.append("above_body")
    return flags


def extract_ledger(
    path: Path,
    *,
    origin: tuple[float, float],
    h_body: float,
    total_w: float,
    panel_widths: list[float],
    clip: tuple[float, float, float, float],
    side: str,
    label: str,
) -> dict:
    ox, oy = origin
    xl, yb, xr, yt = clip
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    ledger = {
        "schema": "reproducao_geometria_v1",
        "source_dxf": str(path),
        "side": side,
        "label": label,
        "origin_abs": [_r(ox, 6), _r(oy, 6)],
        "h_body": _r(h_body, 4),
        "total_w": _r(total_w, 4),
        "panel_widths": [_r(w, 4) for w in panel_widths],
        "clip_rel": [_r(c, 4) for c in clip],
        "lines": [],
        "cotas": [],
        "texts": [],
        "hatches": [],
        "counts": {},
    }
    lid = cid = tid = hid = 0

    def in_clip(x, y):
        return xl <= x <= xr and yb <= y <= yt

    for e in msp:
        t = e.dxftype()
        layer = str(e.dxf.layer)
        fam = _family(layer)

        if t == "LINE":
            a, b = e.dxf.start, e.dxf.end
            x1, y1, x2, y2, o = _norm_line(
                a.x - ox, a.y - oy, b.x - ox, b.y - oy
            )
            mx, my = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
            if not in_clip(mx, my):
                continue
            flags, o2, L, mid = _flags_line((x1, y1, x2, y2), fam, h_body, total_w)
            lid += 1
            ledger["lines"].append(
                {
                    "id": f"{side}-L{lid:04d}",
                    "type": "LINE",
                    "layer": layer,
                    "family": fam,
                    "abs": {
                        "x1": _r(a.x, 6),
                        "y1": _r(a.y, 6),
                        "x2": _r(b.x, 6),
                        "y2": _r(b.y, 6),
                    },
                    "rel": {
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                    },
                    "orient": o2,
                    "length_cm": L,
                    "mid_rel": mid,
                    "flags": flags,
                    "color": int(getattr(e.dxf, "color", 256) or 256),
                    "lineweight": int(getattr(e.dxf, "lineweight", -1) or -1),
                }
            )

        elif t == "LWPOLYLINE":
            pts = [(float(p[0]), float(p[1])) for p in e.get_points("xy")]
            if len(pts) < 2:
                continue
            # expand to segments for reproduction fidelity
            segs = list(zip(pts, pts[1:]))
            if e.closed and len(pts) > 2:
                segs.append((pts[-1], pts[0]))
            for (pa, pb) in segs:
                x1, y1, x2, y2, o = _norm_line(
                    pa[0] - ox, pa[1] - oy, pb[0] - ox, pb[1] - oy
                )
                mx, my = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
                if not in_clip(mx, my):
                    continue
                flags, o2, L, mid = _flags_line((x1, y1, x2, y2), fam, h_body, total_w)
                flags = list(flags) + ["from_lwpolyline"]
                lid += 1
                ledger["lines"].append(
                    {
                        "id": f"{side}-L{lid:04d}",
                        "type": "LWPOLYLINE_SEG",
                        "layer": layer,
                        "family": fam,
                        "abs": {
                            "x1": _r(pa[0], 6),
                            "y1": _r(pa[1], 6),
                            "x2": _r(pb[0], 6),
                            "y2": _r(pb[1], 6),
                        },
                        "rel": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                        "orient": o2,
                        "length_cm": L,
                        "mid_rel": mid,
                        "flags": flags,
                        "closed_parent": bool(e.closed),
                    }
                )

        elif t == "DIMENSION":
            try:
                meas = float(e.dxf.actual_measurement)
            except Exception:
                try:
                    meas = float(e.get_measurement())
                except Exception:
                    meas = None
            defpts = {}
            for attr in (
                "defpoint",
                "defpoint2",
                "defpoint3",
                "defpoint4",
                "text_midpoint",
            ):
                if hasattr(e.dxf, attr):
                    p = getattr(e.dxf, attr)
                    try:
                        defpts[attr] = {
                            "abs": [_r(p.x, 6), _r(p.y, 6)],
                            "rel": [_r(p.x - ox, 4), _r(p.y - oy, 4)],
                        }
                    except Exception:
                        pass
            # p1/p2 convention for linear: defpoint2 / defpoint3 often
            p1 = defpts.get("defpoint2", {}).get("rel")
            p2 = defpts.get("defpoint3", {}).get("rel")
            mid = defpts.get("text_midpoint", {}).get("rel")
            if mid is None and p1 and p2:
                mid = [_r(0.5 * (p1[0] + p2[0]), 4), _r(0.5 * (p1[1] + p2[1]), 4)]
            if mid and not in_clip(mid[0], mid[1]):
                # still keep if measurement points in clip
                if p1 and p2:
                    if not (
                        in_clip(p1[0], p1[1])
                        or in_clip(p2[0], p2[1])
                        or in_clip(0.5 * (p1[0] + p2[0]), 0.5 * (p1[1] + p2[1]))
                    ):
                        continue
                else:
                    continue
            text = str(getattr(e.dxf, "text", "") or "").strip()
            if text in ("", "<>"):
                content = None
            else:
                content = text
            val = _parse_num(content) if content else meas
            if val is None:
                val = meas
            flags = _flags_cota(val, mid, total_w, h_body)
            flags.append("dimension")
            cid += 1
            ledger["cotas"].append(
                {
                    "id": f"{side}-C{cid:04d}",
                    "type": "COTA_DIMENSION",
                    "layer": layer,
                    "family": "Cota",
                    "measurement_cm": _r(val, 4) if val is not None else None,
                    "content": content,
                    "text_override": text,
                    "dimstyle": str(getattr(e.dxf, "dimstyle", "") or ""),
                    "angle_deg": _r(float(getattr(e.dxf, "angle", 0) or 0), 3),
                    "text_mid_rel": mid,
                    "text_mid_abs": defpts.get("text_midpoint", {}).get("abs"),
                    "p1_rel": p1,
                    "p2_rel": p2,
                    "defpoints": defpts,
                    "flags": flags,
                }
            )

        elif t in ("TEXT", "MTEXT"):
            if t == "MTEXT":
                raw = e.text
                ins = e.dxf.insert
                height = float(getattr(e.dxf, "char_height", 0) or 0)
                rot = float(getattr(e.dxf, "rotation", 0) or 0)
            else:
                raw = str(e.dxf.text)
                ins = e.dxf.insert
                height = float(getattr(e.dxf, "height", 0) or 0)
                rot = float(getattr(e.dxf, "rotation", 0) or 0)
            ix, iy = ins.x - ox, ins.y - oy
            if not in_clip(ix, iy):
                continue
            content = raw.replace("\\P", "\n").strip()
            plain = re.sub(r"\s+", "", content.replace(",", "."))
            val = _parse_num(content)
            is_num = bool(re.fullmatch(r"-?\d+(?:\.\d+)?", plain))
            is_cota = (
                is_num
                and val is not None
                and (fam == "Cota" or layer in COTA_LAYERS or "COTA" in layer.upper() or fam == "Painéis")
            )
            if is_cota:
                flags = _flags_cota(val, [ix, iy], total_w, h_body)
                flags.append("text_numeric")
                cid += 1
                ledger["cotas"].append(
                    {
                        "id": f"{side}-C{cid:04d}",
                        "type": "COTA_TEXT",
                        "layer": layer,
                        "family": "Cota",
                        "measurement_cm": val,
                        "content": content,
                        "insert_abs": [_r(ins.x, 6), _r(ins.y, 6)],
                        "insert_rel": [_r(ix, 4), _r(iy, 4)],
                        "height": _r(height, 3),
                        "rotation_deg": _r(rot, 3),
                        "style": str(getattr(e.dxf, "style", "") or ""),
                        "flags": flags,
                    }
                )
            else:
                tid += 1
                flags = []
                if ix < -5 or ix > total_w + 20:
                    flags.append("context_neighbor")
                else:
                    flags.append("must_reproduce")
                ledger["texts"].append(
                    {
                        "id": f"{side}-T{tid:04d}",
                        "type": t,
                        "layer": layer,
                        "family": fam,
                        "content": content,
                        "insert_abs": [_r(ins.x, 6), _r(ins.y, 6)],
                        "insert_rel": [_r(ix, 4), _r(iy, 4)],
                        "height": _r(height, 3),
                        "rotation_deg": _r(rot, 3),
                        "flags": flags,
                    }
                )

        elif t == "HATCH":
            try:
                paths = list(e.paths)
            except Exception:
                paths = []
            # bbox from polyline paths
            xs, ys = [], []
            for path in paths:
                try:
                    verts = list(getattr(path, "vertices", []) or [])
                    for v in verts:
                        if hasattr(v, "x"):
                            xs.append(v.x)
                            ys.append(v.y)
                        elif isinstance(v, (list, tuple)) and len(v) >= 2:
                            xs.append(float(v[0]))
                            ys.append(float(v[1]))
                except Exception:
                    pass
            if not xs:
                continue
            mx = sum(xs) / len(xs) - ox
            my = sum(ys) / len(ys) - oy
            if not in_clip(mx, my):
                continue
            hid += 1
            ledger["hatches"].append(
                {
                    "id": f"{side}-H{hid:04d}",
                    "type": "HATCH",
                    "layer": layer,
                    "family": fam,
                    "pattern": str(getattr(e.dxf, "pattern_name", "") or ""),
                    "bbox_abs": {
                        "xmin": _r(min(xs), 6),
                        "ymin": _r(min(ys), 6),
                        "xmax": _r(max(xs), 6),
                        "ymax": _r(max(ys), 6),
                    },
                    "bbox_rel": {
                        "xmin": _r(min(xs) - ox, 4),
                        "ymin": _r(min(ys) - oy, 4),
                        "xmax": _r(max(xs) - ox, 4),
                        "ymax": _r(max(ys) - oy, 4),
                    },
                    "flags": ["must_reproduce"] if fam in ("Material", "Painéis", "Cota") else ["review"],
                }
            )

    # sort for stable diffs
    ledger["lines"].sort(
        key=lambda L: (
            L["family"],
            L["orient"],
            L["rel"]["x1"],
            L["rel"]["y1"],
            L["rel"]["x2"],
            L["rel"]["y2"],
        )
    )
    ledger["cotas"].sort(
        key=lambda c: (
            c.get("measurement_cm") is None,
            c.get("measurement_cm") or 0,
            (c.get("insert_rel") or c.get("text_mid_rel") or [0, 0])[0],
        )
    )
    ledger["counts"] = {
        "lines": len(ledger["lines"]),
        "cotas": len(ledger["cotas"]),
        "texts": len(ledger["texts"]),
        "hatches": len(ledger["hatches"]),
        "must_reproduce_lines": sum(
            1 for L in ledger["lines"] if "must_reproduce" in L["flags"]
        ),
        "must_reproduce_cotas": sum(
            1 for c in ledger["cotas"] if "must_reproduce" in c["flags"]
        ),
        "flags_lines": dict(Counter(f for L in ledger["lines"] for f in L["flags"])),
        "flags_cotas": dict(Counter(f for c in ledger["cotas"] for f in c["flags"])),
    }
    return ledger


def match_lines(n2_lines, n4_lines, tol=TOL_MATCH, tol_near=TOL_NEAR):
    pool = [dict(L, _used=False) for L in n4_lines]
    out = []
    for A in n2_lines:
        r = A["rel"]
        best_i, best_d = None, 1e18
        for i, B in enumerate(pool):
            if B["_used"]:
                continue
            if A["family"] != B["family"] and not (
                A["family"] in ("Painéis", "SARR") and B["family"] in ("Painéis", "SARR")
            ):
                # allow Painéis/SARR only same family for strict repro
                if A["family"] != B["family"]:
                    continue
            s = B["rel"]
            d = (
                abs(r["x1"] - s["x1"])
                + abs(r["y1"] - s["y1"])
                + abs(r["x2"] - s["x2"])
                + abs(r["y2"] - s["y2"])
            ) / 4.0
            if d < best_d:
                best_d, best_i = d, i
        status = "MISSING_N4"
        n4 = None
        if best_i is not None and best_d <= tol:
            status = "MATCH"
            pool[best_i]["_used"] = True
            n4 = {
                "id": pool[best_i]["id"],
                "rel": pool[best_i]["rel"],
                "delta_avg_cm": _r(best_d, 4),
            }
        elif best_i is not None and best_d <= tol_near:
            status = "NEAR"
            pool[best_i]["_used"] = True
            n4 = {
                "id": pool[best_i]["id"],
                "rel": pool[best_i]["rel"],
                "delta_avg_cm": _r(best_d, 4),
            }
        # reclassify non-must
        if status == "MISSING_N4":
            if "void_junk" in A["flags"]:
                status = "N2_VOID_JUNK_nao_deve_copiar"
            elif "context_neighbor" in A["flags"]:
                status = "N2_CONTEXTO_VIZINHO_nao_copiar"
            elif "tick" in A["flags"]:
                status = "N2_TICK_nao_deve_copiar"
            elif "dim_geometry" in A["flags"]:
                status = "N2_DIM_GEOMETRY_opcional"
        out.append(
            {
                "n2_id": A["id"],
                "family": A["family"],
                "layer": A["layer"],
                "rel": A["rel"],
                "orient": A["orient"],
                "length_cm": A["length_cm"],
                "flags": A["flags"],
                "status": status,
                "n4": n4,
            }
        )
    extras = [
        {
            "n4_id": B["id"],
            "family": B["family"],
            "layer": B["layer"],
            "rel": B["rel"],
            "orient": B["orient"],
            "length_cm": B["length_cm"],
            "flags": B["flags"],
            "status": "EXTRA_N4",
        }
        for B in pool
        if not B["_used"]
    ]
    return out, extras


def match_cotas(n2_cotas, n4_cotas, tol_val=0.15, tol_pos=25.0):
    pool = [dict(c, _used=False) for c in n4_cotas]
    out = []
    # own-face / must_reproduce primeiro — evita vizinho "roubar" o match 1:1
    ordered = sorted(
        n2_cotas,
        key=lambda c: (
            0 if "must_reproduce" in c.get("flags", []) else 1,
            0 if "context_neighbor" not in c.get("flags", []) else 1,
        ),
    )
    for A in ordered:
        val = A.get("measurement_cm")
        pos = A.get("insert_rel") or A.get("text_mid_rel")
        best_i, best_score = None, 1e18
        for i, B in enumerate(pool):
            if B["_used"]:
                continue
            bv = B.get("measurement_cm")
            if val is None or bv is None:
                continue
            dv = abs(float(val) - float(bv))
            bp = B.get("text_mid_rel") or B.get("insert_rel")
            dp = 0.0
            if pos and bp:
                dp = math.hypot(pos[0] - bp[0], pos[1] - bp[1])
            score = dv * 100 + dp
            if score < best_score:
                best_score, best_i = score, i
        status = "MISSING_N4"
        n4 = None
        if best_i is not None:
            B = pool[best_i]
            bv = B.get("measurement_cm")
            dv = abs(float(val) - float(bv)) if val is not None and bv is not None else 99
            bp = B.get("text_mid_rel") or B.get("insert_rel")
            dp = math.hypot(pos[0] - bp[0], pos[1] - bp[1]) if pos and bp else 0
            if dv <= tol_val:
                pool[best_i]["_used"] = True
                status = "MATCH" if dp <= tol_pos else "MATCH_VALUE_POS_OFF"
                n4 = {
                    "id": B["id"],
                    "measurement_cm": bv,
                    "pos": bp,
                    "p1_rel": B.get("p1_rel"),
                    "p2_rel": B.get("p2_rel"),
                    "delta_val": _r(dv, 4),
                    "delta_pos_cm": _r(dp, 3),
                }
        if status == "MISSING_N4" and "context_neighbor" in A.get("flags", []):
            status = "N2_CONTEXTO_VIZINHO_nao_copiar"
        out.append(
            {
                "n2_id": A["id"],
                "content": A.get("content"),
                "measurement_cm": val,
                "insert_rel": pos,
                "type": A.get("type"),
                "flags": A.get("flags"),
                "status": status,
                "n4": n4,
            }
        )
    extras = [
        {
            "n4_id": B["id"],
            "measurement_cm": B.get("measurement_cm"),
            "content": B.get("content") or B.get("text_override"),
            "pos": B.get("text_mid_rel") or B.get("insert_rel"),
            "p1_rel": B.get("p1_rel"),
            "p2_rel": B.get("p2_rel"),
            "status": "EXTRA_N4",
        }
        for B in pool
        if not B["_used"]
    ]
    return out, extras


def write_md(n2, n4, line_tr, line_ex, cota_tr, cota_ex, path: Path):
    L = []
    L.append("# Inventário geométrico de reprodução — coordenadas totais")
    L.append("")
    L.append("## Origens")
    L.append(f"- N2 origin_abs: `{n2['origin_abs']}`")
    if n4:
        L.append(f"- N4 origin_abs: `{n4['origin_abs']}`")
    L.append(f"- h_body={n2['h_body']} total_w={n2['total_w']} widths={n2['panel_widths']}")
    L.append(f"- clip_rel={n2['clip_rel']}")
    L.append("")
    L.append("## Contagens N2")
    L.append(f"```json\n{json.dumps(n2['counts'], ensure_ascii=False, indent=2)}\n```")
    if n4:
        L.append("## Contagens N4")
        L.append(f"```json\n{json.dumps(n4['counts'], ensure_ascii=False, indent=2)}\n```")
    L.append("")
    L.append("## LINEs must_reproduce (N2) — coordenadas rel cm")
    L.append("")
    L.append("| id | fam | o | x1 | y1 | x2 | y2 | L | status | n4_id | Δcm |")
    L.append("|----|-----|---|----|----|----|----|---|--------|-------|-----|")
    for row in line_tr:
        if "must_reproduce" not in row.get("flags", []):
            continue
        r = row["rel"]
        n4id = (row.get("n4") or {}).get("id", "")
        dlt = (row.get("n4") or {}).get("delta_avg_cm", "")
        L.append(
            f"| {row['n2_id']} | {row['family']} | {row['orient']} | "
            f"{r['x1']} | {r['y1']} | {r['x2']} | {r['y2']} | {row['length_cm']} | "
            f"**{row['status']}** | {n4id} | {dlt} |"
        )
    L.append("")
    L.append("## Cotas must_reproduce (N2)")
    L.append("")
    L.append("| id | valor | content | insert/mid rel | p1_n4 | p2_n4 | status | Δpos |")
    L.append("|----|-------|---------|----------------|-------|-------|--------|------|")
    for row in cota_tr:
        if "must_reproduce" not in (row.get("flags") or []):
            continue
        n4 = row.get("n4") or {}
        L.append(
            f"| {row['n2_id']} | {row.get('measurement_cm')} | {row.get('content')} | "
            f"{row.get('insert_rel')} | {n4.get('p1_rel')} | {n4.get('p2_rel')} | "
            f"**{row['status']}** | {n4.get('delta_pos_cm', '')} |"
        )
    L.append("")
    L.append("## EXTRA N4 lines")
    for e in line_ex:
        L.append(f"- `{e['n4_id']}` {e['family']} {e['orient']} rel={e['rel']} L={e['length_cm']}")
    L.append("")
    L.append("## EXTRA N4 cotas")
    for e in cota_ex:
        L.append(
            f"- `{e['n4_id']}` val={e.get('measurement_cm')} pos={e.get('pos')} "
            f"p1={e.get('p1_rel')} p2={e.get('p2_rel')}"
        )
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n2", type=Path, required=True)
    ap.add_argument("--n4", type=Path, default=None)
    ap.add_argument("--face", default="A")
    ap.add_argument("--label", default="V301.A")
    ap.add_argument("--origin-n2", required=True, help="x,y abs N2 body origin")
    ap.add_argument("--origin-n4", default="0,-259", help="x,y abs N4 body origin")
    ap.add_argument("--h-body", type=float, required=True)
    ap.add_argument("--widths", required=True, help="comma panel widths")
    ap.add_argument(
        "--clip",
        default="-80,-100,520,160",
        help="clip_rel xmin,ymin,xmax,ymax",
    )
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    ox, oy = [float(x) for x in args.origin_n2.split(",")]
    widths = [float(x) for x in args.widths.split(",") if x.strip()]
    total_w = sum(widths)
    clip = tuple(float(x) for x in args.clip.split(","))
    assert len(clip) == 4

    args.out.mkdir(parents=True, exist_ok=True)

    n2 = extract_ledger(
        args.n2,
        origin=(ox, oy),
        h_body=args.h_body,
        total_w=total_w,
        panel_widths=widths,
        clip=clip,
        side=args.face,
        label=args.label,
    )
    (args.out / f"ledger_n2_face{args.face}.json").write_text(
        json.dumps(n2, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # pure must_reproduce recipe for replay
    recipe = {
        "schema": "reproducao_recipe_v1",
        "label": args.label,
        "origin_note": "coords are REL to body origin (0,0)=canto inf.esq. corpo",
        "h_body": n2["h_body"],
        "panel_widths": n2["panel_widths"],
        "lines": [
            {
                "id": L["id"],
                "layer": L["layer"],
                "family": L["family"],
                "rel": L["rel"],
                "orient": L["orient"],
                "length_cm": L["length_cm"],
            }
            for L in n2["lines"]
            if "must_reproduce" in L["flags"]
        ],
        "cotas": [
            {
                "id": C["id"],
                "type": C["type"],
                "measurement_cm": C.get("measurement_cm"),
                "content": C.get("content"),
                "insert_rel": C.get("insert_rel") or C.get("text_mid_rel"),
                "p1_rel": C.get("p1_rel"),
                "p2_rel": C.get("p2_rel"),
                "rotation_deg": C.get("rotation_deg"),
                "height": C.get("height"),
            }
            for C in n2["cotas"]
            if "must_reproduce" in C["flags"]
        ],
        "hatches": [
            H
            for H in n2["hatches"]
            if "must_reproduce" in H.get("flags", [])
        ],
    }
    (args.out / f"recipe_n2_face{args.face}.json").write_text(
        json.dumps(recipe, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"N2 lines={n2['counts']['lines']} must={n2['counts']['must_reproduce_lines']} "
        f"cotas={n2['counts']['cotas']} must_c={n2['counts']['must_reproduce_cotas']}"
    )

    n4 = None
    line_tr = line_ex = cota_tr = cota_ex = []
    if args.n4 and args.n4.exists():
        o4x, o4y = [float(x) for x in args.origin_n4.split(",")]
        n4 = extract_ledger(
            args.n4,
            origin=(o4x, o4y),
            h_body=args.h_body,
            total_w=total_w,
            panel_widths=widths,
            clip=clip,
            side=f"N4{args.face}",
            label=f"N4_{args.label}",
        )
        (args.out / f"ledger_n4_face{args.face}.json").write_text(
            json.dumps(n4, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        line_tr, line_ex = match_lines(n2["lines"], n4["lines"])
        cota_tr, cota_ex = match_cotas(n2["cotas"], n4["cotas"])
        trace = {
            "protocol": "reproducao_geometria_v1",
            "summary_lines": dict(Counter(r["status"] for r in line_tr)),
            "summary_cotas": dict(Counter(r["status"] for r in cota_tr)),
            "extra_lines": len(line_ex),
            "extra_cotas": len(cota_ex),
            "lines": line_tr,
            "lines_extra_n4": line_ex,
            "cotas": cota_tr,
            "cotas_extra_n4": cota_ex,
            "must_reproduce_gaps": {
                "lines_missing": [
                    r
                    for r in line_tr
                    if r["status"] == "MISSING_N4" and "must_reproduce" in r["flags"]
                ],
                "cotas_missing": [
                    r
                    for r in cota_tr
                    if r["status"] == "MISSING_N4" and "must_reproduce" in (r.get("flags") or [])
                ],
                "cotas_extra": cota_ex,
                "lines_extra": [
                    e
                    for e in line_ex
                    if e["family"] in ("Painéis", "SARR")
                ],
            },
        }
        (args.out / f"trace_reproducao_face{args.face}.json").write_text(
            json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        write_md(
            n2,
            n4,
            line_tr,
            line_ex,
            cota_tr,
            cota_ex,
            args.out / f"reproducao_face{args.face}.md",
        )
        print("trace lines", trace["summary_lines"])
        print("trace cotas", trace["summary_cotas"])
        print(
            "MUST gaps lines",
            len(trace["must_reproduce_gaps"]["lines_missing"]),
            "cotas",
            len(trace["must_reproduce_gaps"]["cotas_missing"]),
            "extra_lines",
            len(trace["must_reproduce_gaps"]["lines_extra"]),
            "extra_cotas",
            len(trace["must_reproduce_gaps"]["cotas_extra"]),
        )

    print("OUT", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
