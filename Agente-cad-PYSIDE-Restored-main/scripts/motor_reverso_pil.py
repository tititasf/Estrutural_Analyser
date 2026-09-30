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

        _comp_geom_samples: list[float] = []  # amostras fw faces A/B → comp real

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
                # ── Trim spurious annotation-tick H from top of _p_hs_mr ──
                # Se nenhuma PAIN-V (h≥3cm) termina em _p_hs_mr[-1], essa H é
                # um bracket de cota STOG (não limite de painel) e deve ser
                # removida para não gerar interval espúrio no IVS.
                if len(_p_hs_mr) >= 2:
                    _top_h_mr = _p_hs_mr[-1]
                    _v_at_top = False
                    for _ev_trim in msp:
                        if _ev_trim.dxftype() != 'LINE': continue
                        if 'PAIN' not in _ev_trim.dxf.layer.upper(): continue
                        if abs(_ev_trim.dxf.start.x - _ev_trim.dxf.end.x) > 0.5: continue
                        _xvt = (_ev_trim.dxf.start.x + _ev_trim.dxf.end.x) / 2
                        if not (_x_mid_left <= _xvt <= _x_mid_right): continue
                        _yvt_max = max(_ev_trim.dxf.start.y, _ev_trim.dxf.end.y)
                        if abs(_yvt_max - _top_h_mr) < 1.0:
                            if abs(_ev_trim.dxf.start.y - _ev_trim.dxf.end.y) >= 3.0:
                                _v_at_top = True
                                break
                    if not _v_at_top:
                        _p_hs_mr = _p_hs_mr[:-1]

                if len(_p_hs_mr) >= 2:
                    _ivs_mr = [round(_p_hs_mr[_j + 1] - _p_hs_mr[_j], 1)
                               for _j in range(len(_p_hs_mr) - 1)]
                    if _ivs_mr and abs(_ivs_mr[0] - 2.0) < 0.5:
                        _ivs_mr = _ivs_mr[1:]
                        result[f'h1_geom_{_face}'] = 2.0
                    else:
                        result[f'h1_geom_{_face}'] = 0.0
                    if len(_ivs_mr) >= 1:
                        result[f'paineis_intervals_{_face}'] = _ivs_mr

                    # ── Abertura: detecta por PAIN-V acima do topo do corpo da face ──
                    # Estratégia: V lines com ymin >= y_body_top (topo das H full-width)
                    # e NOT em xl ou xr (bordas) = paredes internas de aberturas.
                    _y_h0_mr = _p_hs_mr[0]
                    _face_th_mr = _p_hs_mr[-1] - _p_hs_mr[0]
                    # xl/xr da face via H mais larga (primeira H = mais confiável)
                    _hx_mr = []
                    for _ehx in msp:
                        if _ehx.dxftype() != 'LINE': continue
                        if 'PAIN' not in _ehx.dxf.layer.upper(): continue
                        if abs(_ehx.dxf.start.y - _ehx.dxf.end.y) > 0.5: continue
                        if abs(_ehx.dxf.start.y - _y_h0_mr) > 0.5: continue
                        _xc_hx = (_ehx.dxf.start.x + _ehx.dxf.end.x) / 2
                        if _x_mid_left <= _xc_hx <= _x_mid_right:
                            _hx_mr.extend([_ehx.dxf.start.x, _ehx.dxf.end.x])
                    if _hx_mr and _face_th_mr > 0:
                        _xl_mr = min(_hx_mr)
                        _xr_mr = max(_hx_mr)
                        _fw_mr = _xr_mr - _xl_mr
                        if _fw_mr < 1.0:
                            pass  # skip degenerate face
                        else:
                            # Coleta comp geometrico de faces A/B (fw = comp+22)
                            if _face in ('A', 'B') and _fw_mr > 22:
                                _comp_geom_samples.append(round(_fw_mr - 22, 1))
                            # Extrai larg_c_geom da face C (fw real da face curta, sem +22)
                            if _face == 'C' and _fw_mr > 5:
                                result['larg_c_geom'] = round(_fw_mr, 1)
                            # y_face_body_top: penúltima H da face body (antes da zona de cota)
                            _y_body_top = (_p_hs_mr[-2] if len(_p_hs_mr) >= 2
                                           else _p_hs_mr[-1])

                            # cota_V_acima: PAIN-V com ymin >= _y_body_top,
                            # fora das bordas xl/xr, e estritamente dentro de [xl_mr, xr_mr]
                            _cva_inner: list[tuple] = []
                            for _evc in msp:
                                if _evc.dxftype() != 'LINE': continue
                                if 'PAIN' not in _evc.dxf.layer.upper(): continue
                                _xs_c = _evc.dxf.start.x; _xe_c = _evc.dxf.end.x
                                _ys_c = _evc.dxf.start.y; _ye_c = _evc.dxf.end.y
                                if abs(_xs_c - _xe_c) > 0.5: continue
                                _xv_c = (_xs_c + _xe_c) / 2
                                if not (_x_mid_left <= _xv_c <= _x_mid_right): continue
                                # deve estar DENTRO do intervalo xl_mr..xr_mr
                                if _xv_c < _xl_mr or _xv_c > _xr_mr: continue
                                _ymin_c = min(_ys_c, _ye_c); _ymax_c = max(_ys_c, _ye_c)
                                # inner wall começa na última H full-width (±2cm)
                                # annotation V do STOG começa 3cm acima → >2cm → excluído
                                if abs(_ymin_c - _y_body_top) > 2.0: continue
                                if _ymax_c - _ymin_c < 3.0: continue  # ignora ticks
                                # exclui bordas (xl e xr)
                                if abs(_xv_c - _xl_mr) <= 2.5 or abs(_xv_c - _xr_mr) <= 2.5:
                                    continue
                                _cva_inner.append((_xv_c, _ymin_c, _ymax_c,
                                                   round(_ymax_c - _ymin_c, 1)))

                            if _cva_inner:
                                # Agrupa por ymin (tolerância ±2cm) = zona
                                _zones: dict[float, list] = {}
                                for _xv, _yb, _yt, _hh in _cva_inner:
                                    _zk = round(_yb, 1)
                                    _matched_zone = None
                                    for _ezk in list(_zones.keys()):
                                        if abs(_zk - _ezk) <= 2.0:
                                            _matched_zone = _ezk; break
                                    if _matched_zone is None:
                                        _zones[_zk] = []
                                        _matched_zone = _zk
                                    _zones[_matched_zone].append((_xv, _yb, _yt, _hh))

                                # Processa apenas a PRIMEIRA zona (maior slot = zona principal)
                                # Zonas subsequentes são recortezinhos / laje (não abertura)
                                for _zone_yb, _zone_lines in sorted(_zones.items()):
                                    # x únicos da zona (agrupa ±3cm)
                                    _xs_zone: list[float] = []
                                    for _xv, _, _, _ in _zone_lines:
                                        if not any(abs(_xv - _xe) <= 3.0 for _xe in _xs_zone):
                                            _xs_zone.append(_xv)
                                    _xs_zone.sort()
                                    if not _xs_zone:
                                        continue

                                    _slot_h = max(_hh for _, _, _, _hh in _zone_lines)
                                    _y_rel_ab = round(_zone_yb - _y_h0_mr, 1)

                                    if len(_xs_zone) == 1:
                                        _xi = _xs_zone[0]
                                        _dl = round(_xi - _xl_mr, 1)
                                        _dr = round(_xr_mr - _xi, 1)
                                        if _dl > 0 and _dr > 0:
                                            result[f'abertura_{_face}'] = {
                                                'lado': 'esquerdo' if _dl <= _dr else 'direito',
                                                'largura': _dl if _dl <= _dr else _dr,
                                                'y_rel': _y_rel_ab, 'altura': _slot_h,
                                            }
                                            break  # apenas zona principal
                                    elif len(_xs_zone) == 2:
                                        _xi_l, _xi_r = _xs_zone[0], _xs_zone[1]
                                        _esq_larg = round(_xi_l - _xl_mr, 1)
                                        _dir_larg = round(_xr_mr - _xi_r, 1)
                                        if _esq_larg > 0 and _dir_larg > 0:
                                            # Duas aberturas de canto: esq1 + dir1
                                            result[f'abertura_{_face}_1'] = {
                                                'lado': 'esquerdo', 'largura': _esq_larg,
                                                'y_rel': _y_rel_ab, 'altura': _slot_h,
                                            }
                                            result[f'abertura_{_face}_2'] = {
                                                'lado': 'direito', 'largura': _dir_larg,
                                                'y_rel': _y_rel_ab, 'altura': _slot_h,
                                            }
                                            break  # apenas zona principal
                                        elif _esq_larg <= 0 and _dir_larg > 0:
                                            result[f'abertura_{_face}'] = {
                                                'lado': 'direito', 'largura': _dir_larg,
                                                'y_rel': _y_rel_ab, 'altura': _slot_h,
                                            }
                                            break
                                        elif _dir_larg <= 0 and _esq_larg > 0:
                                            result[f'abertura_{_face}'] = {
                                                'lado': 'esquerdo', 'largura': _esq_larg,
                                                'y_rel': _y_rel_ab, 'altura': _slot_h,
                                            }
                                            break

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

        # comprimento_geom: média das fw das faces A/B extraída das H lines (override Fase-4)
        if _comp_geom_samples:
            result['comprimento_geom'] = round(
                sum(_comp_geom_samples) / len(_comp_geom_samples), 1)

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
        _DXF_PROMOTE = ('abertura_', 'paineis_intervals_', 'comprimento_geom',
                        'h1_geom_', 'larg_c_geom')
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
