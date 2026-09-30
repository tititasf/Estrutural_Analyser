# -*- coding: utf-8 -*-
from pathlib import Path
import ast
import os
import time

p = Path(r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\gerar_lv_dxf_stog.py")
t = p.read_text(encoding="utf-8")


def sub(old, new, label):
    global t
    if old not in t:
        raise SystemExit("missing " + label)
    t = t.replace(old, new, 1)


sub(
    """    if has_laje_sup and 'SCO-___-LAJ' not in skip_layers:
        x_cur = x0
        _small_x_laje = _small_panel_start_x(x0, h, panels)
        for p in panels:
            pw = p['width']
            ls = (
                float(p.get('laje_sup_local', p.get('slab_top', 0)) or 0)
                if has_local_sup else float(laje_sup or 0)
            )
            # Painéis de degrau (P1) são mais baixos que h_face: sem laje acima
            _ph1 = float(p.get('height1', 0) or 0)
            # Zona de marco (estreitos finais): a laje/marco e desenhada pelo
            # contorno N2 + AR-CONC — NAO caixinhas ANSI31 por painel (print
            # ShareX: lixo na altura da laje a direita).
            _in_marco = (
                _small_x_laje is not None
                and x_cur >= _small_x_laje - 0.1
                and not _is_degrau_panel(p, h)
                and pw < 25.0
            )
            if ls <= 0 or _in_marco or (0 < _ph1 < h - 5.0 and
                           float(p.get('laje_central_alt', 0) or 0) == 0):
                x_cur += pw
                continue
            pts = [(x_cur, y0+h), (x_cur+pw, y0+h),
                   (x_cur+pw, y0+h+ls), (x_cur, y0+h+ls)]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': 'SCO-___-LAJ'})
            # N4: hachura somente em vazios; laje permanece como contorno.
            x_cur += pw
""",
    """    if has_laje_sup and 'SCO-___-LAJ' not in skip_layers:
        # Uma faixa continua 0→body_end. Caixinhas por painel inventavam V
        # interior atraves da laje (244 seccionado no 7 mas a laje ainda
        # ganhava aresta no mesmo X).
        _small_x_laje = _small_panel_start_x(x0, h, panels)
        _laje_right = (
            float(_small_x_laje) if _small_x_laje is not None
            else float(x0) + float(comprimento)
        )
        if has_local_sup:
            ls = max(
                (
                    float(p.get('laje_sup_local', p.get('slab_top', 0)) or 0)
                    for p in panels
                ),
                default=float(laje_sup or 0),
            ) or float(laje_sup or 0)
        else:
            ls = float(laje_sup or 0)
        if ls > 0 and _laje_right > float(x0) + 0.5:
            pts = [
                (x0, y0 + h), (_laje_right, y0 + h),
                (_laje_right, y0 + h + ls), (x0, y0 + h + ls),
            ]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': 'SCO-___-LAJ'})
""",
    "laje-continuous",
)

sub(
    """    if has_degrau and degrau_start > x0 + 0.5:
        msp.add_line((x0, y0), (x0, y_top), dxfattribs=a)
        x_cur = float(x0)
""",
    """    if has_degrau and degrau_start > x0 + 0.5:
        # Com marco a esquerda, a parede util e lead_x (N2). V em x0 cola
        # nas cotas 14/7 e vira "linha de painel extra na esquerda".
        if lead_x is None:
            msp.add_line((x0, y0), (x0, y_top), dxfattribs=a)
        x_cur = float(x0)
""",
    "no-lead-x0-wall",
)

sub(
    """        if h1 > h0 + 0.5:
            msp.add_line((h0, y_marco), (h1, y_marco), dxfattribs=a)
        # B: V7 so no divisor ~244 (degrau). NUNCA body_end / full_end.
        if thick_marco and has_degrau:
            y_v7_bot = float(y_marco) - 7.0
            pw0 = float(panels[0].get('width', 0) or 0)
            if pw0 >= 150.0:
                vx = float(x0) + pw0
                msp.add_line((vx, y_v7_bot), (vx, y_marco), dxfattribs=a)
""",
    """        if h1 > h0 + 0.5:
            msp.add_line((h0, y_marco), (h1, y_marco), dxfattribs=a)
        # Nao desenhar V7 residual no divisor largo: o painel de 7 ja secciona
        # so na faixa 7 (nao atravessa a laje).
""",
    "drop-v7-residual",
)

sub(
    """        _marco_right_x = _body_end
        _marco_label_sides = [
            (_vx, _side)
            for _vx, _side, _want in (
                (x0, -1.0, _want_left),
                (_marco_right_x, 1.0, _want_right),
            )
            if _want
        ]
""",
    """        _marco_right_x = _body_end
        _left_wall = (
            float(_lead_x_dim) if _lead_x_dim is not None else float(x0)
        )
        _marco_label_sides = [
            (_vx, _side)
            for _vx, _side, _want in (
                (_left_wall, -1.0, _want_left),
                (_marco_right_x, 1.0, _want_right),
            )
            if _want
        ]
""",
    "cota15-at-body",
)

sub(
    """            y7_bot = float(y0) + float(h) + float(_cota_marco)
            y7_top = y7_bot + float(_top_panel_h)
            _top_right_x = min(float(x0) + float(comprimento), float(_body_end) + 0.01)
            for _vx7, _side7 in ((x0, -1.0), (_top_right_x, 1.0)):
""",
    """            y7_bot = float(y0) + float(h) + float(_cota_marco)
            y7_top = y7_bot + float(_top_panel_h)
            _left7 = float(_top_panel_x)
            _top_right_x = min(float(_top_panel_right), float(_body_end) + 0.01)
            for _vx7, _side7 in ((_left7, -1.0), (_top_right_x, 1.0)):
""",
    "cota7-at-top-panel",
)

ast.parse(t)
dst = Path(str(p) + ".new")
dst.write_text(t, encoding="utf-8")
print("wrote", dst, dst.stat().st_size)

# replace locked original: try delete+move with retries
for i in range(8):
    try:
        if p.exists():
            os.remove(p)
        os.replace(dst, p)
        print("replaced", p, p.stat().st_size)
        break
    except OSError as exc:
        print("retry", i, exc)
        time.sleep(0.4)
else:
    print("LEFT_AT", dst)
