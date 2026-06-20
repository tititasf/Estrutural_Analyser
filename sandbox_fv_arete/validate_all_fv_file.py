import json, glob, os, sys

json_dir = 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-4_Sincronizacao/JSON_Vigas_Fundo'
json_files = sorted(glob.glob(os.path.join(json_dir, '*_fundo.json')))

# Filter out n4er temp files
json_files = [f for f in json_files if 'n4er' not in os.path.basename(f)]

with open('D:/Agente-cad-PYSIDE/sandbox_fv_arete/validation_report.txt', 'w', encoding='utf-8') as out:
    out.write(f"Total FV JSONs: {len(json_files)}\n\n")
    
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
        
        source = 'segments_rich' if segments_rich else 'panels'
        data_list = segments_rich if segments_rich else panels
        
        item_issues = []
        
        if not data_list:
            item_issues.append("SEM DADOS")
        
        comp = 0
        n_seg = len(data_list)
        has_chanfro = False
        
        if segments_rich:
            comp = sum(s.get('total_width', 0) for s in segments_rich)
            for seg in segments_rich:
                for p in seg.get('panels', []):
                    verts = p.get('vertices')
                    if verts and len(verts) > 5:
                        has_chanfro = True
        elif panels:
            comp = sum(p.get('width', 0) for p in panels)
        
        if label_left is None or label_left == 'L Esq':
            item_issues.append(f"label_left MISSING")
        if label_right is None or label_right == 'L Dir':
            item_issues.append(f"label_right MISSING")
            
        active_holes = [h for h in holes if h.get('active')]
        expected_gaps = n_seg - 1 if n_seg > 1 else 0
        if len(active_holes) < expected_gaps:
            item_issues.append(f"HOLES MISMATCH: {len(active_holes)} active vs {expected_gaps} gaps")
            
        if total_width <= 0:
            item_issues.append(f"b = {total_width}")
            
        status = "OK" if not item_issues else "FAIL"
        if not item_issues:
            ok_count += 1
            
        chanfro_flag = " CHANFRO" if has_chanfro else ""
        multi_seg = f" {n_seg}seg" if n_seg > 1 else ""
        
        out.write(f"[{status}] {vname:15s} | b={total_width:5.1f} comp={comp:7.1f} | {source:13s} | holes={len(active_holes)} | L={label_left or '-':8s} R={label_right or '-':8s}{chanfro_flag}{multi_seg}\n")
        
        if item_issues:
            for iss in item_issues:
                out.write(f"     -> {iss}\n")
            issues.append((vname, item_issues))
            
    out.write(f"\n{'='*80}\n")
    out.write(f"RESULTADO: {ok_count}/{len(json_files)} OK, {len(issues)} com problemas\n")
