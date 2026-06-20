# -*- coding: utf-8 -*-
"""
Test script for multi-segment generation.
"""
import sys, io, json
# sys.stdout = io.TextIOWrapper...
from pathlib import Path

PROJ = Path("D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main")
sys.path.insert(0, str(PROJ / "scripts"))

from gerar_fv_dxf_stog import setup_doc, draw_viga
import ezdxf

def test_viga(elem_id, json_path, out_path):
    print(f"\n--- Testing {elem_id} ---")
    if not Path(json_path).exists():
        print(f"File not found: {json_path}")
        return
        
    with open(json_path, 'r', encoding='utf-8') as f:
        ficha = json.load(f)
        
    doc = setup_doc()
    msp = doc.modelspace()
    
    panels = ficha.get('panels', [])
    b_fv = ficha.get('total_width', 19.0)
    holes = ficha.get('holes', [])
    
    footprint = draw_viga(msp, 0, 0, panels, b_fv, elem_id, holes=holes)
    
    doc.saveas(str(out_path))
    print(f"Generated {out_path} with footprint {footprint}cm")


def main():
    test_viga("V306", "D:/Agente-cad-PYSIDE/sandbox_fv_arete/V306_ficha_n2.json", "D:/Agente-cad-PYSIDE/sandbox_fv_arete/N4_V306.dxf")
    test_viga("VF301", "D:/Agente-cad-PYSIDE/sandbox_fv_arete/VF301_ficha_n2.json", "D:/Agente-cad-PYSIDE/sandbox_fv_arete/N4_VF301.dxf")
    test_viga("V305", "D:/Agente-cad-PYSIDE/sandbox_fv_arete/V305_ficha_n2.json", "D:/Agente-cad-PYSIDE/sandbox_fv_arete/N4_V305.dxf")

if __name__ == '__main__':
    main()
