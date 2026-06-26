"""Patch draw_cima v2 — 6 correções baseadas no robô SCR."""
from pathlib import Path

src_path = Path(__file__).parent / "gerar_pl_dxf_stog.py"
src = src_path.read_text(encoding="utf-8")

def patch(old, new, label):
    global src
    cnt = src.count(old)
    assert cnt == 1, f"[{label}] count={cnt}"
    src = src.replace(old, new)
    print(f"  OK [{label}]")

# ── P1: Restaurar 8 hp_ansi nos sarrafos (removidos em v2.3 por engano) ──────
OLD_SARR = """\
    # Face B (left vertical), lower half
    rp(sarr_l, cy_b, TS, SARR_H, 'SARRAFO', lw=13)
    # Face B upper half
    rp(sarr_l, cy_t - SARR_H, TS, SARR_H, 'SARRAFO', lw=13)
    # Face D (right vertical), lower half
    rp(chapa_r, cy_b, TS, SARR_H, 'SARRAFO', lw=13)
    # Face D upper half
    rp(chapa_r, cy_t - SARR_H, TS, SARR_H, 'SARRAFO', lw=13)
    # Corner BL top: x[corner_l, sarr_l], y[cy_t-2, cy_t]
    rp(corner_l, cy_t - CORNER_H, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    # Corner BL bottom: y[cy_b, cy_b+2]
    rp(corner_l, cy_b, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    # Corner DR top:
    rp(sarr_r, cy_t - CORNER_H, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    # Corner DR bottom:
    rp(sarr_r, cy_b, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    for e in entities[-8:]:
        if e.dxftype() == 'LWPOLYLINE':
            e.dxf.color = 251"""
NEW_SARR = """\
    # Face B (left vertical), lower half
    rp(sarr_l, cy_b, TS, SARR_H, 'SARRAFO', lw=13)
    hp_ansi(sarr_l, cy_b, TS, SARR_H)
    # Face B upper half
    rp(sarr_l, cy_t - SARR_H, TS, SARR_H, 'SARRAFO', lw=13)
    hp_ansi(sarr_l, cy_t - SARR_H, TS, SARR_H)
    # Face D (right vertical), lower half
    rp(chapa_r, cy_b, TS, SARR_H, 'SARRAFO', lw=13)
    hp_ansi(chapa_r, cy_b, TS, SARR_H)
    # Face D upper half
    rp(chapa_r, cy_t - SARR_H, TS, SARR_H, 'SARRAFO', lw=13)
    hp_ansi(chapa_r, cy_t - SARR_H, TS, SARR_H)
    # Corner BL top: x[corner_l, sarr_l], y[cy_t-2, cy_t]
    rp(corner_l, cy_t - CORNER_H, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    hp_ansi(corner_l, cy_t - CORNER_H, CORNER_W, CORNER_H)
    # Corner BL bottom: y[cy_b, cy_b+2]
    rp(corner_l, cy_b, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    hp_ansi(corner_l, cy_b, CORNER_W, CORNER_H)
    # Corner DR top:
    rp(sarr_r, cy_t - CORNER_H, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    hp_ansi(sarr_r, cy_t - CORNER_H, CORNER_W, CORNER_H)
    # Corner DR bottom:
    rp(sarr_r, cy_b, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    hp_ansi(sarr_r, cy_b, CORNER_W, CORNER_H)
    for e in entities[-16:]:
        if e.dxftype() == 'LWPOLYLINE':
            e.dxf.color = 251"""
patch(OLD_SARR, NEW_SARR, "P1-restore-hp_ansi-sarrafo")

# ── P2: Remover seção 3h wood-grain (hatch contaminante) ─────────────────────
OLD_WG = """\
    # ── 3h. Textura wood-grain (aproximação procedural, sobre Madeira/Perfil) ─
    # Achado empírico (recorte N2): textura formada por ~1.3125*grade_1+361.5
    # segmentos LINE curtos, bbox largura constante e altura linear em grade_1
    # — padrão repetido por área, sem geometria literal reproduzível sem o
    # hatch original. Aproximação: grade de tracos curtos (1 LINE/célula) sobre
    # a banda Madeira+Perfil (de py0_a2 a py0_c+PERFIL_W_OUT, largura
    # chapa_full_w), densidade calibrada para escalar com grade_1.
    wg_w = chapa_full_w
    wg_band_h = madeira_h + PERFIL_W_OUT
    wg_target = 1.3125 * grade_1 + 361.5
    wg_area_total = wg_w * wg_band_h * 2
    wg_spacing = (wg_area_total / wg_target) ** 0.5 if wg_target > 0 else 4.0
    n_cols = max(1, round(wg_w / wg_spacing))
    n_rows = max(1, round(wg_band_h / wg_spacing))
    cell_w = wg_w / n_cols
    cell_h = wg_band_h / n_rows
    tick = min(cell_w, cell_h) * 0.4

    def _wood_grain_band(y0):
        for r in range(n_rows):
            cy = y0 + (r + 0.5) * cell_h
            for c in range(n_cols):
                cxg = corner_l + (c + 0.5) * cell_w
                entities.append(msp.add_line(
                    (cxg - tick / 2.0, cy - tick / 2.0),
                    (cxg + tick / 2.0, cy + tick / 2.0),
                    dxfattribs={'layer': 'Hachura'},
                ))

    _wood_grain_band(py0_a2)
    _wood_grain_band(madeira_y0)

"""
NEW_WG = "\n"
patch(OLD_WG, NEW_WG, "P2-remove-wood-grain")

