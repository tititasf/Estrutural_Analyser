# -*- coding: utf-8 -*-
"""
Motor Reverso PIL — Extrai ficha granular N2 de recorte DXF STOG pilar.

Estrategia (hibrida):
1. Lookup Fase-4: tenta ler JSON_Pilares/{elem_id}.json em obra_root
2. DXF Extract: le COTA texts, Hachura bbox, NOMENCLATURA labels
3. Merge: Fase-4 como base (confianca=0.95), DXF para validar e preencher gaps
"""

from pathlib import Path
import json, re, math

DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")

def _lookup_fase4_pil(elem_id: str, obra_root: Path) -> dict | None:
    """Busca JSON_Pilares/{elem_id}.json no obra_root. Retorna dict ou None."""
    candidates = [
        obra_root / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{elem_id}.json",
    ]
    for p in candidates:
        if p.exists():
            with open(p, encoding='utf-8') as f:
                return json.load(f)
    return None

def _infer_obra_root(recorte_path: str) -> Path | None:
    """Infere obra_root a partir do caminho do recorte."""
    p = Path(recorte_path)
    # DADOS-OBRAS/{obra}/Fase-2_Triagem/recortes_reversos/...
    for part in p.parts:
        if part.startswith("Obra_"):
            idx = p.parts.index(part)
            return Path(*p.parts[:idx+1])
    return None

