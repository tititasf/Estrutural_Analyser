# -*- coding: utf-8 -*-
"""Resumo honesto gate V301 — foco alucinação (extra / inventada / pixel)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

p = Path(__file__).resolve().parent / "relatorios/g2v/v301_geometry_gate/V301_GEOMETRY_GATE.json"
d = json.loads(p.read_text(encoding="utf-8"))
results = d.get("results") if isinstance(d, dict) else d

print(f"n_results={len(results)}")
print()
hdr = (
    f"{'#':>2} {'label':<18} {'sd':2} {'verdict':<14} "
    f"{'R%':>4} {'G%':>4} {'exG':>3} {'miG':>3} "
    f"{'invented':<24} {'vision':<24} {'pxEx':>5} {'pxMi%':>6}"
)
print(hdr)
print("-" * len(hdr))

hallu = []
clean_primary = []
for i, r in enumerate(results):
    m = r.get("metrics") or {}
    v = r.get("vision") or {}
    pix = v.get("pixel") or {}
    lab = str(r.get("label") or "")
    side = str(r.get("side") or "")
    verd = str(r.get("verdict") or "")
    rm, gm = m.get("r_match"), m.get("g_match")
    rmp = f"{100 * float(rm):.0f}" if rm is not None else "—"
    gmp = f"{100 * float(gm):.0f}" if gm is not None else "—"
    eg, mg = m.get("extra_g"), m.get("miss_g")
    inv = m.get("invented_r") or []
    invs = str(inv)[:22]
    vv = str(v.get("vision_verdict") or "—")[:22]
    pxe = pix.get("extra_pixels")
    pxm = pix.get("miss_ratio")
    pxes = str(pxe) if pxe is not None else "—"
    pxms = f"{100 * float(pxm):.1f}" if pxm is not None else "—"
    print(
        f"{i:>2} {lab:<18} {side:2} {verd:<14} "
        f"{rmp:>4} {gmp:>4} {str(eg if eg is not None else '—'):>3} "
        f"{str(mg if mg is not None else '—'):>3} "
        f"{invs:<24} {vv:<24} {pxes:>5} {pxms:>6}"
    )

    flags = []
    if eg is not None and int(eg) > 0:
        flags.append(f"extra_g={eg}")
    if inv:
        flags.append(f"invented={inv}")
    if pxe is not None and int(pxe) > 0:
        flags.append(f"px_extra={pxe}")
    if vv and "FAIL" in vv:
        flags.append(vv)
    geo = v.get("geometry") if isinstance(v.get("geometry"), dict) else {}
    ph = m.get("phantoms") or (geo.get("phantoms") if geo else None)
    if ph:
        flags.append(f"phantoms={ph}")
    if "inventad" in verd.lower() or (
        "EXTRA" in verd and "MISSING" not in verd
    ):
        flags.append(verd)
    if flags:
        hallu.append((lab, side, flags, r.get("reasons") or []))
    if lab in ("V301.A", "V301.B"):
        clean_primary.append(r)

print()
print("=== ALUCINACAO / EXTRA (sinais duros) ===")
if not hallu:
    print("OK: nenhum extra_g>0, invented_r, phantoms ou px_extra nos pares.")
else:
    for lab, side, flags, reasons in hallu:
        print(f" * [{side}] {lab}: {flags}")
        for rs in reasons[:4]:
            print(f"     - {rs}")

print()
print("=== SUMMARY ===", dict(Counter(r.get("verdict") for r in results)))
print()
print("=== PRIMARY V301.A / B ===")
for r in clean_primary:
    m = r.get("metrics") or {}
    v = r.get("vision") or {}
    pix = v.get("pixel") or {}
    print(f"--- {r.get('label')} ---")
    print(f"  verdict={r.get('verdict')}")
    print(
        f"  R={m.get('r_match')} G={m.get('g_match')} "
        f"extra_g={m.get('extra_g')} miss_g={m.get('miss_g')} "
        f"invented={m.get('invented_r')}"
    )
    print(
        f"  vision={v.get('vision_verdict')} "
        f"arete100={v.get('arete_100_eligible')}"
    )
    if pix:
        print(
            f"  pixel extra={pix.get('extra_pixels')} "
            f"extra_ratio={pix.get('extra_ratio')} "
            f"miss_ratio={pix.get('miss_ratio')} "
            f"densΔ={pix.get('density_delta')}"
        )
    print(f"  reasons={r.get('reasons')}")
