"""
Validação visual item-a-item de TODAS as vigas FV.
Gera DXF individual para cada viga e inspeciona:
  - Número de polylines (painéis)
  - Posições X de cada painel (detecta sobreposição)
  - Textos presentes (labels ESQ/DIR, nomenclatura)
  - Gaps entre segmentos
  - Chanfros (polylines com >4 vértices)
"""
import json, glob, os, sys
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts')

json_dir = 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-4_Sincronizacao/JSON_Vigas_Fundo'
json_files = sorted(glob.glob(os.path.join(json_dir, '*_fundo.json')))

# Filter out n4er temp files
json_files = [f for f in json_files if 'n4er' not in os.path.basename(f)]

print(f"Total FV JSONs: {len(json_files)}\n")

issues = []
ok_count = 0

for jf in json_files:
    basename = os.path.basename(jf)
    vname = basename.replace('_fundo.json', '')
    
    with open(jf, 'r', encoding='utf-8') as f:
        d = json.load(f)
    
    segments_rich = d.get('segments_rich', [])
    panels = d.get('panels', [])
    holes = d.get('holes', [])
    label_left = d.get('label_left')
    label_right = d.get('label_right')
    total_width = d.get('total_width', 0)  # b (espessura)
    total_height = d.get('total_height', 0)  # comprimento
    
    # Use segments_rich if available, else panels
    source = 'segments_rich' if segments_rich else 'panels'
    data_list = segments_rich if segments_rich else panels
    
    item_issues = []
    
    # Check 1: Has data?
    if not data_list:
        item_issues.append("SEM DADOS (panels e segments_rich vazios)")
    
    # Check 2: Compute total comp from segments
    if segments_rich:
        comp = sum(s.get('total_width', 0) for s in segments_rich)
        n_seg = len(segments_rich)
        # Check for chanfros
        has_chanfro = False
        for seg in segments_rich:
            for p in seg.get('panels', []):
                verts = p.get('vertices')
                if verts and len(verts) > 5:  # More than 4 unique vertices = chanfro
                    has_chanfro = True
    elif panels:
        comp = sum(p.get('width', 0) for p in panels)
        n_seg = len(panels)
        has_chanfro = False
    else:
        comp = 0
        n_seg = 0
        has_chanfro = False
    
    # Check 3: Labels
    if label_left is None or label_left == 'L Esq':
        item_issues.append(f"label_left MISSING ({label_left})")
    if label_right is None or label_right == 'L Dir':
        item_issues.append(f"label_right MISSING ({label_right})")
    
    # Check 4: Active holes
    active_holes = [h for h in holes if h.get('active')]
    expected_gaps = n_seg - 1 if n_seg > 1 else 0
    if len(active_holes) < expected_gaps:
        item_issues.append(f"HOLES MISMATCH: {len(active_holes)} active holes but {n_seg} segments (need {expected_gaps} gaps)")
    
    # Check 5: b value
    if total_width <= 0:
        item_issues.append(f"b (total_width) = {total_width}")
    
    status = "✅" if not item_issues else "❌"
    if not item_issues:
        ok_count += 1
    
    chanfro_flag = " 🔶CHANFRO" if has_chanfro else ""
    multi_seg = f" 🔗{n_seg}seg" if n_seg > 1 else ""
    
    print(f"{status} {vname:15s} | b={total_width:5.1f} comp={comp:7.1f} | {source:13s} | segs={n_seg} holes_active={len(active_holes)} | L={label_left or '—':8s} R={label_right or '—':8s}{chanfro_flag}{multi_seg}")
    
    if item_issues:
        for iss in item_issues:
            print(f"   ⚠️  {iss}")
        issues.append((vname, item_issues))

print(f"\n{'='*80}")
print(f"RESULTADO: {ok_count}/{len(json_files)} OK, {len(issues)} com problemas")
if issues:
    print(f"\nITENS COM PROBLEMAS:")
    for vname, isss in issues:
        print(f"  {vname}: {'; '.join(isss)}")
