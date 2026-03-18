#!/usr/bin/env python3
"""
patch_labels.py -- Extrai face labels (V101.A, etc.) e column labels (C16, etc.)
dos DXFs fonte e armazena em viga_params_v3.json.

Coleta:
  1. Face labels: textos que matcham r'V\\d+[AB]' ou r'V\\d+\\.[AB]'
     proximos a zona (y dentro da zone +/- 200)
  2. Column labels: textos que matcham r'^C\\d{1,3}$'
  3. Continuacao labels: textos "CONT." que ainda nao estao em continuacoes

Agrupa por DXF para minimizar reads.

Uso:
  python patch_labels.py
"""
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

import ezdxf

PARAMS_FILE = Path(r'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v3.json')
OBRAS_BASE  = Path(r'D:/Agente-cad-PYSIDE/DADOS-OBRAS')

# Patterns
RE_FACE_LABEL = re.compile(r'V\d+\.?[AB]', re.IGNORECASE)
RE_COL_LABEL  = re.compile(r'^C\d{1,3}$')
RE_CONT       = re.compile(r'CONT\.?', re.IGNORECASE)


def find_dxf(obra, dxf_name):
    for sub in ['Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
                'Fase-1_Ingestao']:
        p = OBRAS_BASE / obra / sub / dxf_name
        if p.exists():
            return p
    return None


def extract_texts_from_msp(msp):
    """Collect all TEXT and MTEXT entities from modelspace."""
    texts = []
    for e in msp:
        if e.dxftype() == 'TEXT':
            try:
                t = e.dxf.text.strip()
                x = e.dxf.insert.x
                y = e.dxf.insert.y
                layer = e.dxf.layer
                texts.append({'text': t, 'x': round(x, 1), 'y': round(y, 1), 'layer': layer})
            except Exception:
                pass
        elif e.dxftype() == 'MTEXT':
            try:
                t = e.text.strip() if hasattr(e, 'text') else e.dxf.text.strip()
                ins = e.dxf.insert
                x = ins.x
                y = ins.y
                layer = e.dxf.layer
                texts.append({'text': t, 'x': round(x, 1), 'y': round(y, 1), 'layer': layer})
            except Exception:
                pass
    return texts


def labels_for_viga(all_texts, zone, existing_continuacoes):
    """Filter and classify texts near this viga's zone."""
    y_top = zone.get('y_top')
    y_bot = zone.get('y_bot')
    x_left = zone.get('x_left')
    x_right = zone.get('x_right')

    if y_top is None or y_bot is None:
        return [], [], []

    y_margin = 200
    x_margin = 300  # labels may be slightly outside the zone x boundaries

    y_lo = y_bot - y_margin
    y_hi = y_top + y_margin
    x_lo = (x_left - x_margin) if x_left is not None else -1e9
    x_hi = (x_right + x_margin) if x_right is not None else 1e9

    face_labels = []
    col_labels = []
    cont_labels = []

    # Existing continuacao texts for dedup
    existing_cont_texts = set()
    for c in (existing_continuacoes or []):
        existing_cont_texts.add((round(c.get('x', 0), 0), round(c.get('y', 0), 0)))

    for t in all_texts:
        tx, ty = t['x'], t['y']
        if ty < y_lo or ty > y_hi or tx < x_lo or tx > x_hi:
            continue

        text = t['text']

        # Face labels
        if RE_FACE_LABEL.search(text):
            face_labels.append({'text': text, 'x': tx, 'y': ty})
            continue

        # Column labels
        if RE_COL_LABEL.match(text):
            col_labels.append({'text': text, 'x': tx, 'y': ty})
            continue

        # Continuacao labels
        if RE_CONT.search(text):
            key = (round(tx, 0), round(ty, 0))
            if key not in existing_cont_texts:
                cont_labels.append({'text': text, 'x': tx, 'y': ty})

    return face_labels, col_labels, cont_labels


def main():
    params = json.loads(PARAMS_FILE.read_text(encoding='utf-8'))

    # Group by (obra, dxf_source)
    from collections import defaultdict
    grupos = defaultdict(list)
    for v in params:
        key = (v['obra'], v.get('dxf_source', ''))
        grupos[key].append(v)

    total_face = 0
    total_col = 0
    total_cont = 0
    vigas_with_face = 0
    vigas_with_col = 0

    for (obra, dxf_src), vigas in grupos.items():
        dxf_path = find_dxf(obra, dxf_src)
        if not dxf_path:
            print(f"  [SKIP] DXF nao encontrado: {obra}/{dxf_src}")
            continue

        print(f"\n  DXF: {dxf_src[:60]}")
        doc = ezdxf.readfile(str(dxf_path))
        all_texts = extract_texts_from_msp(doc.modelspace())
        print(f"    Texts no DXF: {len(all_texts)}")

        for v in vigas:
            zone = v.get('zone', {})
            existing_cont = v.get('continuacoes', [])

            face_labels, col_labels, cont_labels = labels_for_viga(
                all_texts, zone, existing_cont)

            if face_labels:
                v['face_labels'] = face_labels
                total_face += len(face_labels)
                vigas_with_face += 1

            if col_labels:
                v['column_labels'] = col_labels
                total_col += len(col_labels)
                vigas_with_col += 1

            if cont_labels:
                existing = v.get('continuacoes', [])
                v['continuacoes'] = existing + cont_labels
                total_cont += len(cont_labels)

    PARAMS_FILE.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"\nPATCH-C: patch_labels")
    print(f"  Face labels: {total_face} labels em {vigas_with_face} vigas")
    print(f"  Column labels: {total_col} labels em {vigas_with_col} vigas")
    print(f"  Continuacao labels: {total_cont} novos")
    print(f"  Salvo: {PARAMS_FILE}")


if __name__ == '__main__':
    main()
