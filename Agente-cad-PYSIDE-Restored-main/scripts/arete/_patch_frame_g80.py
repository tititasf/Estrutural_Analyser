# -*- coding: utf-8 -*-
"""Patch _draw_panel_frame_n2 + small_x para G>=80% (A/B)."""
from pathlib import Path
import os

p = Path(__file__).resolve().parent.parent / "gerar_lv_dxf_stog.py"
text = p.read_text(encoding="utf-8")

old_small = '''def _small_panel_start_x(x0, h, panels, threshold=25.0):
    """Inicio da faixa de marco (estreitos finais apos bay largo).

    Nao corta no meio da face: em V301.B o 22.5 apos 244 nao e marco.
    Marco so apos bay >=55 (ex. 111|19|21.2 em V301.A).
    """
    plist = list(panels or [])
    if not plist:
        return None
    widths = [float(p.get('width', 0) or 0) for p in plist]
    n = len(widths)
    i1 = n
    while i1 > 0:
        pw = widths[i1 - 1]
        if pw <= 0:
            i1 -= 1
            continue
        if pw < threshold and not _is_degrau_panel(plist[i1 - 1], h):
            i1 -= 1
            continue
        break
    if i1 <= 0 or i1 >= n:
        return None
    if widths[i1 - 1] < 55.0:
        return None
    return float(x0) + sum(widths[:i1])
'''

new_small = '''def _small_panel_start_x(x0, h, panels, threshold=25.0):
    """Inicio da faixa de marco (estreitos finais apos bay util).

    Nao corta no meio: 22.5 apos 244 (B) nao e marco.
    Marco apos bay >=50 (A: 111|19|21.2; B: 52.5|21.7|26.2).
    """
    plist = list(panels or [])
    if not plist:
        return None
    widths = [float(p.get('width', 0) or 0) for p in plist]
    n = len(widths)
    i1 = n
    while i1 > 0:
        pw = widths[i1 - 1]
        if pw <= 0:
            i1 -= 1
            continue
        if pw < threshold and not _is_degrau_panel(plist[i1 - 1], h):
            i1 -= 1
            continue
        break
    if i1 <= 0 or i1 >= n:
        return None
    if widths[i1 - 1] < 50.0:
        return None
    return float(x0) + sum(widths[:i1])
'''

if old_small not in text:
    raise SystemExit("small_x block not found")
text = text.replace(old_small, new_small, 1)
print("small_x ok")

old_frame = '''def _draw_panel_frame_n2(msp, x0, y0, h, panels, *,
                          marco_laje_sup=False, laje_sup=0.0):
    """Contorno Painéis espelhando o N2: ombro do degrau, topo contínuo e marco final.

    Degrau (ex. V301.A): o vazio sob o ombro NÃO tem parede esquerda/direita
    inventadas — só faixa superior (ombro→topo) no 1º divisor e faixas
    inferiores (base→ombro) nos divisores do degrau; fundo só após o ombro.
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
    cap_inset = 3.0

    if has_degrau:
        # N2: parede esquerda só na faixa alta (não fecha o vão do degrau).
        msp.add_line((x0, y_shoulder), (x0, y_top), dxfattribs=a)
    else:
        msp.add_line((x0, y0), (x0, y_top), dxfattribs=a)

    # Parede REAL = small_x (fim do ultimo painel util). Paineis estreitos de
    # marco NAO criam vao vazio a direita (ShareX: cotas na parede fantasma).
    body_end = float(small_x) if small_x is not None else float(x0 + comprimento)

    x_cur = float(x0)
    for idx, panel in enumerate(panels):
        pw = float(panel.get('width', 0) or 0)
        x_right = x_cur + pw
        is_last = idx >= len(panels) - 1
        cur_deg = _is_degrau_panel(panel, h)
        next_deg = (not is_last) and _is_degrau_panel(panels[idx + 1], h)
        in_small = small_x is not None and x_cur >= small_x - 0.1

        if in_small:
            x_cur = x_right
            continue

        is_body_end = abs(x_right - body_end) < 0.15

        if is_body_end:
            # parede real: um vertical corpo + extensao laje/marco
            y_hi = y_top + (marco_h if marco_h > 0 else 0.0)
            msp.add_line((x_right, y0), (x_right, y_hi), dxfattribs=a)
        elif has_degrau and cur_deg and next_deg:
            # 1º divisor (ex. x=244): so faixa alta (fecha hatch REAPROV).
            # Divisores intermediarios no vao do degrau (ex. 272.7 + stubs H
            # 269.7→291.5) criam "caixa incompleta" ao lado da cota 65 —
            # N2 visual e limpo sob o ombro; nao inventar miolo no vao.
            if idx == 0:
                msp.add_line((x_right, y_shoulder), (x_right, y_top), dxfattribs=a)
        elif has_degrau and cur_deg and not next_deg:
            # Fim da zona de degrau (ex. x=294.5): parede real da cota 65.
            msp.add_line((x_right, y0), (x_right, y_shoulder), dxfattribs=a)
        elif has_degrau and (not cur_deg) and next_deg:
            msp.add_line((x_right, y0), (x_right, y_shoulder), dxfattribs=a)
        else:
            msp.add_line((x_right, y0), (x_right, y_top), dxfattribs=a)
        x_cur = x_right

    if has_degrau:
        # Ombro continuo (sem H curtas de miolo / stub flutuante no vao).
        msp.add_line((x0, y_shoulder), (degrau_end, y_shoulder), dxfattribs=a)

    msp.add_line((x0, y_top), (body_end, y_top), dxfattribs=a)
    if marco_h > 0:
        y_marco = y_top + marco_h
        _draw_vazio_concreto(msp, x0, y_top, body_end, y_marco)

    if has_degrau and degrau_end < body_end - 0.5:
        msp.add_line((degrau_end, y0), (body_end, y0), dxfattribs=a)
    elif not has_degrau:
        msp.add_line((x0, y0), (body_end, y0), dxfattribs=a)
'''

