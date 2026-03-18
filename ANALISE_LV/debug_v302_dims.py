"""Debug COTA dim selection for V302 face"""
import sys, os, glob
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts')
import ezdxf, extrair_parametros_viga_v3 as ext

dxf_dir = 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa'
dxf_path = next(f for f in os.listdir(dxf_dir) if 'LV' in f and '13' in f)
dxf_path = os.path.join(dxf_dir, dxf_path)
print(f"DXF: {os.path.basename(dxf_path)}")

doc = ezdxf.readfile(dxf_path)
msp = doc.modelspace()
all_vigas = ext.find_all_inserts(msp)
zone = ext.compute_zone(all_vigas, 'V302')
print(f"Zone: x_left={zone['x_left']} x_right={zone['x_right']:.1f} insert_x={zone['insert_x']:.1f}")

ents = ext.collect_zone_entities(msp, zone)
face_a_data, _ = ext.detect_faces_by_clustering(
    ents['panel_h_lines'], ents['panel_v_lines'], zone['insert_y'],
    insert_x=zone['insert_x'], x_left=zone.get('x_left'), x_right=zone.get('x_right')
)

print(f"\nFace A: y=[{face_a_data['y_min']:.1f},{face_a_data['y_max']:.1f}] h={face_a_data['y_max']-face_a_data['y_min']:.1f}")

# Replicate face_x bounds
lines = face_a_data['lines']
all_x1 = [ln['x1'] for ln in lines]
all_x2 = [ln['x2'] for ln in lines]
face_x_min = min(all_x1)
face_x_max = max(all_x2)
print(f"Face X: [{face_x_min:.1f},{face_x_max:.1f}] total_width={face_x_max-face_x_min:.1f}")

y_min = face_a_data['y_min']
y_max = face_a_data['y_max']

# Show ALL horizontal COTA dimensions in zone, with their positions
print(f"\nAll horizontal COTA dims in zone:")
for d in sorted(ents['dimensions'], key=lambda x: x['y_mid']):
    if not d['horizontal'] or 'cota' not in d['layer'].lower():
        continue
    in_y = y_min - 50 <= d['y_mid'] <= y_max + 50
    in_x = face_x_min - 20 <= d['x_mid'] <= face_x_max + 20
    selected = in_y and in_x and d['actual'] > 30
    marker = '>>> SELECTED' if selected else ''
    print(f"  actual={d['actual']:7.1f}  x_mid={d['x_mid']:7.1f}  y_mid={d['y_mid']:7.1f}  layer={d['layer']}  {marker}")

# Show the v-lines in face Y-band (for gap detection)
print(f"\nV-lines in face Y-band [y_min-5={y_min-5:.0f}, y_max+5={y_max+5:.0f}]:")
face_vlines = [vl for vl in ents['panel_v_lines'] if vl['y1'] <= y_max + 5 and vl['y2'] >= y_min - 5]
vx_set = sorted(set(round(vl['x'], 0) for vl in face_vlines))
print(f"  {len(face_vlines)} v-lines, x positions ({len(vx_set)}): {vx_set}")
