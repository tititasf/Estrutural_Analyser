import ezdxf
import re
from pathlib import Path

def _elem_codes(text: str):
    return re.findall(r'([A-Z]+\d+[A-Z]?)\.C', text.upper())

def test_rich_extraction(dxf_path, target_elem):
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    
    # Get all polys
    polys = []
    for e in msp:
        try:
            if 'PAIN' in e.dxf.layer.upper():
                if e.dxftype() == 'LWPOLYLINE':
                    pts = list(e.get_points())
                    if pts:
                        xs = [p[0] for p in pts]
                        ys = [p[1] for p in pts]
                        polys.append((min(xs), max(xs), min(ys), max(ys)))
        except Exception:
            pass
            
    # Get all texts
    texts = []
    noms = []
    for e in msp:
        if e.dxftype() == 'TEXT':
            try:
                txt = e.dxf.text.strip()
                x, y = e.dxf.insert.x, e.dxf.insert.y
                texts.append((txt, x, y, e.dxf.layer))
                if e.dxf.layer.upper() == 'NOMENCLATURA':
                    noms.append((txt, x, y))
            except Exception:
                pass

    own = [n for n in noms if target_elem in _elem_codes(n[0])]
    if not own:
        return
        
    own_rows = sorted(set((round(y, 1), round(x, 1)) for (_, x, y) in own), key=lambda xy: -xy[0])
    
    GAP_PILAR_MIN = 2.0
    Y_TOL_ROW = 60.0
    
    # Just grab the first row for testing
    nom_y, nom_x = own_rows[0]
    
    row_polys = [p for p in polys if p[2] - Y_TOL_ROW <= nom_y <= p[3] + Y_TOL_ROW]
    row_polys = sorted(row_polys, key=lambda p: p[0])
    
    # ... nearest label logic (simplified for test: assume all row_polys are ours for the test)
    # Actually, let's just use row_polys as if they are ours
    final_polys = row_polys[:10]  # Just take first few
    
    segments = []
    current_segment_polys = []
    
    for i, cur in enumerate(final_polys):
        current_segment_polys.append(cur)
        
        # Look ahead for gap
        gap = 0.0
        if i + 1 < len(final_polys):
            gap = round(final_polys[i+1][0] - cur[1], 1)
            
        if gap > GAP_PILAR_MIN or i == len(final_polys) - 1:
            # End of segment
            # Find gap text
            gap_text = None
            if gap > GAP_PILAR_MIN:
                gap_x = (cur[1] + final_polys[i+1][0]) / 2.0
                # Find text near gap_x and nom_y
                near_texts = [t for t in texts if abs(t[1] - gap_x) < 50 and abs(t[2] - nom_y) < Y_TOL_ROW]
                # Filter for layer 5 or NOMENCLATURA that looks like a pillar
                pillar_texts = [t[0] for t in near_texts if t[3] in ('5', 'NOMENCLATURA') and re.match(r'^V\d+', t[0])]
                if pillar_texts:
                    gap_text = pillar_texts[0]
                    
            # Find texts in panels
            panels_rich = []
            for p in current_segment_polys:
                cx = (p[0] + p[1]) / 2.0
                cy = (p[2] + p[3]) / 2.0
                p_texts = [t[0] for t in texts if t[3] == '5' and p[0]-5 <= t[1] <= p[1]+5 and abs(t[2] - cy) < Y_TOL_ROW]
                panels_rich.append({
                    'width': round(p[1] - p[0], 1),
                    'texts': list(set(p_texts))
                })
                
            segments.append({
                'total_width': sum(p['width'] for p in panels_rich),
                'panels': panels_rich,
                'gap_after': gap,
                'gap_text': gap_text
            })
            current_segment_polys = []

    import json
    print(json.dumps(segments, indent=2, ensure_ascii=False))

test_rich_extraction('D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/ALIMONTI - PARAISO - 13° PAV.- FV - R00_motor/FV_V301_motor_178105102566.dxf', 'V301')