# ── P3: Adicionar hatch ANSI31 às grades (div_a/div_b) ───────────────────────
# Insere após _place_div_dim calls (seção 3f)
OLD_DIV = """\
    div_a = pj.get('grade_1_div_a') or []
    div_b = pj.get('grade_1_div_b') or []
    if div_a:
        _place_div_dim(div_a, py0_a2, offset=5)
    if div_b:
        _place_div_dim(div_b, py0_c + PERFIL_W_OUT, offset=-5)"""
NEW_DIV = """\
    div_a = pj.get('grade_1_div_a') or []
    div_b = pj.get('grade_1_div_b') or []
    if div_a:
        _place_div_dim(div_a, py0_a2, offset=5)
    if div_b:
        _place_div_dim(div_b, py0_c + PERFIL_W_OUT, offset=-5)

    # Hatch ANSI31 nos retângulos de grade (camada Hachura, como no original SCR)
    div_grades = div_a or div_b
    if div_grades:
        gcum = 0.0
        for gv in div_grades:
            gx0 = corner_l + gcum
            gx1 = corner_l + gcum + gv
            gcum += gv
            gpts = [(gx0, cy_b), (gx1, cy_b), (gx1, cy_t), (gx0, cy_t)]
            gh = msp.add_hatch(color=7, dxfattribs={'layer': 'Hachura'})
            gh.paths.add_polyline_path(gpts, is_closed=True)
            gh.set_pattern_fill('ANSI31', scale=0.5)
            entities.append(gh)"""
patch(OLD_DIV, NEW_DIV, "P3-grade-hatch")

# ── P4: Remover GRAVATA PLINEs (seção 5) + gravata cota + substituir bolt code
OLD_SEC56 = """\
    # ── 5. Gravatas (4 PLINEs on GRAVATA, do SCR P1_CIMA) ────────────────────
    GRAV_OUTER_H  = 7.0
    GRAV_INNER_H  = 3.0
    GRAV_INNER_BELOW = 11.0  # distância do concreto à borda interna da gravata inner
    grav_l = corner_l - EXTRA_GRAV
    grav_r = corner_r + EXTRA_GRAV
    grav_w = grav_r - grav_l
    # outer bottom: cy_b-16 a cy_b-9
    rp(grav_l, cy_b - GRAV_BELOW_OUTER - GRAV_OUTER_H, grav_w, GRAV_OUTER_H, 'GRAVATA')
    # outer top: cy_t+9 a cy_t+16
    rp(grav_l, cy_t + GRAV_BELOW_OUTER, grav_w, GRAV_OUTER_H, 'GRAVATA')
    # inner bottom: cy_b-14 a cy_b-11
    rp(grav_l, cy_b - GRAV_INNER_BELOW - GRAV_INNER_H, grav_w, GRAV_INNER_H, 'GRAVATA')
    # inner top: cy_t+11 a cy_t+14
    rp(grav_l, cy_t + GRAV_INNER_BELOW, grav_w, GRAV_INNER_H, 'GRAVATA')

    # ── 6. Cota span total gravata (layer "cota" minúsculo, do SCR) ──────────
    try:
        d = msp.add_linear_dim(
            base=(ox, cy_t + GRAV_BELOW_OUTER + GRAV_OUTER_H + 40),
            p1=(grav_l, cy_t + GRAV_BELOW_OUTER + GRAV_OUTER_H),
            p2=(grav_r, cy_t + GRAV_BELOW_OUTER + GRAV_OUTER_H),
            angle=0, dimstyle='cotax2',
            dxfattribs={'layer': 'cota'}
        )
        d.render()
        entities.append(d.dimension)
    except Exception:
        pass

    # ── 6b. Parafusos (PLINEs 1cm no layer Hachura, de distancia_1+par_X_Y) ──
    bolt_y0 = cy_b - GRAV_BELOW_OUTER - GRAV_OUTER_H - 8
    bolt_y1 = cy_t + GRAV_BELOW_OUTER + GRAV_OUTER_H + 8
    bolt_h  = bolt_y1 - bolt_y0
    dist1 = float(pj.get('distancia_1') or 0)
    if dist1 > 0:
        bolt_x = corner_l + dist1
        par_keys = [f'par_{i}_{i+1}' for i in range(1, 9)]
        spacings = [float(pj.get(k) or 0) for k in par_keys]
        # primeiro parafuso
        entities.append(msp.add_lwpolyline(
            [(bolt_x - 0.5, bolt_y0), (bolt_x + 0.5, bolt_y0),
             (bolt_x + 0.5, bolt_y1), (bolt_x - 0.5, bolt_y1)],
            close=True, dxfattribs={'layer': 'Hachura'}
        ))
        for sp in spacings:
            if sp <= 0:
                break
            bolt_x += sp
            if bolt_x > corner_r:
                break
            entities.append(msp.add_lwpolyline(
                [(bolt_x - 0.5, bolt_y0), (bolt_x + 0.5, bolt_y0),
                 (bolt_x + 0.5, bolt_y1), (bolt_x - 0.5, bolt_y1)],
                close=True, dxfattribs={'layer': 'Hachura'}
            ))"""
