from pathlib import Path

p = Path(r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\gerar_lv_dxf_stog.py")
t = p.read_text(encoding="utf-8")


def sub(old, new, label):
    global t
    if old not in t:
        raise SystemExit("missing " + label)
    t = t.replace(old, new, 1)


sub(
    """        _y_body_top = float(y0) + float(h)
        for _xv in _split_xs:
            msp.add_line(
                (_xv, _y_body_top),
                (_xv, _top_panel_y + _top_panel_h),
                dxfattribs={'layer': 'Painéis'},
            )
""",
    """        # Vertical so no painel de 7 — nao atravessa a laje (secciona).
        for _xv in _split_xs:
            msp.add_line(
                (_xv, _top_panel_y),
                (_xv, _top_panel_y + _top_panel_h),
                dxfattribs={'layer': 'Painéis'},
            )
""",
    "section-7-v",
)

sub(
    """    # Parede esquerda em x0 (mantem origin N4 / pairing multi-seg).
    # Leading-marco skip de V internos quebrava split_n4 widths (N2-only).
    if has_degrau:
        msp.add_line((x0, y_shoulder), (x0, y_top), dxfattribs=a)
    else:
        msp.add_line((x0, y0), (x0, y_top), dxfattribs=a)
""",
    """    # Parede esquerda em x0. No ramo espelhado (degrau a direita) o bloco
    # abaixo desenha a parede cheia — nao duplicar aqui (vira V extra na
    # esquerda, colada nas cotas).
    _mirrored = has_degrau and degrau_start > x0 + 0.5
    if not _mirrored:
        if has_degrau:
            msp.add_line((x0, y_shoulder), (x0, y_top), dxfattribs=a)
        else:
            msp.add_line((x0, y0), (x0, y_top), dxfattribs=a)
""",
    "no-dup-left",
)

sub(
    """            cur_deg = _is_degrau_panel(panel, h)
            next_deg = _is_degrau_panel(panels[idx + 1], h)
            if cur_deg and next_deg:
""",
    """            cur_deg = _is_degrau_panel(panel, h)
            next_deg = _is_degrau_panel(panels[idx + 1], h)
            if lead_x is not None and x_right < lead_x - 0.1:
                x_cur = x_right
                continue
            if cur_deg and next_deg:
""",
    "skip-lead-marco-v",
)

sub(
    """        if any(abs(y - yb) < 1.1 for yb in ban):
            continue
        msp.add_line((x1, y), (x2, y), dxfattribs=attrs)
""",
    """        if any(abs(y - yb) < 1.1 for yb in ban):
            continue
        msp.add_line((x1, y), (x2, y), dxfattribs=attrs)
""",
    "noop-sarr",
)

# add h_face filter to N2 horiz replay — only if we can find the function body
old_sarr = '''        if any(abs(y - yb) < 1.1 for yb in ban):
            continue
        msp.add_line((x1, y), (x2, y), dxfattribs=attrs)
        n += 1
    return n
'''
new_sarr = '''        if any(abs(y - yb) < 1.1 for yb in ban):
            continue
        msp.add_line((x1, y), (x2, y), dxfattribs=attrs)
        n += 1
    return n
'''
# handled below with signature change

old_fn = '''def draw_sarr_lv_horizontal_from_n2(msp, x0, y0, sarrafos_horizontais,
                                    *, frame_ys=None):
    """Replay fiel dos sarrafos horizontais capturados no N2.

    ``frame_ys``: Y de contorno Painéis (ombro/topo/base) — não redesenhar
    sarrafo em cima da linha de painel (conflito visual).
    """
    attrs = {'layer': 'SARR_2.2x7'}
    ban = [float(y) for y in (frame_ys or [])]
    n = 0
    for spec in sarrafos_horizontais or []:
        try:
            y = y0 + float(spec.get('y_offset', 0) or 0)
            x1 = x0 + float(spec.get('x_left', 0) or 0)
            x2 = x0 + float(spec.get('x_right', 0) or 0)
        except Exception:
            continue
        if x2 - x1 < 4.0:
            continue
        if any(abs(y - yb) < 1.1 for yb in ban):
            continue
        msp.add_line((x1, y), (x2, y), dxfattribs=attrs)
        n += 1
    return n
'''
new_fn = '''def draw_sarr_lv_horizontal_from_n2(msp, x0, y0, sarrafos_horizontais,
                                    *, frame_ys=None, h_face=None):
    """Replay fiel dos sarrafos horizontais capturados no N2.

    ``frame_ys``: Y de contorno Painéis (ombro/topo/base) — não redesenhar
    sarrafo em cima da linha de painel (conflito visual).
    y_offset acima do corpo (laje / painel de 7) nao e sarrafo de painel.
    """
    attrs = {'layer': 'SARR_2.2x7'}
    ban = [float(y) for y in (frame_ys or [])]
    y_max = None if h_face is None else float(y0) + float(h_face) + 0.5
    n = 0
    for spec in sarrafos_horizontais or []:
        try:
            y = y0 + float(spec.get('y_offset', 0) or 0)
            x1 = x0 + float(spec.get('x_left', 0) or 0)
            x2 = x0 + float(spec.get('x_right', 0) or 0)
        except Exception:
            continue
        if x2 - x1 < 4.0:
            continue
        if y_max is not None and y > y_max:
            continue
        if any(abs(y - yb) < 1.1 for yb in ban):
            continue
        msp.add_line((x1, y), (x2, y), dxfattribs=attrs)
        n += 1
    return n
'''
sub(old_fn, new_fn, "sarr-filter")

sub(
    """        draw_sarr_lv_horizontal_from_n2(
            msp, x0, y0, sarrafos_horizontais, frame_ys=_ys_frame,
        )
""",
    """        draw_sarr_lv_horizontal_from_n2(
            msp, x0, y0, sarrafos_horizontais, frame_ys=_ys_frame,
            h_face=h,
        )
""",
    "sarr-call",
)

sub(
    """    a_cota = {'layer': 'COTA'}
    # inset à direita: hatch nao encosta no body_end (evita aresta = parede)
    x_hatch_r = float(x_right) - 0.8
    if x_hatch_r <= x_left + 0.5:
        x_hatch_r = float(x_right)
    # Laterais + tampa. A base ja coincide com o topo do corpo em Painéis.
    msp.add_line((x_left, y_bot), (x_left, y_top), dxfattribs=a_cota)
    msp.add_line((x_left, y_top), (x_hatch_r, y_top), dxfattribs=a_cota)
    msp.add_line((x_right, y_bot), (x_right, y_top), dxfattribs=a_cota)
""",
    """    a_cota = {'layer': 'COTA'}
    # inset à direita: hatch nao encosta no body_end (evita aresta = parede)
    x_hatch_r = float(x_right) - 0.8
    if x_hatch_r <= x_left + 0.5:
        x_hatch_r = float(x_right)
    # So a tampa. Laterais nas paredes externas colam nas cotas 15/7 e
    # parecem "linha de painel extra gerada pela cota".
    msp.add_line((x_left, y_top), (x_hatch_r, y_top), dxfattribs=a_cota)
""",
    "vazio-no-side-v",
)

dst = Path(str(p) + ".new")
dst.write_text(t, encoding="utf-8")
import ast
ast.parse(t)
print("ok", dst.stat().st_size)
