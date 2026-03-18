#!/usr/bin/env python3
"""
patch_panel_labels.py — Extrai labels de contagem de sarrafos ("8 1/2pont", etc.)
da layer TEXTO do DXF fonte, abrindo cada DXF apenas UMA VEZ.
"""
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ezdxf
from pathlib import Path
from collections import defaultdict

PARAMS_FILE = 'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v3.json'
OBRAS_BASE  = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')

LABEL_LAYERS = {'TEXTO', 'texto', 'NOMENCLATURA', 'nomenclatura', '0', 'NOMENCLATUR'}

def strip_mtext(raw):
    """Remove format codes de MTEXT/TEXT:
       MTEXT: {\\Q19;\\C256;8 1/2pont} -> '8 1/2pont'
       TEXT:  \\A1;8 1/2pont           -> '8 1/2pont'
    """
    s = str(raw)
    # TEXT alignment code: \\A0; \\A1; \\A2;
    s = re.sub(r'^\\A\d;', '', s)
    # MTEXT: remove {\\...;...} format blocks
    t = re.sub(r'\{[^}]*\\[^}]*;', '', s)
    t = re.sub(r'\}', '', t).strip()
    if not t:
        m = re.search(r';([^;}{]+)\}?$', s)
        if m:
            t = m.group(1).strip()
    return t

def find_dxf(obra, dxf_source):
    for sub in ['Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
                'Fase-1_Ingestao']:
        p = OBRAS_BASE / obra / sub / dxf_source
        if p.exists(): return p
    for p in (OBRAS_BASE / obra).rglob('*.dxf'):
        if p.name == dxf_source: return p
    return None

def main():
    with open(PARAMS_FILE, encoding='utf-8') as f:
        params = json.load(f)

    # Agrupar vigas por (obra, dxf_source) → cada DXF aberto só 1x
    groups = defaultdict(list)
    for i, p in enumerate(params):
        key = (p.get('obra', ''), p.get('dxf_source', ''))
        groups[key].append(i)

    patched = 0
    total_labels = 0

    for (obra, dxf_name), indices in sorted(groups.items()):
        if not dxf_name or not obra:
            continue
        dxf_path = find_dxf(obra, dxf_name)
        if not dxf_path:
            print(f'  DXF nao encontrado: {obra}/{dxf_name}')
            continue

        print(f'Lendo {dxf_name[:60]}...')
        try:
            doc = ezdxf.readfile(str(dxf_path))
            msp = doc.modelspace()
        except Exception as ex:
            print(f'  ERRO ao ler DXF: {ex}')
            continue

        # Coletar TODOS os textos relevantes do DXF inteiro uma vez
        all_labels = []
        for e in msp:
            if e.dxftype() not in ('TEXT', 'MTEXT'): continue
            layer = e.dxf.layer
            if layer not in LABEL_LAYERS: continue
            if not hasattr(e.dxf, 'insert'): continue
            cx = e.dxf.insert.x
            cy = e.dxf.insert.y
            raw = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            text = strip_mtext(raw)
            # Só "N 1/2pont" ou "N pont" — padrão de contagem de sarrafos
            if not re.search(r'\d+\s*(?:1/2\s*)?pont', text, re.IGNORECASE): continue
            all_labels.append((cx, cy, text))

        print(f'  → {len(all_labels)} labels totais no DXF')

        # Para cada viga do grupo, filtrar labels dentro da zona
        for i in indices:
            p = params[i]
            zone = p.get('zone', {})
            if not zone: continue
            y_bot = zone.get('y_bot')
            y_top = zone.get('y_top')
            if y_bot is None or y_top is None: continue
            x_left  = zone.get('x_left')
            x_right = zone.get('x_right')

            # Derivar x range da face_a como fallback
            fa_p = p.get('face_a', {})
            fa_xs = [h['x1'] for h in fa_p.get('face_hlines', [])] + \
                    [h['x2'] for h in fa_p.get('face_hlines', [])] + \
                    [v['x']  for v in fa_p.get('face_vlines', [])]
            fa_xmin = min(fa_xs) if fa_xs else None
            fa_xmax = max(fa_xs) if fa_xs else None

            def in_zone(cx, cy):
                if not (y_bot <= cy <= y_top): return False
                # Se x_left e x_right definidos na zone: usá-los + 15%
                if x_left is not None and x_right is not None:
                    xl = min(x_left, x_right)
                    xr = max(x_left, x_right)
                    gap = abs(xr - xl) * 0.15
                    return xl - gap <= cx <= xr + gap
                # Se só x_right: filtrar em torno dele
                if x_right is not None and abs(x_right) < 1e8:
                    xr = x_right
                    return (xr - 2000) <= cx <= (xr + 200)
                # Fallback: usar range de face_a + margem generosa
                if fa_xmin is not None:
                    span = abs(fa_xmax - fa_xmin)
                    margin = max(span * 0.5, 300)
                    return (fa_xmin - margin) <= cx <= (fa_xmax + margin)
                return True  # sem restrição — aceitar tudo dentro do y

            viga_labels = []
            for cx, cy, text in all_labels:
                if in_zone(cx, cy):
                    viga_labels.append({'text': text, 'x': round(cx, 1), 'y': round(cy, 1), 'layer': 'NOMENCLATURA'})

            if viga_labels:
                p['panel_labels'] = viga_labels
                total_labels += len(viga_labels)
                patched += 1
                print(f'    {p["viga"]:20s} → {len(viga_labels)} labels: {[l["text"] for l in viga_labels]}')

    with open(PARAMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(params, f, ensure_ascii=False, separators=(',', ':'))

    print(f'\nPatchado: {patched} vigas, {total_labels} labels. Salvo: {PARAMS_FILE}')


if __name__ == '__main__':
    main()