def _extract_pil_from_dxf(dxf_path: str) -> dict:
    """
    Extrai campos PIL diretamente da geometria do DXF recorte.

    Retorna dict com campos disponiveis + '_confianca_extracao'.
    """
    import ezdxf
    result = {}
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        # 1. Coletar todos textos COTA
        cota_nums = []
        grade_value = None
        for e in msp:
            if e.dxftype() == 'TEXT' and 'COTA' in e.dxf.layer.upper():
                txt = e.dxf.text.strip()
                # Detectar grade: "82(GRADE)" ou "82 (GRADE)"
                grade_match = re.match(r'^(\d+(?:\.\d+)?)\s*\(GRADE\)', txt, re.IGNORECASE)
                if grade_match:
                    grade_value = float(grade_match.group(1))
                    continue
                try:
                    cota_nums.append(float(txt))
                except Exception:
                    pass

        # 2. grade_1 -> comprimento
        if grade_value:
            result['grade_1'] = grade_value
            result['comprimento'] = round(grade_value - 22, 2)

        # 3. Largura: menor valor COTA razoavel que nao seja h1/h2/h3 range
        if cota_nums:
            # Filtrar valores na faixa de largura tipica (9-100cm)
            widths = [v for v in cota_nums if 5 < v < 120]
            if widths and 'comprimento' in result:
                # A largura e menor que o comprimento
                comp = result['comprimento']
                candidates = [v for v in widths if v < comp]
                if candidates:
                    result['largura'] = min(candidates)

        # 4. Tentar extrair bbox do Hachura/CHAPA layer
        for e in msp:
            if e.dxftype() == 'LWPOLYLINE' and 'HACHU' in e.dxf.layer.upper():
                pts = list(e.get_points())
                if pts:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    w = round(abs(max(xs) - min(xs)), 2)
                    h = round(abs(max(ys) - min(ys)), 2)
                    if w > 5 and h > 5:
                        dim_a, dim_b = max(w, h), min(w, h)
                        if 'comprimento' not in result:
                            result['comprimento'] = dim_a
                        if 'largura' not in result:
                            result['largura'] = dim_b
                        break

        # 5. Faces ativas a partir de TEXTO_GERAL ou Texto Secao
        faces_ativas = set()
        for e in msp:
            if e.dxftype() == 'TEXT':
                lay = e.dxf.layer.upper()
                if 'TEXTO_GERAL' in lay or 'TEXTO' in lay:
                    txt = e.dxf.text.strip().upper()
                    if txt in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'):
                        faces_ativas.add(txt)

        # 6. Construir campos de faces
        comp = result.get('comprimento', 0)
        larg = result.get('largura', 0)
        for face in ('A','B','C','D','E','F','G','H'):
            ativa = face in faces_ativas or face in ('A','B','C','D')  # A-D sempre presentes
            if ativa and comp:
                larg1 = comp if face in ('A','B') else larg
                result[f'h1_{face}'] = 2.0
                result[f'h2_{face}'] = 244.0
                result[f'h3_{face}'] = 34.0  # tipico para h=280
                result[f'h4_{face}'] = 0.0
                result[f'h5_{face}'] = 0.0
                result[f'larg1_{face}'] = larg1
                result[f'larg2_{face}'] = 0.0
                result[f'larg3_{face}'] = 0.0
                result[f'laje_{face}'] = 0.0
                result[f'posicao_laje_{face}'] = 0.0
            else:
                for suffix in ('h1','h2','h3','h4','h5','larg1','larg2','larg3','laje','posicao_laje'):
                    result[f'{suffix}_{face}'] = 0.0

        # 6.5. Per-face laje extraction via COTA geometry
        # Faces como B podem ter sub-painel de laje diferente de A.
        # Detecta: sum(cotas_face > 10) < pd → zona vazia no topo = posicao_laje
        _face_label_xs: dict[str, float] = {}
        _face_label_ys: list[float] = []
        for _e in msp:
            if _e.dxftype() == 'TEXT':
                _m = re.match(r'^[A-Z]\d+\.([ABCDEFGH])$', _e.dxf.text.strip())
                if _m:
                    _face_label_xs[_m.group(1)] = _e.dxf.insert.x
                    _face_label_ys.append(_e.dxf.insert.y)
        # y minimo dos labels = base aproximada do pilar; exclui cotas de largura
        # colocadas abaixo (ex: "82" comprimento em y < y_base)
        _y_face_base = (min(_face_label_ys) - 20.0) if _face_label_ys else -1e9

        if len(_face_label_xs) >= 2:
            # pd: maior valor plausivel em TODOS os textos (pd pode estar em
            # layer nao-COTA, ex.: "NIVEL 2° PAV." com texto "321.0").
            # Tambem verifica DIMENSION entities.
            _pd_cands: list[float] = []
            for _e in msp:
                _et = _e.dxftype()
                if _et == 'TEXT':
                    try:
                        _v = float(_e.dxf.text.strip().replace(',', '.'))
                        if 150.0 <= _v <= 700.0:
                            _pd_cands.append(_v)
                    except Exception:
                        pass
                elif _et == 'DIMENSION':
                    try:
                        _v = abs(_e.dxf.defpoint2.y - _e.dxf.defpoint3.y)
                        if 150.0 <= _v <= 700.0:
                            _pd_cands.append(_v)
                    except Exception:
                        pass
            _pd_val: float | None = round(max(_pd_cands), 1) if _pd_cands else None

            # COTA texts com posicao x para discriminar por face
            # Filtragem y >= _y_face_base exclui cotas de largura (comprimento=82)
            # colocadas abaixo da base do pilar.
            _cota_xy: list[tuple[float, float, float]] = []
            for _e in msp:
                if _e.dxftype() == 'TEXT' and 'COTA' in _e.dxf.layer.upper():
                    try:
                        _v = float(_e.dxf.text.strip().replace(',', '.'))
                        if 2.0 <= _v <= 700.0 and _e.dxf.insert.y >= _y_face_base:
                            _cota_xy.append((_e.dxf.insert.x, _e.dxf.insert.y, _v))
                    except Exception:
                        pass

            _faces_sorted = sorted(_face_label_xs.items(), key=lambda kv: kv[1])
            for _i, (_face, _x_face) in enumerate(_faces_sorted):
                if _face not in ('A', 'B', 'C', 'D'):
                    continue
                _x_next = (_faces_sorted[_i + 1][1]
                            if _i + 1 < len(_faces_sorted)
                            else _x_face + 600.0)
                _x_mid_left  = ((_faces_sorted[_i - 1][1] + _x_face) / 2
                                  if _i > 0 else _x_face - 600.0)
                _x_mid_right = (_x_face + _x_next) / 2

                # y_face_top: max y das V com h≥10cm (exclui ticks de cota)
                _y_face_top_mr = None
                for _ev_ft in msp:
                    if _ev_ft.dxftype() != 'LINE': continue
                    if 'PAIN' not in _ev_ft.dxf.layer.upper(): continue
                    if abs(_ev_ft.dxf.start.x - _ev_ft.dxf.end.x) > 0.5: continue
                    _xv_ft = (_ev_ft.dxf.start.x + _ev_ft.dxf.end.x) / 2
                    if not (_x_mid_left <= _xv_ft <= _x_mid_right): continue
                    _hv_ft = abs(_ev_ft.dxf.start.y - _ev_ft.dxf.end.y)
                    if _hv_ft < 10.0: continue
                    if max(_ev_ft.dxf.start.y, _ev_ft.dxf.end.y) < _y_face_base: continue
                    _yt_ft = max(_ev_ft.dxf.start.y, _ev_ft.dxf.end.y)
                    if _y_face_top_mr is None or _yt_ft > _y_face_top_mr:
                        _y_face_top_mr = _yt_ft

                # Intervals: linhas horizontais Painéis desta face (ground truth)
                _p_hs_mr = sorted(set(
                    round(_ep.dxf.start.y, 1) for _ep in msp
                    if _ep.dxftype() == 'LINE'
                    and 'PAIN' in _ep.dxf.layer.upper()
                    and abs(_ep.dxf.start.y - _ep.dxf.end.y) < 0.5
                    and _x_mid_left <= (_ep.dxf.start.x + _ep.dxf.end.x) / 2 <= _x_mid_right
                    and _ep.dxf.start.y >= _y_face_base
                    and (_y_face_top_mr is None or _ep.dxf.start.y <= _y_face_top_mr + 0.5)
                ))
                if len(_p_hs_mr) >= 2:
                    _ivs_mr = [round(_p_hs_mr[_j + 1] - _p_hs_mr[_j], 1)
                               for _j in range(len(_p_hs_mr) - 1)]
                    if _ivs_mr and abs(_ivs_mr[0] - 2.0) < 0.5:
                        _ivs_mr = _ivs_mr[1:]
                    if len(_ivs_mr) >= 1:
                        result[f'paineis_intervals_{_face}'] = _ivs_mr

                    # ── Abertura: vertical Painéis dentro dos limites x da face ──
                    _y_h0_mr = _p_hs_mr[0]
                    _face_th_mr = _p_hs_mr[-1] - _p_hs_mr[0]   # altura total da face
                    # xl/xr APENAS da linha H em y_h0 (base do painel, sempre full-width).
                    # Usar todas as linhas H infla xr/xl com linhas de cota DIMENSION
                    # que saem fora do painel real, causando lado/largura errados.
                    _hx_mr = []
                    for _ehx in msp:
                        if _ehx.dxftype() != 'LINE': continue
                        if 'PAIN' not in _ehx.dxf.layer.upper(): continue
                        if abs(_ehx.dxf.start.y - _ehx.dxf.end.y) > 0.5: continue
                        if abs(_ehx.dxf.start.y - _y_h0_mr) > 0.5: continue  # só y_h0
                        _xc_hx = (_ehx.dxf.start.x + _ehx.dxf.end.x) / 2
                        if _x_mid_left <= _xc_hx <= _x_mid_right:
                            _hx_mr.extend([_ehx.dxf.start.x, _ehx.dxf.end.x])
                    if _hx_mr and _face_th_mr > 0:
                        _xl_mr = min(_hx_mr)
                        _xr_mr = max(_hx_mr)
                        # menor H por y → endpoints para filtro de abertura
                        _mep_mr: dict = {}
                        for _ehx2 in msp:
                            if _ehx2.dxftype() != 'LINE': continue
                            if 'PAIN' not in _ehx2.dxf.layer.upper(): continue
                            if abs(_ehx2.dxf.start.y - _ehx2.dxf.end.y) > 0.5: continue
                            _xc2 = (_ehx2.dxf.start.x + _ehx2.dxf.end.x) / 2
                            if not (_x_mid_left <= _xc2 <= _x_mid_right
                                    and _ehx2.dxf.start.y >= _y_face_base): continue
                            _epy2 = round(_ehx2.dxf.start.y, 1)
                            _epw2 = abs(_ehx2.dxf.start.x - _ehx2.dxf.end.x)
                            _ex1  = round(min(_ehx2.dxf.start.x, _ehx2.dxf.end.x), 1)
                            _ex2  = round(max(_ehx2.dxf.start.x, _ehx2.dxf.end.x), 1)
                            if _epy2 not in _mep_mr or _epw2 < _mep_mr[_epy2][2]:
                                _mep_mr[_epy2] = (_ex1, _ex2, _epw2)
                        # coleta inner verts individuais
                        _ivraw_mr = []
                        for _evr in msp:
                            if _evr.dxftype() != 'LINE': continue
                            if 'PAIN' not in _evr.dxf.layer.upper(): continue
                            _xs_r, _xe_r = _evr.dxf.start.x, _evr.dxf.end.x
                            _ys_r, _ye_r = _evr.dxf.start.y, _evr.dxf.end.y
                            if abs(_xs_r - _xe_r) > 0.5: continue
                            _xv_r = (_xs_r + _xe_r) / 2
                            if _xv_r <= _xl_mr + 2.0 or _xv_r >= _xr_mr - 2.0: continue
                            if _xv_r < _x_mid_left or _xv_r > _x_mid_right: continue
                            if abs(_ys_r - _ye_r) < 5.0: continue
                            if max(_ys_r, _ye_r) < _y_face_base: continue
                            if _y_face_top_mr is not None and max(_ys_r, _ye_r) > _y_face_top_mr + 1.0: continue
                            _ivraw_mr.append({
                                'x':     round(_xv_r, 1),
                                'y_bot': round(min(_ys_r, _ye_r), 1),
                                'y_top': round(max(_ys_r, _ye_r), 1),
                            })
                        # agrupa por x (±3cm), guarda segs individuais
                        _grps_mr: list = []
                        for _vv in sorted(_ivraw_mr, key=lambda v: v['x']):
                            _placed = False
                            for _g in _grps_mr:
                                if abs(_vv['x'] - _g['x']) <= 3.0:
                                    _g['y_bot'] = min(_g['y_bot'], _vv['y_bot'])
                                    _g['y_top'] = max(_g['y_top'], _vv['y_top'])
                                    _g['segs'].append({'y_bot': _vv['y_bot'], 'y_top': _vv['y_top']})
                                    _placed = True; break
                            if not _placed:
                                _grps_mr.append({
                                    'x': _vv['x'], 'y_bot': _vv['y_bot'], 'y_top': _vv['y_top'],
                                    'segs': [{'y_bot': _vv['y_bot'], 'y_top': _vv['y_top']}],
                                })
                        # filtro ratio
                        _rok_mr = [_g for _g in _grps_mr
                                   if (_g['y_top'] - _g['y_bot']) / _face_th_mr < 0.45]
                        if _rok_mr:
                            def _ep_mr(_xv, _y):
                                _ep = _mep_mr.get(_y)
                                return _ep and min(abs(_xv - _ep[0]), abs(_xv - _ep[1])) <= 2.5
                            _any_multi_mr = any(len(_g['segs']) > 1 for _g in _rok_mr)
                            if len(_rok_mr) >= 3 or _any_multi_mr:
                                _ov_mr = []
                                for _g in _rok_mr:
                                    _matched = None
                                    for _sg in sorted(_g['segs'], key=lambda s: s['y_bot']):
                                        if _ep_mr(_g['x'], _sg['y_bot']) or _ep_mr(_g['x'], _sg['y_top']):
                                            _matched = _sg; break
                                    if _matched:
                                        _g['y_bot_u'] = _matched['y_bot']
                                        _g['y_top_u'] = _matched['y_top']
                                        _ov_mr.append(_g)
                                    elif _any_multi_mr:
                                        # sem endpoint match: usa menor segmento
                                        _sh = min(_g['segs'], key=lambda s: s['y_top'] - s['y_bot'])
                                        _g['y_bot_u'] = _sh['y_bot']; _g['y_top_u'] = _sh['y_top']
                                        _ov_mr.append(_g)
                            else:
                                for _g in _rok_mr:
                                    _g['y_bot_u'] = _g['y_bot']; _g['y_top_u'] = _g['y_top']
                                _ov_mr = _rok_mr
                            if len(_ov_mr) == 1:
                                _vv = _ov_mr[0]
                                _dl = _vv['x'] - _xl_mr; _dr = _xr_mr - _vv['x']
                                result[f'abertura_{_face}'] = {
                                    'lado':    'esquerdo' if _dl <= _dr else 'direito',
                                    'largura': round(_dl if _dl <= _dr else _dr, 1),
                                    'y_rel':   round(_vv['y_bot_u'] - _y_h0_mr, 1),
                                    'altura':  round(_vv['y_top_u'] - _vv['y_bot_u'], 1),
                                }
                            elif len(_ov_mr) == 2:
                                _v1r, _v2r = _ov_mr
                                _lm = round(_v2r['x'] - _v1r['x'], 1)
                                _xo = round(_v1r['x'] - _xl_mr, 1)
                                # detecta slots múltiplos (empilhados)
                                _sls: list = []
                                for _sg1 in _v1r['segs']:
                                    for _sg2 in _v2r['segs']:
                                        _ol = max(_sg1['y_bot'], _sg2['y_bot'])
                                        _oh = min(_sg1['y_top'], _sg2['y_top'])
                                        if _oh - _ol >= 5.0:
                                            _sb2 = round(_ol, 1); _st2 = round(_oh, 1)
                                            if not any(abs(_sb2 - s[0]) < 5 for s in _sls):
                                                _sls.append((_sb2, _st2))
                                _sls.sort(key=lambda s: s[0])
                                if len(_sls) <= 1:
                                    result[f'abertura_{_face}'] = {
                                        'lado':     'meio',
                                        'largura':  _lm,
                                        'x_offset': _xo,
                                        'y_rel':    round(min(_v1r['y_bot_u'], _v2r['y_bot_u']) - _y_h0_mr, 1),
                                        'altura':   round(max(_v1r['y_top_u'], _v2r['y_top_u'])
                                                         - min(_v1r['y_bot_u'], _v2r['y_bot_u']), 1),
                                    }
                                else:
                                    for _si, (_sb2, _st2) in enumerate(_sls, 1):
                                        result[f'abertura_{_face}_{_si}'] = {
                                            'lado':     'meio',
                                            'largura':  _lm,
                                            'x_offset': _xo,
                                            'y_rel':    round(_sb2 - _y_h0_mr, 1),
                                            'altura':   round(_st2 - _sb2, 1),
                                        }

                # Cotas desta face (valores > 10 excluem h1=2 e larguras 7/19)
                _face_cotas_y = sorted(
                    [(_y, _v) for _fx, _y, _v in _cota_xy
                     if _x_face <= _fx <= _x_next and _v > 10.0],
                    reverse=True,  # y decrescente = topo → base
                )
                _face_vals = [_v for _, _v in _face_cotas_y]
                _face_vals_asc = list(reversed(_face_vals))

                # h_par: segunda cota da base (índice 1) = zona parafuso
                if len(_face_vals_asc) >= 2:
                    result[f'h_par_{_face}'] = float(_face_vals_asc[1])

                # Laje: só quando não há intervals (intervals já incluem sub-painéis)
                _ivs_face_mr = result.get(f'paineis_intervals_{_face}')
                if not _ivs_face_mr and len(_face_vals) >= 3 and _pd_val:
                    _gap = round(_pd_val - sum(_face_vals), 1)
                    if _gap > 5.0:
                        result[f'laje_{_face}']         = float(_face_vals[0])
                        result[f'posicao_laje_{_face}'] = _gap

        # Fallback geométrico para DXFs sem anotações de texto (ex: TIPO/12_PAV).
        # SARR_2.2x7 span = (h_low - h1) + h_par = 122 + h_par → h_par = span - 122
        if not _face_label_xs:
            _sarr_ys: list[float] = []
            for _e in msp:
                if _e.dxf.layer == 'SARR_2.2x7':
                    if _e.dxftype() == 'LINE':
                        _sarr_ys += [_e.dxf.start.y, _e.dxf.end.y]
                    elif _e.dxftype() == 'LWPOLYLINE':
                        _sarr_ys += [p[1] for p in _e.get_points()]
            if _sarr_ys:
                _h_par_geom = round(max(_sarr_ys) - min(_sarr_ys) - 122.0, 1)
                if 50.0 <= _h_par_geom <= 150.0:
                    for _face in ('A', 'B'):
                        result.setdefault(f'h_par_{_face}', _h_par_geom)

        # 7. grade_2/3, distancia, par
        result.setdefault('grade_2', 0.0)
        result.setdefault('grade_3', 0.0)
        result.setdefault('distancia_1', 14.0)
        result.setdefault('distancia_2', 0.0)

        # Par calculation based on comprimento
        if comp:
            comp_adj = comp + 24
            n_par = _calc_n_parafusos(comp)
            pars = _distribute_pars(comp_adj, n_par)
            for i in range(1, 9):
                key = f'par_{i}_{i+1}'
                result[key] = pars[i-1] if i-1 < len(pars) else 0.0

        # Confidence based on what was extracted
        extracted = sum(1 for k in ('comprimento','largura','grade_1') if result.get(k,0) > 0)
        result['_confianca_extracao'] = round(0.5 + 0.15 * extracted, 2)

    except Exception as ex:
        result['_extracao_erro'] = str(ex)
        result['_confianca_extracao'] = 0.3

    return result