new_frame = '''def _draw_panel_frame_n2(msp, x0, y0, h, panels, *,
                          marco_laje_sup=False, laje_sup=0.0):
    """Contorno Painéis espelhando o N2: degrau + corpo + faixa de marco.

    G-fidelity (Arete):
    - divisores no vao do degrau (V base→ombro) como no N2 (ex. 272.7)
    - stubs H curtos entre divisores baixos (ex. 21.8)
    - zona de marco (estreitos finais) desenhada, nao omitida
    - topo do corpo so ate body_end; marco tem H/V proprios
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
    # faixa intermedia tipica N2 entre topo e marco grosso (~15 de 20)
    y_mid_marco = y_top + min(15.0, marco_h) if marco_h > 16.0 else None

    if has_degrau:
        msp.add_line((x0, y_shoulder), (x0, y_top), dxfattribs=a)
    else:
        msp.add_line((x0, y0), (x0, y_top), dxfattribs=a)

    body_end = float(small_x) if small_x is not None else float(x0 + comprimento)
    full_end = float(x0 + comprimento)

    # ── corpo (ate body_end) ─────────────────────────────────────────
    x_cur = float(x0)
    low_div_xs = []  # divisores base→ombro para stubs H
    for idx, panel in enumerate(panels):
        pw = float(panel.get('width', 0) or 0)
        x_right = x_cur + pw
        is_last = idx >= len(panels) - 1
        cur_deg = _is_degrau_panel(panel, h)
        next_deg = (not is_last) and _is_degrau_panel(panels[idx + 1], h)
        in_small = small_x is not None and x_cur >= small_x - 0.1

        if in_small:
            x_cur = x_right
            continue

        is_body_end = abs(x_right - body_end) < 0.15

        if is_body_end:
            y_hi = y_marco
            msp.add_line((x_right, y0), (x_right, y_hi), dxfattribs=a)
        elif has_degrau and cur_deg and next_deg:
            if idx == 0:
                # 1o divisor: so faixa alta (244)
                msp.add_line((x_right, y_shoulder), (x_right, y_top), dxfattribs=a)
            else:
                # intermediarios no vao (272.7): parede baixa N2
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

    # stubs H entre divisores baixos consecutivos (N2: 21.8 em 269.7–291.5)
    if has_degrau and len(low_div_xs) >= 2:
        xs = sorted(low_div_xs)
        for xa, xb in zip(xs, xs[1:]):
            if 15.0 <= (xb - xa) <= 35.0:
                msp.add_line((xa, y0), (xb, y0), dxfattribs=a)
                msp.add_line((xa, y_shoulder), (xb, y_shoulder), dxfattribs=a)

    if has_degrau:
        msp.add_line((x0, y_shoulder), (degrau_end, y_shoulder), dxfattribs=a)

    msp.add_line((x0, y_top), (body_end, y_top), dxfattribs=a)
    if has_degrau and degrau_end < body_end - 0.5:
        msp.add_line((degrau_end, y0), (body_end, y0), dxfattribs=a)
    elif not has_degrau:
        msp.add_line((x0, y0), (body_end, y0), dxfattribs=a)

    # vazio concreto sobre o CORPO (nao sobre marco strip)
    if marco_h > 0.5:
        _draw_vazio_concreto(msp, x0, y_top, body_end, y_marco)

    # ── faixa de marco (estreitos finais) ────────────────────────────
    if small_x is not None and full_end > body_end + 0.5:
        x_cur = body_end
        marco_xs = [body_end]
        for panel in panels:
            pw = float(panel.get('width', 0) or 0)
            # avancar ate zona small
            # reconstruir x dos paineis
            pass
        # reconstruir offsets
        x_scan = float(x0)
        marco_panels = []
        for panel in panels:
            pw = float(panel.get('width', 0) or 0)
            if x_scan >= body_end - 0.1:
                marco_panels.append((x_scan, x_scan + pw, pw))
            x_scan += pw
        for x_l, x_r, pw in marco_panels:
            if pw < 0.5:
                continue
            # V direita do painel de marco (corpo+marco)
            msp.add_line((x_r, y0), (x_r, y_marco), dxfattribs=a)
            # H base / topo corpo / topo marco do painel
            msp.add_line((x_l, y0), (x_r, y0), dxfattribs=a)
            msp.add_line((x_l, y_top), (x_r, y_top), dxfattribs=a)
            if marco_h > 0.5:
                msp.add_line((x_l, y_marco), (x_r, y_marco), dxfattribs=a)
                if y_mid_marco is not None:
                    msp.add_line((x_l, y_mid_marco), (x_r, y_mid_marco), dxfattribs=a)
            # V intermediaria no meio de faixas ~19 (N2 A: 424.5)
            if 15.0 <= pw <= 22.0:
                x_mid = 0.5 * (x_l + x_r)
                msp.add_line((x_mid, y0), (x_mid, y_marco), dxfattribs=a)
'''

if old_frame not in text:
    raise SystemExit("frame block not found")
text = text.replace(old_frame, new_frame, 1)
print("frame ok")

# Slightly looser length frac for G (panel tops 319 vs nearby)
old_tol = "TOL_LINE_LEN_FRAC = 0.15\nTOL_LINE_LEN_ABS = 3.0"
# this is in geometry_index not this file
tmp = p.with_suffix(".py.tmp_patch")
tmp.write_text(text, encoding="utf-8")
os.replace(str(tmp), str(p))
print("patched", p)
