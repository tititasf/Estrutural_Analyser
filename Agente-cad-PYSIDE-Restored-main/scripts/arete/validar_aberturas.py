# -*- coding: utf-8 -*-
"""
validar_aberturas.py — Testa extração de aberturas nos itens de exemplo.
Uso: python scripts/arete/validar_aberturas.py
"""
import sys, re
from pathlib import Path

try:
    import ezdxf
except ImportError:
    sys.exit("ezdxf não instalado")

RECORTES_DIR = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/ALIMONTI - PARAISO - 13° PAV.- PL - R00")
ITEMS = ['P11', 'P17', 'P28', 'P29', 'P30', 'P31', 'P32']

RATIO_MAX  = 0.45   # span_vert / face_total_h — acima → divisória, não abertura
MARGIN     = 2.0    # cm: ignora verts próximos da borda da face
GROUP_TOL  = 3.0    # cm: agrupa verts na mesma posição x
EP_TOL     = 2.5    # cm: tolerância para coincidência com endpoint de menor H


def latest_dxf(item: str) -> Path | None:
    candidates = list(RECORTES_DIR.glob(f"PIL_{item}_motor_*.dxf"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: int(re.search(r'(\d+)\.dxf$', p.name).group(1)))


def extract_aberturas(dxf_path: Path) -> dict:
    """Extrai abertura_{face} para todas as faces ABCD do DXF."""
    result = {}
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    # Face labels
    face_label_xs: dict[str, float] = {}
    face_label_ys: list[float] = []
    for e in msp:
        if e.dxftype() == 'TEXT':
            m = re.match(r'^[A-Z]\d+\.([ABCDEFGH])$', e.dxf.text.strip())
            if m:
                face_label_xs[m.group(1)] = e.dxf.insert.x
                face_label_ys.append(e.dxf.insert.y)

    if len(face_label_xs) < 2:
        return result

    y_face_base = (min(face_label_ys) - 20.0) if face_label_ys else -1e9
    faces_sorted = sorted(face_label_xs.items(), key=lambda kv: kv[1])

    for i, (face, x_face) in enumerate(faces_sorted):
        if face not in ('A', 'B', 'C', 'D'):
            continue
        x_next      = faces_sorted[i + 1][1] if i + 1 < len(faces_sorted) else x_face + 600.0
        x_mid_left  = (faces_sorted[i - 1][1] + x_face) / 2 if i > 0 else x_face - 600.0
        x_mid_right = (x_face + x_next) / 2

        # ── y_face_top: max y das linhas V com h≥10cm (exclui ticks de cota <10cm) ──
        # Garante que p_hs não inclua linhas H de anotação de cota acima do painel real.
        _y_face_top = None
        for _ev in msp:
            if _ev.dxftype() != 'LINE': continue
            if 'PAIN' not in _ev.dxf.layer.upper(): continue
            if abs(_ev.dxf.start.x - _ev.dxf.end.x) > 0.5: continue  # deve ser vertical
            _xv = (_ev.dxf.start.x + _ev.dxf.end.x) / 2
            if not (x_mid_left <= _xv <= x_mid_right): continue
            _h_v = abs(_ev.dxf.start.y - _ev.dxf.end.y)
            if _h_v < 10.0: continue  # ignora ticks de cota curtos
            if max(_ev.dxf.start.y, _ev.dxf.end.y) < y_face_base: continue
            _yt = max(_ev.dxf.start.y, _ev.dxf.end.y)
            if _y_face_top is None or _yt > _y_face_top:
                _y_face_top = _yt

        # ── Linhas H da face (capadas em y_face_top para excluir cotas acima) ──
        p_hs = sorted(set(
            round(ep.dxf.start.y, 1)
            for ep in msp
            if ep.dxftype() == 'LINE'
            and 'PAIN' in ep.dxf.layer.upper()
            and abs(ep.dxf.start.y - ep.dxf.end.y) < 0.5
            and x_mid_left <= (ep.dxf.start.x + ep.dxf.end.x) / 2 <= x_mid_right
            and ep.dxf.start.y >= y_face_base
            and (_y_face_top is None or ep.dxf.start.y <= _y_face_top + 0.5)
        ))
        if len(p_hs) < 2:
            continue

        y_h0         = p_hs[0]
        face_total_h = p_hs[-1] - p_hs[0]

        # x extent da face — APENAS da linha H em y_h0 (base, sempre full-width).
        # Usar todas as y inflaria xl/xr com linhas de cota que saem do painel.
        hx_all: list[float] = []
        for ehx in msp:
            if ehx.dxftype() != 'LINE': continue
            if 'PAIN' not in ehx.dxf.layer.upper(): continue
            if abs(ehx.dxf.start.y - ehx.dxf.end.y) > 0.5: continue
            if abs(ehx.dxf.start.y - y_h0) > 0.5: continue  # só y_h0
            xc = (ehx.dxf.start.x + ehx.dxf.end.x) / 2
            if x_mid_left <= xc <= x_mid_right:
                hx_all.extend([ehx.dxf.start.x, ehx.dxf.end.x])
        if not hx_all:
            continue
        xl = min(hx_all)
        xr = max(hx_all)

        # intervals sem h1 inicial
        ivs = [round(p_hs[j + 1] - p_hs[j], 1) for j in range(len(p_hs) - 1)]
        if ivs and abs(ivs[0] - 2.0) < 0.5:
            ivs = ivs[1:]
        result[f'intervals_{face}'] = ivs
        result[f'face_w_{face}']    = round(xr - xl, 1)

        # ── Menor H por y → endpoints ──
        min_ep_by_y: dict[float, tuple[float, float, float]] = {}
        for ep in msp:
            if ep.dxftype() != 'LINE': continue
            if 'PAIN' not in ep.dxf.layer.upper(): continue
            if abs(ep.dxf.start.y - ep.dxf.end.y) > 0.5: continue
            xc = (ep.dxf.start.x + ep.dxf.end.x) / 2
            if not (x_mid_left <= xc <= x_mid_right and ep.dxf.start.y >= y_face_base):
                continue
            epy = round(ep.dxf.start.y, 1)
            epw = abs(ep.dxf.start.x - ep.dxf.end.x)
            ex1 = round(min(ep.dxf.start.x, ep.dxf.end.x), 1)
            ex2 = round(max(ep.dxf.start.x, ep.dxf.end.x), 1)
            if epy not in min_ep_by_y or epw < min_ep_by_y[epy][2]:
                min_ep_by_y[epy] = (ex1, ex2, epw)

        def ep_matches(x_v: float, y: float) -> bool:
            ep = min_ep_by_y.get(y)
            if ep is None:
                return False
            return min(abs(x_v - ep[0]), abs(x_v - ep[1])) <= EP_TOL

        # ── Coleta inner verts individuais ──
        iverts_raw: list[dict] = []
        for ev in msp:
            if ev.dxftype() != 'LINE': continue
            if 'PAIN' not in ev.dxf.layer.upper(): continue
            xs, xe = ev.dxf.start.x, ev.dxf.end.x
            ys, ye = ev.dxf.start.y, ev.dxf.end.y
            if abs(xs - xe) > 0.5: continue
            xv = (xs + xe) / 2
            if xv <= xl + MARGIN or xv >= xr - MARGIN: continue
            if not (x_mid_left <= xv <= x_mid_right): continue
            h = abs(ys - ye)
            if h < 5.0: continue
            if max(ys, ye) < y_face_base: continue
            if _y_face_top is not None and max(ys, ye) > _y_face_top + 1.0: continue
            iverts_raw.append({
                'x':     round(xv, 1),
                'y_bot': round(min(ys, ye), 1),
                'y_top': round(max(ys, ye), 1),
            })

        if not iverts_raw:
            continue

        # ── Agrupa por x (±GROUP_TOL), armazena segs individuais ──
        grouped: list[dict] = []
        for vv in sorted(iverts_raw, key=lambda v: v['x']):
            placed = False
            for g in grouped:
                if abs(vv['x'] - g['x']) <= GROUP_TOL:
                    g['y_bot'] = min(g['y_bot'], vv['y_bot'])
                    g['y_top'] = max(g['y_top'], vv['y_top'])
                    g['segs'].append({'y_bot': vv['y_bot'], 'y_top': vv['y_top']})
                    placed = True; break
            if not placed:
                grouped.append({
                    'x': vv['x'], 'y_bot': vv['y_bot'], 'y_top': vv['y_top'],
                    'segs': [{'y_bot': vv['y_bot'], 'y_top': vv['y_top']}],
                })

        # ── Filtro 1: ratio (span merged / face_total_h) ──
        ratio_ok = [
            g for g in grouped
            if face_total_h > 0
            and (g['y_top'] - g['y_bot']) / face_total_h < RATIO_MAX
        ]

        # ── Filtro 2: endpoint — aplicado quando ratio_ok ≥ 3 verts ──
        # OU quando algum grupo tem múltiplos segmentos (inner wall + continuation
        # acima/abaixo que se mergem em span errado; endpoint seleciona o seg correto).
        _any_multi = any(len(g['segs']) > 1 for g in ratio_ok)
        if len(ratio_ok) >= 3 or _any_multi:
            # Filtra grupos E determina segmento que fez match
            opening_verts: list[dict] = []
            for g in ratio_ok:
                matched_seg = None
                for seg in sorted(g['segs'], key=lambda s: s['y_bot']):
                    if ep_matches(g['x'], seg['y_bot']) or ep_matches(g['x'], seg['y_top']):
                        matched_seg = seg
                        break
                if matched_seg is not None:
                    g['y_bot_use'] = matched_seg['y_bot']
                    g['y_top_use'] = matched_seg['y_top']
                    opening_verts.append(g)
                elif not _any_multi:
                    # ratio_ok >= 3 mas sem match: descartar grupo (divisória)
                    pass
                else:
                    # multi-seg sem endpoint match: fallback para menor segmento
                    shortest = min(g['segs'], key=lambda s: s['y_top'] - s['y_bot'])
                    g['y_bot_use'] = shortest['y_bot']
                    g['y_top_use'] = shortest['y_top']
                    opening_verts.append(g)
        else:
            # Sem filtro de endpoint: usa span merged
            for g in ratio_ok:
                g['y_bot_use'] = g['y_bot']
                g['y_top_use'] = g['y_top']
            opening_verts = ratio_ok

        if not opening_verts:
            continue

        # ── Classifica ──
        if len(opening_verts) == 1:
            vv = opening_verts[0]
            dl = vv['x'] - xl
            dr = xr - vv['x']
            ab: dict = {
                'lado':    'esquerdo' if dl <= dr else 'direito',
                'largura': round(dl if dl <= dr else dr, 1),
                'y_rel':   round(vv['y_bot_use'] - y_h0, 1),
                'altura':  round(vv['y_top_use'] - vv['y_bot_use'], 1),
            }
            result[f'abertura_{face}'] = ab

        elif len(opening_verts) == 2:
            v1, v2 = opening_verts
            _larg_meio  = round(v2['x'] - v1['x'], 1)
            _x_off_meio = round(v1['x'] - xl, 1)

            # Detecta múltiplos slots: cada grupo pode ter segs em y-ranges distintos.
            # Emparelha segs de v1 e v2 que se sobreponham em y → um slot por par.
            _slots: list[tuple[float, float]] = []
            for _s1 in v1['segs']:
                for _s2 in v2['segs']:
                    _ov_lo = max(_s1['y_bot'], _s2['y_bot'])
                    _ov_hi = min(_s1['y_top'], _s2['y_top'])
                    if _ov_hi - _ov_lo >= 5.0:
                        _sb = round(_ov_lo, 1)
                        _st = round(_ov_hi, 1)
                        if not any(abs(_sb - s[0]) < 5 for s in _slots):
                            _slots.append((_sb, _st))
            _slots.sort(key=lambda s: s[0])

            if len(_slots) <= 1:
                # Abertura única (caso normal)
                ab = {
                    'lado':     'meio',
                    'largura':  _larg_meio,
                    'x_offset': _x_off_meio,
                    'y_rel':    round(min(v1['y_bot_use'], v2['y_bot_use']) - y_h0, 1),
                    'altura':   round(
                        max(v1['y_top_use'], v2['y_top_use'])
                        - min(v1['y_bot_use'], v2['y_bot_use']), 1),
                }
                result[f'abertura_{face}'] = ab
            else:
                # Múltiplos slots empilhados (ex: P11/P17 double-slot)
                for _idx, (_sb, _st) in enumerate(_slots, 1):
                    result[f'abertura_{face}_{_idx}'] = {
                        'lado':     'meio',
                        'largura':  _larg_meio,
                        'x_offset': _x_off_meio,
                        'y_rel':    round(_sb - y_h0, 1),
                        'altura':   round(_st - _sb, 1),
                    }

        else:
            result[f'abertura_{face}'] = {'lado': f'multi_{len(opening_verts)}', 'n': len(opening_verts)}

    return result


def main():
    print(f"{'ITEM':<5} {'FACE':<5} {'LADO':<10} {'LARG':>5} {'Y_REL':>6} {'ALTURA':>7}  EXTRA")
    print("-" * 90)
    for item in ITEMS:
        dxf = latest_dxf(item)
        if not dxf:
            print(f"{item:<5} <sem DXF>")
            continue
        try:
            data = extract_aberturas(dxf)
        except Exception as ex:
            print(f"{item:<5} ERRO: {ex}")
            continue

        printed = False
        for face in ('A', 'B', 'C', 'D'):
            ivs = data.get(f'intervals_{face}', [])
            fw  = data.get(f'face_w_{face}', 0)
            # Suporte a abertura única e múltipla
            abs_list = []
            if data.get(f'abertura_{face}'):
                abs_list = [(f'abertura_{face}', data[f'abertura_{face}'])]
            else:
                idx = 1
                while data.get(f'abertura_{face}_{idx}'):
                    abs_list.append((f'abertura_{face}_{idx}', data[f'abertura_{face}_{idx}']))
                    idx += 1
            for key, ab in abs_list:
                lado   = ab.get('lado', '')
                larg   = ab.get('largura', 0)
                y_rel  = ab.get('y_rel', 0)
                altura = ab.get('altura', 0)
                extra  = f"x_off={ab.get('x_offset','')} " if lado == 'meio' else ''
                extra += f"face_w={fw} ivs={ivs}"
                print(f"{item:<5} {face:<5} {key:<20} {lado:<10} {larg:>5.1f} {y_rel:>6.1f} {altura:>7.1f}  {extra}")
                printed = True
        if not printed:
            print(f"{item:<5} (sem aberturas detectadas)")


if __name__ == '__main__':
    main()
