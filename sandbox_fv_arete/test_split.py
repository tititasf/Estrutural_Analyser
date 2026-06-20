viga = {'nome': 'V301', 'b': 19.0, 'comp': 3202.0, 'panels': [{'width': 305.5}, {'width': 100.0}, {'width': 100.0}, {'width': 318.0}, {'width': 318.0}, {'width': 200.0}, {'width': 318.0}, {'width': 318.0}, {'width': 100.0}, {'width': 100.0}, {'width': 629.5}, {'width': 106.0}, {'width': 41.5}, {'width': 247.5}], 'holes': [{'width': 9.4, 'position': 305.5}, {'width': 12.7, 'position': 414.9}, {'width': 9.4, 'position': 527.6}, {'width': 17.8, 'position': 855.0}, {'width': 9.4, 'position': 1190.8}, {'width': 9.4, 'position': 1341.5}, {'width': 17.8, 'position': 1668.9}, {'width': 9.4, 'position': 2004.7}, {'width': 11.7, 'position': 2114.1}, {'width': 9.4, 'position': 2225.8}, {'width': 9.4, 'position': 2807.0}, {'width': 12.7, 'position': 2922.4}, {'width': 9.4, 'position': 2976.6}]}

def split_viga(v, max_w):
    parts = []
    current_panels = []
    current_holes = []
    current_comp = 0.0
    accum_pos = 0.0
    
    for i, p in enumerate(v['panels']):
        w = p['width']
        gap_w = v['holes'][i]['width'] if i < len(v['holes']) else 0.0
        
        # Will adding this panel exceed max_w?
        if current_comp + w > max_w and current_panels:
            name = v['nome'] if not parts else f"CONT. {v['nome']}"
            parts.append({'nome': name, 'b': v['b'], 'comp': current_comp, 'panels': current_panels, 'holes': current_holes})
            accum_pos += current_comp
            # If we split here, there's a gap between the last panel of current part and first panel of next part.
            # We skip adding that gap to the length of any part! It acts as the line break.
            current_panels = []
            current_holes = []
            current_comp = 0.0
            accum_pos += gap_w # skip the gap
            
        current_panels.append(p)
        current_comp += w
        
        if i < len(v['holes']):
            # If we aren't going to split immediately after this, add the hole
            if i + 1 < len(v['panels']):
                next_w = v['panels'][i+1]['width']
                if current_comp + gap_w + next_w > max_w:
                    pass # We will split. The gap is the break point.
                else:
                    current_holes.append({'width': gap_w, 'position': current_comp})
                    current_comp += gap_w

    if current_panels:
        name = v['nome'] if not parts else f"CONT. {v['nome']}"
        parts.append({'nome': name, 'b': v['b'], 'comp': current_comp, 'panels': current_panels, 'holes': current_holes})
        
    return parts

parts = split_viga(viga, 1250)
for part in parts:
    print(f"{part['nome']:15s} comp={part['comp']:6.1f} panels={len(part['panels'])} holes={len(part['holes'])}")
