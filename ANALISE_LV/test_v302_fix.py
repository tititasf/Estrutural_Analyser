import sys, json, glob, os
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts')

import extrair_parametros_viga_v3 as ext
import ezdxf

catalog = json.load(open('D:/Agente-cad-PYSIDE/ANALISE_LV/catalog_rendered.json'))
targets = ['V301', 'V302', 'V303']
subset = [e for e in catalog if e.get('viga') in targets]
print(f"Testing {len(subset)} vigas: {[e['viga'] for e in subset]}")

dxf_cache = {}

for zone in subset:
    src = zone['dxf_source']
    # Handle degree symbol in filename
    src_pattern = src.replace('\u00b0', '*').replace('\u00ba', '*')
    if src not in dxf_cache:
        if os.path.exists(src):
            dxf_cache[src] = ezdxf.readfile(src)
        else:
            found = glob.glob(src_pattern)
            if found:
                dxf_cache[src] = ezdxf.readfile(found[0])
            else:
                print(f"  {zone['viga']}: DXF NOT FOUND")
                continue
    doc = dxf_cache[src]
    msp = doc.modelspace()
    r = ext.extract_viga_params(msp, zone)
    fa = r['face_a']
    fb = r['face_b']
    print(f"  {zone['viga']}:")
    print(f"    FA: panels={fa['panel_count']} h={fa['height']} tot={fa['total_width']} "
          f"y=[{fa['y_min']:.0f},{fa['y_max']:.0f}] widths={fa['panel_widths']}")
    if fb and fb.get('panel_count', 0) > 0:
        print(f"    FB: panels={fb['panel_count']} h={fb['height']} tot={fb['total_width']}")
    else:
        print(f"    FB: none")
    print(f"    zone: x_left={zone.get('x_left')} x_right={zone.get('x_right')} insert_x={zone['insert_x']:.0f}")
