#!/usr/bin/env python3
"""
patch_face_b.py — Extrai face_b para as vigas onde esta ausente.

Bug root cause: detect_faces_by_clustering usa prefilter fixo y_top - 350,
que corta face_b quando a zona eh grande (ex: 1229 u). Fix: aumentar para
max(350, zone_span * 0.65).

v2 improvements:
  - Re-reads zone boundaries (benefits from PATCH-A corrections)
  - Fallback: direct hline search below face_a when clustering fails
  - For vigas with face_b but panel_count=0: retry with wider x_range

Uso:
  python patch_face_b.py
"""
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts')

import ezdxf
from pathlib import Path
import extrair_parametros_viga_v3 as ev3

PARAMS_FILE = Path(r'D:\Agente-cad-PYSIDE\ANALISE_LV\params\viga_params_v3.json')
OBRAS_BASE  = Path(r'D:\Agente-cad-PYSIDE\DADOS-OBRAS')

# --- Monkey-patch: substitui prefilter fixo por dinamico ---
_orig_detect = ev3.detect_faces_by_clustering

def _detect_patched(panel_h_lines, panel_v_lines, insert_y,
                    insert_x=None, x_left=None, x_right=None, y_top=None,
                    _y_bot=None):
    """Igual ao original mas com prefilter adaptativo ao tamanho da zona."""
    # Calcula span da zona para ajustar prefilter
    if y_top is not None and _y_bot is not None:
        zone_span = y_top - _y_bot
        prefilter_dist = max(350, zone_span * 0.65)
    else:
        prefilter_dist = 350

    # Substitui panel_h_lines temporariamente com prefilter maior
    if y_top is not None and panel_h_lines:
        y_prefilter_min = y_top - prefilter_dist
        prefiltered = [l for l in panel_h_lines if l['y'] >= y_prefilter_min]
        if len(prefiltered) >= 2:
            panel_h_lines = prefiltered

    # Chama a funcao original mas sem deixar ela re-aplicar prefilter
    # Passamos y_top=None para desativar o prefilter interno
    return _orig_detect(panel_h_lines, panel_v_lines, insert_y,
                        insert_x=insert_x, x_left=x_left, x_right=x_right,
                        y_top=None)  # y_top=None desativa o prefilter interno

ev3.detect_faces_by_clustering = _detect_patched
# ---


def find_dxf(obra, dxf_name):
    for sub in ['Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
                'Fase-1_Ingestao']:
        p = OBRAS_BASE / obra / sub / dxf_name
        if p.exists():
            return p
    return None


def _direct_hline_search(msp, fa_y_min, x_left, x_right, y_bot):
    """Fallback: busca direta de hlines abaixo de face_a y_min - 50.
    Retorna fb_data compativel com detect_faces_by_clustering output."""
    search_y_max = fa_y_min - 50
    search_y_min = y_bot if y_bot is not None else fa_y_min - 400
    x_margin = 50

    hlines = []
    for e in msp:
        if e.dxftype() != 'LINE':
            continue
        try:
            s = e.dxf.start
            en = e.dxf.end
        except Exception:
            continue
        y1, y2 = s.y, en.y
        if abs(y1 - y2) > 2:  # not horizontal
            continue
        y = (y1 + y2) / 2
        if y < search_y_min or y > search_y_max:
            continue
        x1, x2 = min(s.x, en.x), max(s.x, en.x)
        if x_left is not None and x2 < x_left - x_margin:
            continue
        if x_right is not None and x1 > x_right + x_margin:
            continue
        length = x2 - x1
        if length < 30:
            continue
        hlines.append({'y': y, 'x1': x1, 'x2': x2, 'len': length})

    if len(hlines) < 2:
        return None

    # Group by y proximity (within 80u)
    hlines.sort(key=lambda l: l['y'])
    groups = []
    cur = [hlines[0]]
    for h in hlines[1:]:
        if h['y'] - cur[-1]['y'] < 80:
            cur.append(h)
        else:
            groups.append(cur)
            cur = [h]
    groups.append(cur)

    # Need at least 2 lines in one group to form a face
    best_group = max(groups, key=len)
    if len(best_group) < 2:
        return None

    y_mid = sum(h['y'] for h in best_group) / len(best_group)
    return {
        'lines': best_group,
        'y_mid': y_mid,
    }


