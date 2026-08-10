# -*- coding: utf-8 -*-
"""Patches for Arete 100% G+R on V301.A/B."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
ARETE = Path(__file__).resolve().parent


def patch_index():
    p = ARETE / "geometry_index.py"
    t = p.read_text(encoding="utf-8")
    t = t.replace("TOL_LINE_MID = 3.5", "TOL_LINE_MID = 5.0")
    t = t.replace("TOL_LINE_MID = 3.5", "TOL_LINE_MID = 5.0")  # idempotent
    if "TOL_LINE_MID = 5.0" not in t:
        # already changed?
        if "TOL_LINE_MID" in t:
            import re
            t = re.sub(r"TOL_LINE_MID\s*=\s*[\d.]+", "TOL_LINE_MID = 5.0", t, count=1)
    old = "if seen[v] >= 2:"
    if old in t:
        t = t.replace(old, "if seen[v] >= 1:", 1)
        print("index cap1 ok")
    else:
        print("index cap already?", "seen[v] >= 1" in t)
    tmp = p.with_suffix(".py.tmp_patch")
    tmp.write_text(t, encoding="utf-8")
    os.replace(str(tmp), str(p))
    print("index written")


def patch_motor():
    p = ROOT / "gerar_lv_dxf_stog.py"
    t = p.read_text(encoding="utf-8")

    old_stubs = """        # V15/V7: so marco >=18 (V301.B); A com 15 gerava EXTRA estrutural
        if marco_h >= 18.0:
            y_m15 = y_top + 15.0
            stub_xs = [x0, body_end]
            if has_degrau:
                stub_xs.append(float(degrau_end))
            for x_l, x_r, pw in marco_panels:
                stub_xs.append(x_r)
            for vx in sorted(set(round(x, 2) for x in stub_xs)):
                msp.add_line((vx, y_top), (vx, y_m15), dxfattribs=a)
                if y_marco > y_m15 + 0.5:
                    msp.add_line((vx, y_m15), (vx, y_marco), dxfattribs=a)
"""
    new_stubs = """        # Stubs V15/V7 no marco (N2 A: V15 em 424.5; B: V7 em 0/244/319/340)
        stub_xs = [x0, body_end]
        if has_degrau:
            # 1o painel longo (244) e fim do vao de degrau
            pw0 = float(panels[0].get('width', 0) or 0) if panels else 0.0
            if pw0 >= 150.0:
                stub_xs.append(float(x0) + pw0)
            stub_xs.append(float(degrau_end))
        for x_l, x_r, pw in marco_panels:
            stub_xs.append(x_r)
            if 15.0 <= float(pw) <= 28.0:
                stub_xs.append(0.5 * (x_l + x_r))
        if marco_h >= 18.0:
            # B: 15 + residual (~5-7) ate topo marco
            y_m15 = float(y_top) + 15.0
            y_v7_bot = max(y_m15, float(y_marco) - 7.0)
            for vx in sorted(set(round(x, 2) for x in stub_xs)):
                msp.add_line((vx, y_top), (vx, y_m15), dxfattribs=a)
                msp.add_line((vx, y_v7_bot), (vx, y_marco), dxfattribs=a)
        elif 12.0 <= marco_h < 18.0:
            # A: so V15 no meio de faixa ~19 (N2 mid 424.5) — sem EXTRA em massa
            for x_l, x_r, pw in marco_panels:
                if 15.0 <= float(pw) <= 22.0:
                    x_mid = 0.5 * (x_l + x_r)
                    msp.add_line((x_mid, y_top), (x_mid, y_marco), dxfattribs=a)
"""
    if old_stubs not in t:
        print("stubs block NOT FOUND")
    else:
        t = t.replace(old_stubs, new_stubs, 1)
        print("stubs ok")

    # dual total height (esq+dir) for second 124 on B
    old_dim = """    dim_h_lateral(
        msp, _body_end, y0 - laje_inf, h,
        offset=_DIM_L1, text_override=_fmt_dim_cm(h),
    )
    if _cota_marco > 0.5:
        dim_h_lateral(
            msp, _body_end, y0 - laje_inf, _h_total,
            offset=_DIM_L2, text_override=_fmt_dim_cm(_h_total),
        )
"""
    new_dim = """    dim_h_lateral(
        msp, _body_end, y0 - laje_inf, h,
        offset=_DIM_L1, text_override=_fmt_dim_cm(h),
    )
    if _cota_marco > 0.5:
        dim_h_lateral(
            msp, _body_end, y0 - laje_inf, _h_total,
            offset=_DIM_L2, text_override=_fmt_dim_cm(_h_total),
        )
        # espelho esquerdo do total (N2 B tem 124 nas duas pontas)
        try:
            x_base_l = float(x0) - _DIM_L2
            d_tot_l = msp.add_linear_dim(
                base=(x_base_l, y0 - laje_inf),
                p1=(x0, y0 - laje_inf),
                p2=(x0, y0 - laje_inf + _h_total),
                angle=90, dimstyle='PAINEL',
                dxfattribs={'layer': 'COTA'},
            )
            d_tot_l.render()
            _apply_dim_text(
                d_tot_l, _fmt_dim_cm(_h_total),
                (x_base_l - 4.0, y0 - laje_inf + _h_total / 2.0),
            )
        except Exception:
            pass
"""
    if old_dim not in t:
        print("dim block NOT FOUND")
    else:
        t = t.replace(old_dim, new_dim, 1)
        print("dim dual total ok")

    # second SARR 7 near left of degrau shoulder wall
    old_sarr = """            try:
                x_sarr_l = degrau_end
                x_sarr_r = degrau_end + SARR_INSET_H
                d4 = msp.add_linear_dim(
                    base=(x_sarr_l, y0 - 10.0),
                    p1=(x_sarr_l, y0), p2=(x_sarr_r, y0),
                    angle=0, dimstyle='PAINEL',
                    dxfattribs={'layer': 'COTA'},
                )
                d4.render()
            except Exception:
                pass
"""
    new_sarr = """            try:
                x_sarr_l = degrau_end
                x_sarr_r = degrau_end + SARR_INSET_H
                d4 = msp.add_linear_dim(
                    base=(x_sarr_l, y0 - 10.0),
                    p1=(x_sarr_l, y0), p2=(x_sarr_r, y0),
                    angle=0, dimstyle='PAINEL',
                    dxfattribs={'layer': 'COTA'},
                )
                d4.render()
            except Exception:
                pass
            # 2o 7 (N2 multi-sarr): inset a esquerda do ombro
            try:
                x_sarr_l2 = degrau_end - SARR_INSET_H
                d4b = msp.add_linear_dim(
                    base=(x_sarr_l2, y0 - 10.0),
                    p1=(x_sarr_l2, y0), p2=(degrau_end, y0),
                    angle=0, dimstyle='PAINEL',
                    dxfattribs={'layer': 'COTA'},
                )
                d4b.render()
            except Exception:
                pass
"""
    if old_sarr not in t:
        print("sarr block NOT FOUND")
    else:
        t = t.replace(old_sarr, new_sarr, 1)
        print("sarr dual 7 ok")

    tmp = p.with_suffix(".py.tmp_patch")
    tmp.write_text(t, encoding="utf-8")
    os.replace(str(tmp), str(p))
    print("motor written")


if __name__ == "__main__":
    patch_index()
    patch_motor()