def _calc_n_parafusos(comprimento: float) -> int:
    if comprimento <= 120: return 2
    if comprimento <= 195: return 3
    if comprimento <= 260: return 4
    if comprimento <= 330: return 5
    if comprimento <= 400: return 6
    return 7

def _distribute_pars(total: float, n: int) -> list:
    """Distribui espacamentos entre n parafusos (n-1 intervalos)."""
    if n <= 1: return []
    intervals = n - 1
    unit = round(total / intervals, 1)
    return [unit] * intervals

def extrair_ficha_pilar(
    recorte_path: str,
    elemento_id: str,
    obra_name: str | None = None,
    obra_root: str | Path | None = None,
) -> dict:
    """
    Extrai ficha N2 para um pilar.

    Returns: dict com todos os campos + _er_meta
    """
    obra_root_path = Path(obra_root) if obra_root else _infer_obra_root(recorte_path)
    if obra_name and obra_root_path is None:
        obra_root_path = DADOS_OBRAS_ROOT / obra_name

    # Step 1: Fase-4 lookup
    fase4 = _lookup_fase4_pil(elemento_id, obra_root_path) if obra_root_path else None

    # Step 2: DXF extraction
    dxf_data = _extract_pil_from_dxf(recorte_path)
    dxf_conf = dxf_data.pop('_confianca_extracao', 0.5)
    dxf_err  = dxf_data.pop('_extracao_erro', None)

    if fase4:
        # Fase-4 como base — confianca alta
        result = {k: v for k, v in fase4.items() if k != '_sa_meta'}
        # Campos extraídos do DXF que NÃO existem no Fase-4 JSON (abertura, intervals)
        # são promovidos ao top-level para uso pelo gerador STOG.
        _DXF_PROMOTE = ('abertura_', 'paineis_intervals_')
        for _k, _v in dxf_data.items():
            if any(_k.startswith(_p) for _p in _DXF_PROMOTE):
                result[_k] = _v
        # Override pavimento from recorte path hint
        result['_er_meta'] = {
            'source': 'fase4',
            'dxf_path': str(recorte_path),
            'confianca': 0.95,
            'dxf_validation': dxf_data,
            'fase4_vs_dxf_gaps': _compare_fase4_dxf(fase4, dxf_data),
        }
        result['_confianca'] = 0.95
    else:
        # DXF extraction only
        elem_num = re.sub(r'[^\d]', '', elemento_id)
        result = {
            'numero': int(elem_num) if elem_num else 0,
            'nome': elemento_id,
            'comprimento': dxf_data.get('comprimento', 0.0),
            'largura': dxf_data.get('largura', 0.0),
            'altura': 280.0,
            'pavimento': 'Pavimento',
            'nivel_chegada': 0.0,
            'nivel_saida': 280.0,
            'modo_distribuicao': 'NOVA',
            **dxf_data,
        }
        result['_er_meta'] = {
            'source': 'dxf_extract',
            'dxf_path': str(recorte_path),
            'confianca': dxf_conf,
            'extracao_erro': dxf_err,
        }
        result['_confianca'] = dxf_conf

    return result

def _compare_fase4_dxf(fase4: dict, dxf: dict) -> dict:
    """Compara campos chave entre Fase-4 e extracao DXF."""
    gaps = {}
    for field in ('comprimento', 'largura', 'grade_1'):
        v4 = fase4.get(field, 0)
        vd = dxf.get(field, 0)
        if v4 and vd and abs(v4 - vd) / max(v4, 0.001) > 0.05:
            gaps[field] = {'fase4': v4, 'dxf': vd, 'delta_pct': round(abs(v4-vd)/v4*100,1)}
    return gaps


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    elem = sys.argv[2] if len(sys.argv) > 2 else "P1"
    obra = sys.argv[3] if len(sys.argv) > 3 else None
    result = extrair_ficha_pilar(path, elem, obra)
    print(json.dumps(result, indent=2, ensure_ascii=False))
