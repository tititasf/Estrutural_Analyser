# -*- coding: utf-8 -*-
"""Valida `classificar_aberturas_pilar` contra o N2, por POSICAO DE PAREDE.

    python scripts/arete/validar_abertura_pilar_lv.py [VIGA ...]

Sem argumentos roda as 32 vigas do 13_PAV.

A tampa no N2 e' um SARR vertical curto (5-9cm) e vem em PAR VERTICAL no
mesmo x — duas por PAREDE, nao duas por abertura. Parede que coincide com a
borda da face nao leva tampa (V13.A: a abertura 0..78 so' tem tampa em 78).

Logo a verificacao certa e': cada parede com tampa tem de bater com uma
parede de abertura prevista, e cada parede prevista longe da borda tem de
ter tampa. Contagem de tampas (o oraculo anterior) nao verifica nada — ele
dava 25/7 com um classificador que produzia 927 de largura.
"""
import collections, pathlib, sqlite3, sys
import ezdxf
R = pathlib.Path.cwd()
for p in (R, R / "scripts", R / "scripts" / "arete"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import gerar_lv_dxf_stog as lv
from arete.gerar_lv_n4_fichas import _entry_from_live_recorte
from lv_n4_face_unit_selection import select_n4_face_units

VIGAS = ("V13 V301 V302 V303 V304 V305 V306 V308 V310 V311 V312 V314 V315 V316 "
         "V317 V318 V319 V320 V321 V322 V323 V324 V325 V326 V327 V328 V329 V330 "
         "V331 V332 VF203 VF301").split()
if len(sys.argv) > 1:
    VIGAS = [a.upper() for a in sys.argv[1:]]
TOL = 3.0
conn = sqlite3.connect("../project_data.vision")


def paredes_com_tampa(n2):
    por_x = collections.defaultdict(list)
    for e in ezdxf.readfile(n2).modelspace():
        if e.dxftype() != "LINE" or "SARR" not in e.dxf.layer.upper():
            continue
        a, b = e.dxf.start, e.dxf.end
        if abs(b.x - a.x) > 0.5 or not (5.0 <= abs(b.y - a.y) <= 9.0):
            continue
        por_x[round(a.x, 1)].append(round(min(a.y, b.y), 1))
    return {x: ys for x, ys in por_x.items()}


tp = fn = fp = 0
print(f"{'viga':7s} {'tampa->prev':>12s} {'prev->tampa':>12s}  detalhe")
for V in VIGAS:
    row = conn.execute("SELECT recorte_path FROM reverse_eng_recortes WHERE "
                       "UPPER(elemento_id)=? AND UPPER(classe)='LV' "
                       "ORDER BY id DESC LIMIT 1", (V,)).fetchone()
    if not row:
        continue
    tampas = paredes_com_tampa(row[0])
    ent = _entry_from_live_recorte(V)
    if not ent:
        continue
    prev = []      # (x_abs, y_bot, y_top, e_borda)
    for u in select_n4_face_units(lv, ent.get("face_units") or [], V):
        bb = u.get("bbox") or {}
        xl, xr = float(bb.get("x_left", 0)), float(bb.get("x_right", 0))
        yb = float(bb.get("y_bot", 0))
        yt = yb + float(u.get("h_body", 0) or 0)
        for a, b in lv.classificar_aberturas_pilar(
                u.get("panels") or [], u.get("sarrafos_horizontais") or [],
                painel_sup_width=float(u.get("painel_sup_width", 0) or 0),
                painel_sup_x_offset=float(u.get("painel_sup_x_offset", 0) or 0)):
            for rel in (a, b):
                xabs = xl + rel
                borda = abs(xabs - xl) <= 8.0 or abs(xabs - xr) <= 8.0
                prev.append((xabs, yb, yt, borda))
    faltou, sobrou = [], []
    for x, ys in tampas.items():
        y0 = min(ys)
        if not any(abs(x - px) <= TOL and pyb - 15 <= y0 <= pyt + 15
                   for px, pyb, pyt, _ in prev):
            faltou.append(x)
    for px, pyb, pyt, borda in prev:
        if borda:
            continue
        if not any(abs(px - x) <= TOL and pyb - 15 <= min(ys) <= pyt + 15
                   for x, ys in tampas.items()):
            sobrou.append(round(px, 1))
    ok_t = len(tampas) - len(faltou)
    ok_p = len([p for p in prev if not p[3]]) - len(sobrou)
    tp += ok_t; fn += len(faltou); fp += len(sobrou)
    marca = ""
    if faltou:
        marca += f" tampa sem previsao: {sorted(faltou)[:4]}"
    if sobrou:
        marca += f" previsao sem tampa: {sorted(set(sobrou))[:4]}"
    print(f"{V:7s} {ok_t:5d}/{len(tampas):<6d} {ok_p:5d}/"
          f"{len([p for p in prev if not p[3]]):<6d} {marca}")
print(f"\nparedes com tampa acertadas: {tp}  sem previsao: {fn}  "
      f"previstas sem tampa: {fp}")