NEW_SEC56 = """\
    # ── 5. GRAVATA removida (não existe no recorte N2 ground truth) ───────────

    # ── 6. Parafusos (PLINEs layer Hachura — posições do robô SCR) ───────────
    # Robot: left_extremity = x_inicial - 12 = cx_l - 12 ≈ corner_l - 1
    #        spacings = par_1_2, par_2_3, ... (NÃO distancia_1)
    #        right_extremity = cx_r + 15.5 ≈ corner_r + 4.5
    # y: altura_parafuso = larg + 36.8 (comp < 223) → cy_b - 24.4 a cy_t + 24.4
    _bolt_half_extra = 18.4 if comp < 223 else 20.6
    bolt_y0 = cy_b - _bolt_half_extra - 6
    bolt_y1 = cy_t + _bolt_half_extra + 6

    def _bolt_pline(bx, is_intermediate=False):
        if is_intermediate:
            # Sólido abaixo do concreto
            entities.append(msp.add_lwpolyline(
                [(bx - 0.5, bolt_y0), (bx + 0.5, bolt_y0),
                 (bx + 0.5, cy_b - 2), (bx - 0.5, cy_b - 2)],
                close=True, dxfattribs={'layer': 'Hachura'}
            ))
            # Tracejado através do concreto
            entities.append(msp.add_lwpolyline(
                [(bx - 0.5, cy_b - 2), (bx + 0.5, cy_b - 2),
                 (bx + 0.5, cy_t + 2), (bx - 0.5, cy_t + 2)],
                close=True, dxfattribs={'layer': 'Hachura', 'linetype': 'HIDDEN'}
            ))
            # Sólido acima do concreto
            entities.append(msp.add_lwpolyline(
                [(bx - 0.5, cy_t + 2), (bx + 0.5, cy_t + 2),
                 (bx + 0.5, bolt_y1), (bx - 0.5, bolt_y1)],
                close=True, dxfattribs={'layer': 'Hachura'}
            ))
        else:
            # Extremidade: 1cm PLINE sólido do início ao fim
            entities.append(msp.add_lwpolyline(
                [(bx - 0.5, bolt_y0), (bx + 0.5, bolt_y0),
                 (bx + 0.5, bolt_y1), (bx - 0.5, bolt_y1)],
                close=True, dxfattribs={'layer': 'Hachura'}
            ))

    bx_left  = cx_l - 12.0   # extremidade esquerda (≈ corner_l - 1)
    bx_right = cx_r + 15.5   # extremidade direita  (≈ corner_r + 4.5)
    _bolt_pline(bx_left,  is_intermediate=False)
    par_keys = [f'par_{i}_{i+1}' for i in range(1, 9)]
    bx = bx_left
    for pk in par_keys:
        sp = float(pj.get(pk) or 0)
        if sp <= 0:
            break
        bx += sp
        if bx >= bx_right - 1:
            break
        _bolt_pline(bx, is_intermediate=True)
    _bolt_pline(bx_right, is_intermediate=False)"""
patch(OLD_SEC56, NEW_SEC56, "P4-remove-gravata-fix-bolts")

src_path.write_text(src, encoding="utf-8")
print("Todas as patches aplicadas.")