def main():
    # Re-read JSON (benefits from PATCH-A zone corrections)
    params = json.loads(PARAMS_FILE.read_text(encoding='utf-8'))

    # Vigas com face_b ausente ou vazia
    vigas_sem_b = [
        p for p in params
        if not p.get('face_b') or p['face_b'].get('panel_count', 0) == 0
    ]
    print(f"Vigas sem face_b: {len(vigas_sem_b)}")

    # Agrupa por (obra, dxf_source) para minimizar leituras de DXF
    from collections import defaultdict
    grupos = defaultdict(list)
    for v in vigas_sem_b:
        key = (v['obra'], v.get('dxf_source', ''))
        grupos[key].append(v)

    patchadas = 0
    fallback_ok = 0
    wider_ok = 0

    for (obra, dxf_src), vigas in grupos.items():
        dxf_path = find_dxf(obra, dxf_src)
        if not dxf_path:
            print(f"  [SKIP] DXF nao encontrado: {obra}/{dxf_src}")
            continue

        print(f"\n  DXF: {dxf_src[:60]}")
        doc = ezdxf.readfile(str(dxf_path))

        for v in vigas:
            zone = v.get('zone', {})
            y_top = zone.get('y_top')
            y_bot = zone.get('y_bot')
            x_left = zone.get('x_left')
            x_right = zone.get('x_right')
            ins = v.get('insert') or {}
            insert_x = ins.get('x') or zone.get('x_right') or 0
            insert_y = ins.get('y') or y_top or 0

            zone_full = {
                'y_top': y_top, 'y_bot': y_bot,
                'x_left': x_left, 'x_right': x_right,
                'insert_x': insert_x, 'insert_y': insert_y,
                'secao': v.get('secao', ''),
                'viga': v.get('viga', ''),
            }

            try:
                ents = ev3.collect_zone_entities(doc.modelspace(), zone_full)
            except Exception as e:
                print(f"    {v['viga']}: erro collect_zone: {e}")
                continue

            fb_data = None
            method = 'clustering'

            # Attempt 1: clustering with adaptive prefilter
            try:
                fa_data, fb_data = _detect_patched(
                    ents['panel_h_lines'], ents['panel_v_lines'], insert_y,
                    insert_x=insert_x, x_left=x_left, x_right=x_right,
                    y_top=y_top, _y_bot=y_bot,
                )
            except Exception as e:
                print(f"    {v['viga']}: erro detect: {e}")

            # Attempt 2: fallback direct hline search below face_a
            if not fb_data:
                fa_y_min = v.get('face_a', {}).get('y_min')
                if fa_y_min is not None:
                    fb_data = _direct_hline_search(
                        doc.modelspace(), fa_y_min, x_left, x_right, y_bot)
                    if fb_data:
                        method = 'direct_hline'

            if not fb_data:
                print(f"    {v['viga']}: face_b nao encontrada (clustering + fallback)")
                continue

            # Extract panels
            try:
                face_b = ev3.extract_panels_from_face(
                    fb_data,
                    ents['panel_v_lines'],
                    ents['dimensions'],
                    ents['hatches'],
                    ents['texts'],
                    insert_y,
                    insert_x=insert_x,
                    x_right=x_right,
                    x_left=x_left,
                )
            except Exception as e:
                print(f"    {v['viga']}: erro extract_panels: {e}")
                continue

            # Attempt 3: if panel_count=0, retry with wider x_range
            if face_b.get('panel_count', 0) == 0 and x_left is not None and x_right is not None:
                wider_x_left = x_left - 100
                wider_x_right = x_right + 100
                try:
                    face_b = ev3.extract_panels_from_face(
                        fb_data,
                        ents['panel_v_lines'],
                        ents['dimensions'],
                        ents['hatches'],
                        ents['texts'],
                        insert_y,
                        insert_x=insert_x,
                        x_right=wider_x_right,
                        x_left=wider_x_left,
                    )
                    if face_b.get('panel_count', 0) > 0:
                        method = 'wider_x'
                except Exception:
                    pass

            # Adiciona hlines para reconstrucao
            face_b['face_hlines'] = [
                {'y': l['y'], 'x1': l['x1'], 'x2': l['x2'], 'len': l['len']}
                for l in fb_data['lines']
            ]
            face_b['face_vlines'] = []

            if face_b.get('panel_count', 0) > 0:
                v['face_b'] = face_b
                patchadas += 1
                if method == 'direct_hline':
                    fallback_ok += 1
                elif method == 'wider_x':
                    wider_ok += 1
                print(f"    {v['viga']}: face_b OK [{method}] -- {face_b['panel_count']} paineis, "
                      f"largura={face_b['total_width']:.0f}")
            else:
                print(f"    {v['viga']}: face_b detectada mas 0 paineis extraidos [{method}]")

    PARAMS_FILE.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\nPatchadas: {patchadas} vigas (clustering: {patchadas-fallback_ok-wider_ok}, "
          f"fallback: {fallback_ok}, wider: {wider_ok}). Salvo: {PARAMS_FILE}")


if __name__ == '__main__':
    main()
