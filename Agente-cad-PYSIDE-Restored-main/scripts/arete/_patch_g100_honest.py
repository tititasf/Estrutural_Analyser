# -*- coding: utf-8 -*-
"""G=100% honesto: so geometria presente no N2, zero phantom."""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
p = ROOT / "gerar_lv_dxf_stog.py"
t = p.read_text(encoding="utf-8")

m = re.search(
    r"def _draw_panel_frame_n2\(msp, x0, y0, h, panels, \*,\n"
    r"                          marco_laje_sup=False, laje_sup=0\.0\):",
    t,
)
if not m:
    raise SystemExit("frame not found")
start = m.start()
m2 = re.search(r"\ndef _draw_degrau_step_verticals\(", t[start:])
if not m2:
    raise SystemExit("end not found")
end = start + m2.start()

new_fn = r'''def _draw_panel_frame_n2(msp, x0, y0, h, panels, *,
                          marco_laje_sup=False, laje_sup=0.0):
    """Contorno Painéis fiel ao N2 — G honest (miss→0, extra→0).

    Regras anti-phantom (ShareX):
    - A: 1º divisor (244) SO faixa alta. NUNCA V65 no vão.
    - B: 1º divisor + 2º painel estreito (<25): N2 TEM V65 em ~244.7
      (recesso real) — so nesse caso desenha base→ombro.
    - H curtas so entre divisores BAIXOS consecutivos (272.7–294.5 / 244–266),
      nunca sob o vao vazio A entre 0 e 244.
    - Marco: H por painel (19, 21.2…) + continuous strip; V mid corpo+15;
      H multi-nivel no corpo so se marco grosso (B, >=18).
    """
    a = {'layer': 'Painéis'}
    if not panels:
        return
    comprimento = sum(float(p.get('width', 0) or 0) for p in panels)
    if comprimento <= 0:
        return
    y_top = y0 + h
    y_shoulder = _degrau_shoulder_y(y0, h, panels)
    degrau_end = _degrau_zone_end_x(x0, h, panels)
    has_degrau = y_shoulder is not None and degrau_end > x0 + 0.5
    small_x = _small_panel_start_x(x0, h, panels)
    marco_h = _marco_extension_cm(marco_laje_sup, laje_sup)
    y_marco = y_top + marco_h if marco_h > 0.5 else y_top
    y_m15 = y_top + 15.0 if marco_h >= 15.0 else y_marco
    thick_marco = marco_h >= 18.0  # B-style multi-level

    if has_degrau:
        msp.add_line((x0, y_shoulder), (x0, y_top), dxfattribs=a)
    else:
        msp.add_line((x0, y0), (x0, y_top), dxfattribs=a)

    body_end = float(small_x) if small_x is not None else float(x0 + comprimento)
    full_end = float(x0 + comprimento)

    low_div_xs = []  # so divisores com V base→ombro (nao o phantom A@244)
    x_cur = float(x0)
    for idx, panel in enumerate(panels):
        pw = float(panel.get('width', 0) or 0)
        x_right = x_cur + pw
        is_last = idx >= len(panels) - 1
        cur_deg = _is_degrau_panel(panel, h)
        next_deg = (not is_last) and _is_degrau_panel(panels[idx + 1], h)
        next_pw = float(panels[idx + 1].get('width', 0) or 0) if not is_last else 0.0
        in_small = small_x is not None and x_cur >= small_x - 0.1

        if in_small:
            x_cur = x_right
            continue

        is_body_end = abs(x_right - body_end) < 0.15

        if is_body_end:
            msp.add_line((x_right, y0), (x_right, y_marco), dxfattribs=a)
        elif has_degrau and cur_deg and next_deg:
            if idx == 0:
                # faixa alta sempre
                msp.add_line((x_right, y_shoulder), (x_right, y_top), dxfattribs=a)
                # B: 2o painel estreito (<25) — N2 tem V65 em ~244.7
                # A: 2o painel ~28.7 — N2 NAO tem V65 em 244
                if next_pw < 25.0:
                    msp.add_line((x_right, y0), (x_right, y_shoulder), dxfattribs=a)
                    low_div_xs.append(x_right)
            else:
                msp.add_line((x_right, y0), (x_right, y_shoulder), dxfattribs=a)
                low_div_xs.append(x_right)
        elif has_degrau and cur_deg and not next_deg:
            msp.add_line((x_right, y0), (x_right, y_shoulder), dxfattribs=a)
            low_div_xs.append(x_right)
        elif has_degrau and (not cur_deg) and next_deg:
            msp.add_line((x_right, y0), (x_right, y_shoulder), dxfattribs=a)
            low_div_xs.append(x_right)
        else:
            msp.add_line((x_right, y0), (x_right, y_top), dxfattribs=a)
        x_cur = x_right

    # H curtas entre divisores baixos consecutivos (N2 A: 21.8 @280; B: 22.5 @252)
    if has_degrau and len(low_div_xs) >= 2:
        xs = sorted(low_div_xs)
        for xa, xb in zip(xs, xs[1:]):
            span = xb - xa
            if 15.0 <= span <= 35.0:
                msp.add_line((xa, y0), (xb, y0), dxfattribs=a)
                msp.add_line((xa, y_shoulder), (xb, y_shoulder), dxfattribs=a)

    if has_degrau:
        msp.add_line((x0, y_shoulder), (degrau_end, y_shoulder), dxfattribs=a)

    msp.add_line((x0, y_top), (body_end, y_top), dxfattribs=a)
    if has_degrau and degrau_end < body_end - 0.5:
        msp.add_line((degrau_end, y0), (body_end, y0), dxfattribs=a)
    elif not has_degrau:
        msp.add_line((x0, y0), (body_end, y0), dxfattribs=a)

    # B: niveis de marco no CORPO (N2 H 319 @117 e @124). A nao tem H corpo@124.
    if thick_marco and marco_h > 0.5:
        msp.add_line((x0, y_m15), (body_end, y_m15), dxfattribs=a)
        msp.add_line((x0, y_marco), (body_end, y_marco), dxfattribs=a)

    if marco_h > 0.5:
        _draw_vazio_concreto(msp, x0, y_top, body_end, y_marco)

    # ── marco strip ──────────────────────────────────────────────────
    if small_x is not None and full_end > body_end + 0.5:
        x_scan = float(x0)
        marco_panels = []
        for panel in panels:
            pw = float(panel.get('width', 0) or 0)
            if x_scan >= body_end - 0.1:
                marco_panels.append((x_scan, x_scan + pw, pw))
            x_scan += pw

        # H por painel (N2 A: 19 @418 e 21.2; B: 21.7 @332) em y0/top/marco
        y_levels = [y0, y_top]
        if marco_h > 0.5:
            y_levels.append(y_marco)
            if thick_marco:
                y_levels.append(y_m15)
        for x_l, x_r, pw in marco_panels:
            if pw < 0.5:
                continue
            for yy in y_levels:
                msp.add_line((x_l, yy), (x_r, yy), dxfattribs=a)

        # continuous strip H (N2 A: 40.2; B: 47.9) em base/topo/marco
        for yy in (y0, y_top, y_marco) if marco_h > 0.5 else (y0, y_top):
            msp.add_line((body_end, yy), (full_end, yy), dxfattribs=a)
        if thick_marco:
            msp.add_line((body_end, y_m15), (full_end, y_m15), dxfattribs=a)

        # parede final
        msp.add_line((full_end, y0), (full_end, y_marco), dxfattribs=a)

        # V mid 1a faixa marco: corpo (N2 A V109 @424.5) + V15 marco
        if marco_panels:
            x_l, x_r, pw = marco_panels[0]
            x_mid = 0.5 * (x_l + x_r)
            msp.add_line((x_mid, y0), (x_mid, y_top), dxfattribs=a)
            if marco_h > 0.5:
                msp.add_line((x_mid, y_top), (x_mid, y_marco), dxfattribs=a)

        # B: V7 residual (N2) nos xs criticos — so marco grosso
        if thick_marco and marco_h > 0.5:
            y_v7_bot = float(y_marco) - 7.0
            stub_xs = [x0, body_end, full_end]
            if has_degrau:
                pw0 = float(panels[0].get('width', 0) or 0)
                if pw0 >= 150.0:
                    stub_xs.append(float(x0) + pw0)
            if marco_panels:
                stub_xs.append(0.5 * (marco_panels[0][0] + marco_panels[0][1]))
            for vx in sorted(set(round(x, 2) for x in stub_xs)):
                msp.add_line((vx, y_v7_bot), (vx, y_marco), dxfattribs=a)


'''

t = t[:start] + new_fn + t[end:]
tmp = p.with_suffix(".py.tmp_patch")
tmp.write_text(t, encoding="utf-8")
os.replace(str(tmp), str(p))
print("g100 honest frame written")
