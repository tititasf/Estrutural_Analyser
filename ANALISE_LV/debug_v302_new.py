"""Debug the new detect_faces_by_clustering for V302"""
import sys, json, glob, os
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts')

import ezdxf
import extrair_parametros_viga_v3 as ext

# Load catalog_rendered to get zone info
with open('D:/Agente-cad-PYSIDE/ANALISE_LV/catalog_rendered.json') as f:
    catalog = json.load(f)

target_viga = 'V302'
entry = next((e for e in catalog if e.get('viga') == target_viga), None)
if not entry:
    print(f"V302 not found in catalog")
    sys.exit(1)

print(f"V302 entry: obra={entry['obra']} dxf={entry['dxf_source'][:60]}")

# Find the DXF
src = entry['dxf_source']
dxf_dir = f"D:/Agente-cad-PYSIDE/DADOS-OBRAS/{entry['obra']}/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa"
dxf_path = None
for f in os.listdir(dxf_dir):
    if f.endswith('.dxf') and 'LV' in f and '13' in f:
        dxf_path = os.path.join(dxf_dir, f)
        print(f"Using DXF: {f}")
        break

if not dxf_path:
    print("DXF not found")
    sys.exit(1)

doc = ezdxf.readfile(dxf_path)
msp = doc.modelspace()

all_vigas = ext.find_all_inserts(msp)
zone = ext.compute_zone(all_vigas, target_viga)
print(f"Zone: x_left={zone['x_left']} x_right={zone['x_right']} insert_x={zone['insert_x']:.1f} insert_y={zone['insert_y']:.1f}")
print(f"      y_bot={zone['y_bot']:.1f} y_top={zone['y_top']:.1f}")

ents = ext.collect_zone_entities(msp, zone)
h_lines = ents['panel_h_lines']
print(f"\nAll H-lines in zone: {len(h_lines)}")

# Show all H-lines sorted by Y
for l in sorted(h_lines, key=lambda x: x['y']):
    print(f"  y={l['y']:.1f} x=[{l['x1']:.0f},{l['x2']:.0f}] len={l['len']:.0f}")

# Now run detect with zone params
print(f"\n--- Running detect_faces_by_clustering ---")
# Add inline debug
insert_x = zone['insert_x']
x_left = zone.get('x_left')
x_right = zone.get('x_right')

# Step 1: X filter
filtered = list(h_lines)
x_filter_left = (x_left - 50) if x_left is not None else max(0.0, insert_x - 400)
x_filter_right = (x_right + 50) if x_right is not None else None
print(f"X filter: left>={x_filter_left:.1f} right<={x_filter_right}")

if x_filter_left:
    narrowed = [l for l in filtered if l['x2'] >= x_filter_left]
    if narrowed:
        filtered = narrowed
if x_filter_right:
    narrowed = [l for l in filtered if l['x1'] <= x_filter_right]
    if narrowed:
        filtered = narrowed

print(f"After X filter: {len(filtered)} lines")
for l in sorted(filtered, key=lambda x: x['y']):
    print(f"  y={l['y']:.1f} x=[{l['x1']:.0f},{l['x2']:.0f}] len={l['len']:.0f}")

# Step 2: Anchors
max_len = max(l['len'] for l in filtered)
anchor_min = max(50, max_len * 0.30)
anchors = sorted([l for l in filtered if l['len'] >= anchor_min], key=lambda l: l['y'])
print(f"\nmax_len={max_len:.0f}, anchor_min={anchor_min:.0f}")
print(f"Anchor lines ({len(anchors)}):")
for a in anchors:
    print(f"  y={a['y']:.1f} len={a['len']:.0f}")

# Step 3: Anchor groups
ANCHOR_GROUP_GAP = 60
groups = []
if anchors:
    g_min = anchors[0]['y']
    g_max = anchors[0]['y']
    for al in anchors[1:]:
        if al['y'] - g_max <= ANCHOR_GROUP_GAP:
            g_max = al['y']
        else:
            groups.append((g_min, g_max))
            g_min = al['y']
            g_max = al['y']
    groups.append((g_min, g_max))
print(f"Anchor groups: {groups}")

# Step 4: Face candidates
for i, (g_min_y, g_max_y) in enumerate(groups):
    if i + 1 < len(groups):
        fhm = max(200, (groups[i+1][0] - g_min_y) * 0.85)
    else:
        fhm = 600
    face_y_low = g_min_y - 20
    face_y_high = g_min_y + fhm
    face_lines = [l for l in filtered if face_y_low <= l['y'] <= face_y_high]
    y_min_f = min(l['y'] for l in face_lines) if face_lines else 0
    y_max_f = max(l['y'] for l in face_lines) if face_lines else 0
    print(f"  Group {i}: y=[{g_min_y:.1f},{g_max_y:.1f}] fhm={fhm:.0f} face_y=[{face_y_low:.1f},{face_y_high:.1f}]")
    print(f"    face_lines={len(face_lines)}: y=[{y_min_f:.1f},{y_max_f:.1f}]")
    for l in sorted(face_lines, key=lambda x: x['y']):
        print(f"      y={l['y']:.1f} len={l['len']:.0f}")
